# Axisymmetric (RZ) Taylor impact of shot CuH04_235.9 with MOOSE-native
# Simo-Hughes multiplicative J2 plasticity (neo-Hookean elasticity,
# F-bar stabilization) and a Johnson-Cook consistency flow stress with
# rate and (adiabatic, lagged) temperature dependence.
#
# Independent-physics cross-check for the NEML2 multiplicative run
# (rz_slug_thermal_mult.i): same formulation family (multiplicative
# split, isochoric flow), different code path, different rate form
# (consistency yield vs inverted overstress) and elasticity
# (neo-Hookean vs SVK-on-Ee) -- expected to agree closely but not
# bitwise.

dt = 5e-9
v = 235.9
r = '${units 0.15 in -> m}'
slug_length = '${units 1.5 in -> m}'
nx = 8
ny = 80

# JC constants, full-hard OFHC copper (CuH04)
A = 99.7e6
B = 262.8e6
n = 0.23
C = 0.029
m = 0.98
ep0 = 1.0 # reference strain rate (1/s)
ipe = 0.37 # initial plastic strain (full-hard)
# adiabatic heating: beta/(rho*c_p) = 0.9/(8960*385) K.m^3/J
heat = 2.6090e-7

[Mesh]
  coord_type = RZ
  [slug]
    type = GeneratedMeshGenerator
    dim = 2
    nx = ${nx}
    ny = ${ny}
    xmin = 0
    xmax = ${r}
    ymin = 0
    ymax = ${slug_length}
  []
[]

[GlobalParams]
  displacements = 'disp_x disp_y'
  large_kinematics = true
  stabilize_strain = true
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
    value = '${fparse v*dt}'
    state = OLD
  []
[]

[NodalKernels]
  [anvil]
    type = PenaltyRigidWallNodalKernel
    variable = disp_y
    component = 1
    penalty = 1e9
    wall_position = 0
  []
[]
[BCs]
  [axis]
    type = DirichletBC
    variable = disp_x
    value = 0
    boundary = left
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
  [density]
    type = GenericConstantMaterial
    prop_names = 'density'
    prop_values = '${units 8960 kg/m^3}'
  []
  [elasticity]
    type = ComputeIsotropicElasticityTensor
    youngs_modulus = 117e9
    poissons_ratio = 0.34
  []
  [strain]
    type = ComputeLagrangianStrainAxisymmetricCylindrical
  []
  # JC consistency flow stress: rate via backward-difference of ep (Old[] + dt),
  # thermal softening via the LAGGED adiabatic temperature rise dT (T* = dT/1038),
  # matching the NEML2 model's one-step temperature lag.
  [flow_stress]
    type = DerivativeParsedMaterial
    property_name = flow_stress
    expression = '(${A} + ${B} * (effective_plastic_strain + ${ipe})^${n})'
                 ' * (1 + ${C} * log(max((effective_plastic_strain - ep_old) / dt, ${ep0}) / ${ep0}))'
                 ' * (1 - min(max(dT_old / 1038, 0), 0.9999)^${m})'
    material_property_names = 'effective_plastic_strain ep_old:=Old[effective_plastic_strain] dT_old:=Old[dT]'
    additional_derivative_symbols = 'effective_plastic_strain'
    extra_symbols = 'dt'
    derivative_order = 2
    compute = false
  []
  [stress]
    type = ComputeSimoHughesJ2PlasticityStress
    flow_stress_material = flow_stress
  []
  [vonmises]
    type = RankTwoInvariant
    invariant = 'VonMisesStress'
    rank_two_tensor = cauchy_stress
    property_name = vonmises
  []
  # adiabatic temperature rise, forward-Euler like the NEML2 model:
  # dT_n+1 = dT_n + heat * sigma_vm * (ep_n+1 - ep_n)
  [temperature_rise]
    type = ParsedMaterial
    property_name = dT
    expression = 'dT_old + ${heat} * vonmises * (effective_plastic_strain - ep_old)'
    material_property_names = 'dT_old:=Old[dT] vonmises effective_plastic_strain ep_old:=Old[effective_plastic_strain]'
  []
[]

[UserObjects]
  [rebound]
    type = Terminator
    expression = 'vel_y_avg > 0'
    fail_mode = HARD
    execute_on = TIMESTEP_END
    message = 'Slug COM axial velocity reversed -- rebound detected, stopping.'
  []
[]

[Postprocessors]
  [disp_y_avg]
    type = ElementAverageValue
    variable = disp_y
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [d_disp_y]
    type = ChangeOverTimePostprocessor
    postprocessor = disp_y_avg
    change_with_respect_to_initial = false
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [vel_y_avg]
    type = ParsedPostprocessor
    pp_names = 'd_disp_y'
    pp_symbols = 'dd'
    expression = 'dd / ${dt}'
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [max_dT]
    type = ElementExtremeMaterialProperty
    mat_prop = 'dT'
    value_type = max
    execute_on = 'TIMESTEP_END'
  []
  [max_ep]
    type = ElementExtremeMaterialProperty
    mat_prop = 'effective_plastic_strain'
    value_type = max
    execute_on = 'TIMESTEP_END'
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
  num_steps = 60000
  dt = '${units ${dt} s}'
  dtmin = '${units ${dt} s}'
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
    time_step_interval = 100
  []
[]
