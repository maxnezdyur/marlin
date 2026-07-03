# Same coupled thermo-mechanical Johnson-Cook RZ slug as rz_thermal_neml2.i,
# through the CONVENTIONAL NEML2 coupling: MOOSE gathers the strain into the
# model, NEML2 stress is copied back into a MOOSE material property, and the
# Lagrangian axisymmetric kernels assemble on the reference configuration.
# No manage_state_advance: old state round-trips through material properties.
#
# Requires the t - dt old-time gatherer fix: explicit integrators rewind the
# problem time to the old time during residual evaluation, so gathering
# timeOld() directly would give t == t~1.

!include 'rz_thermal_common.i'

[NEML2]
  input = 'johnson_cook_neml2_thermal.i'
  [all]
    executor_name = 'neml2'
    model = 'model'
    verbose = false
    device = 'cpu'
    derivatives = 'state/S neml2_strain'
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
  [convert_strain]
    type = RankTwoTensorToSymmetricRankTwoTensor
    from = 'mechanical_strain'
    to = 'neml2_strain'
  []
  [stress]
    type = ComputeLagrangianObjectiveCustomSymmetricStress
    custom_small_stress = 'state/S'
    custom_small_jacobian = 'dstate/S/dneml2_strain'
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
  file_base := rz_thermal_out
[]
