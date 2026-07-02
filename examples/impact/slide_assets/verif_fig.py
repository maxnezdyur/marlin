#!/usr/bin/env python
"""Verification figure: NEML2-explicit vs MOOSE-native-J2-explicit Taylor slug.
Reads cmp_j2.e (MOOSE J2) and cmp_inv.e (NEML2 inverted Johnson-Cook) which share
an identical 1157-node mesh and 9 timesteps. Pure scipy/numpy/matplotlib."""
import os
import numpy as np
from scipy.io import netcdf_file
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

IMP = "/Users/maxnezdyur/projects/exp-dyn/marlin/examples/impact"
OUT = os.path.join(IMP, "slide_assets")
os.makedirs(OUT, exist_ok=True)

def load(fn):
    nc = netcdf_file(os.path.join(IMP, fn), "r", mmap=False)
    g = lambda n: nc.variables[n].data.copy()
    d = dict(x=g("coordx"), y=g("coordy"), z=g("coordz"), t=g("time_whole"),
             dx=g("vals_nod_var1"), dy=g("vals_nod_var2"), dz=g("vals_nod_var3"),
             fx=g("vals_nod_var4"), fy=g("vals_nod_var5"), fz=g("vals_nod_var6"))
    nc.close()
    return d

J = load("cmp_j2.e")          # MOOSE native J2 (explicit)
N = load("cmp_inv.e")         # NEML2 inverted Johnson-Cook (explicit)

# identical mesh check
assert np.allclose(J["x"], N["x"]) and np.allclose(J["y"], N["y"]) and np.allclose(J["z"], N["z"]), "mesh mismatch"
t_us = J["t"] * 1e6           # microseconds
nt = J["dy"].shape[0]

# --- relative L2 displacement error vs time (all nodes, all components) ---
relL2 = np.zeros(nt)
for k in range(nt):
    uj = np.concatenate([J["dx"][k], J["dy"][k], J["dz"][k]])
    un = np.concatenate([N["dx"][k], N["dy"][k], N["dz"][k]])
    den = np.linalg.norm(uj)
    relL2[k] = np.linalg.norm(un - uj) / den if den > 0 else 0.0
peak_rel = relL2.max() * 100.0

# --- axial shortening history: most-negative disp_y over nodes (mm) ---
dymin_j = J["dy"].min(axis=1) * 1e3
dymin_n = N["dy"].min(axis=1) * 1e3

# --- node-wise correlation at final step (mm) ---
uj_final = J["dy"][-1] * 1e3
un_final = N["dy"][-1] * 1e3
# slope through origin + R^2
slope = np.dot(uj_final, un_final) / np.dot(uj_final, uj_final)
ss_res = np.sum((un_final - slope * uj_final) ** 2)
ss_tot = np.sum((un_final - un_final.mean()) ** 2)
r2 = 1.0 - ss_res / ss_tot

fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))

# Panel A: axial shortening history
ax[0].plot(t_us, dymin_j, "o-", color="#1f77b4", lw=2, ms=5, label="MOOSE native J2")
ax[0].plot(t_us, dymin_n, "s--", color="#ff7f0e", lw=2, ms=5, label="NEML2 Johnson-Cook")
ax[0].set_xlabel("time (µs)")
ax[0].set_ylabel("peak axial displacement (mm)")
ax[0].set_title("Axial shortening history")
ax[0].legend(frameon=False)
ax[0].grid(alpha=0.3)

# Panel B: node-wise correlation
lim = [min(uj_final.min(), un_final.min()), max(uj_final.max(), un_final.max())]
ax[1].plot(lim, lim, "k-", lw=1, alpha=0.6, label="y = x")
ax[1].scatter(uj_final, un_final, s=8, color="#2ca02c", alpha=0.5, edgecolors="none")
ax[1].set_xlabel("MOOSE J2  disp$_y$ (mm)")
ax[1].set_ylabel("NEML2  disp$_y$ (mm)")
ax[1].set_title(f"Node-wise agreement, final step\nslope={slope:.4f}, $R^2$={r2:.5f}")
ax[1].legend(frameon=False, loc="upper left")
ax[1].grid(alpha=0.3)

# Panel C: relative L2 error vs time
ax[2].plot(t_us, relL2 * 100.0, "d-", color="#d62728", lw=2, ms=5)
ax[2].set_xlabel("time (µs)")
ax[2].set_ylabel("relative L2 displacement error (%)")
ax[2].set_title(f"Solution difference\npeak = {peak_rel:.2f}%")
ax[2].grid(alpha=0.3)
ax[2].set_ylim(bottom=0)

fig.suptitle("Verification: NEML2 explicit nodal-force path vs MOOSE native J2 (same mesh, same explicit integrator, same $\\Delta t$)",
             fontsize=12, y=1.02)
fig.tight_layout()
out = os.path.join(OUT, "verification.png")
fig.savefig(out, dpi=160, bbox_inches="tight")
print("wrote", out)
print(f"peak relative L2 disp error = {peak_rel:.3f} %")
print(f"final-step node-wise: slope={slope:.5f}  R^2={r2:.6f}")
print(f"final axial shortening: MOOSE={dymin_j[-1]:.4f} mm  NEML2={dymin_n[-1]:.4f} mm  "
      f"(diff {abs(dymin_j[-1]-dymin_n[-1])/abs(dymin_j[-1])*100:.2f} %)")
