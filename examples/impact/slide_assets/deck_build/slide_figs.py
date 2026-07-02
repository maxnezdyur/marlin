#!/usr/bin/env python
"""Results figures for the WCCM deck — redesigned to show the physics directly.

fig_verification : the two computed force FIELDS side by side + difference strip
fig_pstrain_xsec : meridional cross-sections colored by effective plastic strain
fig_thermal_xsec : same cross-section design colored by temperature rise
fig_profile      : mirrored-half temper comparison (full-hard top / annealed bottom)

All read exodus outputs directly (scipy netcdf). INL deck style throughout.
"""

import os
from collections import defaultdict

import matplotlib
import numpy as np
from scipy.io import netcdf_file

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from matplotlib import colors

HERE = os.path.dirname(os.path.abspath(__file__))
IMPACT = os.path.normpath(os.path.join(HERE, "../.."))
TESTS = os.path.normpath(os.path.join(HERE, "../../../../test/tests/impact"))
OUT = os.path.join(HERE, "figs")
os.makedirs(OUT, exist_ok=True)

BLUE = "#06509D"
CRIMSON = "#CF1D4C"
GRAY = "#59595C"
INK = "#1E2430"
FAINT = "#B6BABF"

plt.rcParams.update({
    "font.family": "Arial",
    "text.color": INK,
    "axes.edgecolor": FAINT,
    "axes.labelcolor": INK,
    "axes.titlecolor": INK,
    "xtick.color": GRAY,
    "ytick.color": GRAY,
    "axes.linewidth": 0.8,
    "font.size": 12,
})


def _nc(path):
    return netcdf_file(path, "r", mmap=False)


def _names(nc, key):
    return [b"".join(n).decode("ascii", "ignore").strip("\x00 ") for n in nc.variables[key].data]


# ================================================================ verification
def fig_verification():
    """Three horizontal strips: MOOSE force field, NEML2 force field, difference.
    2D slug drawn deformed, axial horizontal, impact face at left."""

    def load(fn):
        nc = _nc(fn)
        g = lambda n: nc.variables[n].data.copy()
        d = dict(x=g("coordx"), y=g("coordy"), conn=g("connect1").astype(int) - 1,
                 dx=g("vals_nod_var1")[-1], dy=g("vals_nod_var2")[-1],
                 fx=g("vals_nod_var3")[-1], fy=g("vals_nod_var4")[-1])
        nc.close()
        return d

    M = load(os.path.join(TESTS, "gold/slug_2d.e"))
    E = load(os.path.join(TESTS, "slug_2d.e"))

    # deformed coords, axial (y) horizontal, in mm; force in kN
    ax_c = (M["y"] + M["dy"]) * 1e3
    r_c = (M["x"] + M["dx"]) * 1e3
    tris = []
    for q in M["conn"]:
        tris.append([q[0], q[1], q[2]])
        tris.append([q[0], q[2], q[3]])
    tri = mtri.Triangulation(ax_c, r_c, np.array(tris))

    fM, fE = M["fy"] * 1e-3, E["fy"] * 1e-3
    # normalize the error by the largest force in the field: a fair, floor-free scale
    diff = np.abs(fM - fE) / np.abs(fM).max()
    vmax = max(abs(fM).max(), abs(fE).max())

    fig, axes = plt.subplots(3, 1, figsize=(9.0, 3.9), sharex=True, sharey=True)
    panels = [
        (fM, "MOOSE native J2 — internal nodal force (kN)", "Blues_r", (-vmax, 0)),
        (fE, "NEML2 force path — same field", "Blues_r", (-vmax, 0)),
        (diff * 1e8, r"$|\Delta F|\ /\ \max|F|\ \ (\times 10^{-8})$", "Reds", (0, 3)),
    ]
    pcs = []
    for ax, (vals, title, cmap, (v0, v1)) in zip(axes, panels):
        pc = ax.tripcolor(tri, vals, shading="gouraud", cmap=cmap, vmin=v0, vmax=v1)
        pcs.append(pc)
        ax.set_aspect("equal")
        ax.set_axis_off()
        ax.set_title(title, fontsize=12, loc="left", pad=2)
    # one shared colorbar for the two identical field panels, one for the diff
    cb1 = fig.colorbar(pcs[0], ax=axes[:2], fraction=0.03, pad=0.015, aspect=14)
    cb1.ax.tick_params(labelsize=9, color=GRAY, labelcolor=GRAY)
    cb1.outline.set_edgecolor(FAINT)
    cb2 = fig.colorbar(pcs[2], ax=axes[2:], fraction=0.06, pad=0.015, aspect=6)
    cb2.ax.tick_params(labelsize=9, color=GRAY, labelcolor=GRAY)
    cb2.outline.set_edgecolor(FAINT)
    axes[0].annotate("impact face", xy=(ax_c.min() + 0.4, r_c.max() * 1.45),
                     fontsize=10, color=GRAY, ha="left")
    out = os.path.join(OUT, "fig_verification.png")
    fig.savefig(out, dpi=220, bbox_inches="tight", pad_inches=0.12, facecolor="white")
    print("wrote", out, f"| max |dF|/max|F| {diff.max():.2e}")
    plt.close(fig)


# ================================================================ cross-sections
def _load_3d(path, fields):
    nc = _nc(path)
    g = lambda n: nc.variables[n].data.copy()
    names = _names(nc, "name_elem_var")
    d = dict(x=g("coordx"), y=g("coordy"), z=g("coordz"), t=g("time_whole"),
             dx=g("vals_nod_var1"), dy=g("vals_nod_var2"), dz=g("vals_nod_var3"),
             conn=g("connect1").astype(int) - 1)
    for f in fields:
        d[f] = g(f"vals_elem_var{names.index(f) + 1}eb1")
    nc.close()
    return d


def _xsec_panels(d, field, frames, cmap, cbar_label, out_name, fmt="{:.2f}",
                 vmax=None, accent=CRIMSON):
    """Meridional (axial-radial) cross-section sequence, azimuthally projected:
    element centroids at deformed positions, mirrored to ±r, tricontourf."""
    conn = d["conn"]
    peak = max(d[field][k].max() for k in frames)
    vmax = vmax or 0.8 * peak  # saturate the top 20% (extend='max') for readable mid-tones
    norm = colors.Normalize(0.0, vmax)
    n = len(frames)
    fig, axes = plt.subplots(1, n, figsize=(3.05 * n, 2.15), sharey=True)
    for ax, k in zip(axes, frames):
        X = d["x"] + d["dx"][k]
        Y = d["y"] + d["dy"][k]
        Z = d["z"] + d["dz"][k]
        cx = X[conn].mean(1)
        cy = Y[conn].mean(1)
        cz = Z[conn].mean(1)
        axial = (cy - (d["y"] + d["dy"][k]).min()) * 1e3
        r = np.sqrt(cx ** 2 + cz ** 2) * 1e3
        vals = d[field][k]
        # mirror to a full section + pin the axis so contours close nicely
        A = np.r_[axial, axial]
        R = np.r_[r, -r]
        V = np.r_[vals, vals]
        levels = np.linspace(0, vmax, 17)
        tpc = ax.tricontourf(A, R, V, levels=levels, cmap=cmap, extend="max")
        for c in (tpc.collections if hasattr(tpc, "collections") else []):
            c.set_edgecolor("face")
        ax.set_aspect("equal")
        ax.set_xlim(-1.5, 40)
        ax.set_ylim(-8.6, 8.6)
        ax.set_axis_off()
        ax.set_title(f"t = {d['t'][k]*1e6:.0f} µs", fontsize=13, pad=2)
        # peak annotation on the last frame
        if k == frames[-1]:
            ax.annotate(f"peak {fmt.format(vals.max())}",
                        xy=(20, -7.4), fontsize=12, color=accent, fontweight="bold")
    # scale bar on the first panel
    axes[0].plot([26, 36], [-7.0, -7.0], "-", color=GRAY, lw=1.6)
    axes[0].annotate("10 mm", xy=(31, -5.9), ha="center", fontsize=9.5, color=GRAY)
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=axes, fraction=0.015, pad=0.012, extend="max")
    cb.set_label(cbar_label, fontsize=11)
    cb.ax.tick_params(labelsize=9.5, color=GRAY, labelcolor=GRAY)
    cb.outline.set_edgecolor(FAINT)
    out = os.path.join(OUT, out_name)
    fig.savefig(out, dpi=220, bbox_inches="tight", pad_inches=0.12, facecolor="white")
    print("wrote", out, f"| {field} peak {max(d[field][k].max() for k in frames):.3f}")
    plt.close(fig)


def _pick_frames(d):
    """4 frames: early, developing, mid, final."""
    nlast = len(d["t"]) - 1
    return [max(1, int(nlast * f)) for f in (0.05, 0.15, 0.4, 1.0)]


def fig_pstrain_xsec(src="3d_slug_thermal_out.e"):
    d = _load_3d(os.path.join(IMPACT, src), ["state/ep"])
    _xsec_panels(d, "state/ep", _pick_frames(d), "Blues",
                 "effective plastic strain", "fig_pstrain.png", fmt="{:.2f}")
    return d


def fig_thermal_xsec(src="3d_slug_thermal_out.e"):
    d = _load_3d(os.path.join(IMPACT, src), ["state/dT"])
    _xsec_panels(d, "state/dT", _pick_frames(d), "OrRd",
                 "temperature rise ΔT (K)", "fig_thermal.png", fmt="{:.0f} K")
    return d


# ================================================================ profile
FACES = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]


def _exterior_nodes(conn):
    cnt = defaultdict(int)
    facemap = {}
    for e, el in enumerate(conn):
        for f in FACES:
            k = tuple(sorted(el[f]))
            cnt[k] += 1
            facemap[k] = el[f]
    s = set()
    for k, c in cnt.items():
        if c == 1:
            s.update(k)
    return np.array(sorted(s))


def _silhouette(dd, k, snodes, nb=26):
    Y = (dd["y"] + dd["dy"][k])[snodes]
    R = np.sqrt((dd["x"] + dd["dx"][k]) ** 2 + (dd["z"] + dd["dz"][k]) ** 2)[snodes]
    Y = Y - Y.min()
    edges = np.linspace(Y.min(), Y.max(), nb + 1)
    idx = np.clip(np.digitize(Y, edges) - 1, 0, nb - 1)
    yc = 0.5 * (edges[:-1] + edges[1:])
    rmax = np.full(nb, np.nan)
    for b in range(nb):
        m = idx == b
        if m.any():
            rmax[b] = R[m].max()
    keep = ~np.isnan(rmax)
    yc, rmax = yc[keep], rmax[keep]
    rs = np.convolve(np.r_[rmax[0], rmax, rmax[-1]], np.ones(3) / 3, mode="valid")
    return yc * 1e3, rs * 1e3


def _load_disp(path):
    nc = _nc(path)
    g = lambda n: nc.variables[n].data.copy()
    d = dict(x=g("coordx"), y=g("coordy"), z=g("coordz"), t=g("time_whole"),
             dx=g("vals_nod_var1"), dy=g("vals_nod_var2"), dz=g("vals_nod_var3"),
             conn=g("connect1").astype(int) - 1)
    nc.close()
    return d


def fig_profile():
    """Mirrored halves: full-hard silhouette on top, annealed below the axis."""
    fh = _load_disp(os.path.join(IMPACT, "3d_slug_mesh_fullhard.e"))
    an = _load_disp(os.path.join(IMPACT, "3d_slug_mesh_annealed_exodus.e"))
    sn = _exterior_nodes(fh["conn"])
    R0 = np.sqrt(fh["x"] ** 2 + fh["z"] ** 2).max() * 1e3
    L0 = (fh["y"].max() - fh["y"].min()) * 1e3
    kfh, kan = fh["dy"].shape[0] - 1, an["dy"].shape[0] - 1
    yfh, rfh = _silhouette(fh, kfh, sn)
    yan, ran = _silhouette(an, kan, sn)
    sh_fh = abs(fh["dy"][kfh].min()) / (fh["y"].max() - fh["y"].min()) * 100
    sh_an = abs(an["dy"][kan].min()) / (an["y"].max() - an["y"].min()) * 100

    fig, ax = plt.subplots(figsize=(7.8, 3.1))
    # undeformed outline
    ax.add_patch(plt.Rectangle((0, -R0), L0, 2 * R0, fill=False, ls="--", ec=GRAY, lw=1.3))
    ax.annotate("undeformed", xy=(L0 - 0.8, R0 * 0.45), ha="right",
                color=GRAY, fontsize=11)
    # top half: full-hard; bottom half: annealed
    ax.fill_between(yfh, 0, rfh, color=CRIMSON, alpha=0.16, linewidth=0)
    ax.plot(yfh, rfh, "-", color=CRIMSON, lw=2.4)
    ax.fill_between(yan, -ran, 0, color=BLUE, alpha=0.16, linewidth=0)
    ax.plot(yan, -ran, "-", color=BLUE, lw=2.4)
    ax.axhline(0.0, color=GRAY, lw=0.8, ls=":")
    ax.annotate("one temper shown on each side of the axis",
                xy=(L0 * 0.55, -1.35), fontsize=9.5, color=GRAY, style="italic")
    ax.annotate(f"full-hard   {sh_fh:.0f}% shorter", xy=(yfh.max() + 1.5, 4.4),
                color=CRIMSON, fontsize=12.5, fontweight="bold")
    ax.annotate(f"annealed   {sh_an:.0f}% shorter", xy=(yan.max() + 1.5, -5.3),
                color=BLUE, fontsize=12.5, fontweight="bold")
    ax.set_xlabel("axial position from impact face (mm)")
    ax.set_ylabel("radius (mm)")
    ax.set_ylim(-7.0, 7.0)
    ax.set_aspect("equal")
    ax.grid(alpha=0.3, linewidth=0.6, color=FAINT)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    out = os.path.join(OUT, "fig_profile.png")
    fig.savefig(out, dpi=220, bbox_inches="tight", pad_inches=0.12, facecolor="white")
    print("wrote", out, f"| shortening fh {sh_fh:.1f}% an {sh_an:.1f}%")
    plt.close(fig)


if __name__ == "__main__":
    import sys
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "verif"):
        fig_verification()
    if which in ("all", "pstrain"):
        fig_pstrain_xsec()
    if which in ("all", "thermal"):
        fig_thermal_xsec()
    if which in ("all", "profile"):
        fig_profile()
