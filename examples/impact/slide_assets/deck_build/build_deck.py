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


TOTAL = 19
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
            tf.text = "GPU-resident material models for explicit dynamics in MOOSE"
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
         (" — stress waves traverse the part in microseconds, with severe, localized plasticity", {})],
        [("Predictive fidelity requires ", {}),
         ("modern constitutive models", {"bold": True}),
         (" — rate- and temperature-dependent plasticity, evolving internal state", {})],
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
    s = new_slide(prs, "Motivation", "Two mature ecosystems — and a gap between them",
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
        [("But: no mesh, no boundary conditions, no solver — ", {}),
         ("not a simulation code", {"bold": True})],
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
               ("an interface that lets NEML2 assemble the nodal internal forces itself — batched, device-resident — while MOOSE keeps doing everything else it is good at.", {"color": INK})]],
             size=16, anchor=MSO_ANCHOR.MIDDLE)


# ================================================================ 4 EQUATIONS I
def s04_governing():
    s = new_slide(prs, "Formulation 1/3", "Governing equations of explicit solid dynamics",
                  number=4, total=TOTAL)
    lx = MARGIN + Inches(0.1)
    label_x = MARGIN + Inches(7.9)
    label_w = CONTENT_W - Inches(7.9)
    rows = [
        (r"$\rho\,\ddot{\mathbf{u}} \;=\; \nabla\!\cdot\!\boldsymbol{\sigma} + \rho\,\mathbf{b} \quad \text{in } \Omega$",
         "balance of linear momentum", 1.9, "momentum_strong_form"),
        (r"$\int_{\Omega}\rho\,\mathbf{w}\!\cdot\!\ddot{\mathbf{u}}\;dV \;+\; \int_{\Omega}\nabla\mathbf{w}:\boldsymbol{\sigma}\;dV \;=\; \int_{\Gamma_t}\mathbf{w}\!\cdot\!\bar{\mathbf{t}}\;dA \;+\; \int_{\Omega}\rho\,\mathbf{w}\!\cdot\!\mathbf{b}\;dV$",
         "weak form: multiply by test function, integrate by parts", 1.9, "weak_form"),
        (r"$\mathbf{M}\,\ddot{\mathbf{u}} \;=\; \mathbf{F}^{\mathrm{ext}} \;-\; \mathbf{F}^{\mathrm{int}}(\boldsymbol{\sigma})$",
         "discretize in space: semi-discrete momentum equation", 1.9, "semi_discrete_momentum"),
        (r"$\mathbf{F}^{\mathrm{int}} \;=\; \mathop{\mathrm{A}}_{e}\int_{\Omega_e}\mathbf{B}^{\!\top}\boldsymbol{\sigma}\;dV, \qquad \boldsymbol{\sigma} = \text{constitutive model}(\boldsymbol{\varepsilon},\ \text{state})$",
         "internal force: assembled from quadrature-point stress", 1.9, "internal_force_assembly"),
    ]
    y = BODY_TOP + Inches(0.2)
    for latex, caption, scale, eqname in rows:
        add_eq(s, latex, lx, y, scale=scale, name=eqname)
        add_text(s, label_x, y - Inches(0.04), label_w, Inches(0.7),
                 caption, size=12.5, color=BODY, italic=True)
        y += Inches(1.08)
    takeaway(s, [("Everything above is standard.", {"bold": True, "color": INK}),
                 (" The physics of the material lives in one place — the stress ", {}),
                 ("σ", {"bold": True, "color": INK}),
                 (" at each quadrature point. That is where NEML2 will plug in.", {})])


# ================================================================ 5 EQUATIONS II
def s05_integration():
    s = new_slide(prs, "Formulation 2/3", "Explicit time integration: ExplicitMixedOrder",
                  number=5, total=TOTAL)
    lw = Inches(7.3)
    add_text(s, MARGIN, BODY_TOP, lw, Inches(0.3),
             [[("Central difference, as implemented in our ", {}),
               ("ExplicitMixedOrder", {"bold": True, "font": MONO, "size": 13.5}),
               (" MOOSE integrator", {})]], size=14, color=BODY)
    eqs = [
        (r"$\mathbf{a}_n \;=\; \mathbf{M}_L^{-1}\big(\mathbf{F}^{\mathrm{ext}}_n - \mathbf{F}^{\mathrm{int}}_n\big)$",
         "pointwise divide — no solver", "accel_lumped_mass"),
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
             [[("No Newton iterations, no global linear solve, no Jacobian — ", {}),
               ("each step is one residual evaluation plus vector updates.", {"bold": True, "color": INK})]],
             size=14, color=BODY)
    # right: mixed order card
    px = MARGIN + lw + Inches(0.42)
    pw = CONTENT_W - lw - Inches(0.42)
    ph = Inches(3.62)
    add_card(s, px, BODY_TOP, pw, ph, fill=BLUE_T, line=BLUE, line_w=1.0)
    add_text(s, px + Inches(0.26), BODY_TOP + Inches(0.2), pw - Inches(0.52), Inches(0.35),
             "WHY “MIXED ORDER”", size=11, color=BLUE, bold=True)
    add_bullets(s, px + Inches(0.28), BODY_TOP + Inches(0.62), pw - Inches(0.56), Inches(1.7), [
        [("Second-order fields", {"bold": True}),
         (" (displacement): central difference, as at left", {})],
        [("First-order fields", {"bold": True}),
         (" (e.g. temperature): forward Euler on the rate — same update loop", {})],
    ], size=13, gap=10, bullet_color=BLUE)
    add_line(s, px + Inches(0.26), BODY_TOP + Inches(2.12), px + pw - Inches(0.26),
             BODY_TOP + Inches(2.12), color=BLUE, weight=0.5)
    add_text(s, px + Inches(0.28), BODY_TOP + Inches(2.32), pw - Inches(0.56), Inches(1.1),
             [[("One integrator advances a ", {}),
               ("coupled thermo-mechanical system", {"bold": True, "color": INK}),
               (" explicitly — the multiphysics lever used later in this talk.", {})]],
             size=13, color=BODY, leading=1.08)
    takeaway(s, [("Developed for this work and upstreamed:", {"bold": True, "color": INK}),
                 (" part of MOOSE solid mechanics today, available to every MOOSE application.", {})])


# ================================================================ 6 EQUATIONS III
def s06_stability_cost():
    s = new_slide(prs, "Formulation 3/3", "Stability sets the step; the material sets the cost",
                  number=6, total=TOTAL)
    lw = Inches(6.9)
    add_text(s, MARGIN, BODY_TOP, lw, Inches(0.3),
             "Conditional stability (CFL): the step must resolve the fastest stress wave",
             size=14, color=BODY)
    add_eq(s, r"$\Delta t \;\le\; \Delta t_{\mathrm{crit}} \;=\; \min\limits_{e}\, \dfrac{\ell_e}{c}, \qquad c = \sqrt{E/\rho}$",
           MARGIN + Inches(0.1), BODY_TOP + Inches(0.45), scale=1.85, name="cfl_critical_timestep")
    add_text(s, MARGIN + Inches(0.12), BODY_TOP + Inches(1.22), lw, Inches(0.3),
             "element length over elastic wave speed (dilatational speed in 3-D)",
             size=11.5, color=MUTED, italic=True)
    add_bullets(s, MARGIN, BODY_TOP + Inches(1.85), lw, Inches(2.4), [
        [("Millimeter elements: ", {}),
         ("Δt ≈ 10 ns", {"bold": True}),
         ("  ⇒  ", {})] + pow10(4, 5) + [(" steps for a 100 µs event", {})],
        [("Each step: no solve — the runtime ", {}),
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
    takeaway(s, [("Explicit runtime  ≈  steps × material-update cost.", {"bold": True, "color": INK}),
                 (" The step count is physics; the material cost is the target.", {})])


# ================================================================ 7 MOOSE
def s07_moose():
    s = new_slide(prs, "Building blocks", "MOOSE: the multiphysics host",
                  number=7, total=TOTAL)
    add_text(s, MARGIN, BODY_TOP, CONTENT_W, Inches(0.35),
             [[("Open-source multiphysics FE framework (Idaho National Laboratory) — ", {}),
               ("we keep all of this for free", {"bold": True, "color": INK})]],
             size=15.5, color=BODY)
    cards = [
        ("Boundary conditions", "full BC library, incl. the penalty and pressure BCs used in this work"),
        ("Contact", "mortar and node-face algorithms — architecture-compatible with this interface"),
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
                 (" the material update already exists here — parallel and production-tested.", {})])


# ================================================================ 8 NEML2
def s08_neml2():
    s = new_slide(prs, "Building blocks", "NEML2: the material engine",
                  number=8, total=TOTAL)
    add_text(s, MARGIN, BODY_TOP, CONTENT_W, Inches(0.35),
             [[("New Engineering Material model Library v2 (ANL, open source) — constitutive models as ", {}),
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
    takeaway(s, [("NEML2 evaluates sophisticated material models the way accelerators want them evaluated.", {"bold": True, "color": INK}),
                 (" What it lacks — mesh, BCs, assembly — is exactly what MOOSE has.", {})])


# ================================================================ 9 WHAT WE DID
def s09_contribution():
    s = new_slide(prs, "This work", "What we built: two pillars, one force path",
                  number=9, total=TOTAL)
    col_gap = Inches(0.5)
    cw = (CONTENT_W - col_gap) / 2
    ch = Inches(2.9)
    for i, (num, title, color, tint, lines) in enumerate([
        ("1", "ExplicitMixedOrder integrator", BLUE, BLUE_T, [
            [("Explicit central-difference integrator with ", {}),
             ("mixed-order multiphysics", {"bold": True}),
             (" (2nd-order mechanics + 1st-order fields)", {})],
            [("Lumped mass via matrix tag — ", {}),
             ("zero linear iterations per step", {"bold": True})],
            [("Variable step size (Abaqus-style midpoint velocity averaging)", {})],
            [("Upstreamed to MOOSE ", {}),
             ("solid_mechanics", {"font": MONO, "size": 12.5})],
        ]),
        ("2", "NEML2 nodal-force interface", GREEN, GREEN_T, [
            [("NEML2 computes ", {}),
             ("internal nodal forces", {"bold": True}),
             (" itself — not just stress — for the whole mesh in batched tensor ops", {})],
            [("Constitutive state lives on the device and ", {}),
             ("advances in place", {"bold": True}),
             (" between steps", {})],
            [("Plugs into the explicit solve as a residual contribution — MOOSE BCs, outputs, MPI unchanged", {})],
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
                  number=10, total=TOTAL)
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
             "DEVICE (libTorch)  —  same code on CPU / CUDA", size=10.5, color=GREEN, bold=True)
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
        ("NEML2", "SmallStrain", "ε = sym ∇u", "whole batch"),
        ("NEML2Model", "Executor", "σ = model(ε, state)", "one batched call"),
        ("NEML2Stress", "Divergence", "Rᵉ = Σ ∇φ·σ JxW", "all elements at once"),
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
               ("shape functions φ, ∇φ,  DOF maps,  weights JxW — rebuilt only on mesh change", {"size": 10.5})]],
             size=10.5, color=BODY, anchor=MSO_ANCHOR.MIDDLE)
    takeaway(s, [("The interior force computation never touches an element loop:", {"bold": True, "color": INK}),
                 (" a short sequence of batched tensor ops.", {})])


# ================================================================ 11 STATE RESIDENCY
def s11_state():
    s = new_slide(prs, "This work", "Constitutive state never leaves the device",
                  number=11, total=TOTAL)
    lane_label_w = Inches(1.15)
    half_h = Inches(1.92)
    gap = Inches(0.34)
    # ---- conventional half
    y1 = BODY_TOP + Inches(0.05)
    add_card(s, MARGIN, y1, CONTENT_W, half_h, fill=RED_T, line=RED, line_w=1.0)
    add_text(s, MARGIN + Inches(0.26), y1 + Inches(0.12), Inches(8), Inches(0.3),
             "CONVENTIONAL COUPLING — state round-trips through MOOSE every step",
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
             "state copied down and back up every step — scales with model complexity",
             size=10.5, color=RED, italic=True, leading=1.1)
    # ---- this-work half
    y2 = y1 + half_h + gap
    add_card(s, MARGIN, y2, CONTENT_W, half_h, fill=GREEN_T, line=GREEN, line_w=1.0)
    add_text(s, MARGIN + Inches(0.26), y2 + Inches(0.12), Inches(9.5), Inches(0.3),
             "THIS WORK — state advances in place on the device  (manage_state_advance)",
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
             "per step: one solution upload, one force download — independent of model complexity",
             size=10.5, color=GREEN, italic=True, leading=1.1)
    takeaway(s, [("The richer the model, the more this matters", {"bold": True, "color": INK}),
                 (" — state stays where it is computed; traffic does not grow with it.", {})])


# ================================================================ 12 SUMMARY / HANDOFF
def s12_summary():
    s = new_slide(prs, "This work", "The method, in one slide",
                  number=12, total=TOTAL)
    rows = [
        ("Explicit runtime ≈ steps × material-update cost",
         "CFL fixes the step count; the constitutive update is the only lever", BLUE),
        ("ExplicitMixedOrder advances mechanics + first-order fields, no solver",
         "lumped mass, zero linear iterations; upstreamed to MOOSE", BLUE),
        ("NEML2 assembles the internal nodal forces on the device",
         "batched over all elements; state advances in place; one upload + one download per step", BLUE),
        ("MOOSE keeps BCs, parallelism, outputs — unchanged",
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
               ("verification across formulations  ·  reduced integration  ·  Taylor impact & thermo-mechanics  ·  calibration against a scanned specimen", {"color": INK})]],
             size=15, anchor=MSO_ANCHOR.MIDDLE)


# ================================================================ 13 RESULTS: VERIFICATION
def s13_verification():
    s = new_slide(prs, None, "The interface adds no error — in any formulation", number=13, total=TOTAL)
    add_text(s, MARGIN, BODY_TOP - Inches(0.08), CONTENT_W, Inches(0.35),
             [[("Matched pairs: ", {}),
               ("the same model through both force paths", {"bold": True, "color": INK}),
               (" — same mesh, same steps; only the assembly differs. Each pair exodiffs against one shared gold.", {})]],
             size=14.5, color=BODY)
    # left: the matched-pair ladder
    lw = Inches(7.15)
    pairs = [
        ("2-D small strain", "NEML2 J2 vs MOOSE native radial return"),
        ("RZ small strain, thermal JC", "force path vs conventional NEML2 coupling"),
        ("RZ total-Lagrangian JC (PK1)", "large deformation on the reference mesh"),
        ("RZ multiplicative JC  (F = FᵉFᵖ)", "finite-strain plasticity, identity-seeded Fᵖ"),
        ("RZ multiplicative + F-bar", "batched volumetric stabilization"),
        ("β = 0 thermal ≡ isothermal", "in-model heating identity to 10⁻¹⁵"),
    ]
    ry = BODY_TOP + Inches(0.52)
    for head, sub in pairs:
        add_card(s, MARGIN, ry, lw, Inches(0.6), fill=WHITE, line=CARD_LN, line_w=0.75)
        add_text(s, MARGIN + Inches(0.24), ry + Inches(0.05), Inches(4.3), Inches(0.32),
                 head, size=12.5, color=INK, bold=True)
        add_text(s, MARGIN + Inches(0.24), ry + Inches(0.33), lw - Inches(1.4), Inches(0.26),
                 sub, size=10, color=MUTED)
        add_text(s, MARGIN + lw - Inches(1.15), ry, Inches(0.95), Inches(0.6),
                 "✓", size=20, color=GREEN, bold=True, align=PP_ALIGN.CENTER,
                 anchor=MSO_ANCHOR.MIDDLE)
        ry += Inches(0.68)
    # right: the two big numbers
    px = MARGIN + lw + Inches(0.45)
    pw = CONTENT_W - lw - Inches(0.45)
    stats = [
        ([("≤ 3 × 10", {}), ("−8", {"sup": True, "size": 26})],
         "max nodal-force difference (rel. to peak)", BLUE),
        ([("≤ 8 × 10", {}), ("−8", {"sup": True, "size": 26})],
         "max relative displacement difference", GREEN),
    ]
    sy = BODY_TOP + Inches(0.52)
    for segs, lab, c in stats:
        add_card(s, px, sy, pw, Inches(1.5), fill=WHITE, line=CARD_LN, line_w=1.0)
        add_rect(s, px, sy + Inches(0.14), Inches(0.06), Inches(1.22), c)
        add_text(s, px + Inches(0.32), sy + Inches(0.16), pw - Inches(0.5), Inches(0.75),
                 [[(t, {**ov, "bold": True, "color": c}) for t, ov in segs]], size=40)
        add_text(s, px + Inches(0.34), sy + Inches(0.98), pw - Inches(0.55), Inches(0.45),
                 lab, size=11.5, color=BODY, leading=1.1)
        sy += Inches(1.66)
    add_text(s, px + Inches(0.05), sy + Inches(0.05), pw - Inches(0.1), Inches(0.8),
             [[("6,000× tighter", {"bold": True, "color": INK}),
               (" than the regression tolerance — floating-point noise territory.", {})]],
             size=12.5, color=BODY, leading=1.15)
    takeaway(s, [("Six matched pairs, one rule:", {"bold": True, "color": INK}),
                 (" the batched force path reproduces conventional assembly to machine precision — "
                  "small strain through finite-strain plasticity, Cartesian and axisymmetric.", {})])


# ================================================================ 14 REDUCED INTEGRATION
def s14_reduced():
    s = new_slide(prs, None, "Reduced integration: one point per element, stabilized",
                  number=14, total=TOTAL)
    lw = Inches(7.3)
    add_bullets(s, MARGIN, BODY_TOP + Inches(0.15), lw, Inches(4.3), [
        [("Full integration ", {}),
         ("locks volumetrically", {"bold": True}),
         (" under large plastic flow — the batched ", {}),
         ("F-bar", {"bold": True}),
         (" correction fixes it (verified to machine precision, previous slide)", {})],
        [("The production choice instead: ", {}),
         ("one-point quadrature", {"bold": True, "color": INK}),
         (" — locking-free by construction and much cheaper per step", {})],
        [("Underintegration admits ", {}),
         ("hourglass modes", {"bold": True}),
         (" → stabilized by a batched Flanagan–Belytschko correction (QUAD4 + HEX8): "
          "remove the least-squares affine part of the element displacement, penalize the rest", {})],
        [("Penalty scale  c = 0.05 · μ · V/h²  uses the ", {}),
         ("physical shear modulus", {"bold": True}),
         (" — the classic coefficient, not a tunable", {})],
    ], size=15, gap=15)
    # right: stat cards
    px = MARGIN + lw + Inches(0.5)
    pw = CONTENT_W - lw - Inches(0.5)
    add_card(s, px, BODY_TOP, pw, Inches(2.0), fill=WHITE, line=CARD_LN, line_w=1.0)
    add_rect(s, px, BODY_TOP + Inches(0.15), Inches(0.06), Inches(1.7), BLUE)
    add_text(s, px + Inches(0.35), BODY_TOP + Inches(0.22), pw - Inches(0.6), Inches(1.0),
             [[("2.6×", {"bold": True, "color": BLUE})]], size=52)
    add_text(s, px + Inches(0.37), BODY_TOP + Inches(1.3), pw - Inches(0.65), Inches(0.6),
             "faster per explicit step than full integration, same mesh",
             size=12.5, color=BODY, leading=1.12)
    ny = BODY_TOP + Inches(2.3)
    add_card(s, px, ny, pw, Inches(2.05), fill=GREEN_T, line=GREEN, line_w=1.0)
    add_text(s, px + Inches(0.26), ny + Inches(0.18), pw - Inches(0.52), Inches(0.3),
             "NOT A TUNING KNOB", size=11, color=GREEN, bold=True)
    add_text(s, px + Inches(0.28), ny + Inches(0.55), pw - Inches(0.56), Inches(1.4),
             [[("Final profiles insensitive to the hourglass penalty over a ", {}),
               ("4× range", {"bold": True, "color": INK}),
               (" — the physics does not hide in the stabilization.", {})]],
             size=13, color=BODY, leading=1.15)
    takeaway(s, [("Every production run in the rest of this talk uses reduced integration + batched hourglass control.",
                  {"bold": True, "color": INK})])


# ================================================================ 15 PERFORMANCE ANATOMY
def s15_perf():
    s = new_slide(prs, None, "After the first step, the element loop is empty",
                  number=15, total=TOTAL)
    lw = Inches(6.6)
    add_text(s, MARGIN, BODY_TOP, lw, Inches(0.35),
             [[("Instrumented the FE element loop of the production RZ impact run:", {})]],
             size=14.5, color=BODY)
    # visit counter card
    vy = BODY_TOP + Inches(0.5)
    add_card(s, MARGIN, vy, lw, Inches(1.85), fill=WHITE, line=CARD_LN, line_w=1.0)
    add_text(s, MARGIN + Inches(0.26), vy + Inches(0.16), lw - Inches(0.5), Inches(0.3),
             "VOLUME ELEMENTS VISITED PER RESIDUAL EVALUATION", size=10.5, color=MUTED, bold=True)
    add_text(s, MARGIN + Inches(0.35), vy + Inches(0.55), lw - Inches(0.6), Inches(1.1),
             [[("step 0:   ", {"font": MONO, "size": 15}),
               ("640", {"font": MONO, "bold": True, "size": 15, "color": BLUE}),
               ("   (builds the device caches: φ, ∇φ, DOF maps, weights)", {"size": 11.5, "color": MUTED})],
              [("step 1:   ", {"font": MONO, "size": 15}),
               ("0", {"font": MONO, "bold": True, "size": 15, "color": GREEN})],
              [("step n:   ", {"font": MONO, "size": 15}),
               ("0", {"font": MONO, "bold": True, "size": 15, "color": GREEN}),
               ("   — for the rest of the run", {"size": 11.5, "color": MUTED})]],
             size=13, color=INK, leading=1.35)
    add_bullets(s, MARGIN, vy + Inches(2.1), lw, Inches(1.7), [
        [("The integrator installs a ", {}),
         ("shrunken algebraic range", {"bold": True}),
         (": only elements adjacent to integrated BCs — none, with node-wise contact", {})],
        [("Contact runs on the ", {}),
         ("9 impact-face nodes", {"bold": True}),
         (" only (boundary-restricted nodal kernels)", {})],
    ], size=13.5, gap=10)
    # right: measured per-step anatomy
    px = MARGIN + lw + Inches(0.5)
    pw = CONTENT_W - lw - Inches(0.5)
    py = BODY_TOP
    add_card(s, px, py, pw, Inches(4.35))
    add_text(s, px + Inches(0.26), py + Inches(0.2), pw - Inches(0.52), Inches(0.3),
             "MEASURED: ONE EXPLICIT STEP (53 ms, serial CPU)", size=10.5, color=MUTED, bold=True)
    bar_x = px + Inches(0.3)
    y = py + Inches(0.62)
    segs = [("batched NEML2 constitutive call", "71%", RED, RED_T, 1.9),
            ("integrator, aux, output", "27%", MUTED, WHITE, 0.75),
            ("contact + residual loops", "2%", BLUE, BLUE_T, 0.28)]
    for name, tag, ln, fl, h_in in segs:
        h = Inches(h_in)
        add_rect(s, bar_x, y, Inches(0.5), h, fl, line=ln, line_w=1.0)
        add_text(s, bar_x + Inches(0.7), y + h / 2 - Inches(0.18), pw - Inches(1.3), Inches(0.4),
                 [[(name, {"bold": h_in > 1}),
                   ("   " + tag, {"color": ln, "size": 11, "bold": True})]],
                 size=12.5, color=INK if h_in > 1 else BODY)
        y += h + Inches(0.14)
    add_text(s, px + Inches(0.3), y + Inches(0.1), pw - Inches(0.6), Inches(0.6),
             "2,000-step production benchmark; geometry caches never rebuilt (0.000 s total)",
             size=10.5, color=MUTED, italic=True, leading=1.1)
    takeaway(s, [("Per-step cost ≈ one batched constitutive call.", {"bold": True, "color": INK}),
                 (" That call is exactly the work that moves to the GPU — everything around it is already negligible.", {})])


# ================================================================ 16 RESULTS: TAYLOR IMPACT
def s14_taylor():
    s = new_slide(prs, None, "3-D Taylor anvil impact, end to end", number=16, total=TOTAL)
    add_text(s, MARGIN, BODY_TOP - Inches(0.08), CONTENT_W, Inches(0.35),
             [[("OFHC copper slug at ", {}),
               ("235.9 m/s", {"bold": True, "color": INK}),
               (" — Johnson–Cook plasticity in NEML2 · Δt = 10 ns · ", {}),
               ("11,000+ explicit steps", {"bold": True, "color": INK})]],
             size=14.5, color=BODY)
    # top: plastic-strain cutaway sequence (full width)
    pw_ = Inches(9.6)
    ph_ = Inches(9.6 / fig_aspect("fig_pstrain.png"))
    py_ = BODY_TOP + Inches(0.46)
    s.shapes.add_picture(str(FIGS / "fig_pstrain.png"), MARGIN + Inches(0.6), py_, pw_, ph_)
    add_text(s, MARGIN + Inches(0.7), py_ + ph_ + Inches(0.03), Inches(11), Inches(0.28),
             "cutaway views (near half removed) — plastic strain localizes at the impact foot; gray plane = rigid anvil",
             size=11, color=MUTED, italic=True)
    # bottom left: temper comparison renders
    fw2 = Inches(4.3)
    fh2 = Inches(4.3 / fig_aspect("fig_profile.png"))
    fy2 = py_ + ph_ + Inches(0.32)
    s.shapes.add_picture(str(FIGS / "fig_profile.png"), MARGIN, fy2, fw2, fh2)
    # bottom right: temper story
    bx = MARGIN + fw2 + Inches(0.5)
    bw = CONTENT_W - fw2 - Inches(0.5)
    add_bullets(s, bx, fy2 + Inches(0.25), bw, fh2 - Inches(0.2), [
        [("Same mesh, BCs, integrator — the copper temper is swapped by ", {}),
         ("changing only NEML2 material parameters", {"bold": True})],
        [("Full-hard ", {}),
         ("51%", {"bold": True, "color": RED}),
         (" vs annealed ", {}),
         ("58%", {"bold": True, "color": BLUE}),
         (" axial shortening — temper sensitivity captured", {})],
    ], size=13.5, gap=12)


# ================================================================ 17 RESULTS: THERMAL
def s15_thermal():
    s = new_slide(prs, None, "Coupled thermo-mechanics: heating from plastic work",
                  number=17, total=TOTAL)
    add_text(s, MARGIN, BODY_TOP - Inches(0.08), CONTENT_W, Inches(0.35),
             [[("The run you just saw is coupled — temperature integrated ", {}),
               ("inside the NEML2 model", {"bold": True, "color": INK}),
               (" (adiabatic Taylor–Quinney heating, β = 0.9)", {})]],
             size=14.5, color=BODY)
    # top: temperature-rise cutaway sequence
    pw_ = Inches(8.2)
    ph_ = Inches(8.2 / fig_aspect("fig_thermal.png"))
    py_ = BODY_TOP + Inches(0.44)
    s.shapes.add_picture(str(FIGS / "fig_thermal.png"), MARGIN + Inches(1.3), py_, pw_, ph_)
    add_text(s, MARGIN + Inches(1.4), py_ + ph_ + Inches(0.03), Inches(11), Inches(0.28),
             "temperature rise above 300 K, cutaway views — run to 114 µs, >99% of the impact kinetic energy dissipated",
             size=11, color=MUTED, italic=True)
    # bottom: three fact cards
    cy = py_ + ph_ + Inches(0.38)
    cards = [
        ("Feeds back into the flow stress",
         "the hot foot softens (Johnson–Cook Θ = 1 − T*ᵐ) and flows more easily", RED),
        ("Adiabatic by physics, not assumption",
         "diffusion length √(αt) ≈ 0.1 mm ≪ element size over the 114 µs run — no heat-conduction PDE needed", BLUE),
        ("Three extra NEML2 model blocks",
         "no new MOOSE modules, no new transfers — temperature state lives on the device like everything else", GREEN),
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
    takeaway(s, [("The abstract’s thermo-mechanical claim, delivered:", {"bold": True, "color": INK}),
                 (" a peak ΔT of 119 K at the mushroom foot, captured through the NEML2 force path.", {})])


# ================================================================ 18 CALIBRATION
def s18_calibration():
    s = new_slide(prs, None, "Validation: calibrated against a scanned specimen",
                  number=18, total=TOTAL)
    add_text(s, MARGIN, BODY_TOP - Inches(0.08), CONTENT_W, Inches(0.35),
             [[("Laser-scanned recovered specimen (OFHC copper, 235.9 m/s) → axis-corrected profile target → ", {}),
               ("Bayesian calibration of the Johnson–Cook parameters", {"bold": True, "color": INK})]],
             size=14.5, color=BODY)
    # figure: scan silhouette vs the calibrated run
    fw = Inches(7.6)
    fh = Inches(7.6 / fig_aspect("fig_calibration.png"))
    fy = BODY_TOP + Inches(0.55)
    s.shapes.add_picture(str(FIGS / "fig_calibration.png"), MARGIN + Inches(0.1), fy, fw, fh)
    add_text(s, MARGIN + Inches(0.2), fy + fh + Inches(0.06), fw, Inches(0.24),
             "final deformed profile, RZ production model at the calibrated posterior median",
             size=10.5, color=MUTED, italic=True)
    # RMS ladder (vertical, right)
    px = MARGIN + fw + Inches(0.6)
    pw = CONTENT_W - fw - Inches(0.6)
    steps = [("hand-tuned", "159 µm", MUTED),
             ("Bayesian posterior median", "81 µm", BLUE),
             ("+ frictionless anvil", "69 µm", GREEN)]
    cy = fy + Inches(0.05)
    for i, (lab, val, c) in enumerate(steps):
        add_card(s, px, cy, pw, Inches(0.86), fill=WHITE, line=CARD_LN, line_w=0.75)
        add_rect(s, px, cy + Inches(0.1), Inches(0.055), Inches(0.66), c)
        add_text(s, px + Inches(0.26), cy + Inches(0.08), pw - Inches(0.5), Inches(0.42),
                 [[(val, {"bold": True, "color": c, "size": 22}),
                   ("  profile RMS", {"size": 10.5, "color": MUTED})]], size=22)
        add_text(s, px + Inches(0.26), cy + Inches(0.52), pw - Inches(0.5), Inches(0.26),
                 lab, size=10.5, color=BODY)
        if i < 2:
            add_arrow(s, px + pw / 2, cy + Inches(0.88), px + pw / 2, cy + Inches(1.16),
                      color=INK, weight=1.75)
        cy += Inches(1.22)
    takeaway(s, [("96-run Sobol design on the production model → GP emulator → posterior.", {"bold": True, "color": INK}),
                 (" The data rejects anvil friction, and one shot cannot separate A–B–n–C — multi-velocity shots are next.", {})])


# ================================================================ 19 CONCLUSIONS
def s19_conclusions():
    s = new_slide(prs, None, "Takeaways", number=19, total=TOTAL)
    rows = [
        ("NEML2 assembles the internal nodal forces inside MOOSE explicit dynamics",
         "batched, device-resident; state advances in place; one upload + one download per step", BLUE),
        ("Verified to machine precision across formulations",
         "small strain → total-Lagrangian → multiplicative plasticity, Cartesian and axisymmetric, incl. F-bar", GREEN),
        ("Per-step cost is one batched constitutive call",
         "the element loop is provably empty after setup; reduced integration + knob-free hourglass control, 2.6× faster", RED),
        ("End-to-end on a real experiment",
         "3-D and RZ Taylor impact with in-model adiabatic heating; Bayesian-calibrated to 69 µm profile RMS against a scanned specimen", GOLD),
    ]
    y = BODY_TOP + Inches(0.1)
    for i, (head, sub, color) in enumerate(rows):
        add_card(s, MARGIN, y, CONTENT_W, Inches(0.92), fill=WHITE, line=CARD_LN, line_w=0.75)
        badge = add_card(s, MARGIN + Inches(0.22), y + Inches(0.23), Inches(0.46), Inches(0.46),
                         fill=color, line=None)
        shape_text(badge, str(i + 1), size=16, color=WHITE, bold=True)
        add_text(s, MARGIN + Inches(0.95), y + Inches(0.13), CONTENT_W - Inches(1.3), Inches(0.35),
                 head, size=15.5, color=INK, bold=True)
        add_text(s, MARGIN + Inches(0.95), y + Inches(0.52), CONTENT_W - Inches(1.3), Inches(0.32),
                 sub, size=12, color=MUTED)
        y += Inches(1.06)
    ny = y + Inches(0.1)
    add_card(s, MARGIN, ny, CONTENT_W, Inches(0.8), fill=BLUE_T, line=BLUE, line_w=1.0)
    add_text(s, MARGIN + Inches(0.3), ny, CONTENT_W - Inches(0.6), Inches(0.8),
             [[("Open source, in MOOSE today.   Next:  ", {"bold": True, "color": BLUE}),
               ("GPU scaling studies  ·  multi-velocity calibration  ·  3-D reduced-integration production runs", {"color": INK})]],
             size=14.5, anchor=MSO_ANCHOR.MIDDLE)


def build():
    s01_title()
    s02_motivation()
    s03_gap()
    s04_governing()
    s05_integration()
    s06_stability_cost()
    s07_moose()
    s08_neml2()
    s09_contribution()
    s10_force_path()
    s11_state()
    s12_summary()
    s13_verification()
    s14_reduced()
    s15_perf()
    s14_taylor()
    s15_thermal()
    s18_calibration()
    s19_conclusions()
    prs.save(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
