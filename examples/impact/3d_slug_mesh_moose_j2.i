# timestep in seconds
dt = 1e-8

# velocity in m/s
v = 200

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
    num_sectors = 8 # adjust for mesh resolution
    radii = '${units 0.25 in -> m}'
    rings = 10 # adjust for mesh resolution
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
    heights = '${units 3 in -> m}'
    num_layers = 50 # adjust for mesh resolution
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
    strain_free_density = '${units 2700 kg/m^3}'
  []
  [elasticity_tensor]
    type = ComputeIsotropicElasticityTensor
    youngs_modulus = '${units 70 GPa -> Pa}'
    poissons_ratio = 0.28
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
  num_steps = 1000
  dt = '${units ${dt} s}'
  dtmin = '${units ${dt} s}'
[]

[Outputs]
  time_step_interval = 50
  exodus = true
[]
