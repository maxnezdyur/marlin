"""rz_profile_compare -- compare a deformed RZ MOOSE Exodus slug to a scanned STL.

Extracts the outer radial profile r(zs) of both bodies (zs = distance from the
impact/foot face, mm), prints a comparison table, and writes an overlay PNG plus
a CSV of the two profiles.

CLI:
    python rz_profile_compare.py SIM.e SCAN.stl [--out PREFIX]

Dependencies: numpy, matplotlib, scipy.io.netcdf_file (Exodus .e is NetCDF-3).
"""

from __future__ import annotations

import argparse
import struct

import numpy as np
from scipy.io import netcdf_file

NBINS = 120
INL_BLUE = "#06509D"
INL_GRAY = "#59595C"


# ---------------------------------------------------------------- readers

_STL_REC = np.dtype([("norm", "<f4", (3,)), ("v", "<f4", (3, 3)), ("attr", "<u2")])


def read_binary_stl_vertices(path: str) -> np.ndarray:
    """Return STL vertices as an (m*3, 3) float64 array (mm, as stored)."""
    with open(path, "rb") as fh:
        fh.read(80)  # header
        (n,) = struct.unpack("<I", fh.read(4))
        data = np.frombuffer(fh.read(n * 50), dtype=_STL_REC, count=n)
    return data["v"].reshape(-1, 3).astype(np.float64)


def _decode_names(raw) -> list:
    """Decode an Exodus char-array variable into a list of stripped strings."""
    return [
        bytes(row).decode("ascii", "ignore").strip().strip("\x00").strip()
        for row in np.asarray(raw)
    ]


def read_exodus_rz(path: str, units_to_mm: float = 1000.0):
    """Read a 2D RZ Exodus file; return displaced (r, z) node coords in mm at
    the LAST timestep. coordx = r, coordy = z."""
    nc = netcdf_file(path, "r", mmap=False)
    try:
        r0 = np.asarray(nc.variables["coordx"][:], dtype=np.float64)
        z0 = np.asarray(nc.variables["coordy"][:], dtype=np.float64)
        names = _decode_names(nc.variables["name_nod_var"][:])
        nidx = {nm: i for i, nm in enumerate(names)}
        for comp in ("disp_x", "disp_y"):
            if comp not in nidx:
                raise KeyError(f"Exodus file lacks nodal variable {comp!r}; have {names}")
        dr = np.asarray(nc.variables[f"vals_nod_var{nidx['disp_x'] + 1}"][-1],
                        dtype=np.float64)
        dz = np.asarray(nc.variables[f"vals_nod_var{nidx['disp_y'] + 1}"][-1],
                        dtype=np.float64)
    finally:
        nc.close()
    r = (r0 + dr) * units_to_mm
    z = (z0 + dz) * units_to_mm

    # Outer-boundary polyline (structured GeneratedMeshGenerator grid): the
    # bottom face (ordered axis -> edge) followed by the lateral surface
    # (ordered bottom -> top). Sampling the polyline densely avoids the
    # zigzag artifact of node-binning when surface nodes cluster in z.
    eps = 1e-12
    bot = np.where(np.abs(z0 - z0.min()) < eps)[0]
    side = np.where(np.abs(r0 - r0.max()) < eps)[0]
    bot = bot[np.argsort(r0[bot])]
    side = side[np.argsort(z0[side])]
    contour = np.concatenate([bot, side])
    cr, cz = r[contour], z[contour]
    # densely resample each segment
    rs, zs = [], []
    for a in range(len(cr) - 1):
        t = np.linspace(0.0, 1.0, 30, endpoint=False)
        rs.append(cr[a] + t * (cr[a + 1] - cr[a]))
        zs.append(cz[a] + t * (cz[a + 1] - cz[a]))
    rs.append(cr[-1:]); zs.append(cz[-1:])
    return r, z, np.concatenate(rs), np.concatenate(zs)


# ---------------------------------------------------------------- profiles


def binned_max_radius(zs: np.ndarray, r: np.ndarray, nbins: int = NBINS):
    """Outer profile: max radius per occupied axial bin. Returns (centers, rmax)."""
    edges = np.linspace(zs.min(), zs.max(), nbins + 1)
    idx = np.clip(np.digitize(zs, edges) - 1, 0, nbins - 1)
    rmax = np.full(nbins, -np.inf)
    np.maximum.at(rmax, idx, r)
    centers = 0.5 * (edges[:-1] + edges[1:])
    keep = np.isfinite(rmax)
    return centers[keep], rmax[keep]


def sim_profile(r: np.ndarray, z: np.ndarray, cr: np.ndarray, cz: np.ndarray):
    """Sim profile + scalar metrics from the outer-boundary contour.
    Foot (impact face) is at z_min -> zs = z - z_min."""
    z_min, z_max = z.min(), z.max()
    length = z_max - z_min
    czs = cz - z_min
    foot_r = cr[czs < 0.5].max()
    rear_r = cr[czs > length - 2.0].max()
    zc, rp = binned_max_radius(czs, cr)
    return zc, rp, length, foot_r, rear_r


def stl_profile(verts: np.ndarray):
    """STL profile + scalar metrics. Axis of revolution is X; foot end is the
    end whose nearby (within 2 mm) max radius is larger."""
    x = verts[:, 0]
    r = np.hypot(verts[:, 1], verts[:, 2])
    x_min, x_max = x.min(), x.max()
    r_lo = r[x < x_min + 2.0].max()
    r_hi = r[x > x_max - 2.0].max()
    zs = (x_max - x) if r_hi > r_lo else (x - x_min)  # foot plane -> zs = 0
    length = x_max - x_min
    foot_r = r[zs < 0.5].max()
    rear_r = r[zs > length - 2.0].max()
    zc, rp = binned_max_radius(zs, r)
    return zc, rp, length, foot_r, rear_r


def volume_of_revolution(zc: np.ndarray, rp: np.ndarray) -> float:
    """pi * integral r^2 dz over the binned profile (mm^3)."""
    trapz = getattr(np, "trapezoid", None) or np.trapz  # numpy 2.x renamed trapz
    return float(np.pi * trapz(rp**2, zc))


# ---------------------------------------------------------------- outputs


def write_overlay_png(path, exp_z, exp_r, sim_z, sim_r):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.family"] = "Arial"
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.fill_between(exp_z, -exp_r, exp_r, color=INL_GRAY, alpha=0.35, lw=0,
                    label="experiment (scan)")
    ax.plot(exp_z, exp_r, color=INL_GRAY, lw=1.0)
    ax.plot(exp_z, -exp_r, color=INL_GRAY, lw=1.0)
    ax.plot(sim_z, sim_r, color=INL_BLUE, lw=2.5, label="simulation")
    ax.plot(sim_z, -sim_r, color=INL_BLUE, lw=2.5)
    ax.axhline(0.0, color="0.75", lw=0.8, zorder=0)
    ax.grid(False)
    ax.set_aspect("equal")
    ax.set_xlabel("distance from impact face (mm)")
    ax.set_ylabel("radius (mm)")
    ax.set_title("CuH04 235.9 m/s - final profile")
    ax.legend(loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_csv(path, zs, r_exp, r_sim):
    with open(path, "w") as f:
        f.write("zs_mm,r_exp_mm,r_sim_mm\n")
        for z, re_, rs in zip(zs, r_exp, r_sim):
            f.write(f"{z:.4f},{re_:.4f},{rs:.4f}\n")


def _row(label, sim, exp, unit="mm"):
    err = 100.0 * (sim - exp) / exp if exp != 0 else float("nan")
    return f"  {label:<24s} {sim:>10.3f} {exp:>10.3f} {err:>+9.1f}%   [{unit}]"


# ---------------------------------------------------------------- main


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Compare an RZ MOOSE Exodus slug profile to a scanned STL.")
    ap.add_argument("exodus", help="MOOSE Exodus .e output (2D RZ, meters)")
    ap.add_argument("stl", help="experimental binary STL scan (mm)")
    ap.add_argument("--out", default="rz_profile", help="output file prefix")
    args = ap.parse_args(argv)

    r, z, cr, cz = read_exodus_rz(args.exodus)
    sim_z, sim_r, sim_len, sim_foot, sim_rear = sim_profile(r, z, cr, cz)

    verts = read_binary_stl_vertices(args.stl)
    exp_z, exp_r, exp_len, exp_foot, exp_rear = stl_profile(verts)

    # profile mismatch over the common zs range (sim interpolated onto exp bins)
    lo = max(sim_z.min(), exp_z.min())
    hi = min(sim_z.max(), exp_z.max())
    common = (exp_z >= lo) & (exp_z <= hi)
    r_sim_on_exp = np.interp(exp_z, sim_z, sim_r, left=np.nan, right=np.nan)
    dr = r_sim_on_exp[common] - exp_r[common]
    rms = float(np.sqrt(np.mean(dr**2)))
    dmax = float(np.max(np.abs(dr)))

    vol_sim = volume_of_revolution(sim_z, sim_r)
    vol_exp = volume_of_revolution(exp_z, exp_r)

    print("=" * 66)
    print("  RZ profile comparison: sim vs experiment")
    print(f"  sim: {args.exodus}")
    print(f"  exp: {args.stl}")
    print("=" * 66)
    print(f"  {'metric':<24s} {'sim':>10s} {'exp':>10s} {'% err':>10s}")
    print("-" * 66)
    print(_row("final length", sim_len, exp_len))
    print(_row("foot (max) radius", sim_foot, exp_foot))
    print(_row("rear radius", sim_rear, exp_rear))
    print(_row("volume of revolution", vol_sim, vol_exp, unit="mm^3"))
    print("-" * 66)
    print(f"  {'profile RMS |dr|':<24s} {rms:>10.3f}   [mm]  "
          f"(common zs {lo:.2f}..{hi:.2f} mm)")
    print(f"  {'profile max |dr|':<24s} {dmax:>10.3f}   [mm]")
    print("=" * 66)

    png = f"{args.out}_overlay.png"
    csv = f"{args.out}_profiles.csv"
    write_overlay_png(png, exp_z, exp_r, sim_z, sim_r)
    write_csv(csv, exp_z, exp_r, r_sim_on_exp)
    print(f"  wrote {png}")
    print(f"  wrote {csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
