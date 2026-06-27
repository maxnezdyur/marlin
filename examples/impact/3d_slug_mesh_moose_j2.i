# timestep in seconds
dt = 1e-8

# impact velocity in m/s (experiment CuH04_235.9_003 -> 235.9 m/s)
v = 235.9

# --- TRUE specimen geometry (MEML2 shot CuH04): Ø0.3 in x 1.5 in, full-hard pure copper ---
r = '${units 0.15 in -> m}'          # 0.3 in diameter  -> 0.15 in radius
slug_length = '${units 1.5 in -> m}' # 1.5 in length

# impact tilt angle in degrees (this shot is flat-on => 0)
alpha = 0

# --- mesh resolution (COARSE on purpose: cheap enough to run long to rebound) ---
n_sectors = 4
n_rings = 2
n_layers = 15

[GlobalParams]
  displacements = 'disp_x disp_y disp_z'
[]

[Problem]
  extra_tag_matrices = 'mass'
[]

# variables
[Variables]
  [disp_x]
  []
  [disp_y]
  []
  [disp_z]
  []
[]

[AuxVariables]
  [force_x]
  []
  [force_y]
  []
  [force_z]
  []
[]

[AuxKernels]
  [force_x]
    type = TagVectorAux
    v = disp_x
    variable = force_x
    vector_tag = NONTIME
  []
  [force_y]
    type = TagVectorAux
    v = disp_y
    variable = force_y
    vector_tag = NONTIME
  []
  [force_z]
    type = TagVectorAux
    v = disp_z
    variable = force_z
    vector_tag = NONTIME
  []
[]

# cylindrical slug mesh
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
  [back_face]
    type = SideSetsAroundSubdomainGenerator
    block = 1
    input = impact_face
    new_boundary = back_face
    normal = '0 1 0'
  []
  # cant the slug for oblique impact: rotate alpha degrees about z (first Euler angle).
  # must come AFTER the sidesets so the normal-based detection still sees the y-aligned cylinder.
  [tilt]
    type = TransformGenerator
    input = back_face
    transform = ROTATE
    vector_value = '${alpha} 0 0'
  []
  # raise the slug so the lowest tilted corner of the impact face just touches y=0,
  # matching the flat-on zero-gap start and avoiding initial penetration of the anvil.
  [standoff]
    type = TransformGenerator
    input = tilt
    transform = TRANSLATE
    vector_value = '0 ${fparse r * sin(abs(alpha) * pi / 180)} 0'
  []
[]

# set velocity in the -y direction
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

# simple penalty anvil BC
[Functions]
  [anvil]
    type = ParsedFunction
    expression = 'if(y<0, -y*${units 20000 GPa -> Pa}, 0)'
  []
[]
[BCs]
  [anvil]
    type = FunctionNeumannBC
    function = anvil
    variable = disp_y
    boundary = impact_face
    use_displaced_mesh = true
  []
[]

# material properties
[Materials]
  [slug_density]
    type = StrainAdjustedDensity
    strain_free_density = '${units 8960 kg/m^3}' # OFHC copper
  []
  [elasticity_tensor]
    type = ComputeIsotropicElasticityTensor
    youngs_modulus = '${units 117 GPa -> Pa}' # OFHC copper
    poissons_ratio = 0.34
  []
  [strain]
    type = ComputeIncrementalStrain
    implicit = false
  []

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
    # OFHC copper Johnson-Cook parameters matching johnson_cook_neml2.i
    expression = 'A:=99.7e6; B:=262.8e6; C:=0.029; n:=0.23; ep_dot_0:=1.0; ep_min:=1e-10;
                  ep_safe:=sqrt(ep*ep+ep_min*ep_min);
                  ep_dot:=if(dt=0, 1, max(0,(ep-ep_old)/dt)); ep_dot_star:=max(1.0,ep_dot/ep_dot_0);
                  (A+B*ep_safe^n)*(1+C*log(ep_dot_star))'
    material_property_names = 'ep:=effective_plastic_strain ep_old:=Old[effective_plastic_strain]'
    additional_derivative_symbols = 'ep'
    extra_symbols = dt
    derivative_order = 2
    compute = false
    epsilon = 0.0
    evalerror_behavior = error
    output_properties = flow_stress
    outputs = exodus
  []
  [plasticity]
    type = FlowStressMaterialPlasticityStressUpdate
    flow_stress_material = slug_flow_stress
    line_search = false
    outputs = exodus
    output_properties = effective_plastic_strain
  []
  [stress]
    type = ComputeMultipleInelasticStress
    inelastic_models = plasticity
    perform_finite_strain_rotations = false
    tangent_operator = elastic
  []
[]

# mechanics and mass matrix kernels
[Kernels]
  [stress_x]
    type = DynamicStressDivergenceTensors
    alpha = 0
    component = 0
    implicit = false
    use_displaced_mesh = false
    variable = disp_x
  []
  [stress_y]
    type = DynamicStressDivergenceTensors
    alpha = 0
    component = 1
    implicit = false
    use_displaced_mesh = false
    variable = disp_y
  []
  [stress_z]
    type = DynamicStressDivergenceTensors
    alpha = 0
    component = 2
    implicit = false
    use_displaced_mesh = false
    variable = disp_z
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
  [mass_z]
    type = MassMatrix
    density = density
    matrix_tags = 'mass'
    variable = disp_z
  []
[]

[Postprocessors]
  [temperature]
    type = ConstantPostprocessor
    value = 300
  []
  # COM axial position (volume-averaged disp_y); reaches its minimum at rebound.
  [disp_y_avg]
    type = ElementAverageValue
    variable = disp_y
    execute_on = 'INITIAL TIMESTEP_END'
  []
  # per-step change in COM position (m); finite-difference source for velocity.
  [d_disp_y]
    type = ChangeOverTimePostprocessor
    postprocessor = disp_y_avg
    change_with_respect_to_initial = false
    execute_on = 'INITIAL TIMESTEP_END'
  []
  # center-of-mass axial velocity (m/s) = d(COM disp)/dt. Starts near -235.9,
  # climbs through 0 (total velocity stops) and goes positive on rebound.
  [vel_y_avg]
    type = ParsedPostprocessor
    pp_names = 'd_disp_y'
    pp_symbols = 'dd'
    expression = 'dd / ${dt}'
    execute_on = 'INITIAL TIMESTEP_END'
  []
[]

[UserObjects]
  # stop as soon as the slug's average axial velocity reverses sign (rebound).
  # fail_mode=HARD calls terminateSolve() -> graceful end of the run (exit 0).
  [rebound]
    type = Terminator
    expression = 'vel_y_avg > 0'
    fail_mode = HARD
    execute_on = TIMESTEP_END
    message = 'Slug COM axial velocity reversed -- rebound detected, stopping.'
  []
[]

[Executioner]
  type = Transient
  [TimeIntegrator]
    type = ExplicitMixedOrder
    mass_matrix_tag = 'mass'
    use_constant_mass = true
    second_order_vars = 'disp_x disp_y disp_z'
  []

  start_time = 0.0
  # Arrest is flow-stress-limited (~150 us / ~15000 steps to stop, a bit more to
  # rebound); cap generously, the rebound Terminator stops us at the reversal.
  num_steps = 25000
  dt = '${units ${dt} s}'
  dtmin = '${units ${dt} s}'
[]

[Outputs]
  # exodus is heavy -> only every 100 steps; CSV is cheap scalars -> every step
  # so the full velocity-vs-time rebound history is captured.
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
