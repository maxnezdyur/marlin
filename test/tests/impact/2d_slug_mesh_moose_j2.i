# timestep in seconds
dt = 1e-8

# initial downward velocity in m/s
v = 200

[GlobalParams]
  displacements = 'disp_x disp_y'
[]

[Problem]
  extra_tag_matrices = 'mass'
[]

[Mesh]
  type = GeneratedMesh
  dim = 2
  xmin = 0
  xmax = '${units 0.25 in -> m}'
  ymin = 0
  ymax = '${units 3 in -> m}'
  nx = 4
  ny = 20
[]

[Variables]
  [disp_x]
  []
  [disp_y]
  []
[]

[AuxVariables]
  [force_x]
  []
  [force_y]
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
[]

# initial -y velocity via nonzero OLD state: v_y = (current - old) / dt = -v
[ICs]
  [old_y]
    type = ConstantIC
    variable = disp_y
    value = '${fparse v*dt}'
    state = OLD
  []
[]

# simple penalty anvil at y < 0
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
    boundary = bottom
    use_displaced_mesh = true
  []
[]

[Materials]
  [density]
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
  [flow_stress]
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
    flow_stress_material = flow_stress
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
    second_order_vars = 'disp_x disp_y'
  []

  start_time = 0.0
  num_steps = 150
  dt = '${units ${dt} s}'
  dtmin = '${units ${dt} s}'
[]

[Outputs]
  execute_on = FINAL
  file_base = slug_2d
  show = 'disp_x disp_y force_x force_y'
  exodus = true
[]
