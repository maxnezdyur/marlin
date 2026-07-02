#!/usr/bin/env python
"""Regenerate the results figures in the deck's INL style (Arial, brand palette,
no in-figure suptitles — the slide carries the title). Reads the same exodus
outputs as verif_2d.py / demo_mushroom.py.

Outputs (deck_build/figs/): fig_verification.png, fig_pstrain.png, fig_profile.png
"""

import os
from collections import defaultdict

import matplotlib
import numpy as np
from scipy.io import netcdf_file

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = os.path.dirname(os.path.abspath(__file__))
IMP = os.path.normpath(os.path.join(HERE, ".."))          # examples/impact/slide_assets
IMPACT = os.path.normpath(os.path.join(HERE, "../.."))    # examples/impact
TESTS = os.path.normpath(os.path.join(HERE, "../../../../test/tests/impact"))
OUT = os.path.join(HERE, "figs")
os.makedirs(OUT, exist_ok=True)

# INL deck palette
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


def _grid(ax):
    ax.grid(alpha=0.35, linewidth=0.6, color=FAINT)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


# ---------------------------------------------------------------- verification
def load_2d(fn):
    nc = netcdf_file(fn, "r", mmap=False)
    g = lambda n: nc.variables[n].data.copy()
    d = dict(x=g("coordx"), y=g("coordy"), dx=g("vals_nod_var1"), dy=g("vals_nod_var2"),
             fx=g("vals_nod_var3"), fy=g("vals_nod_var4"))
    nc.close()
    return d


def rel_err(a, b, floor=1e-5):
    a, b = a[-1], b[-1]
    denom = np.maximum(np.maximum(np.abs(a), np.abs(b)), floor)
    return np.abs(a - b) / denom


def fig_verification():
    M = load_2d(os.path.join(TESTS, "gold/slug_2d.e"))
    E = load_2d(os.path.join(TESTS, "slug_2d.e"))
    max_f = max(rel_err(M["fx"], E["fx"]).max(), rel_err(M["fy"], E["fy"]).max())
    max_d = max(rel_err(M["dx"], E["dx"]).max(), rel_err(M["dy"], E["dy"]).max())

    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.9))
    panels = [("fy", "internal nodal force$_y$ (MN)", 1e-6, axes[0]),
              ("dy", "displacement$_y$ (mm)", 1e3, axes[1])]
    for key, lab, scale, ax in panels:
        m, e = M[key][-1] * scale, E[key][-1] * scale
        lim = [min(m.min(), e.min()), max(m.max(), e.max())]
        pad = 0.06 * (lim[1] - lim[0])
        lim = [lim[0] - pad, lim[1] + pad]
        ax.plot(lim, lim, "--", color=GRAY, lw=1.1, zorder=1)
        ax.annotate("y = x", xy=(0.62, 0.56), xycoords="axes fraction",
                    color=GRAY, fontsize=11, rotation=38)
        ax.scatter(m, e, s=26, color=BLUE, alpha=0.75, edgecolors="white",
                   linewidths=0.5, zorder=2)
        ax.set_xlim(lim); ax.set_ylim(lim)
        ax.set_xlabel(f"MOOSE native J2 — {lab}")
        ax.set_ylabel(f"NEML2 force path — {lab}")
        ax.set_aspect("equal")
        _grid(ax)
    axes[0].set_title("nodal forces", fontsize=13, pad=8)
    axes[1].set_title("displacements", fontsize=13, pad=8)
    fig.tight_layout()
    out = os.path.join(OUT, "fig_verification.png")
    fig.savefig(out, dpi=220, bbox_inches="tight", pad_inches=0.18, facecolor="white")
    print("wrote", out, f"| max rel force diff {max_f:.2e}, disp {max_d:.2e}")
    plt.close(fig)


# ---------------------------------------------------------------- 3D mushroom
FACES = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]


def load_3d(fn, elem_field=None):
    nc = netcdf_file(os.path.join(IMPACT, fn), "r", mmap=False)
    g = lambda n: nc.variables[n].data.copy()
    d = dict(x=g("coordx"), y=g("coordy"), z=g("coordz"), t=g("time_whole"),
             dx=g("vals_nod_var1"), dy=g("vals_nod_var2"), dz=g("vals_nod_var3"),
             conn=g("connect1").astype(int) - 1)
    d["ef"] = g(elem_field) if elem_field else None
    nc.close()
    return d


def exterior(conn):
    cnt = defaultdict(int)
    owner = {}
    for e, el in enumerate(conn):
        for f in FACES:
            nodes = tuple(el[f])
            k = tuple(sorted(nodes))
            cnt[k] += 1
            owner[k] = (nodes, e)
    return [owner[k] for k, c in cnt.items() if c == 1]


def warped(d, k):
    return np.stack([d["x"] + d["dx"][k], d["y"] + d["dy"][k], d["z"] + d["dz"][k]], axis=1)


def fig_pstrain():
    d = load_3d("j2_rateindep_out.e", "vals_elem_var1eb1")
    ext = exterior(d["conn"])
    frames = [3, 9, 15, 20]
    vmax = max(d["ef"][k].max() for k in frames)
    norm = colors.Normalize(0.0, vmax)
    cmap = matplotlib.colormaps["inferno"]
    fig = plt.figure(figsize=(13.2, 3.4))
    for i, k in enumerate(frames):
        ax = fig.add_subplot(1, len(frames), i + 1, projection="3d")
        P = warped(d, k)
        polys = [P[list(n)] for n, e in ext]
        fc = cmap(norm(np.array([d["ef"][k][e] for n, e in ext])))
        ax.add_collection3d(Poly3DCollection(polys, facecolors=fc,
                                             edgecolors=(0, 0, 0, 0.12), linewidths=0.2))
        mins, maxs = P.min(0), P.max(0)
        L = maxs - mins
        ax.set_xlim(mins[0], maxs[0]); ax.set_ylim(mins[1], maxs[1]); ax.set_zlim(mins[2], maxs[2])
        ax.set_box_aspect(tuple(L))
        ax.view_init(elev=10, azim=-80)
        ax.set_axis_off()
        ax.set_title(f"t = {d['t'][k]*1e6:.1f} µs", fontsize=13, color=INK, pad=0)
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=fig.axes, fraction=0.014, pad=0.01)
    cb.set_label("effective plastic strain", fontsize=11, color=INK)
    cb.ax.tick_params(labelsize=10, color=GRAY, labelcolor=GRAY)
    cb.outline.set_edgecolor(FAINT)
    out = os.path.join(OUT, "fig_pstrain.png")
    fig.savefig(out, dpi=220, bbox_inches="tight", facecolor="white")
    print("wrote", out, f"| pstrain max {vmax:.3f}, t range {d['t'][0]*1e6:.2f}-{d['t'][-1]*1e6:.1f} µs, steps {len(d['t'])}")
    plt.close(fig)


def surf_nodes(conn):
    s = set()
    for n, e in exterior(conn):
        s.update(n)
    return np.array(sorted(s))


def silhouette(dd, k, snodes, nb=22):
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


def fig_profile():
    fh = load_3d("3d_slug_mesh_fullhard.e")
    an = load_3d("3d_slug_mesh_annealed_exodus.e")
    sn = surf_nodes(fh["conn"])
    R0 = np.sqrt(fh["x"] ** 2 + fh["z"] ** 2).max() * 1e3
    L0 = (fh["y"].max() - fh["y"].min()) * 1e3
    kfh, kan = fh["dy"].shape[0] - 1, an["dy"].shape[0] - 1
    yfh, rfh = silhouette(fh, kfh, sn)
    yan, ran = silhouette(an, kan, sn)
    sh_fh = abs(fh["dy"][kfh].min()) / (fh["y"].max() - fh["y"].min()) * 100
    sh_an = abs(an["dy"][kan].min()) / (an["y"].max() - an["y"].min()) * 100

    fig, ax = plt.subplots(figsize=(7.6, 3.3))
    ax.add_patch(plt.Rectangle((0, -R0), L0, 2 * R0, fill=False, ls="--",
                               ec=GRAY, lw=1.3))
    ax.annotate("undeformed", xy=(L0 - 1, R0 + 0.4), ha="right", color=GRAY, fontsize=11)
    ax.fill_between(yfh, -rfh, rfh, color=CRIMSON, alpha=0.14, linewidth=0)
    ax.plot(yfh, rfh, "-", color=CRIMSON, lw=2.2)
    ax.plot(yfh, -rfh, "-", color=CRIMSON, lw=2.2)
    ax.plot(yan, ran, "-", color=BLUE, lw=2.2)
    ax.plot(yan, -ran, "-", color=BLUE, lw=2.2)
    # direct labels instead of a legend box
    ax.annotate(f"full-hard — {sh_fh:.0f}% shorter", xy=(yfh[-1] + 0.8, 2.4),
                color=CRIMSON, fontsize=12, fontweight="bold")
    ax.annotate(f"annealed — {sh_an:.0f}% shorter", xy=(yfh[-1] + 0.8, 0.9),
                color=BLUE, fontsize=12, fontweight="bold")
    ax.set_xlabel("axial position from impact face (mm)")
    ax.set_ylabel("radius (mm)")
    ax.set_aspect("equal")
    _grid(ax)
    fig.tight_layout()
    out = os.path.join(OUT, "fig_profile.png")
    fig.savefig(out, dpi=220, bbox_inches="tight", facecolor="white")
    print("wrote", out, f"| shortening fullhard {sh_fh:.1f}% annealed {sh_an:.1f}%, "
          f"t_end fh {fh['t'][kfh]*1e6:.0f} µs, steps {len(fh['t'])}")
    plt.close(fig)


if __name__ == "__main__":
    fig_verification()
    fig_pstrain()
    fig_profile()
