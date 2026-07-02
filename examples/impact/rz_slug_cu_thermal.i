
[Mesh]
  coord_type = RZ

  [slug]
    type = GeneratedMeshGenerator
    dim = 2
    nx = 20
    ny = 150
    # nx = 20
    # ny = 10
    xmin = 0
    xmax = ${units 0.25 in -> m}
    ymin = ${units -3 in -> m}
    ymax = 0
  []
  [slug_block]
    type = SubdomainIDGenerator
    input = slug
    subdomain_id = 1
  []
[]

[GlobalParams]
  displacements = 'disp_x disp_y'
  large_kinematics = true
  stabilize_strain = true
[]

[Problem]
  # type = AugmentedLagrangianContactFEProblem
  kernel_coverage_check = false
[]

[Variables]
  [disp_x]
  []
  [disp_y]
  []
  [T]
    initial_condition = ${units 300 K}
  []
[]

[AuxVariables]
  [vel_x]
    block = 1
  []
  [vel_y]
    block = 1
  []
  [accel_x]
    block = 1
  []
  [accel_y]
    block = 1
  []
  [ep_dot_recovered]
  []
[]

[UserObjects]
  [ep_dot]
    type = NodalPatchRecoveryMaterialProperty
    property = ep_dot
    execute_on = TIMESTEP_END
    patch_polynomial_order = FIRST
  []
  [terminator]
    type = Terminator
    expression = vel_y<0
    fail_mode = HARD
    execute_on = TIMESTEP_END
  []
[]

[Kernels]
  [sdx]
    type = TotalLagrangianStressDivergenceAxisymmetricCylindrical
    # type = TotalLagrangianStressDivergence
    variable = disp_x
    component = 0
    block = 1
  []
  [sdy]
    type = TotalLagrangianStressDivergenceAxisymmetricCylindrical
    # type = TotalLagrangianStressDivergence
    variable = disp_y
    component = 1
    block = 1
  []

  [ifx]
    type = InertialForce
    variable = disp_x
    velocity = vel_x
    acceleration = accel_x
    beta = 0.25
    gamma = 0.5
    alpha = 0 # not implemented in TotalLagrangianStressDivergence
    block = 1
  []
  [ify]
    type = InertialForce
    variable = disp_y
    velocity = vel_y
    acceleration = accel_y
    beta = 0.25
    gamma = 0.5
    alpha = 0 # not implemented in TotalLagrangianStressDivergence
    block = 1
  []

  # ------------- heat equation (framework kernels only) -------------
  # rho*cp dT/dt = div(k grad T) + beta * sigma_vm * ep_dot
  [T_time]
    type = CoefTimeDerivative
    variable = T
    Coefficient = ${fparse 8940 * 385} # rho * cp  (J/(m^3 K))
    block = 1
  []
  [T_conduction]
    type = MatDiffusion
    variable = T
    diffusivity = k_thermal
    block = 1
  []
  [T_plastic_heating]
    type = MatBodyForce
    variable = T
    material_property = q_plastic
    block = 1
  []
[]

[AuxKernels]
  [vel_x]
    type = NewmarkVelAux
    variable = vel_x
    acceleration = accel_x
    gamma = 0.5
    execute_on = 'TIMESTEP_END'
  []
  [vel_y]
    type = NewmarkVelAux
    variable = vel_y
    acceleration = accel_y
    gamma = 0.5
    execute_on = 'TIMESTEP_END'
  []

  [accel_x]
    type = NewmarkAccelAux
    variable = accel_x
    displacement = disp_x
    velocity = vel_x
    beta = 0.25
    execute_on = 'TIMESTEP_END'
  []
  [accel_y]
    type = NewmarkAccelAux
    variable = accel_y
    displacement = disp_y
    velocity = vel_y
    beta = 0.25
    execute_on = 'TIMESTEP_END'
  []
  [ep_dot_recovered]
    type = NodalPatchRecoveryAux
    variable = ep_dot_recovered
    nodal_patch_recovery_uo = ep_dot
    execute_on = TIMESTEP_END
  []
[]

[Materials]
  [slug_strain]
    type = ComputeLagrangianStrainAxisymmetricCylindrical
    # type = ComputeLagrangianStrain
    block = 1
  []

  # lag the effective plastic strain rate
  [effective_plastic_strain_rate]
    type = ParsedMaterial
    property_name = ep_dot
    expression = 'if(dt=0, 1, (ep-ep_old)/dt)'
    material_property_names = 'ep:=effective_plastic_strain ep_old:=Old[effective_plastic_strain]'
    extra_symbols = dt
    outputs = exodus
  []

  [slug_flow_stress]
    type = DerivativeParsedMaterial
    property_name = flow_stress
    # sy   (MPa)
    # K    (MPa)
    # T... (deg C)
    # Cu: Appl. Sci. 2020, 10, 2423; doi:10.3390/app10072423
    expression = 'A:=${units 99.7 MPa -> Pa};
                  B:=${units 262.8 MPa -> Pa};
                  C:=0.029;
                  n:=0.23; m:=0.98; ep_dot_0:=1;
                  T_r:=0; T_m:=1338; T_star:=(T-T_r)/(T_m-T_r); ep_dot_star:=max(1.0,ep_dot_recovered/ep_dot_0);
                  (A+B*if(ep>0, ep^n, 0))*(1+C*log(ep_dot_star))*(1-T_star^m)'
    material_property_names = 'ep:=Old[effective_plastic_strain]'
    coupled_variables = 'T ep_dot_recovered'
    derivative_order = 0
    compute = false
    evalerror_behavior = error
    output_properties = flow_stress
    outputs = exodus
  []
  [slug_stress]
    type = ComputeSimoHughesJ2PlasticityStress
    flow_stress_material = slug_flow_stress
    block = 1
    outputs = exodus
    # relative_tolerance = 1e-06
    output_properties = effective_plastic_strain
  []
  [elasticity_slug]
    type = ComputeIsotropicElasticityTensor
    youngs_modulus = ${units 100 GPa -> Pa}
    poissons_ratio = 0.31
    block = 1
  []
  [thermal_conductivity]
    type = GenericConstantMaterial
    prop_names = 'k_thermal'
    prop_values = '390' # W/(m K), OFHC copper
    block = 1
  []
  [vonmises]
    type = RankTwoInvariant
    rank_two_tensor = cauchy_stress
    invariant = 'VonMisesStress'
    property_name = vonmises
    block = 1
  []
  # Taylor-Quinney: 90% of plastic power converts to heat
  [q_plastic]
    type = ParsedMaterial
    property_name = q_plastic
    expression = '0.9 * vm * epd'
    material_property_names = 'vm:=vonmises epd:=ep_dot'
    block = 1
  []
  [slug_density]
    type = GenericConstantMaterial
    prop_names = 'density'
    prop_values = '${units 8940 kg/m^3}'
  []
[]

[ICs]
  [vel_y]
    type = ConstantIC
    variable = vel_y
    value = ${units 200 m/s}
    block = 1
  []
[]

[Functions]
  [anvil]
    type = ParsedFunction
    expression = 'if(y>0, -y*1e15, 0)'
  []
[]

[BCs]
  [anvil]
    type = FunctionNeumannBC
    function = anvil
    variable = disp_y
    boundary = top
    use_displaced_mesh = true
  []
  [symmetry]
    type = DirichletBC
    variable = disp_x
    value = 0
    boundary = left
  []
[]

[Postprocessors]
  [vel_y]
    type = ElementAverageValue
    variable = vel_y
    block = 1
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [gap_y]
    type = SideAverageValue
    variable = disp_y
    boundary = top
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [rear_y]
    type = SideAverageValue
    variable = disp_y
    boundary = bottom
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [max_T]
    type = NodalExtremeValue
    variable = T
    value_type = max
    block = 1
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [max_ep]
    type = ElementExtremeMaterialProperty
    mat_prop = effective_plastic_strain
    value_type = max
    block = 1
    execute_on = 'INITIAL TIMESTEP_END'
  []
[]

[Executioner]
  type = Transient
  solve_type = NEWTON
  dt = ${units 2e-8 s}
  end_time = ${units 1.5e-4 s} # 150 microseconds
  automatic_scaling = true
  compute_scaling_once = false
  # full Newton with the T<->mechanics cross terms only approximate in the
  # Jacobian: backtracking line search stalls, plain Newton converges
  line_search = none
[]

[Outputs]
  exodus = true
  csv = true
  print_linear_residuals = false
  perf_graph = true
  time_step_interval = 10
[]
