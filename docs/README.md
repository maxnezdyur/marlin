# Taylor-impact / NEML2 explicit dynamics — handoff docs

This folder documents the NEML2 explicit-dynamics work in this repo (marlin,
branch `slug_runs`): the axisymmetric and large-deformation NEML2 force paths,
the Taylor-anvil impact simulations, and the Bayesian calibration of the
Johnson-Cook model against scanned specimens.

| doc | contents |
|---|---|
| [neml2_rz_path.md](neml2_rz_path.md) | The axisymmetric (RZ) NEML2 nodal-force path: objects, input blocks, verification tests |
| [neml2_large_deformation.md](neml2_large_deformation.md) | Total-Lagrangian / multiplicative finite strain, F-bar, reduced integration + hourglass control, contact — and the production impact input |
| [calibration.md](calibration.md) | The Bayesian calibration (optimization): how to run the DOE, the fit, and the median check; where results live |

Theory write-up for the calibration method:
[`python/taylor_cal/METHOD.md`](../python/taylor_cal/METHOD.md).

## Prerequisites

1. **MOOSE fork/branch.** The NEML2 explicit-dynamics objects live in the
   MOOSE fork `github.com/maxnezdyur/moose`, branch **`exp_dyn_hourglass`**
   (one commit on top of PR #32936's branch). marlin must be built against
   that checkout. (`exp_dyn_implicit` additionally carries the implicit
   reduced-integration work; not needed for anything in this folder.)

2. **Environment** (local machine): conda env from the INL channel,

   ```bash
   conda create -n moose moose-dev -c https://conda.software.inl.gov/public
   conda activate moose
   ```

3. **Build** (from the marlin repo root, with MOOSE checked out as a sibling
   or at `MOOSE_DIR`):

   ```bash
   make -j 8
   ```

## Quick start — run the production impact simulation

```bash
cd examples/impact
../../marlin-opt -i rz_slug_thermal_mult_ri.i
```

This is the calibrated CuH04 shot: 235.9 m/s copper slug, multiplicative
Johnson-Cook with adiabatic heating, reduced integration, rigid-anvil contact.
Serial runtime is ~20 min; it stops itself at rebound (~100 µs simulated) via
a Terminator watching the slug's mean axial velocity. Outputs: an Exodus file
(deformed shape) and a CSV of postprocessor histories (velocity, max plastic
strain, max temperature rise).

Useful command-line overrides (HIT syntax, appended to the command):

```bash
v=200                                  # impact velocity [m/s]
Executioner/num_steps=2000             # short run for smoke-testing
Outputs/file_base=my_run               # output name
```

## Verification tests

The whole force path is covered by matched-pair regression tests that compare
the batched NEML2 path against conventional MOOSE assembly at machine
precision:

```bash
./run_tests --re impact -j 2      # marlin tests (test/tests/impact/)
```

and in the MOOSE checkout, the module-side tests:

```bash
cd modules/solid_mechanics
./run_tests --re "hourglass|explicit_dynamics" -j 4
```

All of these must pass before pushing changes to either repo.
