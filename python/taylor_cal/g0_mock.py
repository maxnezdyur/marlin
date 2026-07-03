"""G0-LITE plumbing gate: synthetic self-calibration with a MOCK forward
model (no FEM). Validates emulator + objective + inference end-to-end.

Analytic toy Taylor-profile family over zs in [0, 22] mm:

    r(zs) = r0 + a1 * exp(-zs / l1) + a2 * exp(-(zs / l2)^2)   [mm]

with a smooth, injective-enough map from a 4-parameter theta subset
(A [Pa], B [Pa], n [-], mu [-]) to (a1, l1, a2, l2):

    a1 = 2.2 * sqrt(99.7e6 / A) * s(v)     foot bump amplitude, ~1-4 mm
    l1 = 2.0 + 3.0 * (mu - 0.03) / 0.27    foot decay length, 2-5 mm
    a2 = 0.8 * (262.8e6 / B)^0.4 * s(v)    mid bump amplitude, ~0.5-1.4 mm
    l2 = 4.0 + 8.0 * (n - 0.1) / 0.4       mid bump width, 4-12 mm
    s(v) = (v / 235.9)^1.5                 velocity sensitivity

Mock scalars: L = 26.0 - 1.2*a1 - 0.8*a2 [mm], foot_r = r0 + a1 + a2 [mm].

Pipeline: theta_true -> synthetic noisy target (heteroscedastic
sigma(zs) = 0.02 + 0.03*exp(-zs/2) mm) -> Sobol DOE over priors -> mock
profiles -> ProfileEmulator/ScalarEmulator -> emcee -> recovery check:
theta_true inside the central 95% credible interval per dim AND posterior
sd < 0.5 * prior sd for at least 2 dims. Corner plot to
_qa_check/g0_corner.png.

Run:  PYTHONPATH=marlin/python python -m taylor_cal.g0_mock
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .emulator import ProfileEmulator, ScalarEmulator, ShotEmulator
from .inference import corner_plot, diagnostics, run_mcmc
from .objective import PRIORS, make_log_prob, prior_bounds, sample_prior

R0 = 3.8            # shank radius of the mock profile family [mm]
ZS_MAX = 22.0       # axial extent [mm]
V_NOM = 235.9       # nominal impact velocity [m/s]
PARAM_NAMES = ("A", "B", "n", "mu")


# ------------------------------------------------------------ mock forward


def mock_coeffs(theta, v=V_NOM):
    """(A [Pa], B [Pa], n, mu) -> (a1, l1, a2, l2) [mm]; theta (4,) or (q,4)."""
    th = np.atleast_2d(np.asarray(theta, dtype=float))
    A, B, n, mu = th[:, 0], th[:, 1], th[:, 2], th[:, 3]
    s = (np.asarray(v, dtype=float) / V_NOM) ** 1.5
    a1 = 2.2 * np.sqrt(99.7e6 / A) * s
    l1 = 2.0 + 3.0 * (mu - 0.03) / 0.27
    a2 = 0.8 * (262.8e6 / B) ** 0.4 * s
    l2 = 4.0 + 8.0 * (n - 0.1) / 0.4
    return a1, l1, a2, l2


def mock_profile(theta, zs, v=V_NOM):
    """Mock radius profile r(zs) [mm]; (q, m) for 2-D theta, (m,) for 1-D."""
    a1, l1, a2, l2 = mock_coeffs(theta, v)
    zs = np.asarray(zs, dtype=float)
    r = (R0
         + a1[:, None] * np.exp(-zs[None, :] / l1[:, None])
         + a2[:, None] * np.exp(-((zs[None, :] / l2[:, None]) ** 2)))
    return r[0] if np.asarray(theta).ndim == 1 else r


def mock_scalars(theta, v=V_NOM):
    """Mock (L, foot_r) [mm]."""
    a1, _, a2, _ = mock_coeffs(theta, v)
    L = 26.0 - 1.2 * a1 - 0.8 * a2
    foot_r = R0 + a1 + a2
    if np.asarray(theta).ndim == 1:
        return float(L[0]), float(foot_r[0])
    return L, foot_r


# ----------------------------------------------------------------- target


@dataclass
class MockTarget:
    """Minimal duck-typed calibration target (see objective.py contract)."""

    zs: np.ndarray          # (m,) distance from foot [mm]
    r: np.ndarray           # (m,) measured radius [mm]
    sigma: np.ndarray       # (m,) noise sd [mm]
    trusted: np.ndarray     # (m,) bool mask
    velocity: float         # impact velocity [m/s]
    L_est: Optional[float] = None    # final length [mm]
    sigma_L: float = 0.05            # length sd [mm]
    foot_r: Optional[float] = None   # foot max radius [mm]


def make_synthetic_target(theta_true, seed: int = 0) -> MockTarget:
    """Noisy synthetic 'scan' from the mock forward model at theta_true."""
    rng = np.random.default_rng(seed)
    zs = np.arange(0.0, ZS_MAX + 1e-9, 0.25)
    sigma = 0.02 + 0.03 * np.exp(-zs / 2.0)          # heteroscedastic [mm]
    r_obs = mock_profile(theta_true, zs) + rng.normal(0.0, sigma)
    L_true, foot_true = mock_scalars(theta_true)
    return MockTarget(
        zs=zs, r=r_obs, sigma=sigma,
        trusted=zs >= 0.6,                            # mimic foot-lip mask
        velocity=V_NOM,
        L_est=L_true + rng.normal(0.0, 0.05), sigma_L=0.05,
        foot_r=foot_true + rng.normal(0.0, 0.1))


# ------------------------------------------------------------------- gate


def main(n_doe: int = 60, nsteps: int = 5000, seed: int = 7,
         outdir: Optional[str] = None, cv: bool = False) -> dict:
    """Run the G0-LITE gate; returns a dict with pass/fail and the table."""
    if outdir is None:
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "_qa_check")
    os.makedirs(outdir, exist_ok=True)

    # ---- truth (off-center but well inside the priors) and target
    theta_true = np.array([99.7e6 * 10**0.10,        # A [Pa]
                           262.8e6 * 10**-0.15,      # B [Pa]
                           0.32,                     # n
                           0.12])                    # mu
    target = make_synthetic_target(theta_true, seed=seed)

    # ---- Sobol DOE over priors (+ velocity spread) -> mock training set
    theta_doe = sample_prior(PARAM_NAMES, n=n_doe, seed=seed)
    rng = np.random.default_rng(seed + 1)
    v_doe = V_NOM + rng.uniform(-3.0, 3.0, n_doe)    # [m/s]
    X = np.column_stack([theta_doe, v_doe])
    profiles = mock_profile(theta_doe, target.zs, v_doe)
    L_doe, foot_doe = mock_scalars(theta_doe, v_doe)

    # ---- emulators
    pe = ProfileEmulator(seed=seed).fit(X, profiles, target.zs)
    Le = ScalarEmulator(seed=seed).fit(X, L_doe)
    Fe = ScalarEmulator(seed=seed).fit(X, foot_doe)
    shot = ShotEmulator(profile=pe, L=Le, foot_r=Fe)
    print(f"[g0] emulator: {pe.n_modes} PCA modes, "
          f"{100 * pe.explained:.2f}% variance explained")
    if cv:
        from .emulator import cv_report
        rep = cv_report(pe, X, profiles, k=5, seed=seed)
        print(f"[g0] profile 5-fold CV RMSE: mean "
              f"{rep['rmse_mm'].mean():.4f} mm, "
              f"max {rep['rmse_mm'].max():.4f} mm")

    # ---- MCMC on x = (A, B, n, mu, sigma_d)
    log_prob = make_log_prob([target], [shot], param_names=PARAM_NAMES)
    bounds = prior_bounds(PARAM_NAMES)               # sigma_d appended
    ndim = len(bounds)
    sampler = run_mcmc(log_prob, ndim=ndim, bounds=bounds, nsteps=nsteps,
                       seed=seed)
    diag = diagnostics(sampler)
    chain = diag["chain"]
    print(f"[g0] acceptance fraction {diag['acceptance_fraction']:.3f}; "
          f"autocorr time {diag.get('autocorr_time')}")

    # ---- recovery table + checks
    labels = list(PARAM_NAMES) + ["sigma_d"]
    truths = list(theta_true) + [None]
    prior_sd = sample_prior(PARAM_NAMES, n=1 << 16, seed=123).std(axis=0)

    lo, med, hi = np.percentile(chain, [2.5, 50.0, 97.5], axis=0)
    post_sd = chain.std(axis=0)
    covered, narrower = [], []
    lines = [f"{'dim':<8}{'true':>12}{'median':>12}{'2.5%':>12}"
             f"{'97.5%':>12}{'cov':>5}{'sd_post/sd_prior':>18}"]
    for j, name in enumerate(labels):
        if name == "sigma_d":
            lines.append(f"{name:<8}{'0 (true)':>12}{med[j]:>12.4g}"
                         f"{lo[j]:>12.4g}{hi[j]:>12.4g}{'-':>5}{'-':>18}")
            continue
        t = theta_true[j]
        cov = bool(lo[j] <= t <= hi[j])
        ratio = post_sd[j] / prior_sd[j]
        covered.append(cov)
        narrower.append(ratio < 0.5)
        lines.append(f"{name:<8}{t:>12.4g}{med[j]:>12.4g}{lo[j]:>12.4g}"
                     f"{hi[j]:>12.4g}{str(cov):>5}{ratio:>18.3f}")
    table = "\n".join(lines)
    print(table)

    ok_cov = all(covered)
    ok_narrow = sum(narrower) >= 2
    passed = ok_cov and ok_narrow
    print(f"[g0] coverage (all dims in 95% CI): {ok_cov}; "
          f"narrowed >=2 dims (<0.5x prior sd): {ok_narrow} "
          f"({sum(narrower)}/{len(narrower)})")
    print(f"[g0] GATE {'PASS' if passed else 'FAIL'}")

    png = corner_plot(chain, labels, os.path.join(outdir, "g0_corner.png"),
                      truths=truths)
    print(f"[g0] corner plot: {png}")

    return {"passed": passed, "coverage": ok_cov, "narrowed": ok_narrow,
            "table": table, "chain": chain, "theta_true": theta_true,
            "corner_png": png, "diagnostics": {k: v for k, v in diag.items()
                                               if k != "chain"}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-doe", type=int, default=60)
    ap.add_argument("--nsteps", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--cv", action="store_true",
                    help="also run 5-fold CV of the profile emulator")
    a = ap.parse_args()
    res = main(n_doe=a.n_doe, nsteps=a.nsteps, seed=a.seed, outdir=a.outdir,
               cv=a.cv)
    raise SystemExit(0 if res["passed"] else 1)
