# Large deformation in the NEML2 force path

## Formulation

The large-deformation path is **total-Lagrangian**: everything is integrated
on the reference configuration, which is what lets the batched caches
(shape-function gradients, `JxW`, dof maps) stay valid for the whole run.

- `NEML2DeformationGradient` (Cartesian) / `NEML2DeformationGradientRZ`
  (axisymmetric) gather the deformation gradient `F = I + du/dX` at every
  quadrature point into one batched tensor — the RZ variant includes the hoop
  stretch `1 + u_r/r`.
- The NEML2 model returns stress; `NEML2StressDivergence(RZ)` assembles nodal
  forces from the **first Piola-Kirchhoff** stress (`stress = 'pk1'`). Both
  full `R2` and symmetric `SR2` stress outputs are handled.

### Multiplicative plasticity (the production model)

`examples/impact/johnson_cook_neml2_mult_thermal.i` defines the finite-strain
Johnson-Cook model: multiplicative split `F = Fe * Fp`, trial state with
frozen `Fp`, a one-unknown radial return on the trial elastic strain, and the
plastic update `Fp = (I + dEp) * Fp_n`. Adiabatic heating (Taylor-Quinney) is
integrated *inside* the model, so temperature is internal state, not a MOOSE
variable.

The plastic deformation gradient history must start at the identity (zero is
singular). The executor handles this declaratively:

```
[NEML2]
  [all]
    ...
    identity_seeded_state = 'state/Fp'
  []
[]
```

### F-bar (volumetric locking at full integration)

With full integration, near-incompressible plastic flow locks. The gatherers
accept `stabilize_strain = true` to apply the F-bar volumetric correction over
the batched quadrature data (replace det F per qp with the element mean).
Verified by the `rz_jc_mult_fbar_*` matched pair.

### Reduced integration + hourglass control (the production choice)

Instead of F-bar, the production input runs one-point quadrature — 2.6x faster
per step and locking-free by construction, but it needs hourglass
stabilization:

```
[Executioner]
  [Quadrature]
    type = GAUSS
    order = CONSTANT          # 1 quadrature point per element
  []
[]

[UserObjects]
  [hourglass]
    type = NEML2HourglassCorrection      # batched, QUAD4 (2D/RZ) and HEX8 (3D)
    assembly = 'assembly'
    fe = 'fe'
    executor = 'neml2'
    displacements = 'disp_x disp_y'
    penalty = 0.05                       # classic Flanagan-Belytschko coefficient
    shear_modulus = 43.7e9               # physical mu = E / (2(1+nu))
    residual = 'NONTIME'
  []
[]
```

The kernel removes the least-squares affine part of the elemental
displacement and penalizes the remaining hourglass modes with a
rotation-invariant scale `penalty * mu * V / h^2`. With the physical shear
modulus, `penalty = 0.05` is **not a tuning knob** — results were verified
insensitive over a 4x range. Non-batched twins for regular MOOSE kernels
exist as `HourglassCorrectionQuad4` / `HourglassCorrectionHex8`
(solid_mechanics module, same fork branch).

## Contact: rigid anvil via nodal kernels

The anvil is a penalty rigid wall applied node-wise, restricted to the impact
face:

```
[NodalKernels]
  [anvil]
    type = PenaltyRigidWallNodalKernel        # F = -k * penetration
    variable = disp_y
    component = 1
    penalty = 1e9
    wall_position = 0
    boundary = bottom
  []
  [anvil_friction]
    type = RigidWallCoulombFrictionNodalKernel # F_t = mu k |pen| tanh(v_t/v_reg)
    variable = disp_x
    normal_variable = disp_y
    normal_component = 1
    penalty = 1e9                              # MUST match the wall penalty
    mu = 0.2
    wall_position = 0
    regularization_velocity = 1
    boundary = bottom
  []
[]
```

Why nodal kernels and not an integrated (sideset traction) BC: we swept the
traction stiffness over 1x-50x and every run died mid-fold (interior nodes
tunnel past the traction-pinned surface) while the nodal wall runs to rebound
at 50x *less* total stiffness — per-node enforcement locality is what matters,
not force magnitude. Penalty operating window is ~1e9-1e10; the explicit
stability ceiling (`4 m / dt^2`) is ~1e11 for this mesh/dt. Note: the
calibration found the data prefers **mu = 0** (see
[calibration.md](calibration.md)), so the friction kernel may be dropped
entirely — `mu = 0` and no kernel are exactly equivalent.

## The production input, end to end

`examples/impact/rz_slug_thermal_mult_ri.i` =
RZ mesh (8x80 QUAD4, 0.15 in radius x 1.5 in) + initial velocity via OLD-state
IC + multiplicative JC NEML2 model + reduced integration + batched hourglass +
nodal-kernel anvil + `NEML2CentralDifference` (dt = 5 ns, constant lumped
mass) + rebound Terminator. Postprocessors track mean axial velocity, max
effective plastic strain, and max temperature rise into a CSV.

Performance anatomy (2000-step benchmark, serial): ~53 ms/step total, of
which ~37 ms is the batched NEML2 constitutive evaluation and ~1 ms is
everything contact/residual-loop related. The FE element loop is empty after
the first step (instrumented and verified), so per-step cost is the batched
model plus O(boundary nodes) contact work.

## Where things live

- MOOSE fork branch `exp_dyn_hourglass`, single commit
  "NEML2 explicit dynamics: RZ and large-deformation force path, F-bar,
  reduced integration" — framework NEML2 userobjects + solid_mechanics
  gatherers/post-kernels/integrator/hourglass kernels + module tests.
- marlin (`slug_runs`): contact nodal kernels (`src/nodalkernels/`),
  NEML2 model files and impact inputs (`examples/impact/`), matched-pair
  tests (`test/tests/impact/`).
