# Elastic block dropped onto a rigid wall (PenaltyRigidWallNodalKernel) while
# sliding tangentially at 2 m/s (RigidWallCoulombFrictionNodalKernel, mu = 0.3).
# During the bounce the Coulomb force decelerates the tangential motion; the
# gold verifies the tangential momentum loss (the vertical bounce is covered by
# the penalty_rigid_wall test).

[Mesh]
  [block]
    type = GeneratedMeshGenerator
    dim = 2
    nx = 2
    ny = 2
    xmin = 0
    xmax = 0.1
    ymin = 0.005
    ymax = 0.105
  []
[]

[GlobalParams]
  displacements = 'disp_x disp_y'
[]

[Problem]
  extra_tag_matrices = 'mass'
[]

[Variables]
  [disp_x]
  []
  [disp_y]
  []
[]

# downward 5 m/s + tangential 2 m/s via OLD states
[ICs]
  [current]
    type = ConstantIC
    variable = disp_y
    value = 0
    state = CURRENT
  []
  [old]
    type = ConstantIC
    variable = disp_y
    value = '${fparse 5 * 1e-5}'
    state = OLD
  []
  [current_x]
    type = ConstantIC
    variable = disp_x
    value = 0
    state = CURRENT
  []
  [old_x]
    type = ConstantIC
    variable = disp_x
    value = '${fparse -2 * 1e-5}'
    state = OLD
  []
[]

[NodalKernels]
  [wall]
    type = PenaltyRigidWallNodalKernel
    variable = disp_y
    component = 1
    penalty = 1e7
    wall_position = 0
  []
  [friction]
    type = RigidWallCoulombFrictionNodalKernel
    variable = disp_x
    normal_variable = disp_y
    normal_component = 1
    penalty = 1e7
    mu = 0.3
    wall_position = 0
    regularization_velocity = 0.1
  []
[]

[Kernels]
  [sdx]
    type = StressDivergenceTensors
    variable = disp_x
    component = 0
    use_displaced_mesh = false
  []
  [sdy]
    type = StressDivergenceTensors
    variable = disp_y
    component = 1
    use_displaced_mesh = false
  []
  [mass_x]
    type = MassMatrix
    density = density
    matrix_tags = 'mass'
    variable = disp_x
  []
  [mass_y]
    type = MassMatrix
    density = density
    matrix_tags = 'mass'
    variable = disp_y
  []
[]

[Materials]
  [C]
    type = ComputeIsotropicElasticityTensor
    youngs_modulus = 1e9
    poissons_ratio = 0.3
  []
  [strain]
    type = ComputeSmallStrain
    implicit = false
  []
  [stress]
    type = ComputeLinearElasticStress
    implicit = false
  []
  [density]
    type = GenericConstantMaterial
    prop_names = 'density'
    prop_values = 1000
  []
[]

[Postprocessors]
  [disp_y_avg]
    type = ElementAverageValue
    variable = disp_y
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [disp_y_min]
    type = NodalExtremeValue
    variable = disp_y
    value_type = min
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [disp_x_avg]
    type = ElementAverageValue
    variable = disp_x
    execute_on = 'INITIAL TIMESTEP_END'
  []
[]

[Executioner]
  type = Transient
  [TimeIntegrator]
    type = ExplicitMixedOrder
    mass_matrix_tag = 'mass'
    use_constant_mass = true
    second_order_vars = 'disp_x disp_y'
  []
  start_time = 0.0
  num_steps = 300
  dt = 1e-5
[]

[Outputs]
  csv = true
[]
