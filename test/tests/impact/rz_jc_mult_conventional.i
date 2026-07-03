# Matched reference for rz_jc_mult_neml2.i: the SAME multiplicative
# Johnson-Cook NEML2 model through the conventional coupling with the
# total-Lagrangian axisymmetric kernels. state/Fp initializes to the
# identity via initialize_outputs.

!include 'rz_thermal_common.i'

[GlobalParams]
  large_kinematics = true
[]

[NEML2]
  input = 'johnson_cook_neml2_mult.i'
  [all]
    executor_name = 'neml2'
    model = 'model'
    verbose = false
    device = 'cpu'
    derivatives = 'neml2_stress deformation_gradient'
    initialize_outputs = 'state/Fp'
    initialize_output_values = 'identity_r2'
  []
[]

[Materials]
  [identity_r2]
    type = GenericConstantRankTwoTensor
    tensor_name = identity_r2
    tensor_values = '1 0 0 0 1 0 0 0 1'
  []
  [strain]
    type = ComputeLagrangianStrainAxisymmetricCylindrical
  []
  [stress]
    type = ComputeLagrangianStressCustomPK2
    custom_pk2_stress = 'neml2_stress'
    custom_pk2_jacobian = 'dneml2_stress/ddeformation_gradient'
  []
[]

[Kernels]
  [sdx]
    type = TotalLagrangianStressDivergenceAxisymmetricCylindrical
    variable = disp_x
    component = 0
  []
  [sdy]
    type = TotalLagrangianStressDivergenceAxisymmetricCylindrical
    variable = disp_y
    component = 1
  []
[]

[Executioner]
  [TimeIntegrator]
    type = ExplicitMixedOrder
    mass_matrix_tag = 'mass'
    use_constant_mass = true
    second_order_vars = 'disp_x disp_y'
  []
[]

[Outputs]
  file_base := rz_jc_mult_out
[]
