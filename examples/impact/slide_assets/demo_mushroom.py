#!/usr/bin/env python
"""Static deformed-mushroom snapshots of the 3D Taylor slug -- no vtk/paraview.
(1) plastic-strain sequence from j2_rateindep_out.e (NEML2, elem field).
(2) dramatic final deformed state from 3d_slug_mesh_fullhard.e (disp magnitude)."""
import os, numpy as np
from collections import defaultdict
from scipy.io import netcdf_file
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib import colors

IMP = "/Users/maxnezdyur/projects/exp-dyn/marlin/examples/impact"
OUT = os.path.join(IMP, "slide_assets"); os.makedirs(OUT, exist_ok=True)
FACES = [[0,1,2,3],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]

def load(fn, elem_field=None):
    nc = netcdf_file(os.path.join(IMP, fn), "r", mmap=False); g = lambda n: nc.variables[n].data.copy()
    d = dict(x=g("coordx"), y=g("coordy"), z=g("coordz"), t=g("time_whole"),
             dx=g("vals_nod_var1"), dy=g("vals_nod_var2"), dz=g("vals_nod_var3"),
             conn=g("connect1").astype(int) - 1)
    d["ef"] = g(elem_field) if elem_field else None
    nc.close(); return d

def exterior(conn):
    cnt = defaultdict(int); owner = {}
    for e, el in enumerate(conn):
        for f in FACES:
            nodes = tuple(el[f]); k = tuple(sorted(nodes)); cnt[k] += 1; owner[k] = (nodes, e)
    return [owner[k] for k, c in cnt.items() if c == 1]

def warped(d, k):
    return np.stack([d["x"]+d["dx"][k], d["y"]+d["dy"][k], d["z"]+d["dz"][k]], axis=1)

def frame(ax, P, ext, vals, norm, cmap, title):
    polys = [P[list(n)] for n, e in ext]
    fc = cmap(norm(np.array([vals[e] for n, e in ext])))
    ax.add_collection3d(Poly3DCollection(polys, facecolors=fc, edgecolors=(0,0,0,0.12), linewidths=0.2))
    mins, maxs = P.min(0), P.max(0); L = maxs - mins
    ax.set_xlim(mins[0],maxs[0]); ax.set_ylim(mins[1],maxs[1]); ax.set_zlim(mins[2],maxs[2])
    ax.set_box_aspect(tuple(L))
    ax.view_init(elev=10, azim=-80); ax.set_axis_off(); ax.set_title(title, fontsize=12)

# ---------- (1) plastic-strain sequence ----------
d = load("j2_rateindep_out.e", "vals_elem_var1eb1")
ext = exterior(d["conn"])
frames = [3, 9, 15, 20]
vmax = max(d["ef"][k].max() for k in frames)
norm = colors.Normalize(0.0, vmax); cmap = matplotlib.colormaps["inferno"]
fig = plt.figure(figsize=(16, 4.2))
for i, k in enumerate(frames):
    ax = fig.add_subplot(1, len(frames), i+1, projection="3d")
    frame(ax, warped(d, k), ext, d["ef"][k], norm, cmap, f"t = {d['t'][k]*1e6:.1f} µs")
sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap); sm.set_array([])
cb = fig.colorbar(sm, ax=fig.axes, fraction=0.012, pad=0.01); cb.set_label("effective plastic strain")
fig.suptitle("3D Taylor anvil impact (OFHC copper, 235.9 m/s) — NEML2 explicit, colored by plastic strain", fontsize=13, y=1.0)
out1 = os.path.join(OUT, "demo_mushroom_pstrain.png"); fig.savefig(out1, dpi=160, bbox_inches="tight"); print("wrote", out1)

# ---------- (2) final deformed r-z profile silhouette (Taylor mushroom) ----------
def surf_nodes(conn):
    s = set()
    for n, e in exterior(conn):
        s.update(n)
    return np.array(sorted(s))

def silhouette(dd, k, snodes, nb=22):
    Y = (dd["y"] + dd["dy"][k])[snodes]
    R = np.sqrt((dd["x"]+dd["dx"][k])**2 + (dd["z"]+dd["dz"][k])**2)[snodes]
    Y = Y - Y.min()                                   # mushroom end at axial 0
    edges = np.linspace(Y.min(), Y.max(), nb+1); idx = np.clip(np.digitize(Y, edges)-1, 0, nb-1)
    yc = 0.5*(edges[:-1]+edges[1:]); rmax = np.full(nb, np.nan)
    for b in range(nb):
        m = idx == b
        if m.any(): rmax[b] = R[m].max()
    keep = ~np.isnan(rmax); yc, rmax = yc[keep], rmax[keep]
    rs = np.convolve(np.r_[rmax[0], rmax, rmax[-1]], np.ones(3)/3, mode="valid")  # 3-pt smooth
    return yc*1e3, rs*1e3   # mm

fh = load("3d_slug_mesh_fullhard.e"); an = load("3d_slug_mesh_annealed_exodus.e")
sn = surf_nodes(fh["conn"])
R0 = np.sqrt(fh["x"]**2 + fh["z"]**2).max()*1e3; L0 = (fh["y"].max()-fh["y"].min())*1e3
kfh = fh["dy"].shape[0]-1; kan = an["dy"].shape[0]-1
yfh, rfh = silhouette(fh, kfh, sn); yan, ran = silhouette(an, kan, sn)
sh_fh = abs(fh["dy"][kfh].min())/(fh["y"].max()-fh["y"].min())*100
sh_an = abs(an["dy"][kan].min())/(an["y"].max()-an["y"].min())*100

fig2, ax = plt.subplots(figsize=(8, 5))
# undeformed reference (axial along x, radius along y), mushroom end at x=0
ax.add_patch(plt.Rectangle((0, -R0), L0, 2*R0, fill=False, ls="--", ec="0.5", lw=1.5, label="undeformed"))
ax.fill_between(yfh, -rfh, rfh, color="#d62728", alpha=0.30)
ax.plot(yfh, rfh, "-", color="#d62728", lw=2); ax.plot(yfh, -rfh, "-", color="#d62728", lw=2,
        label=f"full-hard ({sh_fh:.0f}% shortening)")
ax.plot(yan, ran, "-", color="#1f77b4", lw=2); ax.plot(yan, -ran, "-", color="#1f77b4", lw=2,
        label=f"annealed ({sh_an:.0f}% shortening)")
ax.set_xlabel("axial position from impact face (mm)"); ax.set_ylabel("radius (mm)")
ax.set_aspect("equal"); ax.grid(alpha=0.3); ax.legend(frameon=False, loc="upper right")
ax.set_title("Final deformed profile — 3D Taylor slug (OFHC copper, 235.9 m/s), NEML2 explicit")
out2 = os.path.join(OUT, "demo_mushroom_profile.png"); fig2.savefig(out2, dpi=160, bbox_inches="tight"); print("wrote", out2)
print(f"pstrain max={vmax:.3f}; undeformed L0={L0:.1f}mm R0={R0:.2f}mm; "
      f"fullhard shortening={sh_fh:.1f}% foot r={rfh.max():.2f}mm; annealed shortening={sh_an:.1f}% foot r={ran.max():.2f}mm")
