/**********************************************************************/
/*                     DO NOT MODIFY THIS HEADER                      */
/*            Marlin, a Fourier spectral solver for MOOSE             */
/*                                                                    */
/*            Copyright 2024 Battelle Energy Alliance, LLC            */
/*                        ALL RIGHTS RESERVED                         */
/**********************************************************************/

#pragma once

#include "DerivativeMaterialInterface.h"
#include "RadialReturnStressUpdate.h"

class FlowStressMaterialPlasticityStressUpdate
  : public DerivativeMaterialInterface<RadialReturnStressUpdate>
{
public:
  static InputParameters validParams();

  FlowStressMaterialPlasticityStressUpdate(const InputParameters & parameters);

  virtual void initialSetup() override;

protected:
  virtual void initQpStatefulProperties() override;
  virtual void propagateQpStatefulProperties() override;

  virtual void computeStressInitialize(const Real & effective_trial_stress,
                                       const RankFourTensor & elasticity_tensor) override;
  virtual Real computeResidual(const Real & effective_trial_stress, const Real & scalar) override;
  virtual Real computeDerivative(const Real & effective_trial_stress, const Real & scalar) override;
  virtual void iterationFinalize(const Real & scalar) override;
  virtual void computeStressFinalize(const RankTwoTensor & plastic_strain_increment) override;

  void updateFlowStress(const Real & scalar);

  MaterialBase * _flow_stress_material;
  const std::string _ep_name;
  const MaterialPropertyName _flow_stress_name;
  const MaterialProperty<Real> & _flow_stress;
  const MaterialProperty<Real> & _dflow_stress_dep;
  Real _yield_condition;

  MaterialProperty<RankTwoTensor> & _plastic_strain;
  const MaterialProperty<RankTwoTensor> & _plastic_strain_old;
};
