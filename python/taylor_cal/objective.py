"""Priors, likelihood, and posterior for JC calibration (spec Sections 5 & 7).

Per shot s, independent Gaussian blocks (all lengths in mm):

- profile: emulated r(zs; theta, v_s) vs R_exp on the trusted mask, decimated
  to ~40 quasi-independent stations (even in zs), with variance
  sigma_scan(zs)^2 + sigma_GP(zs)^2 + sigma_d^2;
- length L: variance sigma_L^2 + sigma_GP^2;
- foot max radius: variance (0.1 mm)^2 + sigma_GP^2.

sigma_d is the global model-discrepancy jitter, HalfNormal(0.15 mm)
hyperprior, marginalized in the MCMC: the sampled vector is
x = (theta..., sigma_d) with sigma_d as the LAST component.

Targets are duck-typed; each must expose:
    zs (m,) mm, r (m,) mm, sigma (m,) mm, trusted (m,) bool, velocity m/s,
    and optionally L_est mm, sigma_L mm, foot_r mm.
Emulators is a list parallel to targets of emulator.ShotEmulator (or any
object with .profile / .L / .foot_r / .feasibility of matching interfaces).

Every function accepts a single point (1-D x) or a batch (2-D x, one row per
point) so emcee can run with vectorize=True.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import erfinv

_LN10 = np.log(10.0)
_L2PI = np.log(2.0 * np.pi)


# ------------------------------------------------------------------ priors


@dataclass(frozen=True)
class Uniform:
    """Uniform prior on [lo, hi] (physical units)."""

    lo: float
    hi: float

    def logpdf(self, x):
        x = np.asarray(x, dtype=float)
        out = np.full(x.shape, -np.log(self.hi - self.lo))
        out = np.where((x >= self.lo) & (x <= self.hi), out, -np.inf)
        return out

    def ppf(self, u):
        return self.lo + np.asarray(u, dtype=float) * (self.hi - self.lo)

    def bounds(self, q: float = 0.995):
        return (self.lo, self.hi)


@dataclass(frozen=True)
class LogNormal10:
    """Lognormal in base-10: log10(x) ~ N(log10(median), sd_dec^2).

    sd_dec is the standard deviation in decades (spec: 0.2 dec for A, B).
    """

    median: float
    sd_dec: float

    def logpdf(self, x):
        x = np.asarray(x, dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            l10 = np.log10(np.where(x > 0.0, x, np.nan))
            z = (l10 - np.log10(self.median)) / self.sd_dec
            lp = (-0.5 * z**2 - np.log(self.sd_dec)
                  - 0.5 * _L2PI - np.log(x * _LN10))
        return np.where(x > 0.0, lp, -np.inf)

    def ppf(self, u):
        u = np.asarray(u, dtype=float)
        z = np.sqrt(2.0) * erfinv(2.0 * u - 1.0)
        return 10.0 ** (np.log10(self.median) + self.sd_dec * z)

    def bounds(self, q: float = 0.995):
        return (float(self.ppf(1.0 - q)), float(self.ppf(q)))


@dataclass(frozen=True)
class HalfNormal:
    """HalfNormal(scale) on x >= 0 (spec: sigma_d ~ HalfNormal(0.15 mm))."""

    scale: float

    def logpdf(self, x):
        x = np.asarray(x, dtype=float)
        lp = (0.5 * np.log(2.0 / np.pi) - np.log(self.scale)
              - 0.5 * (x / self.scale) ** 2)
        return np.where(x >= 0.0, lp, -np.inf)

    def ppf(self, u):
        u = np.asarray(u, dtype=float)
        return self.scale * np.sqrt(2.0) * erfinv(u)

    def bounds(self, q: float = 0.995):
        return (0.0, float(self.ppf(q)))


#: Spec Section 5 priors (A, B in Pa; the rest dimensionless; sigma_d in mm).
PRIORS = {
    "A": LogNormal10(99.7e6, 0.2),
    "B": LogNormal10(262.8e6, 0.2),
    "n": Uniform(0.1, 0.5),
    "C": Uniform(0.01, 0.05),
    "ipe": Uniform(0.1, 0.5),
    "mu": Uniform(0.03, 0.3),
    "sigma_d": HalfNormal(0.15),
}

DEFAULT_PARAMS = ("A", "B", "n", "C", "ipe", "mu")


def prior_bounds(param_names=DEFAULT_PARAMS, include_sigma_d: bool = True,
                 q: float = 0.995):
    """Box bounds (physical units) for scipy.optimize, sigma_d appended last."""
    b = [PRIORS[p].bounds(q) for p in param_names]
    if include_sigma_d:
        b.append(PRIORS["sigma_d"].bounds(q))
    return b


def sample_prior(param_names=DEFAULT_PARAMS, n: int = 64, seed: int = 0,
                 method: str = "sobol", include_sigma_d: bool = False):
    """(n, d) prior samples via inverse-CDF of Sobol (or uniform) points."""
    names = list(param_names) + (["sigma_d"] if include_sigma_d else [])
    d = len(names)
    if method == "sobol":
        from scipy.stats import qmc
        u = qmc.Sobol(d=d, scramble=True, seed=seed).random(n)
    else:
        u = np.random.default_rng(seed).uniform(size=(n, d))
    u = np.clip(u, 1e-6, 1.0 - 1e-6)
    return np.column_stack([PRIORS[nm].ppf(u[:, j])
                            for j, nm in enumerate(names)])


def log_prior(x, param_names=DEFAULT_PARAMS):
    """Log prior of x = (theta..., sigma_d). 1-D -> float; 2-D -> (q,)."""
    x = np.asarray(x, dtype=float)
    scalar = x.ndim == 1
    X = np.atleast_2d(x)
    if X.shape[1] != len(param_names) + 1:
        raise ValueError(f"expected {len(param_names) + 1} columns "
                         f"(theta + sigma_d), got {X.shape[1]}")
    lp = np.zeros(X.shape[0])
    for j, name in enumerate(param_names):
        lp = lp + PRIORS[name].logpdf(X[:, j])
    lp = lp + PRIORS["sigma_d"].logpdf(X[:, -1])
    return float(lp[0]) if scalar else lp


# -------------------------------------------------------------- likelihood


def _station_indices(zs: np.ndarray, n_stations: int) -> np.ndarray:
    """Indices of ~n_stations points on zs (mm), evenly spaced in zs."""
    if len(zs) <= n_stations:
        return np.arange(len(zs))
    stations = np.linspace(zs[0], zs[-1], n_stations)
    idx = np.abs(zs[None, :] - stations[:, None]).argmin(axis=1)
    return np.unique(idx)


def _interp_rows(grid: np.ndarray, zq: np.ndarray, mean2d: np.ndarray,
                 std2d: np.ndarray):
    """Linear interp of each row of (q, m) mean/std from grid to zq (mm)."""
    j = np.clip(np.searchsorted(grid, zq), 1, len(grid) - 1)
    w = (zq - grid[j - 1]) / (grid[j] - grid[j - 1])
    w = np.clip(w, 0.0, 1.0)
    mu = mean2d[:, j - 1] * (1.0 - w) + mean2d[:, j] * w
    sd = std2d[:, j - 1] * (1.0 - w) + std2d[:, j] * w
    return mu, sd


def log_likelihood(theta_vec, targets, emulators, sigma_d,
                   n_stations: int = 40, foot_r_sigma: float = 0.1):
    """Joint Gaussian log-likelihood over shots (spec Section 7).

    theta_vec : (d,) or (q, d) theta WITHOUT sigma_d.
    targets   : list of duck-typed calibration targets (see module docstring).
    emulators : list of ShotEmulator, parallel to targets.
    sigma_d   : scalar or (q,) model-discrepancy jitter [mm].
    Returns float for 1-D input, (q,) array for 2-D.
    """
    theta = np.asarray(theta_vec, dtype=float)
    scalar = theta.ndim == 1
    T = np.atleast_2d(theta)
    q = T.shape[0]
    sd_d = np.broadcast_to(np.asarray(sigma_d, dtype=float), (q,))
    var_d = sd_d[:, None] ** 2

    ll = np.zeros(q)
    alive = np.ones(q, dtype=bool)
    for tgt, em in zip(targets, emulators):
        X = np.column_stack([T, np.full(q, float(tgt.velocity))])

        if getattr(em, "feasibility", None) is not None:
            alive &= em.feasibility.predict_proba(X) >= 0.5

        # ---- profile block
        m = np.asarray(tgt.trusted, dtype=bool)
        zs_t = np.asarray(tgt.zs, dtype=float)[m]
        r_t = np.asarray(tgt.r, dtype=float)[m]
        s_t = np.asarray(tgt.sigma, dtype=float)[m]
        idx = _station_indices(zs_t, n_stations)
        zq, rq, sq = zs_t[idx], r_t[idx], s_t[idx]

        pm, ps = em.profile.predict(X)                  # (q, m_grid) mm
        mu, sd_gp = _interp_rows(em.profile.zs_grid, zq, pm, ps)
        var = sq**2 + sd_gp**2 + var_d
        ll += -0.5 * (((rq - mu) ** 2) / var + np.log(var) + _L2PI).sum(axis=1)

        # ---- length block
        L_est = getattr(tgt, "L_est", None)
        if getattr(em, "L", None) is not None and L_est is not None:
            Lm, Ls = em.L.predict(X)
            vL = float(tgt.sigma_L) ** 2 + Ls**2
            ll += -0.5 * ((float(L_est) - Lm) ** 2 / vL + np.log(vL) + _L2PI)

        # ---- foot max radius block
        f_est = getattr(tgt, "foot_r", None)
        if getattr(em, "foot_r", None) is not None and f_est is not None:
            fm, fs = em.foot_r.predict(X)
            vF = foot_r_sigma**2 + fs**2
            ll += -0.5 * ((float(f_est) - fm) ** 2 / vF + np.log(vF) + _L2PI)

    ll[~alive] = -np.inf
    return float(ll[0]) if scalar else ll


def neg_log_posterior(x, targets, emulators, param_names=DEFAULT_PARAMS,
                      n_stations: int = 40):
    """-(log prior + log likelihood) of x = (theta..., sigma_d).

    Scalar for 1-D x (scipy.optimize-ready); (q,) array for 2-D x.
    """
    x = np.asarray(x, dtype=float)
    scalar = x.ndim == 1
    X = np.atleast_2d(x)
    lp = np.atleast_1d(log_prior(X, param_names))
    out = np.full(X.shape[0], np.inf)
    ok = np.isfinite(lp)
    if ok.any():
        ll = np.atleast_1d(log_likelihood(X[ok, :-1], targets, emulators,
                                          X[ok, -1], n_stations=n_stations))
        out[ok] = -(lp[ok] + ll)
    return float(out[0]) if scalar else out


def make_log_prob(targets, emulators, param_names=DEFAULT_PARAMS,
                  n_stations: int = 40):
    """emcee-ready log-probability closure (handles 1-D and 2-D x)."""

    def log_prob(x):
        nlp = neg_log_posterior(x, targets, emulators, param_names,
                                n_stations=n_stations)
        return -nlp

    return log_prob
