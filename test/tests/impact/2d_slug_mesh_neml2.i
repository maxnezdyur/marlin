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
[]

[Kernels]
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

[NEML2]
  input = 'johnson_cook_neml2.i'
  [all]
    executor_name = 'neml2'
    model = 'model'
    verbose = false
    keep_tensors_on_device = true
    moose_input_kernels = 'strain'

    moose_input_types = 'POSTPROCESSOR POSTPROCESSOR POSTPROCESSOR'
    moose_inputs = '     time          time          temperature'
    neml2_inputs = '     forces/t      old_forces/t  forces/T'
  []
[]

[Postprocessors]
  [time]
    type = TimePostprocessor
    execute_on = 'INITIAL TIMESTEP_BEGIN'
    outputs = 'none'
  []
  [temperature]
    type = ConstantPostprocessor
    value = 300
  []
[]

[UserObjects]
  [assembly]
    type = NEML2Assembly
  []
  [fe]
    type = NEML2FEInterpolation
    assembly = 'assembly'
  []
  [strain]
    type = NEML2SmallStrain
    assembly = 'assembly'
    fe = 'fe'
    to_neml2 = 'forces/E'
  []
  [residual]
    type = NEML2StressDivergence
    assembly = 'assembly'
    fe = 'fe'
    executor = 'neml2'
    stress = 'state/S'
    residual = 'NONTIME'
  []
[]

[Executioner]
  type = Transient

  [TimeIntegrator]
    type = NEML2CentralDifference
    mass_matrix_tag = 'mass'
    use_constant_mass = true
    second_order_vars = 'disp_x disp_y'
    assembly = 'assembly'
    fe = 'fe'
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
