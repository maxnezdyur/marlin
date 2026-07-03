# Matched-pair verification base: coupled thermo-mechanical Johnson-Cook
# (temperature rise integrated inside NEML2) on an axisymmetric slug.
# Shared by rz_thermal_neml2.i (nodal-force path) and
# rz_thermal_conventional.i (conventional NEML2 coupling).

# timestep in seconds
dt = 1e-7

# initial downward velocity in m/s
v = 200

[GlobalParams]
  displacements = 'disp_x disp_y'
[]

[Problem]
  extra_tag_matrices = 'mass'
[]

[Mesh]
  coord_type = RZ
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
  [axis]
    type = DirichletBC
    variable = disp_x
    boundary = left
    value = 0
  []
[]

[Materials]
  [density]
    type = StrainAdjustedDensity
    strain_free_density = '${units 8940 kg/m^3}'
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

[Executioner]
  type = Transient

  start_time = 0.0
  num_steps = 150
  dt = '${units ${dt} s}'
  dtmin = '${units ${dt} s}'
[]

[Outputs]
  execute_on = FINAL
  show = 'disp_x disp_y force_x force_y'
  exodus = true
[]
