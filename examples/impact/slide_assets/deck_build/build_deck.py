"""Build the WCCM method-section deck (problem -> equations -> NEML2/MOOSE -> what we did).

Usage:  python3 build_deck.py [out.pptx]

Content facts verified against the moose submodule (see slide notes in this file's
comments): ExplicitMixedOrder update forms from ExplicitMixedOrder.C/.md, force-path
classes from framework/src/neml2/* and modules/solid_mechanics/src/neml2/*.
"""

import sys
from pathlib import Path

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from deckkit import (BLUE, BLUE_T, BODY, CARD, CARD_LN, FAINT, GOLD, GOLD_T,
                     GREEN, GREEN_T, INK, MARGIN, MUTED, PAGE_H, PAGE_W, RED,
                     RED_T, SKY, WHITE, add_arrow, add_bullets, add_card,
                     add_eq, add_line, add_rect, add_text, inl_layout,
                     load_inl_base, new_slide, shape_text)

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "WCCM_NEML2_explicit_dynamics_v2.pptx"

prs = load_inl_base()
FIGS = HERE / "figs"


def fig_aspect(name):
    from PIL import Image
    with Image.open(FIGS / name) as im:
        return im.size[0] / im.size[1]


TOTAL = 22
BODY_TOP = Inches(1.32)
CONTENT_W = PAGE_W - 2 * MARGIN
MONO = "Consolas"


def takeaway(s, text_segs, y=Inches(5.88), fill=GOLD_T, line=GOLD):
    add_card(s, MARGIN, y, CONTENT_W, Inches(0.72), fill=fill, line=line, line_w=1.0)
    add_text(s, MARGIN + Inches(0.3), y, CONTENT_W - Inches(0.6), Inches(0.72),
             [text_segs], size=15, color=BODY, anchor=MSO_ANCHOR.MIDDLE)


def pow10(a, b=None):
    """runs for 10^a - 10^b with real superscripts"""
    segs = [("10", {"bold": True}), (str(a), {"bold": True, "sup": True})]
    if b is not None:
        segs += [("–10", {"bold": True}), (str(b), {"bold": True, "sup": True})]
    return segs


# ================================================================ 1 TITLE
def s01_title():
    s = prs.slides.add_slide(inl_layout(prs, "Title Slide Hex_01"))
    for ph in s.placeholders:
        idx = ph.placeholder_format.idx
        if idx == 13:  # main title block
            tf = ph.text_frame
            tf.text = ("Accelerated Explicit Dynamics Simulations of Impact Problems "
                       "Using GPU-Enabled Material Models in MOOSE")
            sub = tf.add_paragraph()
            r = sub.add_run()
            r.text = "A NEML2 nodal-force interface for high-rate solid mechanics"
            r.font.size = Pt(18)
            r.font.bold = False
            r.font.color.rgb = SKY
        elif idx == 16:  # top-left presenter block
            ph.width = Inches(4.2)
            tf = ph.text_frame
            tf.text = "WCCM 2026"
            p2 = tf.add_paragraph()
            p2.text = "Author Name & Co-authors"
            p3 = tf.add_paragraph()
            p3.text = "Idaho National Laboratory"


# ================================================================ 2 MOTIVATION
def s02_motivation():
    s = new_slide(prs, "Motivation", "Advanced reactors bring dynamic-loading questions",
                  number=2, total=TOTAL)
    left_w = Inches(6.9)
    add_bullets(s, MARGIN, BODY_TOP + Inches(0.38), left_w, Inches(4.2), [
        [("Transportable microreactors, pebble-bed cores, accident scenarios: components must be qualified under ", {}),
         ("impact and other high-rate loads", {"bold": True})],
        [("These events are ", {}),
         ("wave-dominated and fast", {"bold": True}),
         (". Stress waves traverse the part in microseconds, with severe, localized plasticity", {})],
        [("Predictive fidelity requires ", {}),
         ("modern constitutive models", {"bold": True}),
         (". Rate- and temperature-dependent, with evolving internal state", {})],
        [("Simulating them means ", {}),
         ("explicit time integration", {"bold": True}),
         (" with a material-model evaluation at every quadrature point, every step", {})],
    ], size=16.5, gap=18)
    # right panel: timescale ladder
    px = MARGIN + left_w + Inches(0.5)
    pw = CONTENT_W - left_w - Inches(0.5)
    py, ph = BODY_TOP, Inches(4.35)
    add_card(s, px, py, pw, ph)
    add_text(s, px + Inches(0.28), py + Inches(0.22), pw - Inches(0.56), Inches(0.3),
             "TIMESCALES OF AN IMPACT EVENT", size=10.5, color=MUTED, bold=True)
    rows = [
        ("event duration", [("~100 µs", {"bold": True, "color": BLUE})]),
        ("wave transit through part", [("~1–10 µs", {"bold": True, "color": BLUE})]),
        ("stable explicit step", [("~10 ns", {"bold": True, "color": RED})]),
        ("⇒  steps to simulate", [(seg[0], {**seg[1], "color": INK}) for seg in pow10(4, 5)]),
    ]
    ry = py + Inches(0.72)
    for label, val_segs in rows:
        add_card(s, px + Inches(0.28), ry, pw - Inches(0.56), Inches(0.72),
                 fill=WHITE, line=CARD_LN, line_w=0.75)
        add_text(s, px + Inches(0.52), ry, pw - Inches(2.1), Inches(0.72),
                 label, size=12.5, color=BODY, anchor=MSO_ANCHOR.MIDDLE)
        add_text(s, px + pw - Inches(1.95), ry, Inches(1.55), Inches(0.72),
                 [val_segs], size=15, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
        ry += Inches(0.87)
    takeaway(s, [("Many steps × expensive material updates:", {"bold": True, "color": INK}),
                 (" high-rate simulation is compute-hungry in a very particular way.", {})])


# ================================================================ 3 THE GAP
def s03_gap():
    s = new_slide(prs, "Motivation", "Two mature ecosystems and a gap between them",
                  number=3, total=TOTAL)
    gap_w = Inches(1.5)
    col_w = (CONTENT_W - gap_w) / 2
    ch = Inches(3.0)
    # left card: FE frameworks
    add_card(s, MARGIN, BODY_TOP, col_w, ch, fill=BLUE_T, line=BLUE, line_w=1.0)
    add_text(s, MARGIN + Inches(0.3), BODY_TOP + Inches(0.22), col_w - Inches(0.6), Inches(0.35),
             "MULTIPHYSICS FE FRAMEWORKS (MOOSE)", size=11.5, color=BLUE, bold=True)
    add_bullets(s, MARGIN + Inches(0.32), BODY_TOP + Inches(0.75), col_w - Inches(0.64), ch - Inches(0.95), [
        "Boundary conditions, contact, parallel domain decomposition",
        "Coupled-physics machinery, in-situ output, meshing, restart",
        [("But: materials evaluated ", {}),
         ("point-by-point on CPU", {"bold": True}),
         (" inside the element loop", {})],
    ], size=14, gap=9, bullet_color=BLUE)
    # right card: material libraries
    rx = MARGIN + col_w + gap_w
    add_card(s, rx, BODY_TOP, col_w, ch, fill=GREEN_T, line=GREEN, line_w=1.0)
    add_text(s, rx + Inches(0.3), BODY_TOP + Inches(0.22), col_w - Inches(0.6), Inches(0.35),
             "MODERN MATERIAL LIBRARIES (NEML2)", size=11.5, color=GREEN, bold=True)
    add_bullets(s, rx + Inches(0.32), BODY_TOP + Inches(0.75), col_w - Inches(0.64), ch - Inches(0.95), [
        "Composable constitutive models with automatic differentiation",
        [("Batched tensor evaluation on ", {}),
         ("GPU or CPU", {"bold": True}),
         (" (libTorch backend)", {})],
        [("But: no mesh, no boundary conditions, no solver. ", {}),
         ("Not a simulation code", {"bold": True})],
    ], size=14, gap=9, bullet_color=GREEN)
    # the gap between
    gx = MARGIN + col_w
    add_text(s, gx, BODY_TOP + Inches(0.9), gap_w, Inches(0.5),
             "?", size=32, color=RED, bold=True, align=PP_ALIGN.CENTER)
    add_text(s, gx + Inches(0.02), BODY_TOP + Inches(1.52), gap_w - Inches(0.04), Inches(1.0),
             ["per-point calls,", "per-step copies"], size=12.5, color=RED,
             align=PP_ALIGN.CENTER, italic=True, leading=1.15)
    # this-talk band
    ty = BODY_TOP + ch + Inches(0.55)
    add_card(s, MARGIN, ty, CONTENT_W, Inches(1.0), fill=BLUE_T, line=BLUE, line_w=1.0)
    add_text(s, MARGIN + Inches(0.3), ty, CONTENT_W - Inches(0.6), Inches(1.0),
             [[("This talk: ", {"bold": True, "color": BLUE}),
               ("an interface where NEML2 assembles the nodal internal forces itself, batched and device-resident, while MOOSE keeps doing everything else.", {"color": INK})]],
             size=16, anchor=MSO_ANCHOR.MIDDLE)


# ================================================================ 4 EQUATIONS I
def s04_governing():
    s = new_slide(prs, "Formulation 1/5", "Governing equations of explicit solid dynamics",
                  number=4, total=TOTAL)
    lx = MARGIN + Inches(0.1)
    label_x = MARGIN + Inches(7.9)
    label_w = CONTENT_W - Inches(7.9)
    rows = [
        (r"$\rho_0\,\ddot{\mathbf{u}} \;=\; \nabla_{\!0}\!\cdot\!\mathbf{P} + \rho_0\,\mathbf{b} \quad \text{in } \Omega_0$",
         "balance of linear momentum on the reference domain", 1.85, "momentum_strong_form_tl"),
        (r"$\int_{\Omega_0}\rho_0\,\mathbf{w}\!\cdot\!\ddot{\mathbf{u}}\;dV \;+\; \int_{\Omega_0}\nabla_{\!0}\mathbf{w}:\mathbf{P}\;dV \;=\; \int_{\Gamma_{0,t}}\mathbf{w}\!\cdot\!\bar{\mathbf{t}}_0\;dA \;+\; \int_{\Omega_0}\rho_0\,\mathbf{w}\!\cdot\!\mathbf{b}\;dV$",
         "total-Lagrangian weak form. Every integral is on the reference configuration", 1.85, "weak_form_tl"),
        (r"$\mathbf{M}\,\ddot{\mathbf{u}} \;=\; \mathbf{F}^{\mathrm{ext}} \;-\; \mathbf{F}^{\mathrm{int}}(\mathbf{P})$",
         "discretize in space: semi-discrete momentum equation", 1.85, "semi_discrete_momentum_tl"),
        (r"$\mathbf{F}^{\mathrm{int}} \;=\; \mathop{\mathrm{A}}_{e}\int_{\Omega_{0,e}}\mathbf{B}^{\!\top}\mathbf{P}\;dV, \qquad \mathbf{P} = \text{constitutive model}(\mathbf{F},\ \text{state})$",
         "internal force from the first Piola–Kirchhoff stress at each quadrature point", 1.85, "internal_force_assembly_tl"),
    ]
    y = BODY_TOP + Inches(0.2)
    for latex, caption, scale, eqname in rows:
        add_eq(s, latex, lx, y, scale=scale, name=eqname)
        add_text(s, label_x, y - Inches(0.04), label_w, Inches(0.7),
                 caption, size=12.5, color=BODY, italic=True)
        y += Inches(1.08)
    takeaway(s, [("Reference-domain integrals: ", {"bold": True, "color": INK}),
                 ("shape functions, weights, and dof maps never change during the run. All material physics enters through the stress ", {}),
                 ("P", {"bold": True, "color": INK}),
                 (" at the quadrature points.", {})])


# ================================================================ 5 CONSTITUTIVE: KINEMATICS
def s05_kinematics():
    s = new_slide(prs, "Formulation 2/5", "The material model I: finite-strain kinematics",
                  number=5, total=TOTAL)
    lx = MARGIN + Inches(0.1)
    label_x = MARGIN + Inches(7.55)
    label_w = CONTENT_W - Inches(7.55)
    rows = [
        (r"$\mathbf{F} \;=\; \mathbf{F}^{e}\,\mathbf{F}^{p}$",
         "multiplicative split: Fᵖ carries the crush, elastic strain stays small", "mult_split"),
        (r"$\mathbf{F}^{e}_{\mathrm{tr}} = \mathbf{F}\,(\mathbf{F}^{p}_{n})^{-1}, \qquad \mathbf{E}^{e}_{\mathrm{tr}} = \tfrac{1}{2}\big(\mathbf{F}^{e\top}_{\mathrm{tr}}\mathbf{F}^{e}_{\mathrm{tr}} - \mathbf{I}\big)$",
         "trial state: plastic flow frozen at the old Fᵖ", "trial_state_kin"),
        (r"$\mathbf{S} = \mathbb{C} : \big(\mathbf{E}^{e}_{\mathrm{tr}} - \Delta\varepsilon^{p}\,\mathbf{N}\big), \qquad \mathbf{N} = \tfrac{3}{2}\,\mathrm{dev}\,\mathbf{S}_{\mathrm{tr}}\,/\,\sigma_{\mathrm{vm,tr}}$",
         "radial return on the trial elastic strain, one scalar unknown", "radial_return_kin"),
        (r"$\mathbf{F}^{p}_{n+1} \;=\; \big(\mathbf{I} + \Delta\varepsilon^{p}\,\mathbf{N}\big)\,\mathbf{F}^{p}_{n}$",
         "linearized exponential-map plastic update", "fp_update"),
        (r"$\mathbf{P} \;=\; \mathbf{F}\;\big(\mathbf{F}^{p-1}\,\mathbf{S}\,\mathbf{F}^{p-\top}\big)$",
         "pull-back to the reference configuration, giving the PK1 stress of the weak form", "pk1_pullback"),
    ]
    y = BODY_TOP + Inches(0.08)
    for latex, caption, eqname in rows:
        add_eq(s, latex, lx, y, scale=1.85, name=eqname)
        add_text(s, label_x, y - Inches(0.02), label_w, Inches(0.7),
                 caption, size=11.5, color=BODY, italic=True)
        y += Inches(0.88)
# ================================================================ 6 CONSTITUTIVE: JC FLOW
def s06_jc():
    s = new_slide(prs, "Formulation 3/5", "The material model II: Johnson–Cook flow and adiabatic heating",
                  number=6, total=TOTAL)
    lw = Inches(8.0)
    rows = [
        (r"$\sigma_y \;=\; \big(A + B\,(\varepsilon^{p} + \varepsilon^{p}_{0})^{\,n}\big)\,\big(1 - T^{*m}\big), \qquad T^{*} = \tfrac{T - T_{\mathrm{ref}}}{T_{\mathrm{melt}} - T_{\mathrm{ref}}}$",
         "flow stress: strain hardening × thermal softening; prior cold work ε₀ᵖ sets the temper", "jc_flow_stress"),
        (r"$\dot{\varepsilon}^{p} \;=\; \dot{\varepsilon}_0\, \exp\!\Big[\tfrac{1}{C}\Big(\tfrac{\sigma_{\mathrm{vm}}}{\sigma_y} - 1\Big)\Big] \quad (\sigma_{\mathrm{vm}} > \sigma_y)$",
         "rate form (inverted Johnson–Cook): smooth viscoplastic overstress law", "jc_rate_form"),
        (r"$\rho\, c_p\, \dot{T} \;=\; \beta\, \sigma_{\mathrm{vm}}\, \dot{\varepsilon}^{p}$",
         "adiabatic Taylor–Quinney heating, integrated inside the model (β = 0.9)", "adiabatic_heating"),
    ]
    y = BODY_TOP + Inches(0.18)
    for latex, caption, eqname in rows:
        add_eq(s, latex, MARGIN + Inches(0.1), y, scale=1.85, name=eqname)
        add_text(s, MARGIN + Inches(0.14), y + Inches(0.62), lw, Inches(0.32),
                 caption, size=11.5, color=MUTED, italic=True)
        y += Inches(1.32)
    # right: parameter card
    px = MARGIN + lw + Inches(0.45)
    pw = CONTENT_W - lw - Inches(0.45)
    add_card(s, px, BODY_TOP, pw, Inches(4.35), fill=WHITE, line=CARD_LN, line_w=1.0)
    add_text(s, px + Inches(0.24), BODY_TOP + Inches(0.16), pw - Inches(0.48), Inches(0.3),
             "OFHC COPPER (CuH04 SHOT)", size=10.5, color=MUTED, bold=True)
    prm = [
        ("E, ν", "117 GPa, 0.34", False),
        ("ρ, cₚ", "8960 kg/m³, 385 J/kg·K", False),
        ("β, m", "0.9, 0.98", False),
        ("A", "104 MPa", True),
        ("B", "329 MPa", True),
        ("n", "0.43", True),
        ("C", "0.025", True),
        ("ε₀ᵖ", "0.12  (H04 temper)", True),
    ]
    ry = BODY_TOP + Inches(0.52)
    for k, v, cal in prm:
        add_text(s, px + Inches(0.26), ry, Inches(1.15), Inches(0.3),
                 k, size=12, color=INK, bold=True)
        add_text(s, px + Inches(1.45), ry, pw - Inches(1.7), Inches(0.3),
                 [[(v, {"color": GREEN if cal else BODY, "bold": cal})]], size=12)
        ry += Inches(0.4)
    add_text(s, px + Inches(0.26), ry + Inches(0.04), pw - Inches(0.5), Inches(0.55),
             [[("green = Bayesian-calibrated against two recovered specimens (later in this talk)",
                {"color": GREEN, "italic": True})]], size=10.5, leading=1.1)
    takeaway(s, [("Internal state (εᵖ, Fᵖ, T) advances inside the model every step.", {"bold": True, "color": INK})])


# ================================================================ 7 EQUATIONS II
def s05_integration():
    s = new_slide(prs, "Formulation 4/5", "Explicit time integration: ExplicitMixedOrder",
                  number=7, total=TOTAL)
    lw = Inches(7.3)
    add_text(s, MARGIN, BODY_TOP, lw, Inches(0.3),
             [[("Central difference, as implemented in our ", {}),
               ("ExplicitMixedOrder", {"bold": True, "font": MONO, "size": 13.5}),
               (" MOOSE integrator", {})]], size=14, color=BODY)
    eqs = [
        (r"$\mathbf{a}_n \;=\; \mathbf{M}_L^{-1}\big(\mathbf{F}^{\mathrm{ext}}_n - \mathbf{F}^{\mathrm{int}}_n\big)$",
         "pointwise divide, no solver", "accel_lumped_mass"),
        (r"$\mathbf{v}_{n+\frac{1}{2}} \;=\; \mathbf{v}_{n-\frac{1}{2}} \;+\; \tfrac{\Delta t_n + \Delta t_{n-1}}{2}\;\mathbf{a}_n$",
         "variable-Δt midpoint velocity update", "velocity_midpoint_update"),
        (r"$\mathbf{u}_{n+1} \;=\; \mathbf{u}_n \;+\; \Delta t_n\,\mathbf{v}_{n+\frac{1}{2}}$",
         "displacement update", "displacement_update"),
    ]
    y = BODY_TOP + Inches(0.52)
    for latex, caption, eqname in eqs:
        add_eq(s, latex, MARGIN + Inches(0.1), y, scale=1.8, name=eqname)
        add_text(s, MARGIN + Inches(4.75), y + Inches(0.08), lw - Inches(4.8), Inches(0.6),
                 caption, size=11.5, color=MUTED, italic=True)
        y += Inches(1.02)
    add_text(s, MARGIN, y + Inches(0.12), lw, Inches(0.6),
             [[("No Newton iterations, no global linear solve, no Jacobian. ", {}),
               ("Each step is one residual evaluation plus vector updates.", {"bold": True, "color": INK})]],
             size=14, color=BODY)
    # right: mixed order card
    px = MARGIN + lw + Inches(0.42)
    pw = CONTENT_W - lw - Inches(0.42)
    ph = Inches(3.62)
    add_card(s, px, BODY_TOP, pw, ph, fill=BLUE_T, line=BLUE, line_w=1.0)
    add_text(s, px + Inches(0.26), BODY_TOP + Inches(0.2), pw - Inches(0.52), Inches(0.35),
             "MIXED ORDER", size=11, color=BLUE, bold=True)
    add_bullets(s, px + Inches(0.28), BODY_TOP + Inches(0.62), pw - Inches(0.56), Inches(1.7), [
        [("Displacements: ", {"bold": True}),
         ("central difference", {})],
        [("First-order fields (temperature): ", {"bold": True}),
         ("forward Euler on the rate", {})],
    ], size=13, gap=10, bullet_color=BLUE)
    add_line(s, px + Inches(0.26), BODY_TOP + Inches(2.12), px + pw - Inches(0.26),
             BODY_TOP + Inches(2.12), color=BLUE, weight=0.5)
    add_text(s, px + Inches(0.28), BODY_TOP + Inches(2.32), pw - Inches(0.56), Inches(1.1),
             [[("Both advance in the same update loop.", {})]],
             size=13, color=BODY, leading=1.08)
    takeaway(s, [("Developed for this work and upstreamed:", {"bold": True, "color": INK}),
                 (" part of MOOSE solid mechanics today.", {})])


# ================================================================ 6 EQUATIONS III
def s06_stability_cost():
    s = new_slide(prs, "Formulation 5/5", "Stability sets the step; the material sets the cost",
                  number=8, total=TOTAL)
    lw = Inches(6.9)
    add_text(s, MARGIN, BODY_TOP, lw, Inches(0.3),
             "Conditional stability (CFL): the step must resolve the fastest stress wave",
             size=14, color=BODY)
    add_eq(s, r"$\Delta t \;\le\; \Delta t_{\mathrm{crit}} \;=\; \min\limits_{e}\, \dfrac{\ell_e}{c}, \qquad c = \sqrt{E/\rho}$",
           MARGIN + Inches(0.1), BODY_TOP + Inches(0.45), scale=1.85, name="cfl_critical_timestep")
    add_text(s, MARGIN + Inches(0.12), BODY_TOP + Inches(1.22), lw, Inches(0.3),
             "element length over elastic wave speed",
             size=11.5, color=MUTED, italic=True)
    add_bullets(s, MARGIN, BODY_TOP + Inches(1.85), lw, Inches(2.4), [
        [("Millimeter elements: ", {}),
         ("Δt ≈ 10 ns", {"bold": True}),
         ("  ⇒  ", {})] + pow10(4, 5) + [(" steps for a 100 µs event", {})],
        [("Each step needs no solve. The runtime ", {}),
         ("is", {"italic": True}),
         (" the residual, and the residual ", {}),
         ("is", {"italic": True}),
         (" the constitutive update at every quadrature point", {})],
        [("Advanced models (rate/temperature-dependent plasticity, internal state) make each of those updates expensive", {})],
    ], size=15, gap=13)
    # right: cost anatomy
    px = MARGIN + lw + Inches(0.5)
    pw = CONTENT_W - lw - Inches(0.5)
    py, ph = BODY_TOP, Inches(4.35)
    add_card(s, px, py, pw, ph)
    add_text(s, px + Inches(0.26), py + Inches(0.2), pw - Inches(0.52), Inches(0.3),
             "ANATOMY OF ONE EXPLICIT STEP", size=10.5, color=MUTED, bold=True)
    bar_x = px + Inches(0.3)
    y = py + Inches(0.62)
    segs = [("constitutive update", "dominant", RED, RED_T, 1.75),
            ("force assembly + scatter", "", BLUE, BLUE_T, 0.65),
            ("time advance, BCs, output", "", MUTED, WHITE, 0.45)]
    for name, tag, ln, fl, h_in in segs:
        h = Inches(h_in)
        add_rect(s, bar_x, y, Inches(0.5), h, fl, line=ln, line_w=1.0)
        add_text(s, bar_x + Inches(0.7), y + h / 2 - Inches(0.16), pw - Inches(1.3), Inches(0.36),
                 [[(name, {"bold": bool(tag)}),
                   (("   " + tag) if tag else "", {"color": RED, "size": 10.5, "italic": True})]],
                 size=12.5, color=INK if tag else BODY)
        y += h + Inches(0.12)
    add_text(s, px + Inches(0.3), y + Inches(0.12), pw - Inches(0.6), Inches(0.35),
             "schematic; plasticity dominates the step cost",
             size=10.5, color=MUTED, italic=True)
    takeaway(s, [("Explicit runtime  ≈  steps × material-update cost.", {"bold": True, "color": INK})])


# ================================================================ 7 MOOSE
def s07_moose():
    s = new_slide(prs, "Building blocks", "MOOSE: the multiphysics host",
                  number=9, total=TOTAL)
    add_text(s, MARGIN, BODY_TOP, CONTENT_W, Inches(0.35),
             [[("Open-source multiphysics FE framework (Idaho National Laboratory). ", {}),
               ("We keep all of this for free", {"bold": True, "color": INK})]],
             size=15.5, color=BODY)
    cards = [
        ("Boundary conditions", "full BC library, incl. the penalty and pressure BCs used in this work"),
        ("Contact", "mortar and node-face algorithms, architecture-compatible with this interface"),
        ("Parallel execution", "MPI domain decomposition, scalable assembly and solves"),
        ("Coupled physics", "heat conduction, neutronics, porous flow, ... in one input file"),
        ("Meshing & output", "mesh generators, adaptivity, in-situ Exodus/CSV output"),
        ("Ecosystem", "NQA-1 quality assurance; large application family (BISON, Grizzly, ...)"),
    ]
    cw = (CONTENT_W - Inches(0.8)) / 3
    chh = Inches(1.5)
    for i, (t, d) in enumerate(cards):
        cx = MARGIN + (i % 3) * (cw + Inches(0.4))
        cy = BODY_TOP + Inches(0.62) + (i // 3) * (chh + Inches(0.32))
        add_card(s, cx, cy, cw, chh)
        add_rect(s, cx, cy + Inches(0.12), Inches(0.055), chh - Inches(0.24), BLUE)
        add_text(s, cx + Inches(0.25), cy + Inches(0.16), cw - Inches(0.45), Inches(0.35),
                 t, size=14.5, color=INK, bold=True)
        add_text(s, cx + Inches(0.25), cy + Inches(0.58), cw - Inches(0.45), Inches(0.85),
                 d, size=12, color=BODY, leading=1.1)
    takeaway(s, [("Everything in a high-rate simulation that is ", {}),
                 ("not", {"italic": True}),
                 (" the material update already exists here, parallel and production-tested.", {})])


# ================================================================ 8 NEML2
def s08_neml2():
    s = new_slide(prs, "Building blocks", "NEML2: the material engine",
                  number=10, total=TOTAL)
    add_text(s, MARGIN, BODY_TOP, CONTENT_W, Inches(0.35),
             [[("New Engineering Material model Library v2 (ANL, open source). Constitutive models as ", {}),
               ("composable tensor programs", {"bold": True, "color": INK})]],
             size=15.5, color=BODY)
    # left: composition diagram
    lw = Inches(6.7)
    dy = BODY_TOP + Inches(0.62)
    add_card(s, MARGIN, dy, lw, Inches(2.05), fill=WHITE, line=CARD_LN)
    add_text(s, MARGIN + Inches(0.24), dy + Inches(0.14), lw, Inches(0.3),
             "A MODEL = SMALL OPERATORS, COMPOSED", size=10, color=MUTED, bold=True)
    ops = [["elasticity"], ["flow rule"], ["hardening"], ["rate", "sensitivity"], ["state", "update"]]
    ow = Inches(1.02)
    arrow_gap = Inches(0.26)
    ox = MARGIN + Inches(0.28)
    oy = dy + Inches(0.56)
    for i, op in enumerate(ops):
        c = add_card(s, ox, oy, ow, Inches(0.85), fill=GREEN_T, line=GREEN, line_w=1.0)
        shape_text(c, [[(line_, {})] for line_ in op], size=10.5, color=INK, leading=1.05)
        if i < len(ops) - 1:
            add_arrow(s, ox + ow + Inches(0.03), oy + Inches(0.425),
                      ox + ow + arrow_gap - Inches(0.03), oy + Inches(0.425),
                      color=GREEN, weight=1.5)
        ox += ow + arrow_gap
    add_text(s, MARGIN + Inches(0.24), oy + Inches(1.0), lw - Inches(0.5), Inches(0.35),
             "declared in an input file; exact derivatives by automatic differentiation",
             size=11, color=MUTED, italic=True)
    add_bullets(s, MARGIN, dy + Inches(2.35), lw, Inches(2.0), [
        [("Batched:", {"bold": True}),
         (" all quadrature points evaluated in ", {}),
         ("one batched call", {"bold": True})],
        [("Device-portable:", {"bold": True}),
         (" libTorch (PyTorch C++) backend runs the same model on CPU or GPU", {})],
        [("NEML2 library benchmark:", {"bold": True}),
         (" 42,500 s (NEML, CPU) → 68 s on one GPU", {})],
    ], size=14, gap=9, bullet_color=GREEN)
    # right: batching visual
    px = MARGIN + lw + Inches(0.5)
    pw = CONTENT_W - lw - Inches(0.5)
    add_card(s, px, dy, pw, Inches(3.4))
    add_text(s, px + Inches(0.26), dy + Inches(0.17), pw - Inches(0.52), Inches(0.3),
             "ONE CALL, ALL POINTS", size=10.5, color=MUTED, bold=True)
    gx = px + Inches(0.35)
    gy = dy + Inches(0.62)
    cell = Inches(0.34)
    for r_ in range(3):
        for c_ in range(8):
            add_rect(s, gx + c_ * (cell + Inches(0.06)), gy + r_ * (cell + Inches(0.06)),
                     cell, cell, GREEN_T, line=GREEN, line_w=0.5)
    add_text(s, gx, gy + Inches(1.35), pw - Inches(0.7), Inches(0.4),
             [[("σ = model(ε, state)", {"font": MONO, "size": 12, "color": INK}),
               ("   over the whole batch", {"size": 11, "color": MUTED})]],
             size=11, color=MUTED)
    add_text(s, gx, gy + Inches(1.85), pw - Inches(0.7), Inches(0.75),
             "GPUs want exactly this shape of work: wide, uniform, no per-point branching",
             size=11.5, color=BODY, italic=True, leading=1.1)
    takeaway(s, [("NEML2 evaluates material models as batched tensor programs.", {"bold": True, "color": INK}),
                 (" It has no mesh, boundary conditions, or assembly. MOOSE does.", {})])


# ================================================================ 9 WHAT WE DID
def s09_contribution():
    s = new_slide(prs, "This work", "What we built: two pillars, one force path",
                  number=11, total=TOTAL)
    col_gap = Inches(0.5)
    cw = (CONTENT_W - col_gap) / 2
    ch = Inches(2.9)
    for i, (num, title, color, tint, lines) in enumerate([
        ("1", "ExplicitMixedOrder integrator", BLUE, BLUE_T, [
            [("Explicit central-difference integrator with ", {}),
             ("mixed-order multiphysics", {"bold": True}),
             (" (2nd-order mechanics + 1st-order fields)", {})],
            [("Lumped mass via matrix tag. ", {}),
             ("Zero linear iterations per step", {"bold": True})],
            [("Variable step size (Abaqus-style midpoint velocity averaging)", {})],
            [("Upstreamed to MOOSE ", {}),
             ("solid_mechanics", {"font": MONO, "size": 12.5})],
        ]),
        ("2", "NEML2 nodal-force interface", GREEN, GREEN_T, [
            [("NEML2 computes ", {}),
             ("internal nodal forces", {"bold": True}),
             (" itself, not just stress, for the whole mesh in batched tensor ops", {})],
            [("Constitutive state lives on the device and ", {}),
             ("advances in place", {"bold": True}),
             (" between steps", {})],
            [("Plugs into the explicit solve as a residual contribution. MOOSE BCs, outputs, and MPI are unchanged", {})],
        ]),
    ]):
        cx = MARGIN + i * (cw + col_gap)
        add_card(s, cx, BODY_TOP, cw, ch, fill=tint, line=color, line_w=1.25)
        badge = add_card(s, cx + Inches(0.28), BODY_TOP + Inches(0.26), Inches(0.5), Inches(0.5),
                         fill=color, line=None)
        shape_text(badge, num, size=20, color=WHITE, bold=True)
        add_text(s, cx + Inches(0.95), BODY_TOP + Inches(0.3), cw - Inches(1.2), Inches(0.45),
                 title, size=17, color=INK, bold=True)
        add_bullets(s, cx + Inches(0.3), BODY_TOP + Inches(0.95), cw - Inches(0.6), ch - Inches(1.15),
                    lines, size=13, gap=9, bullet_color=color)
    # foundation bar
    fy = BODY_TOP + ch + Inches(0.3)
    add_card(s, MARGIN, fy, CONTENT_W, Inches(0.85), fill=CARD, line=CARD_LN)
    add_text(s, MARGIN + Inches(0.3), fy, CONTENT_W - Inches(0.6), Inches(0.85),
             [[("Foundation, unchanged:  ", {"bold": True, "color": MUTED, "size": 12}),
               ("MOOSE boundary conditions  ·  parallel domain decomposition  ·  meshing & output  ·  contact (architecture-compatible)", {"color": BODY})]],
             size=13.5, anchor=MSO_ANCHOR.MIDDLE)
    takeaway(s, [("All of it is open source in the MOOSE framework and solid-mechanics module; ", {}),
                 ("the NEML2 force path is verified against conventional MOOSE on CPU and CUDA.", {"bold": True, "color": INK})])


# ================================================================ 10 FORCE PATH
def s10_force_path():
    s = new_slide(prs, "This work", "One explicit step through the NEML2 force path",
                  number=12, total=TOTAL)
    # geometry
    top = BODY_TOP + Inches(0.62)
    stage_h = Inches(1.62)
    end_w = Inches(1.55)
    # device region
    dev_x = MARGIN + end_w + Inches(0.42)
    dev_w = CONTENT_W - 2 * (end_w + Inches(0.42))
    dev_y = top - Inches(0.44)
    dev_h = stage_h + Inches(1.56)
    add_card(s, dev_x, dev_y, dev_w, dev_h, fill=GREEN_T, line=GREEN, line_w=1.0)
    add_text(s, dev_x + Inches(0.2), dev_y + Inches(0.1), dev_w - Inches(0.4), Inches(0.28),
             "DEVICE (libTorch) · same code on CPU / CUDA", size=10.5, color=GREEN, bold=True)
    # endpoints (host)
    ey = top
    h1 = add_card(s, MARGIN, ey, end_w, stage_h, fill=WHITE, line=CARD_LN, line_w=1.0)
    shape_text(h1, [[("MOOSE", {"bold": True, "size": 12.5})],
                    [("solution vector", {"size": 10.5})],
                    [("(PETSc)", {"size": 10, "color": MUTED})],
                    [("one upload / step", {"size": 9.5, "color": BLUE, "italic": True})]],
               color=INK, leading=1.1)
    h2 = add_card(s, PAGE_W - MARGIN - end_w, ey, end_w, stage_h, fill=WHITE, line=CARD_LN, line_w=1.0)
    shape_text(h2, [[("residual →", {"size": 10.5, "color": MUTED})],
                    [("ExplicitMixed", {"bold": True, "size": 11.5})],
                    [("Order", {"bold": True, "size": 11.5})],
                    [("advance u", {"size": 10.5})],
                    [("one download / step", {"size": 9.5, "color": BLUE, "italic": True})]],
               color=INK, leading=1.1)
    # stages inside device
    stages = [
        ("NEML2FE", "Interpolation", "gather u, ∇u at", "all quad points"),
        ("NEML2Def", "Gradient", "F = I + ∂u/∂X", "whole batch"),
        ("NEML2Model", "Executor", "P = model(F, state)", "one batched call"),
        ("NEML2Stress", "Divergence", "Rᵉ = Σ ∇φ·P JxW", "all elements at once"),
    ]
    n = len(stages)
    sgap = Inches(0.42)
    sw = (dev_w - Inches(0.6) - (n - 1) * sgap) / n
    sx = dev_x + Inches(0.3)
    sy = top + Inches(0.02)
    for i, (n1, n2, d1, d2) in enumerate(stages):
        c = add_card(s, sx, sy, sw, stage_h - Inches(0.04), fill=WHITE, line=GREEN, line_w=1.25)
        shape_text(c, [[(n1, {"bold": True, "size": 11, "font": MONO})],
                       [(n2, {"bold": True, "size": 11, "font": MONO})],
                       [(d1, {"size": 10.5})],
                       [(d2, {"size": 10.5, "color": MUTED})]],
                   color=INK, leading=1.08)
        if i < n - 1:
            add_arrow(s, sx + sw + Inches(0.02), sy + (stage_h - Inches(0.04)) / 2,
                      sx + sw + sgap - Inches(0.02), sy + (stage_h - Inches(0.04)) / 2,
                      color=GREEN, weight=1.75)
        sx += sw + sgap
    # host<->device transfer arrows
    mid_y = ey + stage_h / 2
    add_arrow(s, MARGIN + end_w + Inches(0.02), mid_y, dev_x + Inches(0.3) - Inches(0.02), mid_y,
              color=INK, weight=1.75)
    add_arrow(s, dev_x + dev_w - Inches(0.28), mid_y, PAGE_W - MARGIN - end_w - Inches(0.02), mid_y,
              color=INK, weight=1.75)
    # loop back
    loop_y = dev_y + dev_h + Inches(0.34)
    add_line(s, PAGE_W - MARGIN - end_w / 2, ey + stage_h, PAGE_W - MARGIN - end_w / 2, loop_y, color=BLUE, weight=1.5)
    add_line(s, MARGIN + end_w / 2, loop_y, PAGE_W - MARGIN - end_w / 2, loop_y, color=BLUE, weight=1.5)
    add_arrow(s, MARGIN + end_w / 2, loop_y, MARGIN + end_w / 2, ey + stage_h + Inches(0.02),
              color=BLUE, weight=1.5)
    add_text(s, PAGE_W / 2 - Inches(1.6), loop_y + Inches(0.08), Inches(3.2), Inches(0.28),
             "next explicit step (Δt ≈ 10 ns)", size=10.5, color=BLUE, align=PP_ALIGN.CENTER, italic=True)
    # cached-context note
    ny = dev_y + dev_h - Inches(0.82)
    add_card(s, dev_x + Inches(0.3), ny, dev_w - Inches(0.6), Inches(0.64), fill=WHITE, line=GREEN, line_w=0.75)
    add_text(s, dev_x + Inches(0.5), ny, dev_w - Inches(1.0), Inches(0.64),
             [[("built once, cached on device:  ", {"bold": True, "size": 10.5, "color": GREEN}),
               ("shape functions φ, ∇φ,  DOF maps,  weights JxW. Rebuilt only on mesh change", {"size": 10.5})]],
             size=10.5, color=BODY, anchor=MSO_ANCHOR.MIDDLE)
    takeaway(s, [("The interior force computation never touches an element loop:", {"bold": True, "color": INK}),
                 (" a short sequence of batched tensor ops.", {})])


# ================================================================ 11 STATE RESIDENCY
def s11_state():
    s = new_slide(prs, "This work", "Constitutive state never leaves the device",
                  number=13, total=TOTAL)
    lane_label_w = Inches(1.15)
    half_h = Inches(1.92)
    gap = Inches(0.34)
    # ---- conventional half
    y1 = BODY_TOP + Inches(0.05)
    add_card(s, MARGIN, y1, CONTENT_W, half_h, fill=RED_T, line=RED, line_w=1.0)
    add_text(s, MARGIN + Inches(0.26), y1 + Inches(0.12), Inches(8), Inches(0.3),
             "CONVENTIONAL COUPLING · state round-trips through MOOSE every step",
             size=11, color=RED, bold=True)
    # lanes
    lane_x = MARGIN + Inches(0.3)
    lane_w = CONTENT_W - Inches(0.6)
    host_y1 = y1 + Inches(0.52)
    dev_y1 = y1 + Inches(1.28)
    for ly, lbl in ((host_y1, "HOST"), (dev_y1, "DEVICE")):
        add_text(s, lane_x, ly + Inches(0.05), lane_label_w, Inches(0.3), lbl,
                 size=9.5, color=MUTED, bold=True)
    bx = lane_x + lane_label_w + Inches(0.25)
    add_line(s, lane_x + lane_label_w, y1 + Inches(1.12), bx + Inches(7.15),
             y1 + Inches(1.12), color=RED, weight=0.75, dash="dash")
    b1 = add_card(s, bx, host_y1 - Inches(0.08), Inches(2.9), Inches(0.52), fill=WHITE, line=RED, line_w=0.75)
    shape_text(b1, "state in MOOSE material properties", size=10.5, color=INK)
    b2 = add_card(s, bx + Inches(4.6), host_y1 - Inches(0.08), Inches(2.6), Inches(0.52), fill=WHITE, line=RED, line_w=0.75)
    shape_text(b2, "age state:  old ← current", size=10.5, color=INK)
    b3 = add_card(s, bx + Inches(2.0), dev_y1 - Inches(0.08), Inches(3.4), Inches(0.52), fill=WHITE, line=RED, line_w=0.75)
    shape_text(b3, "batched stress + state update", size=10.5, color=INK)
    # arrows crossing the boundary
    add_arrow(s, bx + Inches(1.45), host_y1 + Inches(0.44), bx + Inches(2.6), dev_y1 - Inches(0.08),
              color=RED, weight=1.5)
    add_arrow(s, bx + Inches(5.1), dev_y1 - Inches(0.08), bx + Inches(5.6), host_y1 + Inches(0.44),
              color=RED, weight=1.5)
    add_text(s, bx + Inches(7.35), y1 + Inches(0.62), Inches(2.8), Inches(1.1),
             "state copied down and back up every step. Traffic scales with model complexity",
             size=10.5, color=RED, italic=True, leading=1.1)
    # ---- this-work half
    y2 = y1 + half_h + gap
    add_card(s, MARGIN, y2, CONTENT_W, half_h, fill=GREEN_T, line=GREEN, line_w=1.0)
    add_text(s, MARGIN + Inches(0.26), y2 + Inches(0.12), Inches(9.5), Inches(0.3),
             "THIS WORK · state advances in place on the device  (manage_state_advance)",
             size=11, color=GREEN, bold=True)
    host_y2 = y2 + Inches(0.52)
    dev_y2 = y2 + Inches(1.28)
    for ly, lbl in ((host_y2, "HOST"), (dev_y2, "DEVICE")):
        add_text(s, lane_x, ly + Inches(0.05), lane_label_w, Inches(0.3), lbl,
                 size=9.5, color=MUTED, bold=True)
    add_line(s, lane_x + lane_label_w, y2 + Inches(1.12), bx + Inches(7.15),
             y2 + Inches(1.12), color=GREEN, weight=0.75, dash="dash")
    g1 = add_card(s, bx, host_y2 - Inches(0.08), Inches(2.3), Inches(0.52), fill=WHITE, line=GREEN, line_w=0.75)
    shape_text(g1, "solution u", size=10.5, color=INK)
    g2 = add_card(s, bx + Inches(4.6), host_y2 - Inches(0.08), Inches(2.3), Inches(0.52), fill=WHITE, line=GREEN, line_w=0.75)
    shape_text(g2, "nodal forces F", size=10.5, color=INK)
    g3 = add_card(s, bx + Inches(1.7), dev_y2 - Inches(0.08), Inches(4.0), Inches(0.52), fill=WHITE, line=GREEN, line_w=1.0)
    shape_text(g3, [[("state (Eᵖ, εᵖ, T, ...) advances in place", {"bold": True, "size": 10.5})]], color=INK)
    add_arrow(s, bx + Inches(1.15), host_y2 + Inches(0.44), bx + Inches(2.2), dev_y2 - Inches(0.08),
              color=GREEN, weight=1.5)
    add_arrow(s, bx + Inches(5.2), dev_y2 - Inches(0.08), bx + Inches(5.75), host_y2 + Inches(0.44),
              color=GREEN, weight=1.5)
    add_text(s, bx + Inches(7.35), y2 + Inches(0.62), Inches(2.8), Inches(1.1),
             "per step: one solution upload, one force download. Independent of model complexity",
             size=10.5, color=GREEN, italic=True, leading=1.1)
    takeaway(s, [("State stays where it is computed.", {"bold": True, "color": INK}),
                 (" Transfer volume does not grow with model complexity.", {})])


# ================================================================ 14 SPEED
def s14_speed():
    s = new_slide(prs, "This work", "Speed against an implicit twin", number=14, total=TOTAL)
    add_text(s, MARGIN, BODY_TOP - Inches(0.05), CONTENT_W, Inches(0.7),
             [[("Same mesh, material, and timestep, serial, run to rebound. The implicit twin uses "
                "Newmark-beta with the exact NEML2 tangent and full integration with F-bar. The "
                "explicit path uses reduced integration with hourglass control.", {})]],
             size=14.5, color=BODY, leading=1.15)
    # two big speedup stats
    col_gap = Inches(0.5)
    cw = (CONTENT_W - col_gap) / 2
    sy = BODY_TOP + Inches(0.85)
    sh_ = Inches(2.0)
    stats = [("9.5×", "faster in 2D", BLUE),
             ("25×", "faster in 3D", GREEN)]
    for i, (val, lab, c) in enumerate(stats):
        cx = MARGIN + i * (cw + col_gap)
        add_card(s, cx, sy, cw, sh_, fill=WHITE, line=CARD_LN, line_w=1.0)
        add_rect(s, cx, sy + Inches(0.18), Inches(0.07), sh_ - Inches(0.36), c)
        add_text(s, cx + Inches(0.45), sy + Inches(0.28), cw - Inches(0.7), Inches(1.0),
                 [[(val, {"bold": True, "color": c})]], size=54)
        add_text(s, cx + Inches(0.47), sy + Inches(1.4), cw - Inches(0.75), Inches(0.45),
                 lab, size=14.5, color=BODY)
    # where the gap comes from
    ny = sy + sh_ + Inches(0.35)
    add_card(s, MARGIN, ny, CONTENT_W, Inches(1.15), fill=WHITE, line=CARD_LN, line_w=0.75)
    add_text(s, MARGIN + Inches(0.28), ny + Inches(0.12), CONTENT_W - Inches(0.56), Inches(0.3),
             "WHERE THE GAP COMES FROM", size=10.5, color=MUTED, bold=True)
    add_text(s, MARGIN + Inches(0.28), ny + Inches(0.45), CONTENT_W - Inches(0.56), Inches(0.6),
             [[("Each implicit step pays Newton iterations, a global Jacobian assembly, and a direct "
                "solve, with four times the constitutive evaluations per element. The explicit step is "
                "one batched residual and vector updates.", {"color": BODY})]],
             size=13, leading=1.15)
    takeaway(s, [("The gap grows with problem size.", {"bold": True, "color": INK}),
                 (" The direct solve scales superlinearly; the batched residual scales linearly.", {})])


# ================================================================ 12 SUMMARY / HANDOFF
def s12_summary():
    s = new_slide(prs, "This work", "The method, in one slide",
                  number=15, total=TOTAL)
    rows = [
        ("Explicit runtime ≈ steps × material-update cost",
         "CFL fixes the step count; the constitutive update is the only lever", BLUE),
        ("ExplicitMixedOrder advances mechanics + first-order fields, no solver",
         "lumped mass, zero linear iterations; upstreamed to MOOSE", BLUE),
        ("NEML2 assembles the internal nodal forces on the device",
         "batched over all elements; state advances in place; one upload + one download per step", BLUE),
        ("MOOSE keeps BCs, parallelism, outputs unchanged",
         "and the path is verified to match conventional MOOSE assembly (CPU and CUDA test suite)", BLUE),
    ]
    y = BODY_TOP + Inches(0.1)
    for i, (head, sub, color) in enumerate(rows):
        add_card(s, MARGIN, y, CONTENT_W, Inches(0.88), fill=WHITE, line=CARD_LN, line_w=0.75)
        badge = add_card(s, MARGIN + Inches(0.22), y + Inches(0.21), Inches(0.46), Inches(0.46),
                         fill=color, line=None)
        shape_text(badge, str(i + 1), size=16, color=WHITE, bold=True)
        add_text(s, MARGIN + Inches(0.95), y + Inches(0.12), CONTENT_W - Inches(1.3), Inches(0.35),
                 head, size=15.5, color=INK, bold=True)
        add_text(s, MARGIN + Inches(0.95), y + Inches(0.5), CONTENT_W - Inches(1.3), Inches(0.32),
                 sub, size=12, color=MUTED)
        y += Inches(1.02)
    # up-next strip
    ny = y + Inches(0.12)
    add_card(s, MARGIN, ny, CONTENT_W, Inches(0.85), fill=BLUE_T, line=BLUE, line_w=1.0)
    add_text(s, MARGIN + Inches(0.3), ny, CONTENT_W - Inches(0.6), Inches(0.85),
             [[("Up next:  ", {"bold": True, "color": BLUE}),
               ("the experiment  ·  Taylor impact simulation  ·  calibration against the scanned specimen", {"color": INK})]],
             size=15, anchor=MSO_ANCHOR.MIDDLE)


# ================================================================ 15 THE EXPERIMENT
def s15_experiment():
    s = new_slide(prs, None, "The experiment", number=16, total=TOTAL)
    # video placeholder: 16:9 frame, replaced manually with the high-speed clip
    vw = Inches(7.9)
    vh = vw * 9 / 16
    vy = BODY_TOP + Inches(0.18)
    ph = add_card(s, MARGIN, vy, vw, vh, fill=INK, line=None)
    add_text(s, MARGIN, vy + vh / 2 - Inches(0.55), vw, Inches(0.7),
             "▶", size=40, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(s, MARGIN, vy + vh / 2 + Inches(0.15), vw, Inches(0.35),
             "high-speed video placeholder", size=12, color=FAINT,
             align=PP_ALIGN.CENTER, italic=True)
    add_text(s, MARGIN + Inches(0.1), vy + vh + Inches(0.08), vw, Inches(0.28),
             "impact and rebound of shot CuH04, high-speed camera",
             size=10.5, color=MUTED, italic=True)
    # right: shot facts
    px = MARGIN + vw + Inches(0.5)
    pw = CONTENT_W - vw - Inches(0.5)
    facts = [
        ("Specimen", "OFHC copper slug, Ø 7.62 mm × 38.1 mm, H04 full-hard temper"),
        ("Shot", "235.9 m/s impact against a rigid anvil"),
        ("Recovered geometry", "laser-scanned to a 46k-triangle surface mesh"),
        ("Role in this talk", "the scan is the calibration and validation target"),
    ]
    fy = vy
    for t, d in facts:
        add_card(s, px, fy, pw, Inches(1.0), fill=WHITE, line=CARD_LN, line_w=0.75)
        add_rect(s, px, fy + Inches(0.1), Inches(0.055), Inches(0.8), BLUE)
        add_text(s, px + Inches(0.24), fy + Inches(0.1), pw - Inches(0.45), Inches(0.3),
                 t, size=12.5, color=INK, bold=True)
        add_text(s, px + Inches(0.24), fy + Inches(0.42), pw - Inches(0.45), Inches(0.55),
                 d, size=11, color=BODY, leading=1.1)
        fy += Inches(1.14)


# ================================================================ 16 RESULTS: TAYLOR IMPACT
def s14_taylor():
    s = new_slide(prs, None, "Taylor anvil impact, end to end", number=17, total=TOTAL)
    add_text(s, MARGIN, BODY_TOP - Inches(0.08), CONTENT_W, Inches(0.35),
             [[("OFHC copper slug at ", {}),
               ("235.9 m/s", {"bold": True, "color": INK}),
               (" · calibrated multiplicative Johnson–Cook · reduced integration · Δt = 10 ns · ", {}),
               ("9,600+ explicit steps", {"bold": True, "color": INK})]],
             size=14.5, color=BODY)
    # top: plastic-strain cutaway sequence (full width)
    pw_ = Inches(9.6)
    ph_ = Inches(9.6 / fig_aspect("fig_pstrain.png"))
    py_ = BODY_TOP + Inches(0.46)
    s.shapes.add_picture(str(FIGS / "fig_pstrain.png"), MARGIN + Inches(0.6), py_, pw_, ph_)
    add_text(s, MARGIN + Inches(0.7), py_ + ph_ + Inches(0.03), Inches(11), Inches(0.28),
             "cutaway views (near half removed). Plastic strain localizes at the impact foot. The gray plane is the rigid anvil",
             size=11, color=MUTED, italic=True)
    # bottom left: temper comparison renders
    fw2 = Inches(4.3)
    fh2 = Inches(4.3 / fig_aspect("fig_profile.png"))
    fy2 = py_ + ph_ + Inches(0.32)
    s.shapes.add_picture(str(FIGS / "fig_profile.png"), MARGIN, fy2, fw2, fh2)
    # bottom right: temper story
    bx = MARGIN + fw2 + Inches(0.5)
    bw = CONTENT_W - fw2 - Inches(0.5)
    add_bullets(s, bx, fy2 + Inches(0.1), bw, fh2 + Inches(0.1), [
        [("Same mesh, BCs, integrator. The temper is swapped by ", {}),
         ("one NEML2 parameter", {"bold": True}),
         (": the prior cold work (initial plastic strain)", {})],
        [("Full-hard ", {}),
         ("39%", {"bold": True, "color": RED}),
         (" vs annealed ", {}),
         ("43%", {"bold": True, "color": BLUE}),
         (" axial shortening", {})],
    ], size=13.5, gap=10)


# ================================================================ 17 SIMULATION VIDEOS
def s17_videos():
    s = new_slide(prs, None, "The simulated impact", number=18, total=TOTAL)
    vids = [
        ("slug_impact_horizontal.mp4", "fig_video_h_poster.png", "perspective view"),
        ("slug_impact_side.mp4", "fig_video_side_poster.png",
         "side profile, the high-speed camera framing"),
    ]
    gap = Inches(0.5)
    vw = (CONTENT_W - gap) / 2
    vh = vw * 9 / 16
    vy = BODY_TOP + Inches(0.55)
    for i, (mp4, poster, cap) in enumerate(vids):
        vx = MARGIN + i * (vw + gap)
        s.shapes.add_movie(str(HERE.parent / mp4), vx, vy, vw, vh,
                           poster_frame_image=str(FIGS / poster),
                           mime_type="video/mp4")
        add_text(s, vx + Inches(0.05), vy + vh + Inches(0.08), vw, Inches(0.3),
                 cap, size=11, color=MUTED, italic=True)
    add_text(s, MARGIN, vy + vh + Inches(0.55), CONTENT_W, Inches(0.35),
             [[("Calibrated model, run to rebound at 96.7 µs. "
                "Color is effective plastic strain.", {"color": BODY})]], size=13)


# ================================================================ 17 RESULTS: THERMAL
def s15_thermal():
    s = new_slide(prs, None, "Coupled thermo-mechanics: heating from plastic work",
                  number=19, total=TOTAL)
    add_text(s, MARGIN, BODY_TOP - Inches(0.08), CONTENT_W, Inches(0.35),
             [[("The run you just saw is coupled. Temperature is integrated ", {}),
               ("inside the NEML2 model", {"bold": True, "color": INK}),
               (" (adiabatic Taylor–Quinney heating, β = 0.9)", {})]],
             size=14.5, color=BODY)
    # top: temperature-rise cutaway sequence
    pw_ = Inches(8.2)
    ph_ = Inches(8.2 / fig_aspect("fig_thermal.png"))
    py_ = BODY_TOP + Inches(0.44)
    s.shapes.add_picture(str(FIGS / "fig_thermal.png"), MARGIN + Inches(1.3), py_, pw_, ph_)
    add_text(s, MARGIN + Inches(1.4), py_ + ph_ + Inches(0.03), Inches(11), Inches(0.28),
             "temperature rise above 300 K, cutaway views. Run to rebound at 96 µs with >99% of the impact kinetic energy dissipated",
             size=11, color=MUTED, italic=True)
    # bottom: three fact cards
    cy = py_ + ph_ + Inches(0.38)
    cards = [
        ("Feeds back into the flow stress",
         "the hot foot softens (Johnson–Cook Θ = 1 − T*ᵐ) and flows more easily", RED),
        ("Adiabatic by physics, not assumption",
         "diffusion length √(αt) ≈ 0.1 mm ≪ element size over the ~100 µs run. No heat-conduction PDE needed", BLUE),
        ("Three extra NEML2 model blocks",
         "no new MOOSE modules, no new transfers. Temperature state lives on the device like everything else", GREEN),
    ]
    cw = (CONTENT_W - Inches(0.8)) / 3
    for i, (t, d, c) in enumerate(cards):
        cx = MARGIN + i * (cw + Inches(0.4))
        add_card(s, cx, cy, cw, Inches(1.05))
        add_rect(s, cx, cy + Inches(0.09), Inches(0.055), Inches(0.87), c)
        add_text(s, cx + Inches(0.24), cy + Inches(0.08), cw - Inches(0.44), Inches(0.3),
                 t, size=12, color=INK, bold=True, leading=1.02)
        add_text(s, cx + Inches(0.24), cy + Inches(0.43), cw - Inches(0.44), Inches(0.6),
                 d, size=10, color=BODY, leading=1.06)


# ================================================================ 17 BAYESIAN METHOD
def s17_bayes():
    s = new_slide(prs, None, "Bayesian calibration of the material parameters",
                  number=20, total=TOTAL)
    add_text(s, MARGIN, BODY_TOP - Inches(0.08), CONTENT_W, Inches(0.35),
             [[("Unknowns: ", {}),
               ("θ = (A, B, n, C, ε₀ᵖ)", {"bold": True, "color": INK}),
               (" plus a model-discrepancy scale σ", {}),
               ("d", {"sub": True}),
               (". Two shots, 235.9 and 132.3 m/s, are fit jointly. The forward model in the loop is the production simulation itself.", {})]],
             size=14.5, color=BODY)
    # pipeline
    stages = [
        ("Priors", "A, B lognormal, ×/÷ 2 at 90% around literature values. "
                   "n ∈ [0.1, 0.5], C ∈ [0.01, 0.05], ε₀ᵖ ∈ [0.1, 0.5] uniform. "
                   "Discrepancy half-normal (0.15 mm)."),
        ("96-run Sobol design per shot", "one production simulation per point and velocity (~21 min each)"),
        ("Gaussian-process emulator", "PCA of the outer profile, one GP per mode. Cross-validated to 0.03 mm."),
        ("MCMC posterior", "emcee over parameters and discrepancy. The posterior median is re-run through the true model."),
    ]
    n = len(stages)
    gap = Inches(0.45)
    cw = (CONTENT_W - (n - 1) * gap) / n
    ch = Inches(1.7)
    cy = BODY_TOP + Inches(0.55)
    cx = MARGIN
    for i, (t, d) in enumerate(stages):
        add_card(s, cx, cy, cw, ch, fill=WHITE, line=CARD_LN, line_w=1.0)
        add_rect(s, cx, cy + Inches(0.12), Inches(0.055), ch - Inches(0.24), BLUE)
        add_text(s, cx + Inches(0.22), cy + Inches(0.14), cw - Inches(0.4), Inches(0.55),
                 t, size=13.5, color=INK, bold=True, leading=1.02)
        add_text(s, cx + Inches(0.22), cy + Inches(0.62), cw - Inches(0.4), Inches(1.0),
                 d, size=11, color=BODY, leading=1.12)
        if i < n - 1:
            add_arrow(s, cx + cw + Inches(0.04), cy + ch / 2,
                      cx + cw + gap - Inches(0.04), cy + ch / 2, color=BLUE, weight=1.75)
        cx += cw + gap
    # posterior + likelihood
    ey = cy + ch + Inches(0.45)
    add_eq(s, r"$\pi(\theta, \sigma_d \mid \mathrm{scan}) \;\propto\; \mathcal{L}(\mathrm{scan} \mid \theta, \sigma_d)\; \pi(\theta)\, \pi(\sigma_d)$",
           MARGIN + Inches(0.1), ey, scale=1.7, name="bayes_posterior")
    add_text(s, MARGIN + Inches(0.14), ey + Inches(0.6), Inches(6.9), Inches(0.3),
             "posterior over parameters and discrepancy", size=11, color=MUTED, italic=True)
    add_eq(s, r"$\mathcal{L}: \;\; r(z_i) \sim \mathcal{N}\big(r_{\mathrm{GP}}(z_i;\theta),\; \sigma_{\mathrm{scan}}^2 + \sigma_{\mathrm{GP}}^2 + \sigma_d^2\big)$",
           MARGIN + Inches(0.1), ey + Inches(1.05), scale=1.7, name="bayes_likelihood")
    add_text(s, MARGIN + Inches(0.14), ey + Inches(1.68), Inches(6.9), Inches(0.35),
             "Gaussian over ~40 profile stations, final length, and foot radius, per shot",
             size=11, color=MUTED, italic=True)
    # right: prior bands vs posterior marginals
    fw = Inches(4.7)
    fh = Inches(4.7 / fig_aspect("fig_priors.png"))
    s.shapes.add_picture(str(FIGS / "fig_priors.png"), PAGE_W - MARGIN - fw, ey - Inches(0.25), fw, fh)


# ================================================================ 18 CALIBRATION
def s18_calibration():
    s = new_slide(prs, None, "Validation: the first shot",
                  number=21, total=TOTAL)
    add_text(s, MARGIN, BODY_TOP - Inches(0.08), CONTENT_W, Inches(0.35),
             [[("The jointly calibrated model at the first shot velocity of ", {}),
               ("235.9 m/s", {"bold": True, "color": INK}),
               (".", {})]],
             size=14.5, color=BODY)
    # figure: scan silhouette vs the calibrated run
    fw = Inches(7.6)
    fh = Inches(7.6 / fig_aspect("fig_calibration.png"))
    fy = BODY_TOP + Inches(0.55)
    s.shapes.add_picture(str(FIGS / "fig_calibration.png"), MARGIN + Inches(0.1), fy, fw, fh)
    add_text(s, MARGIN + Inches(0.2), fy + fh + Inches(0.06), fw, Inches(0.24),
             "final deformed profile, production model at the calibrated posterior median",
             size=10.5, color=MUTED, italic=True)
    # RMS ladder (vertical, right)
    px = MARGIN + fw + Inches(0.6)
    pw = CONTENT_W - fw - Inches(0.6)
    cy = fy + Inches(0.05)
    add_card(s, px, cy, pw, Inches(1.5), fill=WHITE, line=CARD_LN, line_w=0.75)
    add_rect(s, px, cy + Inches(0.12), Inches(0.055), Inches(1.26), GREEN)
    add_text(s, px + Inches(0.26), cy + Inches(0.14), pw - Inches(0.5), Inches(0.5),
             [[("77 µm", {"bold": True, "color": GREEN, "size": 26}),
               ("  profile RMS", {"size": 11, "color": MUTED})]], size=26)
    add_text(s, px + Inches(0.26), cy + Inches(0.74), pw - Inches(0.5), Inches(0.6),
             "final length 22.96 mm vs 22.41 ± 0.44 scanned",
             size=11.5, color=BODY, leading=1.15)


# ================================================================ 21 SECOND SHOT
def s21_prediction():
    s = new_slide(prs, None, "The second shot",
                  number=22, total=TOTAL)
    add_text(s, MARGIN, BODY_TOP - Inches(0.08), CONTENT_W, Inches(0.35),
             [[("The same parameter set, run at the second shot velocity of ", {}),
               ("132.3 m/s", {"bold": True, "color": INK}),
               (".", {})]],
             size=14.5, color=BODY)
    fw = Inches(7.6)
    fh = Inches(7.6 / fig_aspect("fig_predict132.png"))
    fy = BODY_TOP + Inches(0.55)
    s.shapes.add_picture(str(FIGS / "fig_predict132.png"), MARGIN + Inches(0.1), fy, fw, fh)
    add_text(s, MARGIN + Inches(0.2), fy + fh + Inches(0.06), fw, Inches(0.24),
             "final deformed profile, production model at the calibrated posterior median",
             size=10.5, color=MUTED, italic=True)
    # right: stat cards
    px = MARGIN + fw + Inches(0.6)
    pw = CONTENT_W - fw - Inches(0.6)
    cy = fy + Inches(0.05)
    add_card(s, px, cy, pw, Inches(1.5), fill=WHITE, line=CARD_LN, line_w=0.75)
    add_rect(s, px, cy + Inches(0.12), Inches(0.055), Inches(1.26), GREEN)
    add_text(s, px + Inches(0.26), cy + Inches(0.14), pw - Inches(0.5), Inches(0.5),
             [[("74 µm", {"bold": True, "color": GREEN, "size": 26}),
               ("  profile RMS", {"size": 11, "color": MUTED})]], size=26)
    add_text(s, px + Inches(0.26), cy + Inches(0.72), pw - Inches(0.5), Inches(0.7),
             "at a velocity 44% below the first shot, and a much lower strain range",
             size=11.5, color=BODY, leading=1.15)
    cy += Inches(1.72)
    add_card(s, px, cy, pw, Inches(1.6), fill=WHITE, line=CARD_LN, line_w=0.75)
    add_rect(s, px, cy + Inches(0.12), Inches(0.055), Inches(1.36), BLUE)
    add_text(s, px + Inches(0.26), cy + Inches(0.12), pw - Inches(0.5), Inches(0.35),
             "Why two velocities matter", size=12.5, color=INK, bold=True)
    add_text(s, px + Inches(0.26), cy + Inches(0.5), pw - Inches(0.5), Inches(1.0),
             "One shot cannot separate rate sensitivity from strain hardening. "
             "The second velocity resolves the trade-off and pulls every "
             "parameter to the interior of its prior.",
             size=11.5, color=BODY, leading=1.15)


def build():
    s01_title()
    s02_motivation()
    s03_gap()
    s04_governing()
    s05_kinematics()
    s06_jc()
    s05_integration()
    s06_stability_cost()
    s07_moose()
    s08_neml2()
    s09_contribution()
    s10_force_path()
    s11_state()
    s14_speed()
    s12_summary()
    s15_experiment()
    s14_taylor()
    s17_videos()
    s15_thermal()
    s17_bayes()
    s18_calibration()
    s21_prediction()
    prs.save(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
