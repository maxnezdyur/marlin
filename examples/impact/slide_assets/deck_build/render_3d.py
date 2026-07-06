#!/usr/bin/env python
"""ParaView-style 3-D renders of the Taylor slug for the WCCM deck.

Renders the deformed hex mesh with smooth-shaded fields via pyvista (offscreen),
then composes multi-panel figures with matplotlib for typography.

fig_pstrain.png  : cutaway sequence colored by effective plastic strain
fig_thermal.png  : cutaway sequence colored by temperature rise
fig_profile.png  : full-hard vs annealed final shapes, side by side
"""

import os
from math import pi

import matplotlib
import numpy as np
from scipy.io import netcdf_file

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pyvista as pv
from matplotlib import colors

pv.OFF_SCREEN = True

HERE = os.path.dirname(os.path.abspath(__file__))
IMPACT = os.path.normpath(os.path.join(HERE, "../.."))
OUT = os.path.join(HERE, "figs")
os.makedirs(OUT, exist_ok=True)

BLUE = "#06509D"
CRIMSON = "#CF1D4C"
GRAY = "#59595C"
INK = "#1E2430"
FAINT = "#B6BABF"

plt.rcParams.update({
    "font.family": "Arial", "text.color": INK, "axes.edgecolor": FAINT,
    "axes.labelcolor": INK, "xtick.color": GRAY, "ytick.color": GRAY,
    "font.size": 12,
})


def load(path, fields=()):
    nc = netcdf_file(path, "r", mmap=False)
    g = lambda n: nc.variables[n].data.copy()
    names = [b"".join(n).decode("ascii", "ignore").strip("\x00 ") for n in
             (nc.variables["name_elem_var"].data if "name_elem_var" in nc.variables else [])]
    d = dict(x=g("coordx"), y=g("coordy"), z=g("coordz"), t=g("time_whole"),
             dx=g("vals_nod_var1"), dy=g("vals_nod_var2"), dz=g("vals_nod_var3"),
             conn=g("connect1").astype(int) - 1)
    for f in fields:
        d[f] = g(f"vals_elem_var{names.index(f) + 1}eb1")
    nc.close()
    # drop trailing garbage frames (partially written records after a crash)
    t = d["t"]
    nvalid = len(t)
    for k in range(len(t)):
        vals_ok = all(np.isfinite(d[f][k]).all() and np.abs(d[f][k]).max() < 1e12
                      for f in fields)
        disp_ok = np.isfinite(d["dy"][k]).all() and np.abs(d["dy"][k]).max() < 1.0
        t_ok = np.isfinite(t[k]) and (k == 0 or t[k] > t[k - 1])
        if not (vals_ok and disp_ok and t_ok):
            nvalid = k
            break
    if nvalid < len(t):
        d["t"] = t[:nvalid]
        for key in ("dx", "dy", "dz", *fields):
            d[key] = d[key][:nvalid]
    return d


def grid_at(d, k, field=None):
    """pyvista UnstructuredGrid of the deformed mesh at frame k (mm units)."""
    pts = np.stack([d["x"] + d["dx"][k], d["y"] + d["dy"][k], d["z"] + d["dz"][k]], axis=1) * 1e3
    n = len(d["conn"])
    cells = np.hstack([np.full((n, 1), 8), d["conn"]]).ravel()
    celltypes = np.full(n, pv.CellType.HEXAHEDRON, dtype=np.uint8)
    gr = pv.UnstructuredGrid(cells, celltypes, pts)
    if field is not None:
        # copy: VTK wraps numpy arrays zero-copy and can stomp views into the
        # (nframes x nelem) field array
        gr.cell_data["f"] = np.array(d[field][k], dtype=float, copy=True)
        gr = gr.cell_data_to_point_data()
    return gr


CAMERA_DIR = np.array([1.45, 0.5, 1.0])


def _truncated(cmap_name, lo=0.08, hi=1.0):
    """Colormap without the near-white base so low field values still read."""
    base = matplotlib.colormaps[cmap_name]
    return colors.ListedColormap(base(np.linspace(lo, hi, 256)))


def render_field(gr, cmap, clim, clip=True, px=900, camera=None):
    """One shaded render; returns RGBA array. Cutaway reveals the interior.
    Pass the same `camera` (position, focal, up) for every frame of a sequence
    so all panels share one physical scale."""
    pl = pv.Plotter(off_screen=True, window_size=(px, px))
    pl.set_background("white")
    if clip:
        # keep the z<0 half so the exposed cut plane faces the camera (+z side)
        body = gr.clip(normal=(0, 0, 1), origin=(0.0, 0.0, 0.0))
    else:
        body = gr
    pl.add_mesh(body, scalars="f", cmap=cmap, clim=clim, smooth_shading=True,
                show_edges=False, specular=0.12, specular_power=8,
                diffuse=0.95, ambient=0.35, show_scalar_bar=False)
    # rigid anvil under the impact face
    b = gr.bounds
    D = max(b[1] - b[0], b[5] - b[4])
    anvil = pv.Plane(center=(0, b[2] - 0.15, 0), direction=(0, 1, 0),
                     i_size=2.6 * D, j_size=2.6 * D)
    pl.add_mesh(anvil, color="#E2E5E9", ambient=0.45, diffuse=0.75,
                specular=0.05, show_scalar_bar=False)
    if camera is None:
        camera = camera_for(gr)
    pl.camera_position = camera
    img = pl.screenshot(transparent_background=True, return_img=True)
    pl.close()
    return img


def camera_for(gr, zoom=2.05):
    ctr = np.array(gr.center)
    L = max(gr.bounds[1] - gr.bounds[0], gr.bounds[3] - gr.bounds[2]) * 1.15
    pos = ctr + CAMERA_DIR / np.linalg.norm(CAMERA_DIR) * L * zoom
    return [tuple(pos), tuple(ctr), (0, 1, 0)]


def _autocrop(img, pad=8):
    a = img[..., 3]
    ys, xs = np.where(a > 0)
    if len(ys) == 0:
        return img
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, img.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, img.shape[1])
    return img[y0:y1, x0:x1]


def _union_crop(imgs, pad=10):
    """Crop all images to the union of their occupied pixels — preserves the
    common physical scale across a fixed-camera sequence."""
    y0 = x0 = 10 ** 9
    y1 = x1 = -1
    for im in imgs:
        ys, xs = np.where(im[..., 3] > 0)
        if len(ys):
            y0, y1 = min(y0, ys.min()), max(y1, ys.max())
            x0, x1 = min(x0, xs.min()), max(x1, xs.max())
    y0, x0 = max(y0 - pad, 0), max(x0 - pad, 0)
    y1, x1 = y1 + pad, x1 + pad
    return [im[y0:y1, x0:x1] for im in imgs]


def sequence_figure(src, field, cmap, label, out_name, fmt, frac=(0.05, 0.15, 0.4, 1.0)):
    d = load(os.path.join(IMPACT, src), [field])
    nlast = len(d["t"]) - 1
    frames = [max(1, int(nlast * f)) for f in frac]
    peak = max(d[field][k].max() for k in frames)
    vmax = 0.9 * peak
    cam = camera_for(grid_at(d, 0))   # frame-0 camera for every panel: shared scale
    imgs = _union_crop([render_field(grid_at(d, k, field), cmap, (0, vmax), camera=cam)
                        for k in frames])

    fig = plt.figure(figsize=(12.6, 3.0))
    gs = fig.add_gridspec(1, len(frames) + 1, width_ratios=[1] * len(frames) + [0.06],
                          wspace=0.04)
    for i, (k, im) in enumerate(zip(frames, imgs)):
        ax = fig.add_subplot(gs[0, i])
        ax.imshow(im)
        ax.set_axis_off()
        ax.set_title(f"t = {d['t'][k]*1e6:.0f} µs", fontsize=15, pad=4)
    axc = fig.add_subplot(gs[0, -1])
    sm = plt.cm.ScalarMappable(norm=colors.Normalize(0, vmax), cmap=cmap)
    cb = fig.colorbar(sm, cax=axc, extend="max")
    cb.set_label(label, fontsize=13)
    cb.ax.tick_params(labelsize=12, color=GRAY, labelcolor=GRAY)
    cb.outline.set_edgecolor(FAINT)
    fig.axes[len(frames) - 1].annotate(f"peak {fmt.format(peak)}", xy=(0.5, -0.06),
                                       xycoords="axes fraction", ha="center",
                                       fontsize=14.5, color=CRIMSON, fontweight="bold")
    out = os.path.join(OUT, out_name)
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.1, facecolor="white")
    print("wrote", out, f"| {field} peak {peak:.3f} at t={d['t'][frames[-1]]*1e6:.0f}us")
    plt.close(fig)


def render_solid(gr, color, camera, px=900):
    pl = pv.Plotter(off_screen=True, window_size=(px, px))
    pl.set_background("white")
    pl.add_mesh(gr, color=color, smooth_shading=True, specular=0.2,
                specular_power=10, diffuse=0.9, ambient=0.32)
    b = gr.bounds
    D = max(b[1] - b[0], b[5] - b[4])
    anvil = pv.Plane(center=(0, b[2] - 0.15, 0), direction=(0, 1, 0),
                     i_size=2.6 * D, j_size=2.6 * D)
    pl.add_mesh(anvil, color="#E2E5E9", ambient=0.45, diffuse=0.75, specular=0.05)
    pl.camera_position = camera
    img = pl.screenshot(transparent_background=True, return_img=True)
    pl.close()
    return img


def profile_figure():
    fh = load(os.path.join(IMPACT, "3d_mult_ri_fullhard.e"))
    an = load(os.path.join(IMPACT, "3d_mult_ri_annealed.e"))
    kfh, kan = len(fh["t"]) - 1, len(an["t"]) - 1
    sh_fh = abs(fh["dy"][kfh].min()) / (fh["y"].max() - fh["y"].min()) * 100
    sh_an = abs(an["dy"][kan].min()) / (an["y"].max() - an["y"].min()) * 100
    cam = camera_for(grid_at(fh, 0))  # one camera: shared physical scale
    imgs = _union_crop([
        render_solid(grid_at(fh, 0), "#D9DDE2", cam),
        render_solid(grid_at(fh, kfh), "#E08292", cam),
        render_solid(grid_at(an, kan), "#7FA8D4", cam),
    ])
    panels = [("undeformed", GRAY, ""),
              ("full-hard", CRIMSON, f"{sh_fh:.0f}% shorter"),
              ("annealed", BLUE, f"{sh_an:.0f}% shorter")]
    fig = plt.figure(figsize=(9.6, 2.9))
    gs = fig.add_gridspec(1, 3, wspace=0.04)
    for i, (im, (name, c, note)) in enumerate(zip(imgs, panels)):
        ax = fig.add_subplot(gs[0, i])
        ax.imshow(im)
        ax.set_axis_off()
        ax.set_title(name, fontsize=16, color=c, fontweight="bold", pad=4)
        if note:
            ax.annotate(note, xy=(0.5, -0.05), xycoords="axes fraction", ha="center",
                        fontsize=15, color=c, fontweight="bold")
    out = os.path.join(OUT, "fig_profile.png")
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.1, facecolor="white")
    print("wrote", out, f"| fh {sh_fh:.1f}% an {sh_an:.1f}%")
    plt.close(fig)


TESTS = os.path.normpath(os.path.join(HERE, "../../../../test/tests/impact"))


def _load_2d(fn):
    nc = netcdf_file(fn, "r", mmap=False)
    g = lambda n: nc.variables[n].data.copy()
    d = dict(x=g("coordx"), y=g("coordy"), conn=g("connect1").astype(int) - 1,
             dx=g("vals_nod_var1")[-1], dy=g("vals_nod_var2")[-1],
             fx=g("vals_nod_var3")[-1], fy=g("vals_nod_var4")[-1])
    nc.close()
    return d


def _render_2d(d, vals, cmap, clim, px_w=2400):
    """Shaded 3-D slab render of the deformed 2D verification mesh — the 2D
    quads are extruded to thin hexes so the panel matches the deck's 3-D look."""
    ax_c = (d["y"] + d["dy"]) * 1e3
    r_c = (d["x"] + d["dx"]) * 1e3
    n_nodes = len(ax_c)
    th = (r_c.max() - r_c.min()) * 0.55   # slab thickness
    bottom = np.stack([ax_c, r_c, np.zeros(n_nodes)], axis=1)
    top = bottom + np.array([0, 0, th])
    pts = np.vstack([bottom, top])
    n = len(d["conn"])
    hexes = np.hstack([np.full((n, 1), 8), d["conn"], d["conn"] + n_nodes]).ravel()
    celltypes = np.full(n, pv.CellType.HEXAHEDRON, dtype=np.uint8)
    gr = pv.UnstructuredGrid(hexes, celltypes, pts)
    gr.point_data["f"] = np.tile(np.array(vals, dtype=float, copy=True), 2)
    pl = pv.Plotter(off_screen=True, window_size=(px_w, 520))
    pl.set_background("white")
    pl.add_mesh(gr, scalars="f", cmap=cmap, clim=clim, smooth_shading=False,
                show_edges=True, edge_color=[1.0, 1.0, 1.0], line_width=1.0,
                specular=0.15, specular_power=10, diffuse=0.9, ambient=0.4,
                show_scalar_bar=False)
    pl.enable_parallel_projection()
    ctr = np.array(gr.center)
    cam_dir = np.array([0.18, 0.55, 1.0])
    pos = ctr + cam_dir / np.linalg.norm(cam_dir) * 200
    pl.camera_position = [tuple(pos), tuple(ctr), (0, 1, 0)]
    pl.camera.parallel_scale = (r_c.max() - r_c.min()) * 1.35
    img = pl.screenshot(transparent_background=True, return_img=True)
    pl.close()
    return _autocrop(img, pad=4)


def verification_figure():
    """Log-scale error ladder: where the measured path-to-path differences sit
    relative to tolerances the audience knows. No mesh, no fields — the number."""
    M = _load_2d(os.path.join(TESTS, "gold/slug_2d.e"))
    E = _load_2d(os.path.join(TESTS, "slug_2d.e"))
    f_diff = (np.hypot(M["fx"] - E["fx"], M["fy"] - E["fy"])
              / np.hypot(M["fx"], M["fy"]).max()).max()
    floor = 1e-5
    def rel(a, b):
        return (np.abs(a - b) / np.maximum(np.maximum(np.abs(a), np.abs(b)), floor)).max()
    d_diff = max(rel(M["dx"], E["dx"]), rel(M["dy"], E["dy"]))

    fig, ax = plt.subplots(figsize=(7.7, 3.4))
    ax.set_xscale("log")
    ax.set_xlim(3e-9, 3e-1)
    ax.invert_xaxis()                       # smaller error -> further right
    ax.set_ylim(0, 1)
    ax.get_yaxis().set_visible(False)
    for side in ("left", "top", "right"):
        ax.spines[side].set_visible(False)
    axis_y = 0.52
    ax.spines["bottom"].set_position(("axes", axis_y))
    ax.set_xticks([1e-1, 1e-2, 1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8])
    ax.tick_params(labelsize=11.5, colors=GRAY)
    ax.set_xlabel("relative difference between the two force paths  (log scale — right is better)",
                  fontsize=12.5, labelpad=10)

    # floating-point noise zone straddling the axis
    ax.axvspan(3e-9, 3e-7, ymin=0.42, ymax=0.62, color="#E9EDF3", zorder=0)
    ax.annotate("floating-point noise", xy=(3.2e-8, 0.655), fontsize=11, color=GRAY,
                ha="center", style="italic")

    # reference tolerances (above the axis, hanging downward, staggered l/r)
    ax.plot([1e-2], [axis_y], "o", color=GRAY, ms=9, zorder=5, clip_on=False)
    ax.plot([5e-4], [axis_y], "o", color=GRAY, ms=9, zorder=5, clip_on=False)
    ax.annotate("1%  “engineering\nagreement”", xy=(1.35e-2, 0.76), fontsize=11.5,
                color=GRAY, ha="right", va="top", linespacing=1.25)
    ax.annotate("exodiff regression\ntolerance  $5\\times10^{-4}$", xy=(3.6e-4, 0.76),
                fontsize=11.5, color=GRAY, ha="left", va="top", linespacing=1.25)
    # our measurements (markers on the axis, labels below the axis caption)
    green = "#5E8614"
    ax.plot([f_diff], [axis_y], "D", color=BLUE, ms=13, zorder=6, clip_on=False)
    ax.plot([d_diff], [axis_y], "D", color=green, ms=13, zorder=6, clip_on=False)
    ax.annotate("nodal forces  $3\\times10^{-8}$", xy=(f_diff * 0.9, 0.20),
                fontsize=12.5, color=BLUE, ha="left", fontweight="bold")
    ax.annotate("displacements  $8\\times10^{-8}$", xy=(d_diff * 1.3, 0.06),
                fontsize=12.5, color=green, ha="right", fontweight="bold")
    ax.plot([f_diff, f_diff * 0.95], [axis_y - 0.03, 0.265], "-", color=BLUE,
            lw=0.9, clip_on=False)
    ax.plot([d_diff, d_diff * 1.22], [axis_y - 0.03, 0.125], "-", color=green,
            lw=0.9, clip_on=False)
    # margin arrow across the top, headline above it
    worst = max(f_diff, d_diff)
    ratio = 5e-4 / worst
    ax.annotate("", xy=(worst * 1.5, 0.86), xytext=(5e-4, 0.86),
                arrowprops=dict(arrowstyle="->", color=INK, lw=1.8))
    ax.annotate(f"{ratio/1000:.0f},000× tighter than the test suite requires",
                xy=(np.sqrt(worst * 5e-4), 0.955), fontsize=13.5,
                color=INK, ha="center", fontweight="bold")
    out = os.path.join(OUT, "fig_verification.png")
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.15, facecolor="white")
    print("wrote", out, f"| force {f_diff:.2e} disp {d_diff:.2e} margin {ratio:,.0f}x")
    plt.close(fig)


if __name__ == "__main__":
    import sys
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    src = sys.argv[2] if len(sys.argv) > 2 else "3d_slug_thermal_out.e"
    if which in ("all", "pstrain"):
        sequence_figure(src, "ep", "viridis", "effective plastic strain",
                        "fig_pstrain.png", "{:.2f}")
    if which in ("all", "thermal"):
        sequence_figure(src, "dT", _truncated("inferno", 0.05, 0.92), "temperature rise ΔT (K)",
                        "fig_thermal.png", "{:.0f} K")
    if which in ("all", "profile"):
        profile_figure()
    if which in ("all", "verif"):
        verification_figure()
