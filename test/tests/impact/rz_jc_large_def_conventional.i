# Matched reference for rz_jc_large_def_neml2.i: the SAME total-Lagrangian
# Johnson-Cook NEML2 model through the conventional coupling with the
# Lagrangian axisymmetric kernel system (no manage_state_advance; state
# round-trips through material properties, old time gathered as t - dt).

!include 'rz_thermal_common.i'

[GlobalParams]
  large_kinematics = true
[]

[NEML2]
  input = 'johnson_cook_neml2_large_def.i'
  [all]
    executor_name = 'neml2'
    model = 'model'
    verbose = false
    device = 'cpu'
    derivatives = 'neml2_stress deformation_gradient'
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

[Materials]
  [strain]
    type = ComputeLagrangianStrainAxisymmetricCylindrical
  []
  [stress]
    type = ComputeLagrangianStressCustomPK2
    custom_pk2_stress = 'neml2_stress'
    custom_pk2_jacobian = 'dneml2_stress/ddeformation_gradient'
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
  file_base := rz_jc_large_def_out
[]
