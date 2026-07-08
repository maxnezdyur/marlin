"""Pure side view: orthographic camera square-on to the slug axis.

Anvil on the left (thin gray wall seen edge-on), slug horizontal. 16:9.
"""
import os
import sys

HERE = "/Users/maxnezdyur/projects/exp-dyn/marlin/examples/impact/slide_assets/deck_build"
sys.path.insert(0, HERE)
import numpy as np
import pyvista as pv

import render_3d as r3

OUT = "/private/tmp/claude-501/-Users-maxnezdyur-projects-exp-dyn/52baa9fe-7cd7-4401-9332-c99b0398d94e/scratchpad/frames_side"
os.makedirs(OUT, exist_ok=True)

d = r3.load("/Users/maxnezdyur/projects/exp-dyn/marlin/examples/impact/3d_mid_np6.e", ("ep",))
n = len(d["t"])
print("frames:", n)

peak = max(d["ep"][k].max() for k in range(n))
vmax = 0.9 * peak


def horiz(gr):
    return gr.rotate_z(-90, point=(0, 0, 0), inplace=False)


g0 = horiz(r3.grid_at(d, 0))
ctr = np.array(g0.center)
L = g0.bounds[1] - g0.bounds[0]
D = max(g0.bounds[3] - g0.bounds[2], g0.bounds[5] - g0.bounds[4])
cam_pos = ctr + np.array([0.0, 0.0, 3.0 * L])

for k in range(n):
    gr = horiz(r3.grid_at(d, k, "ep"))
    pl = pv.Plotter(off_screen=True, window_size=(1600, 900))
    pl.set_background("white")
    surf = gr.extract_surface()
    pl.add_mesh(surf, scalars="f", cmap="viridis", clim=(0, vmax), smooth_shading=False,
                show_edges=False, specular=0.15, specular_power=10,
                diffuse=0.95, ambient=0.4, show_scalar_bar=False)
    wall = pv.Cube(center=(g0.bounds[0] - 0.01 * L, ctr[1], ctr[2]),
                   x_length=0.02 * L, y_length=3.4 * D, z_length=2.0 * D)
    pl.add_mesh(wall, color="#D4D8DD", ambient=0.5, diffuse=0.7, specular=0.05)
    pl.camera_position = [tuple(cam_pos), tuple(ctr), (0, 1, 0)]
    pl.enable_parallel_projection()
    pl.camera.parallel_scale = 0.35 * L
    pl.add_text(f"t = {d['t'][k]*1e6:5.1f} us", position="upper_left",
                font_size=16, color="#1E2430", font="arial")
    pl.screenshot(os.path.join(OUT, f"f{k:04d}.png"))
    pl.close()
    if k % 25 == 0:
        print("rendered", k)
print("done rendering")
