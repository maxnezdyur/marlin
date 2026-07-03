/**********************************************************************/
/*                     DO NOT MODIFY THIS HEADER                      */
/*            Marlin, a Fourier spectral solver for MOOSE             */
/*                                                                    */
/*            Copyright 2024 Battelle Energy Alliance, LLC            */
/*                        ALL RIGHTS RESERVED                         */
/**********************************************************************/

#pragma once

#include "NodalKernel.h"

/**
 * Tangential Coulomb friction companion of PenaltyRigidWallNodalKernel.
 * Applied to a TANGENTIAL displacement variable: while a node penetrates the
 * wall (position along the normal component below the wall plane), a friction
 * force F_t = -mu * penalty * |penetration| * tanh(v_t / v_reg) opposes the
 * tangential nodal velocity. The tanh regularization keeps the force smooth
 * through v_t = 0; v_reg should sit well below typical slip velocities and
 * high enough that the effective damping mu*penalty*|pen|/v_reg stays inside
 * the explicit stability limit 2 m_node / dt.
 */
class RigidWallCoulombFrictionNodalKernel : public NodalKernel
{
public:
  static InputParameters validParams();

  RigidWallCoulombFrictionNodalKernel(const InputParameters & parameters);

protected:
  virtual Real computeQpResidual() override;

  /// Normal-direction penalty stiffness per node (N/m), same as the wall kernel
  const Real _penalty;

  /// Coulomb friction coefficient
  const Real _mu;

  /// Wall plane position along the normal component
  const Real _wall_position;

  /// Coordinate component of the wall normal (0=x, 1=y, 2=z)
  const unsigned int _normal_component;

  /// Regularization velocity for the tanh slip law (m/s)
  const Real _v_reg;

  /// Displacement along the wall normal at this node
  const VariableValue & _normal_disp;

  /// Previous-step value of the tangential displacement (dofValuesOlder under explicit; see .C)
  const VariableValue & _u_old;
};
