# F-bar variant of rz_jc_mult_neml2.i: the batched NEML2 path applies the
# volumetric element-average correction in NEML2DeformationGradientRZ.
!include 'rz_jc_mult_neml2.i'

[UserObjects]
  [deformation_gradient]
    stabilize_strain = true
  []
[]

[Outputs]
  file_base := rz_jc_mult_fbar_out
[]
