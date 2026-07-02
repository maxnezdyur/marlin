#!/usr/bin/env python
"""Core method figures for slides 7-9 (NEML2 nodal-force path, explicit dynamics).
(7) formulation equations, (8) force-assembly data flow, (9) state residency.
Wide 16:9-friendly PNGs for PowerPoint."""
import os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = "/Users/maxnezdyur/projects/exp-dyn/marlin/examples/impact/slide_assets"
os.makedirs(OUT, exist_ok=True)
BLUE, GREEN, RED, GREY, GOLD = "#1f77b4", "#2ca02c", "#d62728", "#555555", "#ff7f0e"

def box(ax, xy, w, h, text, fc="white", ec=BLUE, lw=2, fs=12, tc="black", bold=False):
    x, y = xy
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                fc=fc, ec=ec, lw=lw, mutation_aspect=0.6))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs, color=tc,
            fontweight="bold" if bold else "normal", linespacing=1.35)

def arrow(ax, a, b, color=GREY, lw=2.2, style="-|>"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=18,
                                 lw=lw, color=color, shrinkA=2, shrinkB=2))

# ---------------- (7) FORMULATION ----------------
fig, ax = plt.subplots(figsize=(12, 6)); ax.axis("off"); ax.set_xlim(0,1); ax.set_ylim(0,1)
ax.text(0.5, 0.95, "Explicit dynamics with NEML2 internal forces", ha="center", fontsize=16, fontweight="bold")
eqs = [
    (0.86, r"$\mathbf{M}\,\ddot{\mathbf{u}} \;=\; \mathbf{F}_{\mathrm{ext}} \;-\; \mathbf{R}_{\mathrm{int}}$",
     "semi-discrete momentum balance  (lumped, diagonal $\\mathbf{M}$)"),
    (0.62, r"$\mathbf{R}_{\mathrm{int}} \;=\; \bigcup_{e}\!\int_{\Omega_e}\! \nabla\phi : \sigma\,\,dV,"
           r"\qquad \sigma = \mathcal{N}_{\theta}(\varepsilon)$",
     "internal nodal force (weak form);   $\\mathcal{N}_\\theta$ = NEML2 constitutive model (AD, GPU-capable)"),
    (0.36, r"$\ddot{\mathbf{u}}^{\,n} = \mathbf{M}^{-1}\!\left(\mathbf{F}_{\mathrm{ext}}^{\,n}-\mathbf{R}_{\mathrm{int}}^{\,n}\right),"
           r"\quad \mathbf{u}^{\,n+1}=2\mathbf{u}^{\,n}-\mathbf{u}^{\,n-1}+\Delta t^2\,\ddot{\mathbf{u}}^{\,n}$",
     "central-difference update  (ExplicitMixedOrder);   $\\Delta t \\leq \\Delta t_{\\mathrm{crit}}$ (CFL)"),
]
for yy, eq, cap in eqs:
    ax.text(0.5, yy, eq, ha="center", va="center", fontsize=20)
    ax.text(0.5, yy-0.085, cap, ha="center", va="center", fontsize=11.5, color=GREY)
box(ax, (0.18, 0.04), 0.64, 0.10,
    "the entire $\\mathbf{R}_{\\mathrm{int}}$ assembly is ONE batched tensor evaluation in NEML2",
    fc="#fff4e6", ec=GOLD, lw=2, fs=13, bold=True)
fig.savefig(f"{OUT}/method_formulation.png", dpi=170, bbox_inches="tight"); print("wrote method_formulation.png")
plt.close(fig)

# ---------------- (8) FORCE-ASSEMBLY DATA FLOW ----------------
fig, ax = plt.subplots(figsize=(13, 6)); ax.axis("off"); ax.set_xlim(0,1); ax.set_ylim(0,1)
ax.text(0.5, 0.96, "Nodal-force assembly inside NEML2 (no per-step state transfer)",
        ha="center", fontsize=16, fontweight="bold")
y0, h = 0.55, 0.26
xs = [0.015, 0.215, 0.415, 0.645, 0.84]; w = [0.18, 0.18, 0.21, 0.175, 0.15]
labels = [
    ("MOOSE FE\n$\\mathbf{u},\\,\\boldsymbol{\\varepsilon}$\nat quad points", "white", BLUE, False),
    ("NEML2FEInterpolation\ngather $\\rightarrow$ batched\ntensor (all qp)", "white", BLUE, False),
    ("NEML2 forward()\n[libTorch · CPU/GPU]\n$\\boldsymbol{\\sigma}=\\mathcal{N}_\\theta(\\boldsymbol{\\varepsilon})$\n$\\mathbf{R}_{\\mathrm{int}}=\\int\\nabla\\phi:\\boldsymbol{\\sigma}$", "#e8f4ff", BLUE, True),
    ("NEML2StressDivergence\n$\\rightarrow$ PETSc residual\nadd_vector()", "white", BLUE, False),
    ("ExplicitMixedOrder\n$\\mathbf{a}=\\mathbf{M}^{-1}(\\mathbf{F}_{\\mathrm{ext}}\\!-\\!\\mathbf{R}_{\\mathrm{int}})$\nadvance $\\mathbf{u}$", "white", GREEN, False),
]
for x, ww, (lab, fc, ec, bold) in zip(xs, w, labels):
    box(ax, (x, y0), ww, h, lab, fc=fc, ec=ec, lw=2.4 if bold else 2, fs=11, bold=bold)
for i in range(4):
    arrow(ax, (xs[i]+w[i], y0+h/2), (xs[i+1], y0+h/2))
# loop-back arrow (next step)
arrow(ax, (xs[4]+w[4]/2, y0), (xs[0]+w[0]/2, y0), color=GREEN, lw=2, style="-|>")
ax.text(0.5, 0.30, "next explicit step  ($\\Delta t = 10\\,$ns)", ha="center", fontsize=11, color=GREEN, style="italic")
# state-residency callout under core box
box(ax, (0.30, 0.06), 0.45, 0.13,
    "constitutive state $(\\mathbf{E}^p,\\,\\varepsilon^p)$ stays resident in NEML2 between steps\nno per-step host$\\leftrightarrow$device copy   [manage_state_advance]",
    fc="#eaffea", ec=GREEN, lw=2, fs=11.5, bold=True)
arrow(ax, (0.52, 0.19), (0.52, y0), color=GREEN, lw=1.8, style="-|>")
fig.savefig(f"{OUT}/method_forcepath.png", dpi=170, bbox_inches="tight"); print("wrote method_forcepath.png")
plt.close(fig)

# ---------------- (9) STATE RESIDENCY (the efficiency lever) ----------------
fig, ax = plt.subplots(figsize=(12, 6)); ax.axis("off"); ax.set_xlim(0,1); ax.set_ylim(0,1)
ax.text(0.5, 0.96, "Why it is fast: constitutive state stays on the device",
        ha="center", fontsize=16, fontweight="bold")
# conventional row
ax.text(0.5, 0.85, "Conventional pointwise material loop", ha="center", fontsize=13, color=RED, fontweight="bold")
cy, ch = 0.60, 0.16
box(ax, (0.04, cy), 0.18, ch, "host state\n$(\\mathbf{E}^p,\\varepsilon^p)$", fc="white", ec=RED)
box(ax, (0.41, cy), 0.18, ch, "device:\nevaluate $\\boldsymbol{\\sigma}$", fc="#ffecec", ec=RED)
box(ax, (0.78, cy), 0.18, ch, "host state\n(updated)", fc="white", ec=RED)
arrow(ax, (0.22, cy+ch/2), (0.41, cy+ch/2), color=RED); arrow(ax, (0.59, cy+ch/2), (0.78, cy+ch/2), color=RED)
ax.text(0.315, cy+ch/2+0.055, "copy in", ha="center", fontsize=10, color=RED)
ax.text(0.685, cy+ch/2+0.055, "copy out", ha="center", fontsize=10, color=RED)
ax.text(0.5, cy-0.06, "host$\\leftrightarrow$device transfer EVERY step  $\\Rightarrow$ bottleneck for expensive models",
        ha="center", fontsize=11.5, color=RED, style="italic")
# this-work row
ax.text(0.5, 0.36, "This work: state resident in NEML2", ha="center", fontsize=13, color=GREEN, fontweight="bold")
ty, th = 0.12, 0.16
box(ax, (0.30, ty), 0.40, th, "NEML2 device-resident state\n$(\\mathbf{E}^p,\\varepsilon^p)$ persists across steps", fc="#eaffea", ec=GREEN, lw=2.4, bold=True)
ax.add_patch(FancyArrowPatch((0.30, ty+th/2), (0.16, ty+th/2), arrowstyle="<|-", mutation_scale=16, lw=2, color=GREEN))
ax.add_patch(FancyArrowPatch((0.70, ty+th/2), (0.84, ty+th/2), arrowstyle="-|>", mutation_scale=16, lw=2, color=GREEN))
ax.text(0.15, ty+th/2+0.055, "$\\boldsymbol{\\varepsilon}$ in", ha="center", fontsize=10, color=GREEN)
ax.text(0.85, ty+th/2+0.055, "$\\mathbf{R}_{\\mathrm{int}}$ out", ha="center", fontsize=10, color=GREEN)
ax.text(0.5, ty-0.06, "only strain in / nodal force out  $\\Rightarrow$  per-step transfer eliminated",
        ha="center", fontsize=11.5, color=GREEN, style="italic")
fig.savefig(f"{OUT}/method_state_residency.png", dpi=170, bbox_inches="tight"); print("wrote method_state_residency.png")
plt.close(fig)
print("done")
