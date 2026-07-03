# Large-deformation Johnson-Cook RZ slug through the NEML2 nodal-force path
# with manage_state_advance: F (incl. hoop stretch) gathered by
# NEML2DeformationGradientRZ, PK1 assembled by NEML2StressDivergenceRZ.
# The full-stack test: large kinematics + stateful advance + rate terms.

!include 'rz_thermal_common.i'

[NEML2]
  input = 'johnson_cook_neml2_large_def.i'
  [all]
    executor_name = 'neml2'
    model = 'model'
    verbose = false
    manage_state_advance = true
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
  file_base = rz_jc_large_def_out
[]
