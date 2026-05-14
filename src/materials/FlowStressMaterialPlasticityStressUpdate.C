/**********************************************************************/
/*                     DO NOT MODIFY THIS HEADER                      */
/*            Marlin, a Fourier spectral solver for MOOSE             */
/*                                                                    */
/*            Copyright 2024 Battelle Energy Alliance, LLC            */
/*                        ALL RIGHTS RESERVED                         */
/**********************************************************************/

#include "FlowStressMaterialPlasticityStressUpdate.h"

registerMooseObject("MarlinApp", FlowStressMaterialPlasticityStressUpdate);

InputParameters
FlowStressMaterialPlasticityStressUpdate::validParams()
{
  InputParameters params = DerivativeMaterialInterface<RadialReturnStressUpdate>::validParams();
  params.addClassDescription("J2 radial-return plasticity using a flow stress supplied by another "
                             "material property.");
  params.addRequiredParam<MaterialName>("flow_stress_material",
                                        "The material defining the flow stress");
  params.addParam<MaterialPropertyName>("flow_stress", "flow_stress", "The flow stress property");
  params.set<std::string>("effective_inelastic_strain_name") = "effective_plastic_strain";
  return params;
}

FlowStressMaterialPlasticityStressUpdate::FlowStressMaterialPlasticityStressUpdate(
    const InputParameters & parameters)
  : DerivativeMaterialInterface<RadialReturnStressUpdate>(parameters),
    _flow_stress_material(nullptr),
    _ep_name(_base_name + getParam<std::string>("effective_inelastic_strain_name")),
    _flow_stress_name(_base_name + getParam<MaterialPropertyName>("flow_stress")),
    _flow_stress(getMaterialPropertyByName<Real>(_flow_stress_name)),
    _dflow_stress_dep(getDefaultMaterialPropertyByName<Real, false>(
        derivativePropertyName(_flow_stress_name, {_ep_name}))),
    _yield_condition(-1.0),
    _plastic_strain(declareProperty<RankTwoTensor>(_base_name + "plastic_strain")),
    _plastic_strain_old(getMaterialPropertyOld<RankTwoTensor>(_base_name + "plastic_strain"))
{
  _check_range = true;
}

void
FlowStressMaterialPlasticityStressUpdate::initialSetup()
{
  _flow_stress_material = &getMaterial("flow_stress_material");
}

void
FlowStressMaterialPlasticityStressUpdate::initQpStatefulProperties()
{
  RadialReturnStressUpdate::initQpStatefulProperties();
  _plastic_strain[_qp].zero();
}

void
FlowStressMaterialPlasticityStressUpdate::propagateQpStatefulProperties()
{
  propagateQpStatefulPropertiesRadialReturn();
  _plastic_strain[_qp] = _plastic_strain_old[_qp];
}

void
FlowStressMaterialPlasticityStressUpdate::computeStressInitialize(
    const Real & effective_trial_stress, const RankFourTensor & elasticity_tensor)
{
  RadialReturnStressUpdate::computeStressInitialize(effective_trial_stress, elasticity_tensor);
  _plastic_strain[_qp] = _plastic_strain_old[_qp];
  updateFlowStress(0.0);
  _yield_condition = effective_trial_stress - _flow_stress[_qp];
}

Real
FlowStressMaterialPlasticityStressUpdate::computeResidual(const Real & effective_trial_stress,
                                                          const Real & scalar)
{
  mooseAssert(_yield_condition != -1.0,
              "The yield condition was not updated by computeStressInitialize");

  if (_yield_condition <= 0.0)
    return 0.0;

  updateFlowStress(scalar);
  return (effective_trial_stress - _flow_stress[_qp]) / _three_shear_modulus - scalar;
}

Real
FlowStressMaterialPlasticityStressUpdate::computeDerivative(const Real & /*effective_trial_stress*/,
                                                            const Real & scalar)
{
  if (_yield_condition <= 0.0)
    return 1.0;

  updateFlowStress(scalar);
  return -_dflow_stress_dep[_qp] / _three_shear_modulus - 1.0;
}

void
FlowStressMaterialPlasticityStressUpdate::iterationFinalize(const Real & scalar)
{
  if (_yield_condition > 0.0)
    updateFlowStress(scalar);
}

void
FlowStressMaterialPlasticityStressUpdate::computeStressFinalize(
    const RankTwoTensor & plastic_strain_increment)
{
  _plastic_strain[_qp] += plastic_strain_increment;
}

void
FlowStressMaterialPlasticityStressUpdate::updateFlowStress(const Real & scalar)
{
  _effective_inelastic_strain[_qp] = _effective_inelastic_strain_old[_qp] + scalar;
  _flow_stress_material->computePropertiesAtQp(_qp);
}
