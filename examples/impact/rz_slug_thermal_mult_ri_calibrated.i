# Explicit RZ production run at the calibrated posterior median, frictionless.
# Wraps rz_slug_thermal_mult_ri.i and overrides the two hand-era settings:
# the NEML2 model file (calibrated constants) and the anvil friction (the
# calibration rejects friction; mu = 0 makes the kernel force identically
# zero). This is the exact configuration behind the validation figures.
#
# Run:  ../../marlin-opt -i rz_slug_thermal_mult_ri_calibrated.i

!include 'rz_slug_thermal_mult_ri.i'

[NEML2]
  input := 'johnson_cook_neml2_mult_thermal_calibrated.i'
[]

[NodalKernels]
  [anvil_friction]
    mu := 0
  []
[]
