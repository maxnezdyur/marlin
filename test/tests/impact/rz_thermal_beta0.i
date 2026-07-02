# beta = 0 variant of the coupled model: with the Taylor-Quinney factor zeroed
# the thermal model must reproduce the isothermal model exactly.

!include 'rz_thermal_common.i'

[NEML2]
  input = 'johnson_cook_neml2_thermal_beta0.i'
  [all]
    executor_name = 'neml2'
    model = 'model'
    verbose = false
    manage_state_advance = true
    auto_output = false
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
  [neml2_strain]
    type = NEML2SmallStrainRZ
    assembly = 'assembly'
    fe = 'fe'
    to_neml2 = 'neml2_strain'
  []
  [residual]
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
    mass_matrix_tag = 'mass'
    use_constant_mass = true
    second_order_vars = 'disp_x disp_y'
    assembly = 'assembly'
    fe = 'fe'
  []
[]

[Outputs]
  file_base = rz_beta0_equiv
[]
