"""emcee driver + diagnostics for JC calibration (spec Section 8).

Sampler: affine-invariant ensemble (emcee), nwalkers = max(32, 4*ndim),
initialized at the MAP (scipy differential_evolution on the neg log
posterior within prior box bounds) plus a small scatter.

`log_prob` must accept a 1-D point (returning a float) AND a 2-D batch of
points (returning a (q,) array) — objective.make_log_prob provides exactly
that — so both the vectorized DE and emcee's vectorize=True stay cheap.
All parameters are in physical units (Pa, dimensionless, mm for sigma_d).
"""

from __future__ import annotations

import os

import numpy as np

import emcee
from scipy.optimize import differential_evolution


def _neg_wrapper(log_prob):
    """Adapter for scipy DE: handles (ndim,) and vectorized (ndim, S) calls."""

    def neg(xt):
        xt = np.asarray(xt, dtype=float)
        if xt.ndim == 2:                       # DE vectorized: (ndim, S)
            return -np.asarray(log_prob(xt.T), dtype=float)
        return -float(log_prob(xt))

    return neg


def find_map(log_prob, bounds, seed: int = 0, maxiter: int = 150,
             popsize: int = 16):
    """MAP point via differential evolution inside prior box bounds."""
    neg = _neg_wrapper(log_prob)
    try:
        res = differential_evolution(
            neg, bounds, seed=seed, maxiter=maxiter, popsize=popsize,
            tol=1e-8, polish=False, vectorized=True, updating="deferred")
    except TypeError:                          # scipy < 1.9: no vectorized
        res = differential_evolution(
            neg, bounds, seed=seed, maxiter=maxiter, popsize=popsize,
            tol=1e-8, polish=False)
    return np.asarray(res.x, dtype=float)


def run_mcmc(log_prob, ndim: int, bounds, nsteps: int = 5000,
             nwalkers: int | None = None, init: str = "map+scatter",
             seed: int = 0, progress: bool = False,
             scatter_frac: float = 0.02) -> emcee.EnsembleSampler:
    """Run emcee; returns the sampler.

    bounds : list of (lo, hi) per dimension (physical units), e.g.
             objective.prior_bounds(param_names).
    init   : 'map+scatter' (differential_evolution MAP + Gaussian scatter of
             scatter_frac * box width) or 'prior' (uniform in the box).
    """
    rng = np.random.default_rng(seed)
    nwalkers = int(nwalkers) if nwalkers else max(32, 4 * ndim)
    lo = np.array([b[0] for b in bounds], dtype=float)
    hi = np.array([b[1] for b in bounds], dtype=float)
    width = hi - lo

    if init == "map+scatter":
        x0 = find_map(log_prob, bounds, seed=seed)
    elif init == "prior":
        x0 = lo + 0.5 * width
    else:
        raise ValueError(f"unknown init {init!r}")

    def _draw(n):
        p = x0 + scatter_frac * width * rng.standard_normal((n, ndim))
        return np.clip(p, lo + 1e-6 * width, hi - 1e-6 * width)

    p0 = _draw(nwalkers) if init == "map+scatter" else \
        lo + rng.uniform(0.02, 0.98, (nwalkers, ndim)) * width
    # ensure every walker starts at finite log prob
    for _ in range(100):
        lp = np.asarray(log_prob(p0), dtype=float)
        bad = ~np.isfinite(lp)
        if not bad.any():
            break
        p0[bad] = _draw(int(bad.sum()))

    sampler = emcee.EnsembleSampler(nwalkers, ndim, log_prob, vectorize=True)
    sampler.run_mcmc(p0, nsteps, progress=progress)
    return sampler


def diagnostics(sampler: emcee.EnsembleSampler, discard: int | None = None,
                thin: int = 1) -> dict:
    """Acceptance fraction, autocorr time (safe), flat chain, R-hat/ESS.

    discard defaults to the first third of the chain (burn-in).
    """
    nsteps = sampler.iteration
    if discard is None:
        discard = nsteps // 3

    out = {
        "nsteps": nsteps,
        "nwalkers": sampler.nwalkers,
        "discard": discard,
        "acceptance_fraction": float(np.mean(sampler.acceptance_fraction)),
        "autocorr_time": None,
    }
    try:
        out["autocorr_time"] = sampler.get_autocorr_time(discard=discard)
    except Exception:
        try:
            out["autocorr_time"] = sampler.get_autocorr_time(discard=discard,
                                                             tol=0)
        except Exception:
            pass

    out["chain"] = sampler.get_chain(discard=discard, thin=thin, flat=True)

    try:                                        # optional arviz R-hat / ESS
        import arviz as az
        ch = sampler.get_chain(discard=discard, thin=thin)  # (step, walk, d)
        ds = az.convert_to_dataset(np.moveaxis(ch, 1, 0))   # (chain, draw, d)
        out["rhat"] = np.asarray(az.rhat(ds).to_array()).ravel()
        out["ess_bulk"] = np.asarray(az.ess(ds).to_array()).ravel()
    except Exception:
        pass
    return out


def corner_plot(chain: np.ndarray, labels, path: str, truths=None) -> str:
    """Corner plot of a flat chain (nsamples, ndim); writes PNG, returns path."""
    import matplotlib
    matplotlib.use("Agg")
    import corner

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig = corner.corner(np.asarray(chain), labels=list(labels), truths=truths,
                        quantiles=[0.025, 0.5, 0.975], show_titles=True,
                        title_fmt=".3g")
    fig.savefig(path, dpi=150)
    import matplotlib.pyplot as plt
    plt.close(fig)
    return path
