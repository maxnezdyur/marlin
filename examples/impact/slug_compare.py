"""slug_compare -- compare a MOOSE Exodus Taylor-impact slug to a scanned STL.

Purpose
-------
Given a deformed MOOSE simulation (Exodus ``.e``) and an experimental surface
scan (binary ``.stl``) of a recovered Taylor-impact slug, return a single scalar
shape-mismatch (symmetric Chamfer distance, mm) plus diagnostics. The scalar is
intended as the objective for calibrating NEML2 (Johnson-Cook) material params.

Key facts this module bakes in (see the design grill that produced it):
  * The STL is in **millimeters**, the Exodus mesh in **meters** (x1000).
  * The STL captures only the **deformed front** of the slug; the undeformed
    tail is cut off. So the sim surface is clipped to the STL's axial extent
    before comparing, otherwise the sim tail dominates the Chamfer.
  * The impact (mushroom) end is the **larger-diameter** end of each body.
  * The shot is treated as **flat-on / axisymmetric**: Chamfer is rotation
    invariant about the slug axis, so registration only pins the axis + the
    impact-face plane (no azimuthal degree of freedom).

Dependencies: numpy, scipy (``io.netcdf_file``, ``spatial.cKDTree``), and
matplotlib only for the optional ``--emit-artifacts`` plots. No netCDF4 / meshio
/ trimesh / vtk needed -- the ``.e`` files are NetCDF-3 which scipy reads
directly, and binary STL is parsed with numpy.

CLI
---
    python slug_compare.py SIM.e SCAN.stl [--emit-artifacts] [--outdir DIR]
                                          [--no-refine] [--sim-velocity V]

Library
-------
    from slug_compare import compare, load_stl_target
    # one-off
    result = compare("sim_out.e", "scan.stl")
    # optimization loop: preload the STL once, reuse across many sims
    target = load_stl_target("scan.stl")
    for sim in sims:
        result = compare(sim, target)   # target may be a path or a preloaded obj
        chamfer = result["chamfer_mm"]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import struct
from dataclasses import dataclass

import numpy as np
from scipy.io import netcdf_file
from scipy.spatial import cKDTree

# ----------------------------------------------------------------------------
# Geometry helpers
# ----------------------------------------------------------------------------

# Local node indices (0-based) of the 6 quad faces of an Exodus HEX8 element.
# Used only for boundary (free-surface) extraction; orientation is irrelevant
# because point-to-triangle distance does not care about facet winding.
_HEX8_FACES = (
    (0, 1, 2, 3),
    (4, 5, 6, 7),
    (0, 1, 5, 4),
    (1, 2, 6, 5),
    (2, 3, 7, 6),
    (3, 0, 4, 7),
)


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def _orthonormal_basis(axis: np.ndarray) -> np.ndarray:
    """Return a 3x3 rotation R whose first row is ``axis`` (unit).

    Q = (P - c) @ R.T then has Q[:, 0] = (P - c) . axis. The transverse axes
    (rows 1, 2) are arbitrary -- fine here because the body is axisymmetric.
    """
    a = _unit(axis)
    # pick the world axis least aligned with `a` to build a stable perpendicular
    seed = np.eye(3)[np.argmin(np.abs(a))]
    u = _unit(np.cross(a, seed))
    v = np.cross(a, u)
    return np.vstack([a, u, v])


def point_triangle_distance(p: np.ndarray, tri: np.ndarray) -> np.ndarray:
    """Exact distance from points ``p`` (n,3) to triangles ``tri`` (n,3,3).

    Vectorized closest-point-on-triangle (Ericson, *Real-Time Collision
    Detection*, region tests). One triangle per point.
    """
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    ab, ac = b - a, c - a
    ap = p - a
    d1 = np.einsum("ij,ij->i", ab, ap)
    d2 = np.einsum("ij,ij->i", ac, ap)
    bp = p - b
    d3 = np.einsum("ij,ij->i", ab, bp)
    d4 = np.einsum("ij,ij->i", ac, bp)
    cp = p - c
    d5 = np.einsum("ij,ij->i", ab, cp)
    d6 = np.einsum("ij,ij->i", ac, cp)

    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    denom = va + vb + vc
    # guard zero-area / degenerate triangles
    safe = np.where(np.abs(denom) < 1e-30, 1.0, denom)
    v = vb / safe
    w = vc / safe

    # default: closest point is on the triangle face (barycentric)
    closest = a + v[:, None] * ab + w[:, None] * ac

    # edge AB: 0 <= d1/(d1-d3) <= 1
    mab = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
    tab = np.where((d1 - d3) != 0, d1 / np.where((d1 - d3) != 0, d1 - d3, 1.0), 0.0)
    closest = np.where(mab[:, None], a + tab[:, None] * ab, closest)

    # edge AC
    mac = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
    tac = np.where((d2 - d6) != 0, d2 / np.where((d2 - d6) != 0, d2 - d6, 1.0), 0.0)
    closest = np.where(mac[:, None], a + tac[:, None] * ac, closest)

    # edge BC
    mbc = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
    den_bc = (d4 - d3) + (d5 - d6)
    tbc = np.where(den_bc != 0, (d4 - d3) / np.where(den_bc != 0, den_bc, 1.0), 0.0)
    closest = np.where(mbc[:, None], b + tbc[:, None] * (c - b), closest)

    # vertices (corners take priority)
    closest = np.where(((d1 <= 0) & (d2 <= 0))[:, None], a, closest)
    closest = np.where(((d3 >= 0) & (d4 <= d3))[:, None], b, closest)
    closest = np.where(((d6 >= 0) & (d5 <= d6))[:, None], c, closest)

    return np.linalg.norm(p - closest, axis=1)


def nearest_surface_distance(
    query: np.ndarray, tris: np.ndarray, k: int = 12
) -> np.ndarray:
    """Distance from each ``query`` point (n,3) to the triangle soup ``tris``
    (m,3,3). KDTree on triangle centroids prunes to the ``k`` nearest, then
    exact point-to-triangle on those candidates.
    """
    centroids = tris.mean(axis=1)
    tree = cKDTree(centroids)
    k = min(k, len(tris))
    _, idx = tree.query(query, k=k)
    idx = np.atleast_2d(idx.T).T  # ensure (n, k)
    if idx.ndim == 1:
        idx = idx[:, None]
    n, kk = idx.shape
    q_rep = np.repeat(query, kk, axis=0)
    t_rep = tris[idx.reshape(-1)]
    d = point_triangle_distance(q_rep, t_rep).reshape(n, kk)
    return d.min(axis=1)


# ----------------------------------------------------------------------------
# Readers
# ----------------------------------------------------------------------------

_STL_REC = np.dtype(
    [("norm", "<f4", (3,)), ("v", "<f4", (3, 3)), ("attr", "<u2")]
)


def read_binary_stl(path: str) -> np.ndarray:
    """Return STL triangles as a (m, 3, 3) float64 array (mm, as stored)."""
    with open(path, "rb") as fh:
        fh.read(80)  # header
        (n,) = struct.unpack("<I", fh.read(4))
        data = np.frombuffer(fh.read(n * 50), dtype=_STL_REC, count=n)
    return data["v"].astype(np.float64)


def _decode_names(raw) -> list[str]:
    """Decode an Exodus char-array variable into a list of stripped strings."""
    arr = np.asarray(raw)
    out = []
    for row in arr:
        out.append(bytes(row).decode("ascii", "ignore").strip().strip("\x00").strip())
    return out


def read_exodus_surface(
    path: str, exodus_units_to_mm: float = 1000.0
) -> np.ndarray:
    """Extract the deformed free-surface triangles (mm) at the LAST timestep.

    Reads undeformed coords + nodal disp_x/y/z, adds them, extracts boundary
    faces of all HEX8 blocks, triangulates each quad. Returns (m, 3, 3).
    """
    nc = netcdf_file(path, "r", mmap=False)
    try:
        coords = np.column_stack(
            [
                nc.variables["coordx"][:],
                nc.variables["coordy"][:],
                nc.variables["coordz"][:],
            ]
        ).astype(np.float64)

        names = _decode_names(nc.variables["name_nod_var"][:])
        nidx = {nm: i for i, nm in enumerate(names)}
        for comp in ("disp_x", "disp_y", "disp_z"):
            if comp not in nidx:
                raise KeyError(f"Exodus file lacks nodal variable {comp!r}; "
                               f"have {names}")
        disp = np.column_stack(
            [
                nc.variables[f"vals_nod_var{nidx['disp_x'] + 1}"][-1],
                nc.variables[f"vals_nod_var{nidx['disp_y'] + 1}"][-1],
                nc.variables[f"vals_nod_var{nidx['disp_z'] + 1}"][-1],
            ]
        ).astype(np.float64)

        nodes = (coords + disp) * exodus_units_to_mm

        # gather hex connectivity across every element block
        conns = []
        for key in nc.variables:
            if re.fullmatch(r"connect\d+", key):
                c = np.asarray(nc.variables[key][:], dtype=np.int64) - 1  # to 0-based
                if c.shape[1] == 8:
                    conns.append(c)
        if not conns:
            raise ValueError("No HEX8 element blocks found in Exodus file.")
        conn = np.vstack(conns)
    finally:
        nc.close()

    # boundary faces = quads referenced by exactly one element
    counts: dict[tuple, list] = {}
    for face in _HEX8_FACES:
        quads = conn[:, face]  # (nelem, 4) global node ids
        for q in quads:
            key = tuple(sorted(q.tolist()))
            slot = counts.get(key)
            if slot is None:
                counts[key] = [1, q]
            else:
                slot[0] += 1
    boundary = [q for cnt, q in counts.values() if cnt == 1]
    quads = np.asarray(boundary, dtype=np.int64)

    # triangulate each boundary quad (a,b,c) + (a,c,d)
    qv = nodes[quads]  # (nq, 4, 3)
    tris = np.concatenate([qv[:, (0, 1, 2)], qv[:, (0, 2, 3)]], axis=0)
    return tris


# ----------------------------------------------------------------------------
# Alignment to the canonical frame (axis -> +X, impact face at x=0)
# ----------------------------------------------------------------------------


@dataclass
class Body:
    """A slug surface in its canonical frame.

    Canonical frame: the slug axis is +X; the impact (mushroom) face plane sits
    at x = 0; the body extends toward negative x (tail direction). The axial
    coordinate ``s = -x >= 0`` is the distance from the impact face.
    """

    tris: np.ndarray          # (m, 3, 3) triangles in canonical frame
    verts: np.ndarray         # (k, 3) unique vertices in canonical frame
    axial_min: float          # most-negative x present (= -captured length)
    length: float             # axial extent (mm)


def _radius_profile(x: np.ndarray, r: np.ndarray, nbins: int = 24):
    """Outer radius vs axial position. Returns (centers, radius95)."""
    edges = np.linspace(x.min(), x.max(), nbins + 1)
    centers, rad = [], []
    for i in range(nbins):
        m = (x >= edges[i]) & (x < edges[i + 1])
        if m.sum() < 3:
            continue
        centers.append(0.5 * (edges[i] + edges[i + 1]))
        rad.append(np.percentile(r[m], 95.0))
    return np.array(centers), np.array(rad)


def _tri_area(tris: np.ndarray) -> np.ndarray:
    return 0.5 * np.linalg.norm(
        np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1
    )


def _medial_axis_correction(tcq: np.ndarray, w: np.ndarray, nslice: int = 24):
    """Given triangle centroids ``tcq`` in a provisional frame (axis ~ +x) and
    area weights ``w``, fit the medial line y(x), z(x) through area-weighted
    per-slice transverse centroids. Returns (Rc, origin) that rotate+shift the
    frame so the medial line becomes the x-axis.

    Per-slice transverse centroids lie on the true symmetry axis even for a
    tapered (cone-like) body, so this recovers the axis that PCA tilts away
    from the wide (mushroom) end.
    """
    x = tcq[:, 0]
    edges = np.linspace(x.min(), x.max(), nslice + 1)
    cx, cy, cz, cw = [], [], [], []
    for i in range(nslice):
        m = (x >= edges[i]) & (x < edges[i + 1])
        ws = w[m].sum()
        if m.sum() < 5 or ws <= 0:
            continue
        wm = w[m] / ws
        cx.append((wm * tcq[m, 0]).sum())
        cy.append((wm * tcq[m, 1]).sum())
        cz.append((wm * tcq[m, 2]).sum())
        cw.append(ws)
    cx, cy, cz, cw = map(np.asarray, (cx, cy, cz, cw))
    if len(cx) < 3:
        return np.eye(3), np.zeros(3)
    A = np.column_stack([cx, np.ones_like(cx)])
    sw = np.sqrt(cw)
    ay, by = np.linalg.lstsq(A * sw[:, None], cy * sw, rcond=None)[0]
    az, bz = np.linalg.lstsq(A * sw[:, None], cz * sw, rcond=None)[0]
    new_axis = _unit(np.array([1.0, ay, az]))
    return _orthonormal_basis(new_axis), np.array([0.0, by, bz])


def to_canonical(tris: np.ndarray) -> Body:
    """Align a triangle soup to the canonical frame: medial (symmetry) axis ->
    +x, impact (mushroom) face at x = 0, body extending to -x.

    Steps: (1) area-weighted PCA for a provisional long axis; (2) orient the
    larger-diameter (mushroom) end to +x; (3) refine the axis to the medial line
    so taper doesn't bias it; (4) datum the impact face to x = 0.
    """
    tris = np.ascontiguousarray(tris, dtype=np.float64)
    area = _tri_area(tris)
    wsum = area.sum()
    w = area / wsum if wsum > 0 else np.full(len(area), 1.0 / len(area))

    # (1) provisional axis from area-weighted moments (tessellation-independent)
    tc = tris.mean(axis=1)
    c = (w[:, None] * tc).sum(axis=0)
    dctr = tc - c
    cov = np.einsum("i,ij,ik->jk", w, dctr, dctr)
    ew, V = np.linalg.eigh(cov)
    R = _orthonormal_basis(V[:, np.argmax(ew)])

    T = ((tris.reshape(-1, 3) - c) @ R.T).reshape(tris.shape)

    # (2) orient mushroom (larger radius) end to +x
    tcq = T.mean(axis=1)
    radq = np.hypot(tcq[:, 1], tcq[:, 2])
    t = tcq[:, 0]
    r_hi = np.average(radq[t > np.percentile(t, 85)]) if (t > np.percentile(t, 85)).any() else 0.0
    r_lo = np.average(radq[t < np.percentile(t, 15)]) if (t < np.percentile(t, 15)).any() else 0.0
    if r_hi < r_lo:
        T[..., 0] *= -1.0
        T[..., 1] *= -1.0  # keep right-handed (radius unchanged)

    # (3) refine to the medial line (2 iterations); fixes cone/taper PCA bias
    for _ in range(2):
        tcq = T.mean(axis=1)
        Rc, origin = _medial_axis_correction(tcq, w)
        T = ((T.reshape(-1, 3) - origin) @ Rc.T).reshape(tris.shape)

    # (4) datum: impact face plane (max x) -> x = 0; body extends to -x
    x_impact = T[..., 0].max()
    T[..., 0] -= x_impact

    verts = np.unique(T.reshape(-1, 3), axis=0)
    axial_min = float(verts[:, 0].min())
    return Body(tris=T, verts=verts, axial_min=axial_min, length=abs(axial_min))


def _rigid_yz(params, V):
    """Apply small tilt (about y, z) + transverse shift (dy, dz). Axial pinned."""
    ty, tz, dy, dz = params
    cy, sy = np.cos(ty), np.sin(ty)
    cz, sz = np.cos(tz), np.sin(tz)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    out = V @ (Rz @ Ry).T
    out[:, 1] += dy
    out[:, 2] += dz
    return out


# Bounds for the constrained refinement. Tilt is capped small: PCA already
# fixes the axis to within a fraction of a degree for an elongated body, so the
# refine should only nudge it -- never swing the bar (which would corrupt the
# axial datum and the radial profile). Shift corrects residual off-axis centering.
_TILT_CAP_RAD = 0.05          # ~2.9 degrees
_SHIFT_CAP_MM = 1.5


def refine_alignment(stl: Body, sim: Body, n_sample: int = 1500) -> np.ndarray:
    """Constrained refinement of STL onto SIM. Optimizes 4 bounded DOF (two
    small tilt angles + transverse shift); axial translation and azimuth are NOT
    free (axial is pinned by the impact-face datum; azimuth is irrelevant for an
    axisymmetric body). Returns the best parameter vector.
    """
    from scipy.optimize import minimize

    rng = np.random.default_rng(0)
    sample = stl.verts
    if len(sample) > n_sample:
        sample = sample[rng.choice(len(sample), n_sample, replace=False)]

    sim_centroids = sim.tris.mean(axis=1)
    tree = cKDTree(sim_centroids)

    def obj(params):
        P = _rigid_yz(params, sample)
        # cheap one-directional mean distance using exact point-to-tri on
        # the 6 nearest candidate triangles
        _, idx = tree.query(P, k=min(6, len(sim.tris)))
        if idx.ndim == 1:
            idx = idx[:, None]
        n, kk = idx.shape
        d = point_triangle_distance(
            np.repeat(P, kk, axis=0), sim.tris[idx.reshape(-1)]
        ).reshape(n, kk)
        return float(d.min(axis=1).mean())

    bounds = [
        (-_TILT_CAP_RAD, _TILT_CAP_RAD),
        (-_TILT_CAP_RAD, _TILT_CAP_RAD),
        (-_SHIFT_CAP_MM, _SHIFT_CAP_MM),
        (-_SHIFT_CAP_MM, _SHIFT_CAP_MM),
    ]
    res = minimize(
        obj,
        x0=np.zeros(4),
        method="Powell",
        bounds=bounds,
        options={"xtol": 1e-4, "ftol": 1e-5, "maxiter": 400},
    )
    return res.x


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------


@dataclass
class STLTarget:
    """Preprocessed STL: reuse across many ``compare`` calls in an opt loop."""

    path: str
    body: Body
    shank_dia_mm: float
    mushroom_dia_mm: float
    meta: dict


def _diameter(verts: np.ndarray, x_lo: float, x_hi: float) -> float:
    """Outer diameter (2 * 95th-pct radius) of the axial slab [x_lo, x_hi]."""
    m = (verts[:, 0] >= x_lo) & (verts[:, 0] <= x_hi)
    if m.sum() < 3:
        return float("nan")
    r = np.hypot(verts[m, 1], verts[m, 2])
    return float(2.0 * np.percentile(r, 95.0))


def _parse_stl_meta(path: str) -> dict:
    """Decode a name like 'CuH04_235.9_003_downsample.stl'."""
    base = os.path.basename(path)
    meta: dict = {"filename": base}
    # e.g. 'CuH04_235.9_003' -> element 'Cu', temper 'H04', 235.9 m/s, shot 003
    m = re.match(r"([A-Z][a-z]?)([A-Za-z0-9]*?)_(\d+(?:\.\d+)?)_(\d+)", base)
    if m:
        meta["material"] = m.group(1)
        if m.group(2):
            meta["temper"] = m.group(2)
        meta["velocity_m_s"] = float(m.group(3))
        meta["shot"] = m.group(4)
    return meta


def load_stl_target(path: str) -> STLTarget:
    """Read + canonicalize an STL once. Pass the result to ``compare`` to avoid
    re-parsing the scan on every optimization iteration."""
    tris = read_binary_stl(path)
    body = to_canonical(tris)
    # shank = least-deformed slab nearest the cut (most negative x);
    # mushroom = slab at the impact face (x ~ 0)
    span = body.length
    shank = _diameter(body.verts, body.axial_min, body.axial_min + 0.15 * span)
    mush = _diameter(body.verts, -0.10 * span, 0.0)
    return STLTarget(
        path=path,
        body=body,
        shank_dia_mm=shank,
        mushroom_dia_mm=mush,
        meta=_parse_stl_meta(path),
    )


def compare(
    exodus,
    stl,
    *,
    refine: bool = True,
    dia_tol: float = 0.05,
    sim_velocity: float | None = None,
    emit_artifacts: bool = False,
    outdir: str = ".",
    exodus_units_to_mm: float = 1000.0,
    kdtree_k: int = 12,
) -> dict:
    """Compare a sim Exodus surface to an experimental STL.

    Parameters
    ----------
    exodus : str
        Path to the MOOSE Exodus ``.e`` output.
    stl : str | STLTarget
        Path to the STL, or a preloaded :func:`load_stl_target` result.
    refine : bool
        Run the constrained alignment refinement (recommended).
    dia_tol : float
        Relative tolerance for the shank-diameter consistency guard.
    sim_velocity : float | None
        If given, compared to the velocity parsed from the STL filename.
    emit_artifacts : bool
        Write ParaView ``.vtk`` overlays + matplotlib PNGs (off in opt loops).
    outdir : str
        Where artifacts go.

    Returns
    -------
    dict with ``chamfer_mm`` (the headline scalar) plus diagnostics & warnings.
    """
    target = stl if isinstance(stl, STLTarget) else load_stl_target(stl)
    stl_body = target.body

    sim_tris = read_exodus_surface(exodus, exodus_units_to_mm)
    sim_body = to_canonical(sim_tris)

    warnings: list[str] = []

    # --- optional constrained refinement: move STL onto SIM ---
    if refine:
        params = refine_alignment(stl_body, sim_body)
        if max(abs(params[0]), abs(params[1])) >= 0.98 * _TILT_CAP_RAD:
            warnings.append(
                "alignment refine saturated the tilt bound "
                f"(±{np.degrees(_TILT_CAP_RAD):.1f}°) -- the surfaces don't fit "
                "rigidly; usually means the sim geometry doesn't match the scan."
            )
        stl_verts = _rigid_yz(params, stl_body.verts)
        stl_tris = _rigid_yz(params, stl_body.tris.reshape(-1, 3)).reshape(
            stl_body.tris.shape
        )
    else:
        params = np.zeros(4)
        stl_verts = stl_body.verts
        stl_tris = stl_body.tris

    # --- clip SIM to the STL axial extent (omit the undeformed tail) ---
    stl_xmin = stl_verts[:, 0].min()
    sim_centroid_x = sim_body.tris[:, :, 0].mean(axis=1)
    keep = sim_centroid_x >= stl_xmin
    sim_tris_clip = sim_body.tris[keep]
    if len(sim_tris_clip) == 0:
        raise ValueError("Clip removed all sim triangles -- sim shorter than STL "
                         "or alignment failed.")
    sim_verts_clip = np.unique(sim_tris_clip.reshape(-1, 3), axis=0)

    # --- symmetric exact point-to-triangle Chamfer ---
    d_stl_to_sim = nearest_surface_distance(stl_verts, sim_tris_clip, k=kdtree_k)
    d_sim_to_stl = nearest_surface_distance(sim_verts_clip, stl_tris, k=kdtree_k)

    mean_a = float(d_stl_to_sim.mean())
    mean_b = float(d_sim_to_stl.mean())
    chamfer = 0.5 * (mean_a + mean_b)
    rms = float(
        np.sqrt(0.5 * ((d_stl_to_sim ** 2).mean() + (d_sim_to_stl ** 2).mean()))
    )
    hausdorff = float(max(d_stl_to_sim.max(), d_sim_to_stl.max()))
    hausdorff95 = float(
        max(np.percentile(d_stl_to_sim, 95), np.percentile(d_sim_to_stl, 95))
    )

    # --- geometry consistency guard ---
    sim_shank = _diameter(
        sim_body.verts, sim_body.axial_min, sim_body.axial_min + 0.15 * sim_body.length
    )
    sim_mush = _diameter(sim_body.verts, -0.10 * sim_body.length, 0.0)
    if np.isfinite(target.shank_dia_mm) and np.isfinite(sim_shank):
        rel = abs(sim_shank - target.shank_dia_mm) / target.shank_dia_mm
        if rel > dia_tol:
            warnings.append(
                f"shank diameter mismatch: STL={target.shank_dia_mm:.2f} mm vs "
                f"sim={sim_shank:.2f} mm ({rel * 100:.1f}% > {dia_tol * 100:.0f}%). "
                f"Sim initial geometry likely does not match the specimen."
            )
    stl_v = target.meta.get("velocity_m_s")
    if sim_velocity is not None and stl_v is not None:
        if abs(sim_velocity - stl_v) / stl_v > 0.02:
            warnings.append(
                f"velocity mismatch: STL={stl_v} m/s vs sim={sim_velocity} m/s."
            )
    if sim_body.length < target.body.length * 0.98:
        warnings.append(
            f"sim captured length ({sim_body.length:.1f} mm) < STL extent "
            f"({target.body.length:.1f} mm); clip may be incomplete."
        )

    result = {
        "chamfer_mm": chamfer,
        "rms_mm": rms,
        "hausdorff_mm": hausdorff,
        "hausdorff95_mm": hausdorff95,
        "mean_stl_to_sim_mm": mean_a,
        "mean_sim_to_stl_mm": mean_b,
        "stl_shank_dia_mm": target.shank_dia_mm,
        "sim_shank_dia_mm": sim_shank,
        "stl_mushroom_dia_mm": target.mushroom_dia_mm,
        "sim_mushroom_dia_mm": sim_mush,
        "stl_captured_length_mm": target.body.length,
        "sim_length_mm": sim_body.length,
        "align_params": {
            "tilt_y_rad": float(params[0]),
            "tilt_z_rad": float(params[1]),
            "shift_y_mm": float(params[2]),
            "shift_z_mm": float(params[3]),
        },
        "stl_meta": target.meta,
        "n_stl_tris": int(len(stl_tris)),
        "n_sim_tris_clipped": int(len(sim_tris_clip)),
        "warnings": warnings,
    }

    if emit_artifacts:
        os.makedirs(outdir, exist_ok=True)
        _write_vtk(os.path.join(outdir, "stl_aligned.vtk"), stl_tris, stl_verts,
                   d_stl_to_sim)
        _write_vtk(os.path.join(outdir, "sim_clipped.vtk"), sim_tris_clip,
                   sim_verts_clip, d_sim_to_stl)
        _plot_artifacts(outdir, stl_verts, sim_verts_clip, d_stl_to_sim)
        result["artifacts"] = outdir

    return result


# ----------------------------------------------------------------------------
# Artifacts (gated)
# ----------------------------------------------------------------------------


def _write_vtk(path: str, tris: np.ndarray, verts: np.ndarray,
               vert_scalar: np.ndarray) -> None:
    """Write a legacy-ASCII VTK POLYDATA of the surface, with a per-vertex
    nearest-distance scalar. Opens in ParaView."""
    # map each triangle vertex to a row in `verts`
    tree = cKDTree(verts)
    flat = tris.reshape(-1, 3)
    _, vid = tree.query(flat)
    vid = vid.reshape(-1, 3)
    with open(path, "w") as f:
        f.write("# vtk DataFile Version 3.0\nslug_compare\nASCII\n")
        f.write("DATASET POLYDATA\n")
        f.write(f"POINTS {len(verts)} float\n")
        for p in verts:
            f.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")
        f.write(f"POLYGONS {len(vid)} {len(vid) * 4}\n")
        for t in vid:
            f.write(f"3 {t[0]} {t[1]} {t[2]}\n")
        f.write(f"POINT_DATA {len(verts)}\n")
        f.write("SCALARS distance_mm float 1\nLOOKUP_TABLE default\n")
        for d in vert_scalar:
            f.write(f"{d:.6f}\n")


def _plot_artifacts(outdir, stl_verts, sim_verts, d_stl_to_sim) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # radial profile overlay (axisymmetric collapse): s = -x = dist from impact
    sc, sr = _radius_profile(stl_verts[:, 0], np.hypot(stl_verts[:, 1],
                                                       stl_verts[:, 2]))
    mc, mr = _radius_profile(sim_verts[:, 0], np.hypot(sim_verts[:, 1],
                                                       sim_verts[:, 2]))
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].plot(-sc, sr, "o-", label="STL (scan)", ms=3)
    ax[0].plot(-mc, mr, "s-", label="sim (clipped)", ms=3)
    ax[0].set_xlabel("distance from impact face (mm)")
    ax[0].set_ylabel("outer radius (mm)")
    ax[0].set_title("radial profile")
    ax[0].legend()
    ax[0].grid(alpha=0.3)

    ax[1].hist(d_stl_to_sim, bins=40)
    ax[1].set_xlabel("STL->sim nearest distance (mm)")
    ax[1].set_ylabel("count")
    ax[1].set_title("distance distribution")
    ax[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "compare.png"), dpi=130)
    plt.close(fig)


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Compare a MOOSE Exodus slug to an STL.")
    ap.add_argument("exodus", help="MOOSE Exodus .e output")
    ap.add_argument("stl", help="experimental binary STL scan")
    ap.add_argument("--emit-artifacts", action="store_true",
                    help="write ParaView .vtk overlays + PNG plots")
    ap.add_argument("--outdir", default="slug_compare_out")
    ap.add_argument("--no-refine", action="store_true",
                    help="skip the constrained alignment refinement")
    ap.add_argument("--sim-velocity", type=float, default=None,
                    help="sim impact velocity (m/s) for the consistency guard")
    ap.add_argument("--dia-tol", type=float, default=0.05)
    args = ap.parse_args(argv)

    result = compare(
        args.exodus,
        args.stl,
        refine=not args.no_refine,
        dia_tol=args.dia_tol,
        sim_velocity=args.sim_velocity,
        emit_artifacts=args.emit_artifacts,
        outdir=args.outdir,
    )
    print(json.dumps(result, indent=2))
    for w in result["warnings"]:
        print(f"WARNING: {w}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
