# Heating-identity check: with one quadrature point per element the elemental
# output equals the qp value, so the forward-Euler update of the temperature
# rise must satisfy, per element and per step, exactly:
#   dT_n - dT_{n-1} = scaling * s_n * (ep_n - ep_{n-1})
!include 'rz_thermal_neml2.i'

[NEML2]
  [all]
    auto_output := true
  []
[]

[Executioner]
  [Quadrature]
    order = CONSTANT
  []
[]

[Outputs]
  execute_on := 'INITIAL TIMESTEP_END'
  file_base := rz_thermal_identity_out
  show := ''
  exodus := false
  [exo]
    type = Exodus
    output_material_properties = true
  []
[]

# enforce the identity in CI: this material is zero up to float64 roundoff
[Materials]
  [identity_error]
    type = ParsedMaterial
    property_name = identity_error
    expression = 'abs((dT - dT_old) - 2.6090e-7 * s * (ep - ep_old))'
    material_property_names = 'dT:=state/dT dT_old:=Old[state/dT] s:=state/s ep:=state/ep ep_old:=Old[state/ep]'
  []
[]

[Postprocessors]
  [max_identity_error]
    type = ElementExtremeMaterialProperty
    mat_prop = identity_error
    value_type = max
    execute_on = 'TIMESTEP_END'
  []
[]

[Outputs]
  [csv]
    type = CSV
  []
[]
