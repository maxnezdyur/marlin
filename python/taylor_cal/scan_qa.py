"""STL scan -> CalTarget + QA report for Taylor-impact specimens.

Reuses the machinery validated in ``examples/impact/rz_profile_compare.py``:
binary STL reader, per-slice Kasa circle fits about the local centroid
(axis-corrected radius), and the volume-of-revolution audit.

Pipeline (all lengths mm, velocity m/s):

1. Parse ``<ID>_<velocity>.stl`` filename metadata.
2. Read binary STL triangles; unique vertices. Axis of revolution is X.
3. Foot end = end with the larger near-end (2 mm) max raw radius; zs is
   measured from that foot plane, increasing toward the rear.
4. 0.25 mm slices, Kasa circle fit per slice (>= 30 verts) -> centerline
   c(zs), radius R(zs), fit rms s(zs).
5. Artifact audit: rear end-cap detection (truncation), volume audit ->
   true-length estimate L_est +/- sigma_L, axis-wander span.
6. Trusted mask: zs > 0.6 (foot-lip mixing), zs < extent - 1.0 when
   truncated, fit rms <= 0.15 mm.
"""

from __future__ import annotations

import os
import struct

import numpy as np

from .targets import CalTarget

SLICE_MM = 0.25          # axial slice width [mm]
MIN_SLICE_VERTS = 30     # minimum vertices for a valid circle fit
SIGMA_FLOOR_MM = 0.02    # scanner noise floor [mm]
RMS_UNTRUSTED_MM = 0.15  # slices fitting worse than this are dropped [mm]
FOOT_LIP_MM = 0.6        # foot-lip mixing zone excluded from the mask [mm]
CUT_GUARD_MM = 1.0       # rear guard band ahead of a detected cut face [mm]
CAP_TOL_MM = 0.05        # end-cap plane tolerance (50 um) [mm]
CAP_MIN_TRIS = 5         # triangles on the rear plane to call it a cap
DIM_TOL_REL = 0.005      # nominal-dimension tolerance (0.5% on r0, L0)

_STL_REC = np.dtype([("norm", "<f4", (3,)), ("v", "<f4", (3, 3)), ("attr", "<u2")])

_trapz = getattr(np, "trapezoid", None) or np.trapz  # numpy 2.x rename


# ---------------------------------------------------------------- STL


def read_binary_stl(path: str) -> np.ndarray:
    """Read a binary STL; return triangles as an (n, 3, 3) float64 array [mm]."""
    with open(path, "rb") as fh:
        fh.read(80)  # header
        (n,) = struct.unpack("<I", fh.read(4))
        data = np.frombuffer(fh.read(n * 50), dtype=_STL_REC, count=n)
    return data["v"].astype(np.float64)


def parse_stl_name(path: str) -> tuple[str, float | None]:
    """Parse ``<ID>_<velocity>.stl`` -> (shot_id, velocity [m/s] or None)."""
    stem = os.path.splitext(os.path.basename(path))[0]
    if "_" in stem:
        head, tail = stem.rsplit("_", 1)
        try:
            return head, float(tail)
        except ValueError:
            pass
    return stem, None


# ---------------------------------------------------------------- fits


def fit_circle(yy: np.ndarray, zz: np.ndarray) -> tuple[float, float, float, float]:
    """Algebraic (Kasa) least-squares circle fit.

    Returns (cy, cz, R, rms) where rms is the radial residual rms [mm].
    """
    A = np.column_stack([2 * yy, 2 * zz, np.ones_like(yy)])
    b = yy**2 + zz**2
    (cy, cz, c), *_ = np.linalg.lstsq(A, b, rcond=None)
    R = np.sqrt(c + cy**2 + cz**2)
    rms = float(np.sqrt(np.mean((np.hypot(yy - cy, zz - cz) - R) ** 2)))
    return float(cy), float(cz), float(R), rms


def slice_fits(v: np.ndarray, foot_at_max: bool):
    """Per-slice circle fits over 0.25 mm axial bins.

    Parameters
    ----------
    v : (m, 3) unique STL vertices [mm]; axis of revolution is X.
    foot_at_max : True when the foot (impact) face is at x_max.

    Returns dict of ascending-zs arrays: zs [mm from foot plane], R [mm],
    rms [mm], cy, cz [mm, scan frame].
    """
    x = v[:, 0]
    x_min, x_max = x.min(), x.max()
    edges = np.arange(x_min, x_max + SLICE_MM, SLICE_MM)
    zs_l, R_l, rms_l, cy_l, cz_l = [], [], [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (x >= lo) & (x < hi)
        if m.sum() < MIN_SLICE_VERTS:
            continue
        cy, cz, R, rms = fit_circle(v[m, 1], v[m, 2])
        xc = 0.5 * (lo + hi)
        zs_l.append((x_max - xc) if foot_at_max else (xc - x_min))
        R_l.append(R)
        rms_l.append(rms)
        cy_l.append(cy)
        cz_l.append(cz)
    zs = np.asarray(zs_l)
    o = np.argsort(zs)
    return {
        "zs": zs[o],
        "R": np.asarray(R_l)[o],
        "rms": np.asarray(rms_l)[o],
        "cy": np.asarray(cy_l)[o],
        "cz": np.asarray(cz_l)[o],
    }


# ---------------------------------------------------------------- audits


def detect_end_cap(tris: np.ndarray, foot_at_max: bool) -> tuple[bool, int]:
    """Detect a closed cut face (end cap) at the rear extreme.

    A cap is present when >= CAP_MIN_TRIS triangles lie entirely within
    CAP_TOL_MM (50 um) of the rear extreme plane. Returns (truncated, count).
    """
    x = tris[:, :, 0]
    rear = x.min() if foot_at_max else x.max()
    on_plane = np.all(np.abs(x - rear) <= CAP_TOL_MM, axis=1)
    n = int(on_plane.sum())
    return n >= CAP_MIN_TRIS, n


def axis_wander_span(cy: np.ndarray, cz: np.ndarray) -> float:
    """Max pairwise distance between slice centerline points [mm]."""
    c = np.column_stack([cy, cz])
    d = np.linalg.norm(c[:, None, :] - c[None, :, :], axis=-1)
    return float(d.max()) if d.size else 0.0


# ---------------------------------------------------------------- build


def build_target(stl_path: str, r0_mm: float, L0_mm: float,
                 velocity: float | None = None) -> tuple[CalTarget, dict]:
    """Build a :class:`CalTarget` and QA-report dict from a scanned STL.

    Parameters
    ----------
    stl_path : path to a binary STL scan (mm units, axis of revolution X).
    r0_mm, L0_mm : nominal pre-test specimen radius and length [mm].
    velocity : impact velocity [m/s]; parsed from ``<ID>_<velocity>.stl``
        when omitted.

    Returns (target, qa_report).
    """
    shot_id, v_name = parse_stl_name(stl_path)
    if velocity is None:
        velocity = v_name
    if velocity is None:
        raise ValueError(
            f"velocity not given and not parseable from filename: {stl_path!r}")

    tris = read_binary_stl(stl_path)
    v = np.unique(tris.reshape(-1, 3), axis=0)

    # foot end = end with larger near-end (2 mm) max raw radius
    x = v[:, 0]
    x_min, x_max = x.min(), x.max()
    r_raw = np.hypot(v[:, 1], v[:, 2])
    foot_at_max = r_raw[x > x_max - 2.0].max() > r_raw[x < x_min + 2.0].max()
    extent = float(x_max - x_min)

    s = slice_fits(v, foot_at_max)
    zs, R, rms = s["zs"], s["R"], s["rms"]
    sigma = np.maximum(rms, SIGMA_FLOOR_MM)

    truncated, n_cap_tris = detect_end_cap(tris, foot_at_max)

    # trusted mask
    trusted = zs > FOOT_LIP_MM
    if truncated:
        trusted &= zs < extent - CUT_GUARD_MM
    trusted &= rms <= RMS_UNTRUSTED_MM

    # scalar profile metrics
    foot_r = float(R[zs < 1.0].max())
    zt = zs[trusted]
    rear_r = float(R[trusted][zt > zt.max() - 2.0].mean())

    # volume audit -> true-length estimate
    V_scan = float(np.pi * _trapz(R**2, zs))
    V0 = float(np.pi * r0_mm**2 * L0_mm)
    dL = (V0 - V_scan) / (np.pi * rear_r**2)
    L_est = extent + max(dL, 0.0)
    # nominal-dimension tolerance (0.5% on r0, L0) propagated through V0
    sigma_V0 = V0 * np.hypot(2 * DIM_TOL_REL, DIM_TOL_REL)
    sigma_dL_tol = sigma_V0 / (np.pi * rear_r**2)
    sigma_L = float(np.hypot(0.5 * abs(dL), sigma_dL_tol))

    wander = axis_wander_span(s["cy"][trusted], s["cz"][trusted])

    warnings = []
    if truncated:
        warnings.append(
            f"rear end-cap detected ({n_cap_tris} triangles within "
            f"{CAP_TOL_MM * 1e3:.0f} um of rear plane): scan is truncated; "
            f"last {CUT_GUARD_MM:.1f} mm untrusted, L_est extrapolated")
    if dL < 0:
        warnings.append(
            f"volume audit dL = {dL:.3f} mm < 0 (scan volume exceeds "
            "nominal): check r0/L0")
    if wander > 0.1:
        warnings.append(
            f"axis wander {wander:.3f} mm > 0.1 mm: specimen bent/tilted in "
            "scan frame; axis-corrected radii used")
    n_bad = int((rms > RMS_UNTRUSTED_MM).sum())
    if n_bad:
        warnings.append(
            f"{n_bad} slice(s) dropped for fit rms > {RMS_UNTRUSTED_MM} mm "
            "(out-of-round / lip / cut face)")

    meta = {
        "stl_path": os.path.abspath(stl_path),
        "foot_at_max": bool(foot_at_max),
        "slice_mm": SLICE_MM,
        "sigma_floor_mm": SIGMA_FLOOR_MM,
        "n_triangles": int(tris.shape[0]),
        "n_unique_vertices": int(v.shape[0]),
        "n_cap_tris": n_cap_tris,
        "V_scan_mm3": V_scan,
        "V0_mm3": V0,
        "dL_mm": float(dL),
        "fit_rms": rms.tolist(),
        "center_y": s["cy"].tolist(),
        "center_z": s["cz"].tolist(),
    }

    target = CalTarget(
        shot_id=shot_id, velocity=float(velocity), r0=float(r0_mm),
        L0=float(L0_mm), zs=zs, R=R, sigma=sigma, trusted=trusted,
        L_extent=extent, L_est=float(L_est), sigma_L=sigma_L,
        foot_r=foot_r, rear_r=rear_r, truncated=bool(truncated),
        axis_wander=wander, meta=meta,
    )

    mid = trusted & (zs > 5.0) & (zs < extent - 5.0)
    qa = {
        "shot_id": shot_id,
        "velocity_m_s": float(velocity),
        "r0_mm": float(r0_mm),
        "L0_mm": float(L0_mm),
        "extent_mm": extent,
        "L_est_mm": float(L_est),
        "sigma_L_mm": sigma_L,
        "dL_mm": float(dL),
        "V_scan_mm3": V_scan,
        "V0_mm3": V0,
        "foot_r_mm": foot_r,
        "rear_r_mm": rear_r,
        "truncated": bool(truncated),
        "n_cap_tris": n_cap_tris,
        "axis_wander_mm": wander,
        "n_slices": int(zs.size),
        "n_trusted": int(trusted.sum()),
        "fit_rms_mid_min_mm": float(rms[mid].min()) if mid.any() else float("nan"),
        "fit_rms_mid_max_mm": float(rms[mid].max()) if mid.any() else float("nan"),
        "slices": {
            "zs_mm": zs.tolist(),
            "R_mm": R.tolist(),
            "sigma_mm": sigma.tolist(),
            "fit_rms_mm": rms.tolist(),
            "center_y_mm": s["cy"].tolist(),
            "center_z_mm": s["cz"].tolist(),
            "trusted": trusted.tolist(),
        },
        "warnings": warnings,
    }
    return target, qa


# ---------------------------------------------------------------- figure


def write_qa_png(target: CalTarget, path: str) -> str:
    """Two-panel QA figure: profile R +/- sigma with trusted shading (top)
    and centerline wander vs zs (bottom). Returns the path written."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    zs, R, sig, tr = target.zs, target.R, target.sigma, target.trusted
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9, 7), sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1.0]})

    # untrusted zs intervals (shared shading on both panels)
    spans = []
    start = None
    for i, ok in enumerate(tr):
        if not ok and start is None:
            start = zs[i]
        elif ok and start is not None:
            spans.append((start, zs[i]))
            start = None
    if start is not None:
        spans.append((start, zs[-1]))

    for ax in (ax1, ax2):
        for lo, hi in spans:
            ax.axvspan(lo, hi, color="0.85", zorder=0,
                       label="untrusted" if (ax is ax1 and (lo, hi) == spans[0])
                       else None)

    ax1.fill_between(zs, R - sig, R + sig, color="#06509D", alpha=0.25, lw=0,
                     label=r"R $\pm\sigma$")
    ax1.plot(zs, R, color="#06509D", lw=1.5, label="fitted radius R(zs)")
    ax1.axhline(target.r0, color="0.6", lw=0.8, ls="--", label=r"nominal $r_0$")
    if target.truncated:
        ax1.axvline(target.L_extent, color="#B31B1B", lw=1.0, ls=":",
                    label="scan extent (cut)")
        ax1.axvline(target.L_est, color="#B31B1B", lw=1.0, ls="--",
                    label=r"$L_{est}$")
    ax1.set_ylabel("radius (mm)")
    ax1.set_title(
        f"{target.shot_id} @ {target.velocity:.1f} m/s -- scan QA\n"
        f"L_est = {target.L_est:.2f} +/- {target.sigma_L:.2f} mm  |  "
        f"foot_r = {target.foot_r:.2f} mm  |  rear_r = {target.rear_r:.3f} mm  |  "
        f"wander = {target.axis_wander:.2f} mm  |  truncated = {target.truncated}",
        fontsize=10)
    ax1.legend(loc="upper right", frameon=False, fontsize=8)

    cy = np.asarray(target.meta.get("center_y", []), dtype=float)
    cz = np.asarray(target.meta.get("center_z", []), dtype=float)
    if cy.size == zs.size and cy.size:
        ref = np.array([cy[tr].mean(), cz[tr].mean()]) if tr.any() else \
            np.array([cy.mean(), cz.mean()])
        off = np.hypot(cy - ref[0], cz - ref[1])
        ax2.plot(zs, off, color="#59595C", lw=1.5)
        ax2.set_ylabel("centerline offset (mm)")
    else:
        ax2.text(0.5, 0.5, "no centerline data in target.meta",
                 ha="center", va="center", transform=ax2.transAxes)
    ax2.set_xlabel("zs -- distance from foot plane (mm)")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path
