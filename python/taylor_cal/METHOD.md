# Bayesian calibration of Johnson–Cook parameters from Taylor-impact scans

**Method class:** emulator-based Bayesian calibration — a Kennedy–O'Hagan-style
inverse method in which an expensive forward model is replaced by a
Gaussian-process surrogate trained on a space-filling design, a Gaussian
likelihood with an explicit (marginalized) model-discrepancy term compares the
surrogate to the measured specimen geometry, and the posterior over the
constitutive parameters is drawn by ensemble MCMC. Implementation lives in
`marlin/python/taylor_cal/`; campaign drivers and results in
`marlin/python/campaign_r0/` (with friction) and
`marlin/python/campaign_r1_nofric/` (frictionless).

The calibration data is a single post-mortem geometry: the CuH04 specimen
(OFHC copper, nominal r0 = 3.81 mm, L0 = 38.1 mm) recovered from a
235.9 m/s Taylor anvil impact and laser-scanned to an STL.

## 1. Unknowns and priors

Johnson–Cook flow stress with adiabatic heating integrated inside the NEML2
model (thermal exponent m fixed at 0.98):

sigma_y = (A + B ep^n) (1 + C ln(epdot/epdot0)) (1 - T*^m)

| parameter | meaning | prior |
|---|---|---|
| A | initial yield [Pa] | LogNormal10(99.7e6, 0.2 dec) |
| B | hardening modulus [Pa] | LogNormal10(262.8e6, 0.2 dec) |
| n | hardening exponent | Uniform(0.1, 0.5) |
| C | rate sensitivity | Uniform(0.01, 0.05) |
| ipe | initial plastic strain (prior cold work) | Uniform(0.1, 0.5) |
| mu | Coulomb friction at the anvil | Uniform(0.03, 0.3) — round 0 only; pinned to 0 in round 1 |
| sigma_d | model discrepancy [mm] | HalfNormal(0.15) |

`sigma_d` is a global profile-level jitter added in quadrature to the
measurement and emulator variances. It is *sampled* alongside theta and
marginalized, so the posterior widths honestly absorb whatever the model
class cannot reproduce (a lightweight stand-in for a full KOH discrepancy
process). Priors and inverse-CDF sampling: `objective.py` (`PRIORS`,
`LogNormal10`, `Uniform`, `HalfNormal`).

## 2. Target construction from the scan (`scan_qa.py`)

The STL is reduced to an axis-corrected radial profile with a per-station
noise model — not raw max-radius, which inflates under specimen tilt/bend:

1. Binary STL parsed directly (no mesh library); axis of revolution is X;
   the foot end is the end with the larger near-end radius.
2. 0.25 mm axial slices; per slice an algebraic (Kasa) least-squares circle
   fit about the local centroid gives centerline c(zs), radius R(zs), and
   radial fit rms s(zs). Circle fitting removes the axis-wander artifact
   (0.2+ mm for CuH04).
3. Artifact audit: rear end-cap (cut face) detection, volume-of-revolution
   audit yielding a true-length estimate L_est ± sigma_L, axis-wander span.
4. Trusted mask: drop zs < 0.6 mm (foot-lip mixing), the last 1 mm before a
   detected cut, and any slice with fit rms > 0.15 mm. Noise model
   sigma(zs) = max(fit rms, 0.02 mm floor).

Output is a `CalTarget` with (zs, R, sigma, trusted, L_est, sigma_L, foot_r)
plus a QA figure (`write_qa_png`). For CuH04: L_est = 22.41 ± 0.44 mm,
foot_r = 8.633 mm, 80 trusted stations.

## 3. Forward model (`forward.py`)

Production explicit-dynamics model, not a surrogate physics: axisymmetric
(RZ) slug, multiplicative finite-strain Johnson–Cook in NEML2 through the
batched nodal-force path, reduced integration (1-pt quadrature) with
Flanagan–Belytschko hourglass control, penalty rigid-wall contact
(+ Coulomb friction kernel in round 0), central-difference time integration
(`rz_slug_thermal_mult_ri.i`, fidelity tag "RI", ~21 min/run on 1 thread).

Theta injection: constitutive constants are substituted into a per-run copy
of the NEML2 model file (regex scoped to the `[jc_flowrate]` block, `ipe ->
initial_plastic_strain`) passed via the `NEML2/all/input` CLI override;
velocity and `mu` go on the command line. Setting `mu = 0` makes the friction
force identically zero — equivalent to removing the kernel.

Extracted observables per run: the displaced outer-boundary contour resampled
and binned to a max-radius profile r(zs) (120 bins), final length L, foot
radius (zs < 1 mm), rear radius, arrest time, end velocity, max effective
plastic strain and temperature rise. Runs are classified `ok` (arrested,
|v_end| < 1 m/s, max ep < 8), `marginal` (arrested, localized melt),
`blowup` (adiabatic extrusion runaway: |v_end| > 100 or ep > 100), or
`error`; the classification feeds the feasibility classifier below.

## 4. Design of experiments (`campaign.py`)

96-point scrambled Sobol sequence in the unit hypercube mapped through the
prior inverse CDFs (so the design is space-filling *in prior probability*,
not in a box). Batch runner: `ProcessPoolExecutor` (8 workers, 1 BLAS/torch
thread each), append-only parquet ledger with content-hash caching
(theta + velocity + fidelity + input-file sha), so campaigns are re-entrant
and never re-run an evaluated point. Round-1 outcome: 43 ok / 40 blowup /
13 error — the frictionless model runs away on roughly half the prior box,
which the feasibility classifier turns into posterior support truncation.

## 5. Emulator (`emulator.py`)

Higdon-style PCA-GP for the profile plus scalar GPs, all on standardized
inputs X = (theta, velocity):

- **ProfileEmulator**: DOE profiles interpolated to a common 90-point zs
  grid (0.7–20 mm), centered/scaled, SVD; keep the leading modes covering
  99.5 % variance (cap 6; 4 modes in round 1). One GP per mode weight —
  Matern-5/2 ARD kernel + white noise, `normalize_y`, 2 restarts. Predictive
  variance = propagated per-mode GP variance + PCA truncation residual, so
  emulator uncertainty enters the likelihood per station.
- **ScalarEmulator**: same GP recipe for L and foot_r.
- **FeasibilityClassifier**: GP classifier (RBF) on ok/marginal vs blowup
  over *all* DOE points; the likelihood is gated to -inf where
  p(feasible) < 0.5, keeping the sampler out of the runaway region.
- **Validation gate**: 5-fold CV of the profile emulator; holdout RMSE per
  station must sit below the scan sigma / 0.1 mm. Round 1: mean 0.032 mm,
  max 0.142 mm on 43 training runs.

## 6. Likelihood and posterior (`objective.py`)

Independent Gaussian blocks per shot, all in mm:

- **Profile**: emulated r(zs) vs scan R(zs) on the trusted mask, decimated to
  ~40 evenly spaced stations (decorrelates neighboring 0.25 mm slices);
  per-station variance sigma_scan^2 + sigma_GP^2 + sigma_d^2.
- **Length**: L_est with variance sigma_L^2 + sigma_GP^2.
- **Foot radius**: foot_r with variance (0.1 mm)^2 + sigma_GP^2.

log posterior = log priors + sum of blocks, with the feasibility gate
applied first. Everything is vectorized over batches of points so both the
MAP search and emcee run with `vectorize=True`.

## 7. Sampling (`inference.py`)

1. **MAP**: scipy `differential_evolution` on the negative log posterior
   inside the prior box (vectorized, no polish).
2. **MCMC**: emcee affine-invariant ensemble, nwalkers = max(32, 4·ndim),
   12 000 steps, walkers initialized at the MAP + 2 % box-width Gaussian
   scatter (resampled until all start at finite posterior). First third
   discarded as burn-in.
3. **Diagnostics**: acceptance fraction (0.46 in round 1), autocorrelation
   time, optional arviz R-hat/ESS, corner plot.

## 8. Closing the loop (emulator-error check)

The posterior median is re-run through the *true* forward model
(`median_check/`) and scored against the scan directly — profile RMS on the
trusted stations — so the reported fit quality never rests on the surrogate.
Round 0 also re-ran the DOE-independent hand calibration for reference.

## 9. Results summary

| configuration | profile RMS vs scan |
|---|---|
| hand calibration (mu = 0.2) | 0.159 mm |
| round-0 posterior median (mu = 0.036) | 0.081 mm |
| round-0 median re-run with mu = 0 | 0.067 mm |
| round-1 frictionless posterior median | 0.069 mm |

Round-0 medians: A = 8.48e7, B = 3.00e8, n = 0.387, C = 0.0375, ipe = 0.140,
mu = 0.036 (pinned at the prior floor). Round-1 (mu = 0): A = 1.29e8,
B = 3.08e8, n = 0.47, C = 0.022, ipe = 0.141, sigma_d = 0.052 mm.

Findings and caveats:

- **Friction**: the data rejects Coulomb friction at this shot — round 0
  drove mu to its prior floor, and simply zeroing it improved the round-0
  median by ~15 %. The frictionless recalibration matches that (67 vs 69 um
  is far inside sigma_d), so the production model drops the friction kernel.
- **Degeneracy**: a strong A–B–n–C ridge (|corr| up to 0.68) means one shot
  at one velocity cannot separate the hardening trio from rate sensitivity;
  two very different thetas give indistinguishable profiles. Multi-velocity
  shots are the designed remedy (C decouples across impact speeds).
- **Prior edge**: the round-1 posterior for n presses the 0.5 upper bound
  (84th percentile at 0.49) — the box is informative there.
- **Systematic floor**: all models share a −0.10 mm residual on the
  undeformed rear shank; the physical specimen is slightly fatter than the
  nominal 3.81 mm radius the mesh uses. Re-referencing r0 from the scan's
  rear section would remove a common-mode bias from every RMS above.
