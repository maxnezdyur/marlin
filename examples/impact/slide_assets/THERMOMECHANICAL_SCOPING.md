# Coupled thermomechanical Taylor slug — scoping

Goal: flip the slug from isothermal to a coupled run that shows **temperature
rise from plastic work**, to back the abstract's thermomechanical claim with a
real temperature-field figure (slide 14).

Current state (verified in code):
- Every Johnson-Cook run sets `use_temperature = false`; temperature is a constant 300 K.
- `HEAT_TRANSFER := no`, `CONTACT := no` in `marlin/Makefile`; only `SOLID_MECHANICS := yes`.
- The NEML2 `JohnsonCookFlowRate` object **already** declares a `temperature`
  input and its AD temperature derivative (`marlin/include/neml2/JohnsonCookFlowRate.h:53`,
  `src/neml2/JohnsonCookFlowRate.C:176-190`) — so the model side is ready; it's
  only ever been wired off.

## Recommended approach: adiabatic heating, entirely inside NEML2

At Taylor-impact timescales the slug is **adiabatic** — quantify it so it's
defensible in Q&A:

- Cu thermal diffusivity α ≈ 1.1e-4 m²/s; run time t ≈ 120 µs.
- Diffusion length √(αt) ≈ √(1.1e-4 · 1.2e-4) ≈ **0.11 mm** ≪ element size ≈ 2 mm.
- ⇒ heat doesn't move between elements during the event → no conduction needed.

So the temperature evolves by a **local ODE** at each material point:

```
ρ c_p dT/dt = β σ_vm ε̇_p        (Taylor-Quinney, β ≈ 0.9)
```

This needs **no MOOSE heat equation, no HEAT_TRANSFER module, no Makefile
change** — it's three extra NEML2 model blocks. Draft is in
`johnson_cook_neml2_thermal.i` (this dir). The additions:

1. `jc_flowrate`: `use_temperature = true`, `temperature = 'old_state/T'` (lagged).
2. `plastic_heating` (`ScalarMultiplication`): `Ṫ = scaling · σ_vm · ε̇_p`,
   `scaling = β/(ρc_p) = 0.9/(8960·385) = 2.6090e-7` K·m³/J.
3. `integrate_T` (`ScalarForwardEulerTimeIntegration` on `state/T`).
4. `model`: add `plastic_heating integrate_T`; add `state/T` to `additional_outputs`.

Temperature is **lagged one step** (flow rate reads `old_state/T`) so the
radial-return system stays a 1-unknown (`state/ep`) solve and the dependency
graph stays acyclic. At dt = 1e-8 s the lag is negligible.

### MOOSE-side change: almost none
`3d_slug_mesh.i` only needs `[NEML2] input = '...thermal.i'`. With
`auto_output = true` the new `state/T` is emitted, so a temperature field is
available to color the deformed mushroom (slide 14). Optionally add an
`AuxVariable temperature` to pull it onto nodes for nicer rendering.

## The one runtime risk to validate first

**Initialize `old_state/T` to 300 K.** A NEML2 state defaults to 0, which gives
`T* = (0−300)/1038 < 0` on step 1 (clamped, but wrong physics). Two fixes:

- **(a)** Seed the NEML2 state IC to 300 K (marlin's NEML2 path manages the
  state vector via `manage_state_advance = true`; confirm it exposes a state IC —
  the standard NEML2 action uses `initialize_outputs`, `NEML2ToMOOSEMaterialProperty.C:83`).
- **(b)** If a state IC is awkward, make temperature a **MOOSE `forces/T`**
  instead (next section) where a plain MOOSE IC sets 300 K — also the more
  "multiphysics-looking" option.

Validate the constitutive wiring at a single point before the full 3D run
(cheap): a 1-element driver input through `marlin-opt`/`--check-input`, confirm
`state/T` rises and `σ_y` softens. (No NEML2 CLI tools or `neml2` python module
are installed in `moose-exp-dyn`; use the marlin binary.)

## Expected result (set slide expectations honestly)

Peak plastic work density ≈ σ_vm·ε_p ≈ 400 MPa · 0.4 ≈ 1.6e8 J/m³ at the foot.
⇒ ΔT ≈ β·W_p/(ρc_p) ≈ 0.9·1.6e8/3.45e6 ≈ **40–50 K** at the mushroom.

That softens the flow stress by Θ = 1 − (ΔT/1038)^0.98 ≈ **3–4%** — real but
**secondary** at 235.9 m/s. Don't oversell it: it's a clean "the framework
captures plastic-work heating" capability slide, not a dominant effect. For a
visually stronger temperature field, a higher impact velocity or a lower-melt
material would show a larger rise.

## Alternatives (if you want more than adiabatic)

- **Temperature as a MOOSE field (`forces/T`)** — temperature becomes a MOOSE
  variable advanced by the explicit integrator alongside displacement; NEML2
  reads `forces/T` and outputs the dissipation `σ_vm·ε̇_p` back as a heat source.
  Best match to the abstract's "explicit multiphysics integrator solving heat +
  mechanics simultaneously," and gives a true temperature *field* with a trivial
  IC. More plumbing (a gather of T into NEML2 + a dissipation output + an
  explicit nodal capacity update).
- **Literal heat conduction** — add `HeatConduction` (needs `HEAT_TRANSFER := yes`)
  on top of the MOOSE-field variant. Explicit-diffusion stability dt ≈ dx²/α ≈
  (2e-3)²/1.1e-4 ≈ 0.036 s ≫ mechanical dt, so it's stable and cheap — but the
  physics says it changes nothing over 120 µs (see adiabatic estimate). Only do
  this if a reviewer specifically demands conduction.

## Slide wording

Use **"adiabatic temperature rise from plastic work (Taylor-Quinney β = 0.9)"** —
accurate and matches what runs. Reserve "heat transfer / conduction" for the
forces/T + HeatConduction variant only.
