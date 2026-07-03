# Axisymmetric (RZ) Taylor impact of shot CuH04_235.9 through the NEML2
# nodal-force path: total-Lagrangian, thermally-coupled (adiabatic)
# Johnson-Cook, explicit central difference with manage_state_advance.
#
# Goal: run to rebound and compare the final deformed profile against the
# experimental surface scan stl_results/CuH04_235.9.stl
# (final length 22.08 mm, foot radius ~9.06 mm, rear radius ~4.15 mm).

# timestep in seconds. Reference-element CFL is ~1.1e-7 s; elements at the
# foot crush to a fraction of their height, so run with ~20x margin.
dt = 5e-9

# impact velocity in m/s -- from the scan file name (experiment CuH04_235.9_003)
v = 235.9

# --- TRUE specimen geometry (shot CuH04): O 0.3 in x 1.5 in, full-hard copper ---
r = '${units 0.15 in -> m}'          # 0.3 in diameter  -> 0.15 in radius
slug_length = '${units 1.5 in -> m}' # 1.5 in length

# --- mesh resolution: ~0.48 mm square elements (8 across the radius) ---
nx = 8
ny = 80

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
[]

[Problem]
  extra_tag_matrices = 'mass'
  kernel_coverage_check = false
[]

[Variables]
  [disp_x]
  []
  [disp_y]
  []
[]

# set velocity in the -y direction via a nonzero OLD state: v_y = (current - old)/dt = -v
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

# rigid-wall anvil at y = 0, enforced NODE-WISE on the whole mesh (the standard
# explicit rigid-wall contact). A sideset traction is not enough at this impact
# severity: the crushed first element row collapses and the rows above punch
# through the pinned surface, tangling the mesh. The nodal penalty holds
# interior nodes too. k = 1e9 N/m per node: penalty frequency stays ~5x below
# the central-difference stability limit for the lightest (axis) nodes, and the
# static penetration at the ~kN/node contact force is ~1 um.
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

[Materials]
  [density]
    type = GenericConstantMaterial
    prop_names = 'density'
    prop_values = '${units 8960 kg/m^3}' # OFHC copper
  []
[]

# mass matrix kernels (total Lagrangian: reference-configuration mass is exact)
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
  input = 'johnson_cook_neml2_thermal_large_def.i'
  [all]
    executor_name = 'neml2'
    model = 'model'
    verbose = false
    manage_state_advance = true
    input_kernels = 'deformation_gradient'
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
  [deformation_gradient]
    type = NEML2DeformationGradientRZ
    assembly = 'assembly'
    fe = 'fe'
    to_neml2 = 'deformation_gradient'
  []
  [residual]
    type = NEML2StressDivergenceRZ
    assembly = 'assembly'
    fe = 'fe'
    executor = 'neml2'
    stress = 'pk1'
    residual = 'NONTIME'
  []
  # stop as soon as the slug's average axial velocity reverses sign (rebound).
  [rebound]
    type = Terminator
    expression = 'vel_y_avg > 0'
    fail_mode = HARD
    execute_on = TIMESTEP_END
    message = 'Slug COM axial velocity reversed -- rebound detected, stopping.'
  []
[]

[Postprocessors]
  # COM axial position (volume-averaged disp_y); reaches its minimum at rebound.
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
  # center-of-mass axial velocity (m/s); starts near -235.9, climbs through 0.
  [vel_y_avg]
    type = ParsedPostprocessor
    pp_names = 'd_disp_y'
    pp_symbols = 'dd'
    expression = 'dd / ${dt}'
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [max_dT]
    type = ElementExtremeMaterialProperty
    mat_prop = 'state/dT'
    value_type = max
    execute_on = 'TIMESTEP_END'
  []
  [max_ep]
    type = ElementExtremeMaterialProperty
    mat_prop = 'state/ep'
    value_type = max
    execute_on = 'TIMESTEP_END'
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
  # arrest is flow-stress-limited; cap generously, the Terminator stops us.
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
