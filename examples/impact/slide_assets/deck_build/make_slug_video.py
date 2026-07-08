"""Render the refined 3-D Taylor run to a smooth-shaded mp4.

Horizontal composition: the anvil (smash surface) is a wall on the LEFT,
the slug flies in from the right. 16:9 frame.
"""
import os
import sys

HERE = "/Users/maxnezdyur/projects/exp-dyn/marlin/examples/impact/slide_assets/deck_build"
sys.path.insert(0, HERE)
import numpy as np
import pyvista as pv

import render_3d as r3

OUT = "/private/tmp/claude-501/-Users-maxnezdyur-projects-exp-dyn/52baa9fe-7cd7-4401-9332-c99b0398d94e/scratchpad/frames"
os.makedirs(OUT, exist_ok=True)

d = r3.load("/Users/maxnezdyur/projects/exp-dyn/marlin/examples/impact/3d_mid_np6.e", ("ep",))
n = len(d["t"])
print("frames:", n)

peak = max(d["ep"][k].max() for k in range(n))
vmax = 0.9 * peak
cmap = "viridis"


def horiz(gr):
    """Rotate so the slug axis (+y) points along +x: anvil wall on the left."""
    return gr.rotate_z(-90, point=(0, 0, 0), inplace=False)


# fixed camera framed on the undeformed horizontal slug
g0 = horiz(r3.grid_at(d, 0))
ctr = np.array(g0.center)
L = g0.bounds[1] - g0.bounds[0]
u = np.array([0.32, 0.42, 1.0])
pos = ctr + u / np.linalg.norm(u) * L * 1.35
cam = [tuple(pos), tuple(ctr), (0, 1, 0)]

for k in range(n):
    gr = horiz(r3.grid_at(d, k, "ep"))
    pl = pv.Plotter(off_screen=True, window_size=(1600, 900))
    pl.set_background("white")
    surf = gr.extract_surface().smooth_taubin(n_iter=30, pass_band=0.05)
    pl.add_mesh(surf, scalars="f", cmap=cmap, clim=(0, vmax), smooth_shading=True,
                show_edges=False, specular=0.15, specular_power=10,
                diffuse=0.95, ambient=0.35, show_scalar_bar=False)
    D = max(g0.bounds[3] - g0.bounds[2], g0.bounds[5] - g0.bounds[4])
    anvil = pv.Plane(center=(gr.bounds[0] - 0.15, ctr[1], ctr[2]),
                     direction=(1, 0, 0), i_size=3.6 * D, j_size=3.6 * D)
    pl.add_mesh(anvil, color="#E2E5E9", ambient=0.45, diffuse=0.75, specular=0.05)
    pl.camera_position = cam
    pl.add_text(f"t = {d['t'][k]*1e6:5.1f} us", position="upper_left",
                font_size=16, color="#1E2430", font="arial")
    pl.screenshot(os.path.join(OUT, f"f{k:04d}.png"))
    pl.close()
    if k % 25 == 0:
        print("rendered", k)
print("done rendering")
