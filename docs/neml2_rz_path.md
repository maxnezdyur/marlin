# The axisymmetric (RZ) NEML2 nodal-force path

## What it is

The NEML2 nodal-force path skips MOOSE's per-element material/kernel loop
entirely: geometry and shape-function data are gathered **once** into batched
torch tensors, every timestep the strain (or deformation gradient) at all
quadrature points is computed in one batched operation, the NEML2 constitutive
model is evaluated on the whole batch at once, and nodal internal forces are
assembled straight into the residual vector by a batched einsum. Under the
`NEML2CentralDifference` time integrator the regular FE element loop runs over
**zero volume elements** after the first evaluation — we verified this by
instrumenting the element visit count (640 visits at t=0, 0 for every step
after).

The RZ variants extend this to axisymmetric problems:

- integration weights become `2 pi r * JxW` (measured on the reference
  configuration — the formulation is total-Lagrangian),
- the strain/deformation gradient gains the hoop component `u_r / r`,
- the stress divergence gains the hoop term in the radial residual.

## Objects

All in MOOSE (`framework/` and `modules/solid_mechanics/`), fork branch
`exp_dyn_hourglass`:

| object | role |
|---|---|
| `NEML2Assembly` | caches `2 pi r JxW` and quadrature-point coordinates as tensors |
| `NEML2FEInterpolation` | caches shape functions, gradients, dof maps; per-step batched gather of solution values |
| `NEML2SmallStrainRZ` | gathers the small-strain tensor incl. hoop strain (input to the NEML2 model) |
| `NEML2DeformationGradientRZ` | large-deformation counterpart: gathers F incl. the hoop stretch |
| `NEML2StressDivergenceRZ` | post-kernel: assembles nodal forces from the batched stress (Cauchy/S for small strain, PK1 for large deformation), incl. the hoop term |
| `NEML2CentralDifference` | explicit central-difference integrator; shrinks the algebraic element/node ranges so no volume element is visited after setup |

## Input file anatomy

From `test/tests/impact/rz_thermal_neml2.i` (small strain, coupled
thermo-mechanical Johnson-Cook):

```
[Mesh]
  coord_type = RZ            # required: x = radial, y = axial
[]

[NEML2]
  input = 'johnson_cook_neml2_thermal.i'   # the NEML2 model file
  [all]
    executor_name = 'neml2'
    model = 'model'
    manage_state_advance = true            # executor owns old/new state swap
    input_kernels = 'neml2_strain'
  []
[]

[UserObjects]
  [assembly]
    type = NEML2Assembly
  []
  [fe]
    type = NEML2FEInterpolation
    assembly = 'assembly'
  []
  [neml2_strain]                           # pre-kernel: model input
    type = NEML2SmallStrainRZ
    assembly = 'assembly'
    fe = 'fe'
    to_neml2 = 'neml2_strain'
  []
  [residual]                               # post-kernel: forces
    type = NEML2StressDivergenceRZ
    assembly = 'assembly'
    fe = 'fe'
    executor = 'neml2'
    stress = 'state/S'
    residual = 'NONTIME'
  []
[]

[Executioner]
  [TimeIntegrator]
    type = NEML2CentralDifference
    mass_matrix_tag = 'mass'               # from a MassMatrix kernel on a matrix tag
    use_constant_mass = true
    second_order_vars = 'disp_x disp_y'
    assembly = 'assembly'
    fe = 'fe'
  []
[]
```

The displacement variables carry an initial velocity through a nonzero OLD
state IC (`v_y = (u - u_old)/dt`), and the mass matrix is assembled once from
`MassMatrix` kernels on the `mass` matrix tag.

Note the ordering rule: user objects that **add** to the residual must be
post-kernels (`NEML2StressDivergenceRZ`, `NEML2HourglassCorrection`) — a
mid-pass residual zeroing wipes contributions from ordinary user objects.

## Verification

`test/tests/impact/` contains matched pairs, each running the same physics
through the NEML2 nodal-force path and through conventional MOOSE
assembly, exodiffed against a **shared** gold file:

| pair | what it proves |
|---|---|
| `rz_thermal_neml2` / `rz_thermal_conventional` | RZ small strain + in-model adiabatic heating, identical to material-property coupling with Lagrangian RZ kernels |
| `rz_thermal_beta0` / `rz_isothermal` | Taylor-Quinney = 0 reproduces the isothermal model exactly (1e-15) |
| `rz_thermal_identity` | the in-model temperature update satisfies the forward-Euler heating identity to machine precision |
| `rz_jc_large_def_*` | RZ total-Lagrangian pair (see [neml2_large_deformation.md](neml2_large_deformation.md)) |
| `rz_jc_mult_*`, `rz_jc_mult_fbar_*` | RZ multiplicative-plasticity and F-bar pairs |

Run them with `./run_tests --re impact` from the marlin root.
