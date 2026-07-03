# Total-Lagrangian Johnson-Cook: the isothermal copper JC radial-return chain
# operating on Green-Lagrange strain / PK2 stress conjugates,
#   E = 1/2 (F^T F - I),  radial return in (E, S),  P = F S.
# Outputs both PK2 as a full R2 ('state/neml2_stress', for the conventional
# coupling) and PK1 ('state/pk1', for the NEML2 nodal-force path).
# Johnson-Cook rate- AND temperature-dependent plasticity for NEML2 -- ADIABATIC variant.
#
# DRAFT scaffold (Claude) for the coupled thermomechanical slug. It adds an
# adiabatic temperature state to the existing isothermal johnson_cook_neml2.i:
#
#   dT/dt = beta/(rho*c_p) * sigma_vm * ep_dot          (Taylor-Quinney heating)
#   sigma_y = [A + B*ep^n] * (1 - T*^m),  T* = (T-T_ref)/(T_melt-T_ref)
#
# Conduction is omitted on purpose: over the ~120 us run the thermal diffusion
# length sqrt(alpha*t) ~ 0.11 mm << element size (~2 mm), so the slug is adiabatic.
# => NO heat-conduction PDE, NO HEAT_TRANSFER module, NO MOOSE thermal kernels.
#
# Temperature is LAGGED one explicit step (jc_flowrate reads old_state/T) so the
# radial-return system stays 1-unknown (state/ep) and acyclic. At dt=1e-8 s the
# lag error is negligible.
#
# SEEDING SOLVED by reformulating in temperature RISE: state/dT = T - 300 K.
# NEML2 zero-inits state, and dT=0 is exactly correct at t=0. Johnson-Cook is
# reparameterized to consume the rise directly:
#   T* = (T - 300)/(1338 - 300) == dT/1038  ->  reference_temperature=0,
#   melting_temperature=1038, temperature = state/dT~1.
# Absolute temperature for plots = 300 K + dT.

[Solvers]
  [newton]
    type = NewtonWithLineSearch
    # thermal softening stiffens the late-time return map (large ep, Theta < 0.9):
    # more iterations + slightly relaxed tolerances than the isothermal variant.
    # abs_tol 1e-7 is still ~1e3x tighter than a typical per-step ep increment.
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
    use_temperature = false
    flow_rate = 'state/ep_rate'
    A = 99.7e6
    B = 262.8e6
    n = 0.23
    C = 0.029
    m = 0.98
    reference_strain_rate = 1.0
    reference_temperature = 0    # dT formulation: T* = dT/1038 == (T-300)/(1338-300)
    melting_temperature = 1038   # dT formulation (see reference_temperature)
    initial_plastic_strain = 0.0 # match johnson_cook_neml2.i for the beta = 0 equivalence test
  []
  [integrate_ep]
    type = ScalarBackwardEulerTimeIntegration
    variable = 'state/ep'
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
    models = 'gl_strain trial_state radial_return ep_rate plastic_update stress_update vonmises pk2_r2 pk1'
    additional_outputs = 'state/s state/ep state/S state/Ep neml2_stress'
  []
[]

[EquationSystems]
  [return_map_sys]
    type = NonlinearSystem
    model = 'rate'
    unknowns = 'state/ep'
  []
[]
