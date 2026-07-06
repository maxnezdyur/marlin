# Running the Johnson-Cook calibration (taylor_cal)

Bayesian calibration of the Johnson-Cook parameters against a scanned
post-mortem Taylor specimen. Method in one line: Sobol design over the priors
→ ~96 forward simulations → PCA-GP emulator → Gaussian likelihood with a
marginalized model-discrepancy term → emcee posterior → posterior median
re-run through the real forward model. Full theory:
[`python/taylor_cal/METHOD.md`](../python/taylor_cal/METHOD.md).

## Layout

```
python/
  taylor_cal/            the package (importable, campaign-agnostic)
    scan_qa.py           STL -> calibration target (axis-corrected profile + noise model)
    forward.py           one forward run: CLI build, execution, profile/metric extraction
    campaign.py          Sobol DOE + parallel batch runner with a parquet ledger
    emulator.py          PCA-GP profile emulator, scalar GPs, feasibility classifier
    objective.py         priors, likelihood, posterior
    inference.py         MAP (differential evolution) + emcee driver + diagnostics
    METHOD.md            method write-up
  campaign_r0/           round 0: 6 params incl. friction mu (done)
  campaign_r1_nofric/    round 1: 5 params, mu pinned to 0 (done, current best)
```

Each campaign directory is self-contained: `run_doe.py`, `fit_g2.py`,
`ledger.parquet` (one row per run), `runs/` (per-run outputs), the posterior
chain/median/corner plot, and `median_check/` (the posterior median re-run).

## Prerequisites

- A built `marlin-opt` (see [README.md](README.md)).
- Python with: `numpy scipy pandas pyarrow scikit-learn emcee corner matplotlib`.
  (The MOOSE conda env lacks sklearn/emcee — use a separate env for the fit.)
- The scan STL: `examples/impact/stl_results/CuH04_235.9.stl`
  (filename convention `<shotID>_<velocity>.stl`, binary STL, mm).
- **Edit the hardcoded paths** in `python/taylor_cal/forward.py` for your
  checkout: `IMPACT_DIR` and `DEFAULT_EXE` point at absolute paths. Same for
  the STL path in each campaign's `fit_g2.py`.

## Step 1 — DOE (the expensive part)

```bash
cd python/campaign_r1_nofric        # or a new campaign dir
python run_doe.py                   # ~4.5 h with 8 parallel workers
```

What it does: 96 Sobol points over the priors (`campaign.PRIORS`), each run
~21 min serial, 8 at a time (`max_parallel=8`, one BLAS/torch thread each).
Constitutive constants are injected by writing a per-run copy of the NEML2
model file (`johnson_cook_neml2_mult_thermal_cal.i` templating, scoped to the
`[jc_flowrate]` block); velocity and `mu` go on the command line.

The ledger is append-only and content-hashed: you can kill and re-run
`run_doe.py` at any time and it resumes, never repeating a finished point.
Expect a substantial infeasible fraction (runaway adiabatic extrusion at
extreme parameter corners): round 1 finished 43 ok / 40 blowup / 13 error —
that's normal, blowups train the feasibility classifier.

Monitor progress:

```bash
python -c "import pandas as pd; df = pd.read_parquet('ledger.parquet'); \
           print(len(df), dict(df.status.value_counts()))"
```

## Step 2 — Fit (emulator + MCMC)

```bash
python fit_g2.py                    # ~15 min
```

Prints the emulator cross-validation gate (profile CV RMSE should be well
under 0.1 mm — round 1: 0.032 mm mean), the MCMC acceptance fraction
(healthy: 0.2-0.5), and the posterior table. Writes `g2_chain.npy`,
`g2_median.json`, `g2_corner.png`.

## Step 3 — Median check (close the loop)

Re-run the posterior median through the **real** forward model so the quoted
fit quality never rests on the emulator:

```bash
python -c "
import json, sys; sys.path.insert(0, '..')
from taylor_cal import forward
th = json.load(open('g2_median.json'))
res = forward.run_forward(th, 235.9, 'median_check', fidelity='RI')
print(res.status, res.L, res.foot_r)"
```

Then compare profiles (silhouette + residual figure):

```bash
python plot_final.py                # campaign_r1_nofric; adapt for a new campaign
```

## Results so far

Profile RMS against the trusted scan stations (CuH04, 235.9 m/s):

| configuration | RMS |
|---|---|
| hand calibration (mu = 0.2) | 0.159 mm |
| round-0 posterior median (mu = 0.036) | 0.081 mm |
| round-1 frictionless posterior median | **0.069 mm** |

Round-1 median (current best, `campaign_r1_nofric/g2_median.json`):

```
A = 1.286e8 Pa   B = 3.08e8 Pa   n = 0.4715   C = 0.02235   ipe = 0.1408   mu = 0
```

Two caveats worth knowing before quoting numbers:

1. **Parameter degeneracy.** One shot at one velocity cannot separate the
   A-B-n hardening trio from the rate sensitivity C (posterior correlations
   up to 0.68). Two very different parameter sets fit equally well.
   Multi-velocity shots are the designed remedy.
2. **Rear-shank systematic.** Every model shares a -0.10 mm residual on the
   undeformed rear section — the physical specimen is slightly fatter than
   the nominal 3.81 mm radius the mesh uses. Re-referencing the initial
   radius from the scan's rear would remove this common-mode bias.

## Starting a new campaign (new shot / new parameter set)

1. Copy a campaign dir; point `fit_g2.py` at the new STL
   (`scan_qa.build_target(<stl>, r0_mm=..., L0_mm=...)`).
2. In `run_doe.py`: set the velocity, choose the free parameters (subset of
   `campaign.PRIORS`; pin the rest by writing fixed values into each theta,
   as `campaign_r1_nofric` does with `th['mu'] = 0.0`).
3. Keep the fit's `PARAMS` tuple consistent between `run_doe.py` and
   `fit_g2.py`.
4. Fresh ledger, fresh `runs/` — nothing collides with old campaigns (the
   run hash includes theta, velocity, fidelity, and the input file sha).
