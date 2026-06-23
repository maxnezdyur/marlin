# timestep in seconds
dt = 1e-8

# impact velocity in m/s (experiment CuH04_235.9_003 -> 235.9 m/s)
v = 235.9

# slug radius -- real specimen is Ø8 mm OFHC copper, so r = 4 mm
r = '${units 4 mm -> m}'

# slug length -- WORKING VALUE, confirm from experiment records (~30 mm)
slug_length = '${units 30 mm -> m}'

# impact tilt angle in degrees (this shot is flat-on => 0)
alpha = 0

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
    radii = '${r}'
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
    heights = '${slug_length}'
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
  # [elasticity_slug]
  #   type = ComputeIsotropicElasticityTensor
  #   youngs_modulus = ${units 70 GPa -> Pa}
  #   poissons_ratio = 0.28
  # []
  [slug_density]
    type = StrainAdjustedDensity
    strain_free_density = '${units 8960 kg/m^3}' # OFHC copper
  []
[]

# mechanics and mass matrix kernels
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
  [mass_z]
    type = MassMatrix
    density = density
    matrix_tags = 'mass'
    variable = disp_z
  []
[]

[NEML2]
  input = 'johnson_cook_neml2.i'
  [all]
    executor_name = 'neml2'
    model = 'model'
    verbose = true
    manage_state_advance = true
    input_kernels = 'neml2_strain'
    auto_output = true
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
  [neml2_strain]
    type = NEML2SmallStrain
    assembly = 'assembly'
    fe = 'fe'
    to_neml2 = 'neml2_strain'
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
    second_order_vars = 'disp_x disp_y disp_z'
    assembly = 'assembly'
    fe = 'fe'
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
