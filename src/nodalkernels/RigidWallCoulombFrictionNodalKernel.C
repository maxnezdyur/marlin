/**********************************************************************/
/*                     DO NOT MODIFY THIS HEADER                      */
/*            Marlin, a Fourier spectral solver for MOOSE             */
/*                                                                    */
/*            Copyright 2024 Battelle Energy Alliance, LLC            */
/*                        ALL RIGHTS RESERVED                         */
/**********************************************************************/

#include "RigidWallCoulombFrictionNodalKernel.h"

registerMooseObject("MarlinApp", RigidWallCoulombFrictionNodalKernel);

InputParameters
RigidWallCoulombFrictionNodalKernel::validParams()
{
  InputParameters params = NodalKernel::validParams();
  params.addClassDescription(
      "Regularized Coulomb friction against a rigid wall, applied node-wise to a tangential "
      "displacement variable: F_t = -mu * penalty * |penetration| * tanh(v_t / "
      "regularization_velocity) while the node is below the wall plane. Pair with "
      "PenaltyRigidWallNodalKernel using the same penalty.");
  params.addRequiredRangeCheckedParam<Real>(
      "penalty", "penalty > 0", "Normal penalty stiffness per node (N/m), same as the wall.");
  params.addRequiredRangeCheckedParam<Real>("mu", "mu >= 0", "Coulomb friction coefficient.");
  params.addParam<Real>("wall_position", 0.0, "Wall plane position along the normal component.");
  params.addRequiredRangeCheckedParam<unsigned int>(
      "normal_component",
      "normal_component <= 2",
      "Coordinate component of the wall normal (0=x, 1=y, 2=z).");
  params.addRangeCheckedParam<Real>(
      "regularization_velocity",
      1.0,
      "regularization_velocity > 0",
      "Slip-velocity scale of the tanh regularization (m/s). Choose well below typical slip "
      "velocities but large enough that mu*penalty*|penetration|/regularization_velocity stays "
      "below the explicit damping stability limit 2*m_node/dt.");
  params.addRequiredCoupledVar("normal_variable",
                               "Displacement variable along the wall normal at this node.");
  return params;
}

RigidWallCoulombFrictionNodalKernel::RigidWallCoulombFrictionNodalKernel(
    const InputParameters & parameters)
  : NodalKernel(parameters),
    _penalty(getParam<Real>("penalty")),
    _mu(getParam<Real>("mu")),
    _wall_position(getParam<Real>("wall_position")),
    _normal_component(getParam<unsigned int>("normal_component")),
    _v_reg(getParam<Real>("regularization_velocity")),
    _normal_disp(coupledValue("normal_variable")),
    _u_old(_var.dofValuesOlder())
{
}

Real
RigidWallCoulombFrictionNodalKernel::computeQpResidual()
{
  const auto pen = (*_current_node)(_normal_component) + _normal_disp[_qp] - _wall_position;
  if (pen >= 0 || _dt <= 0)
    return 0.0;

  // Under explicit central difference the residual is evaluated at the previous
  // solution, so dofValuesOld() equals _u there; the older state gives u_{n-1}.
  const auto v_t = (_u[_qp] - _u_old[_qp]) / _dt;
  // friction force opposes slip; residual = -F
  return _mu * _penalty * (-pen) * std::tanh(v_t / _v_reg);
}
