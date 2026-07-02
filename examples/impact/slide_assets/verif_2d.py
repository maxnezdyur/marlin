#!/usr/bin/env python
"""2D matched-constitutive verification: NEML2 nodal-force path vs MOOSE radial-return J2.
gold/slug_2d.e = MOOSE J2 reference; slug_2d.e = NEML2 result. Same mesh, single final step.
This isolates the force-assembly implementation (identical J2 physics through both paths)."""
import os, numpy as np
from scipy.io import netcdf_file
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

T = "/Users/maxnezdyur/projects/exp-dyn/marlin/test/tests/impact"
OUT = "/Users/maxnezdyur/projects/exp-dyn/marlin/examples/impact/slide_assets"
os.makedirs(OUT, exist_ok=True)

def load(fn):
    nc = netcdf_file(fn, "r", mmap=False); g = lambda n: nc.variables[n].data.copy()
    d = dict(x=g("coordx"), y=g("coordy"), dx=g("vals_nod_var1"), dy=g("vals_nod_var2"),
             fx=g("vals_nod_var3"), fy=g("vals_nod_var4")); nc.close(); return d

M = load(os.path.join(T, "gold/slug_2d.e"))   # MOOSE radial-return J2 (reference)
E = load(os.path.join(T, "slug_2d.e"))         # NEML2 (current output)
assert np.allclose(M["x"], E["x"]) and np.allclose(M["y"], E["y"]), "mesh mismatch"

# exodiff-style relative error: |a-b| / max(|a|,|b|, floor)
def rel_err(a, b, floor=1e-5):
    a = a[-1]; b = b[-1]
    denom = np.maximum(np.maximum(np.abs(a), np.abs(b)), floor)
    return np.abs(a - b) / denom

re_fx = rel_err(M["fx"], E["fx"]); re_fy = rel_err(M["fy"], E["fy"])
re_dx = rel_err(M["dx"], E["dx"]); re_dy = rel_err(M["dy"], E["dy"])
maxforce = max(re_fx.max(), re_fy.max())

fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.6))
for a, key, lab in [(ax[0], "fy", "force$_y$ (N)"), (ax[1], "dy", "disp$_y$ (m)")]:
    m = M[key][-1]; e = E[key][-1]
    lim = [min(m.min(), e.min()), max(m.max(), e.max())]
    a.plot(lim, lim, "k-", lw=1, alpha=0.6, label="y = x")
    a.scatter(m, e, s=14, color="#1f77b4", alpha=0.6, edgecolors="none")
    a.set_xlabel(f"MOOSE J2  {lab}"); a.set_ylabel(f"NEML2  {lab}")
    a.grid(alpha=0.3); a.legend(frameon=False, loc="upper left")
ax[0].set_title(f"Internal nodal force\nmax relative diff = {maxforce:.2e}  (exodiff tol 5e-4)")
ax[1].set_title(f"Displacement\nmax relative diff = {re_dy.max():.2e}")
fig.suptitle("2D matched-constitutive verification: NEML2 nodal-force path reproduces MOOSE radial-return J2",
             fontsize=12, y=1.02)
fig.tight_layout()
out = os.path.join(OUT, "verification_2d_matched.png")
fig.savefig(out, dpi=160, bbox_inches="tight"); print("wrote", out)
print(f"max relative force diff = {maxforce:.3e}  (force_x {re_fx.max():.2e}, force_y {re_fy.max():.2e})")
print(f"max relative disp  diff = {max(re_dx.max(), re_dy.max()):.3e}")
print(f"force_y range MOOSE [{M['fy'][-1].min():.3e}, {M['fy'][-1].max():.3e}]")
