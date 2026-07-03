# Multiplicative finite-strain Johnson-Cook RZ slug through the NEML2
# nodal-force path with manage_state_advance. state/Fp history is seeded
# with the identity via identity_seeded_state.

!include 'rz_thermal_common.i'

[NEML2]
  input = 'johnson_cook_neml2_mult.i'
  [all]
    executor_name = 'neml2'
    model = 'model'
    verbose = false
    manage_state_advance = true
    identity_seeded_state = 'state/Fp'
    auto_output = false
    input_kernels = 'deformation_gradient'
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
  [deformation_gradient]
    type = NEML2DeformationGradientRZ
    assembly = 'assembly'
    fe = 'fe'
    to_neml2 = 'deformation_gradient'
  []
  [residual]
    type = NEML2StressDivergenceRZ
    assembly = 'assembly'
    fe = 'fe'
    executor = 'neml2'
    stress = 'pk1'
    residual = 'NONTIME'
  []
[]

[Executioner]
  [TimeIntegrator]
    type = NEML2CentralDifference
    mass_matrix_tag = 'mass'
    use_constant_mass = true
    second_order_vars = 'disp_x disp_y'
    assembly = 'assembly'
    fe = 'fe'
  []
[]

[Outputs]
  file_base = rz_jc_mult_out
[]
