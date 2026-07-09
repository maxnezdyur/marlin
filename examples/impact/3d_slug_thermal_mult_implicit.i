# IMPLICIT twin of 3d_slug_thermal_mult_ri.i: the same calibrated
# multiplicative thermal Johnson-Cook slug in full 3-D, run with Newmark-beta
# implicit dynamics through the conventional NEML2 coupling. Full integration
# with F-bar stabilization; nodal penalty anvil. The adaptive step is capped
# at the explicit run's timestep.

# impact velocity in m/s
v = 235.9

r = '${units 0.15 in -> m}'
slug_length = '${units 1.5 in -> m}'
n_sectors = 4
n_rings = 2
n_layers = 24

[GlobalParams]
  displacements = 'disp_x disp_y disp_z'
  large_kinematics = true
[]

[Mesh]
  [disc]
    type = ConcentricCircleMeshGenerator
    num_sectors = '${n_sectors}'
    radii = '${r}'
    rings = '${n_rings}'
    has_outer_square = false
    preserve_volumes = true
    smoothing_max_it = 3
  []
  [rotate_x_90]
    type = TransformGenerator
    input = disc
    transform = ROTATE
    vector_value = '0 90 0'
  []
  [extrude]
    type = AdvancedExtruderGenerator
    input = rotate_x_90
    direction = '0 1 0'
    heights = '${slug_length}'
    num_layers = '${n_layers}'
  []
  [impact_face]
    type = SideSetsAroundSubdomainGenerator
    block = 1
    input = extrude
    new_boundary = impact_face
    normal = '0 -1 0'
  []
[]

[Variables]
  [disp_x]
  []
  [disp_y]
  []
  [disp_z]
  []
[]

[AuxVariables]
  [vel_x]
  []
  [vel_y]
    initial_condition = '${fparse -v}'
  []
  [vel_z]
  []
  [accel_x]
  []
  [accel_y]
  []
  [accel_z]
  []
[]

[AuxKernels]
  [accel_x]
    type = NewmarkAccelAux
    variable = accel_x
    displacement = disp_x
    velocity = vel_x
    beta = 0.3025
    execute_on = TIMESTEP_END
  []
  [vel_x]
    type = NewmarkVelAux
    variable = vel_x
    acceleration = accel_x
    gamma = 0.6
    execute_on = TIMESTEP_END
  []
  [accel_y]
    type = NewmarkAccelAux
    variable = accel_y
    displacement = disp_y
    velocity = vel_y
    beta = 0.3025
    execute_on = TIMESTEP_END
  []
  [vel_y]
    type = NewmarkVelAux
    variable = vel_y
    acceleration = accel_y
    gamma = 0.6
    execute_on = TIMESTEP_END
  []
  [accel_z]
    type = NewmarkAccelAux
    variable = accel_z
    displacement = disp_z
    velocity = vel_z
    beta = 0.3025
    execute_on = TIMESTEP_END
  []
  [vel_z]
    type = NewmarkVelAux
    variable = vel_z
    acceleration = accel_z
    gamma = 0.6
    execute_on = TIMESTEP_END
  []
[]

[NEML2]
  input = 'johnson_cook_neml2_mult_thermal_calibrated.i'
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
    type = ComputeLagrangianStrain
    stabilize_strain = true
  []
  [stress]
    type = ComputeLagrangianStressCustomPK2
    custom_pk2_stress = 'neml2_stress'
    custom_pk2_jacobian = 'dneml2_stress/ddeformation_gradient'
  []
  [density]
    type = GenericConstantMaterial
    prop_names = 'density'
    prop_values = '${units 8960 kg/m^3}'
  []
[]

[Kernels]
  [sdx]
    type = TotalLagrangianStressDivergence
    variable = disp_x
    component = 0
    stabilize_strain = true
  []
  [sdy]
    type = TotalLagrangianStressDivergence
    variable = disp_y
    component = 1
    stabilize_strain = true
  []
  [sdz]
    type = TotalLagrangianStressDivergence
    variable = disp_z
    component = 2
    stabilize_strain = true
  []
  [inertia_x]
    type = InertialForce
    variable = disp_x
    velocity = vel_x
    acceleration = accel_x
    beta = 0.3025
    gamma = 0.6
    density = density
  []
  [inertia_y]
    type = InertialForce
    variable = disp_y
    velocity = vel_y
    acceleration = accel_y
    beta = 0.3025
    gamma = 0.6
    density = density
  []
  [inertia_z]
    type = InertialForce
    variable = disp_z
    velocity = vel_z
    acceleration = accel_z
    beta = 0.3025
    gamma = 0.6
    density = density
  []
[]

# rigid anvil: node-wise penalty wall on the impact face (frictionless)
[NodalKernels]
  [anvil]
    type = PenaltyRigidWallNodalKernel
    variable = disp_y
    component = 1
    penalty = 1e9
    wall_position = 0
    boundary = impact_face
  []
[]

[Postprocessors]
  [vel_y_avg]
    type = ElementAverageValue
    variable = vel_y
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [max_dT]
    type = ElementExtremeMaterialProperty
    mat_prop = 'state/dT'
    value_type = max
    execute_on = TIMESTEP_END
  []
  [max_ep]
    type = ElementExtremeMaterialProperty
    mat_prop = 'state/ep'
    value_type = max
    execute_on = TIMESTEP_END
  []
  [nl_its]
    type = NumNonlinearIterations
    execute_on = TIMESTEP_END
  []
[]

[UserObjects]
  [rebound]
    type = Terminator
    expression = 'vel_y_avg > 0'
    fail_mode = HARD
    execute_on = TIMESTEP_END
    message = 'Slug COM axial velocity reversed. Rebound detected, stopping.'
  []
[]

[Executioner]
  type = Transient
  solve_type = NEWTON
  petsc_options_iname = '-pc_type'
  petsc_options_value = 'lu'
  line_search = 'default'
  nl_rel_tol = 1e-6
  nl_abs_tol = 1e-8
  nl_max_its = 25

  start_time = 0.0
  end_time = 150e-6
  # cap the adaptive step at the explicit run's timestep
  dtmax = 1e-8
  dtmin = 1e-11
  [TimeStepper]
    type = IterationAdaptiveDT
    dt = 1e-8
    optimal_iterations = 8
    growth_factor = 1.4
    cutback_factor = 0.5
  []
[]

[Outputs]
  [exodus]
    type = Exodus
    time_step_interval = 100
  []
  [csv]
    type = CSV
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [console]
    type = Console
    time_step_interval = 10
  []
[]
