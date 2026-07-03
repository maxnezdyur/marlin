# F-bar variant of rz_jc_mult_conventional.i: stabilize_strain on the strain
# material (the kernels' flag only affects the never-assembled Jacobian).
!include 'rz_jc_mult_conventional.i'

[Materials]
  [strain]
    stabilize_strain = true
  []
[]

[Kernels]
  [sdx]
    stabilize_strain = true
  []
  [sdy]
    stabilize_strain = true
  []
[]
