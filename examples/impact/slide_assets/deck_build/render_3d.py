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
        ax.set_title(f"t = {d['t'][k]*1e6:.0f} µs", fontsize=13, pad=4)
    axc = fig.add_subplot(gs[0, -1])
    sm = plt.cm.ScalarMappable(norm=colors.Normalize(0, vmax), cmap=cmap)
    cb = fig.colorbar(sm, cax=axc, extend="max")
    cb.set_label(label, fontsize=11.5)
    cb.ax.tick_params(labelsize=10, color=GRAY, labelcolor=GRAY)
    cb.outline.set_edgecolor(FAINT)
    fig.axes[len(frames) - 1].annotate(f"peak {fmt.format(peak)}", xy=(0.5, -0.06),
                                       xycoords="axes fraction", ha="center",
                                       fontsize=12.5, color=CRIMSON, fontweight="bold")
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
    fh = load(os.path.join(IMPACT, "3d_slug_mesh_fullhard.e"))
    an = load(os.path.join(IMPACT, "3d_slug_mesh_annealed_exodus.e"))
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
        ax.set_title(name, fontsize=13.5, color=c, fontweight="bold", pad=4)
        if note:
            ax.annotate(note, xy=(0.5, -0.05), xycoords="axes fraction", ha="center",
                        fontsize=12.5, color=c, fontweight="bold")
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
    """Flat crisp render of the deformed 2D mesh (axial horizontal)."""
    ax_c = (d["y"] + d["dy"]) * 1e3
    r_c = (d["x"] + d["dx"]) * 1e3
    pts = np.stack([ax_c, r_c, np.zeros_like(ax_c)], axis=1)
    n = len(d["conn"])
    faces = np.hstack([np.full((n, 1), 4), d["conn"]]).ravel()
    surf = pv.PolyData(pts, faces)
    surf.point_data["f"] = np.array(vals, dtype=float, copy=True)
    w = ax_c.max() - ax_c.min()
    h = (r_c.max() - r_c.min()) * 2.2
    pl = pv.Plotter(off_screen=True, window_size=(px_w, max(int(px_w * h / w / 2), 140)))
    pl.set_background("white")
    pl.add_mesh(surf, scalars="f", cmap=cmap, clim=clim, show_edges=True,
                edge_color="white", line_width=1.2, lighting=False,
                show_scalar_bar=False)
    pl.enable_parallel_projection()
    ctr = np.array(surf.center)
    pl.camera_position = [tuple(ctr + np.array([0, 0, 100])), tuple(ctr), (0, 1, 0)]
    pl.camera.parallel_scale = (r_c.max() - r_c.min()) * 0.62
    img = pl.screenshot(transparent_background=True, return_img=True)
    pl.close()
    return _autocrop(img, pad=4)


def verification_figure():
    M = _load_2d(os.path.join(TESTS, "gold/slug_2d.e"))
    E = _load_2d(os.path.join(TESTS, "slug_2d.e"))
    fM = np.hypot(M["fx"], M["fy"]) * 1e-3   # kN
    fE = np.hypot(E["fx"], E["fy"]) * 1e-3
    dvec = np.hypot(M["fx"] - E["fx"], M["fy"] - E["fy"]) * 1e-3
    diff = dvec / fM.max()
    vmax = max(fM.max(), fE.max())

    img1 = _render_2d(M, fM, "viridis", (0, vmax))
    img2 = _render_2d(E, fE, "viridis", (0, vmax))
    img3 = _render_2d(M, diff * 1e8, "inferno", (0, 3))

    fig = plt.figure(figsize=(10.0, 3.55))
    gs = fig.add_gridspec(3, 2, width_ratios=[1, 0.018], hspace=0.75, wspace=0.03)
    titles = ["MOOSE native J2  —  internal nodal force magnitude (kN)",
              "NEML2 force path  —  same field",
              r"difference, relative to peak force   $(\times 10^{-8})$"]
    for i, (im, ti) in enumerate(zip([img1, img2, img3], titles)):
        ax = fig.add_subplot(gs[i, 0])
        ax.imshow(im)
        ax.set_axis_off()
        ax.set_title(ti, fontsize=12, loc="left", pad=3)
    for rows, cmap_, clim_ in ((slice(0, 2), "viridis", (0, vmax)), (slice(2, 3), "inferno", (0, 3))):
        axc = fig.add_subplot(gs[rows, 1])
        sm = plt.cm.ScalarMappable(norm=colors.Normalize(*clim_), cmap=cmap_)
        cb = fig.colorbar(sm, cax=axc)
        cb.ax.tick_params(labelsize=9, color=GRAY, labelcolor=GRAY)
        cb.outline.set_edgecolor(FAINT)
    out = os.path.join(OUT, "fig_verification.png")
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.1, facecolor="white")
    print("wrote", out, f"| max diff/peak {diff.max():.2e}")
    plt.close(fig)


if __name__ == "__main__":
    import sys
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    src = sys.argv[2] if len(sys.argv) > 2 else "3d_slug_thermal_out.e"
    if which in ("all", "pstrain"):
        sequence_figure(src, "state/ep", "viridis", "effective plastic strain",
                        "fig_pstrain.png", "{:.2f}")
    if which in ("all", "thermal"):
        sequence_figure(src, "state/dT", _truncated("inferno", 0.05, 0.92), "temperature rise ΔT (K)",
                        "fig_thermal.png", "{:.0f} K")
    if which in ("all", "profile"):
        profile_figure()
    if which in ("all", "verif"):
        verification_figure()
