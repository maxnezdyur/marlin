# Total-Lagrangian, thermally-coupled Johnson-Cook for NEML2 -- ADIABATIC.
#
# Merger of the two verified test models:
#  - test/tests/impact/johnson_cook_neml2_large_def.i  (Green-Lagrange / PK2
#    conjugates, P = F S, machine-precision match vs the Lagrangian kernels)
#  - test/tests/impact/johnson_cook_neml2_thermal.i    (adiabatic temperature
#    rise state/dT with Taylor-Quinney heating, lagged one explicit step)
#
#   E = 1/2 (F^T F - I),  radial return in (E, S),  P = F S
#   dT/dt = beta/(rho*c_p) * sigma_vm * ep_dot
#   sigma_y = [A + B*ep^n] * (1 + C ln(ep_dot/ep0)) * (1 - T*^m)
#
# Temperature-rise formulation: state/dT = T - 300 K, zero-init exactly right.
#   T* = (T - 300)/(1338 - 300) == dT/1038  ->  reference_temperature = 0,
#   melting_temperature = 1038, temperature = 'state/dT~1' (lagged).
#
# Conduction omitted on purpose: over the ~200 us impact the thermal diffusion
# length sqrt(alpha*t) ~ 0.15 mm << element size, so the slug is adiabatic.
#
# Full-hard OFHC copper (H04), matching shot CuH04_235.9:
#   E = 117 GPa, nu = 0.34; JC A = 99.7 MPa, B = 262.8 MPa, n = 0.23,
#   C = 0.029, m = 0.98 (Appl. Sci. 2020, 10, 2423).
#
# Variables the MOOSE action touches use bare root-axis names
# (deformation_gradient, pk1) -- the input_kernels/derivatives lookup
# compares literal names.

[Solvers]
  [newton]
    type = NewtonWithLineSearch
    # thermal softening stiffens the late-time return map (large ep, Theta < 0.9):
    # more iterations + slightly relaxed tolerances than the isothermal variant.
    abs_tol = 1e-7
    rel_tol = 1e-8
    max_its = 250
    linear_solver = 'lu'
  []
  [lu]
    type = DenseLU
  []
[]

[Models]
  [gl_strain]
    type = GreenLagrangeStrain
    deformation_gradient = 'deformation_gradient'
    strain = 'E'
  []
  [trial_elastic_strain]
    type = SR2LinearCombination
    to = 'state/Ee'
    from = 'E state/Ep~1'
    weights = '1 -1'
  []
  [cauchy_stress]
    type = LinearIsotropicElasticity
    coefficient_types = 'YOUNGS_MODULUS POISSONS_RATIO'
    coefficients = '117e9 0.34' # OFHC copper
    strain = 'state/Ee'
    stress = 'state/S'
  []
  [flow_direction]
    type = AssociativeJ2FlowDirection
    mandel_stress = 'state/S'
    flow_direction = 'forces/N'
  []
  [trial_state]
    type = ComposedModel
    models = 'trial_elastic_strain cauchy_stress flow_direction'
  []

  [ep_rate]
    type = ScalarVariableRate
    variable = 'state/ep'
  []
  [plastic_strain_rate]
    type = AssociativePlasticFlow
    flow_direction = 'forces/N'
    flow_rate = 'state/ep_rate'
    plastic_strain_rate = 'state/Ep_rate'
  []
  [plastic_strain]
    type = SR2ForwardEulerTimeIntegration
    variable = 'state/Ep'
  []
  [plastic_update]
    type = ComposedModel
    models = 'ep_rate plastic_strain_rate plastic_strain'
  []
  [elastic_strain]
    type = SR2LinearCombination
    to = 'state/Ee'
    from = 'E state/Ep'
    weights = '1 -1'
  []
  [stress_update]
    type = ComposedModel
    models = 'elastic_strain cauchy_stress'
  []

  [vonmises]
    type = SR2Invariant
    invariant_type = 'VONMISES'
    tensor = 'state/S'
    invariant = 'state/s'
  []
  [jc_flowrate]
    type = JohnsonCookFlowRate
    vonmises_stress = 'state/s'
    equivalent_plastic_strain = 'state/ep'
    use_temperature = true
    temperature = 'state/dT~1' # lagged one step (NEML2 history notation)
    flow_rate = 'state/ep_rate'
    A = 99.7e6
    B = 262.8e6
    n = 0.23
    C = 0.029
    m = 0.98
    reference_strain_rate = 1.0
    reference_temperature = 0    # dT formulation: T* = dT/1038 == (T-300)/(1338-300)
    melting_temperature = 1038   # dT formulation (see reference_temperature)
    initial_plastic_strain = 0.37 # CuH04 full-hard; 0 for annealed
  []
  [integrate_ep]
    type = ScalarBackwardEulerTimeIntegration
    variable = 'state/ep'
  []

  # adiabatic plastic heating: T_rate = beta/(rho*c_p) * sigma_vm * ep_dot
  #   beta = 0.9 (Taylor-Quinney), rho = 8960 kg/m^3, c_p = 385 J/(kg.K)  [OFHC Cu]
  #   scaling = 0.9 / (8960 * 385) = 2.6090e-7  K.m^3/J
  [plastic_heating]
    type = ScalarMultiplication
    from = 'state/s state/ep_rate'
    to = 'state/dT_rate'
    scaling = 2.6090e-7
  []
  [integrate_T]
    type = ScalarForwardEulerTimeIntegration
    variable = 'state/dT' # auto-uses state/dT_rate and state/dT~1
  []

  [rate]
    type = ComposedModel
    models = "plastic_update stress_update vonmises jc_flowrate integrate_ep"
  []
  [predictor]
    type = ConstantExtrapolationPredictor
    unknowns_Scalar = 'state/ep'
  []
  [radial_return]
    type = ImplicitUpdate
    equation_system = 'return_map_sys'
    solver = 'newton'
    predictor = 'predictor'
  []

  [pk2_r2]
    type = SR2ToR2
    input = 'state/S'
    output = 'neml2_stress'
  []
  [pk1]
    type = R2Multiplication
    A = 'deformation_gradient'
    B = 'neml2_stress'
    to = 'pk1'
  []
  [model]
    type = ComposedModel
    # plastic_heating + integrate_T run AFTER the return map (post-solve),
    # consuming the converged state/s and state/ep_rate.
    models = 'gl_strain trial_state radial_return ep_rate plastic_update stress_update vonmises plastic_heating integrate_T pk2_r2 pk1'
    additional_outputs = 'state/s state/ep state/S state/Ep state/dT'
  []
[]

[EquationSystems]
  [return_map_sys]
    type = NonlinearSystem
    model = 'rate'
    unknowns = 'state/ep'
  []
[]
