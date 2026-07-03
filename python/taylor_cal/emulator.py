"""PCA-GP emulators for Taylor-impact calibration (spec Section 6).

Higdon/Walters-style profile emulator: stack DOE profiles r(zs) [mm] on a
common zs grid [mm], center/scale, SVD, keep the leading PCA modes, and fit
one sklearn GP per mode weight. Inputs X are (theta columns + velocity):
stresses in Pa, dimensionless exponents/coefficients, velocity in m/s.
Outputs are radii in mm (ProfileEmulator) or scalar metrics in mm
(ScalarEmulator: final length L, foot max radius foot_r).

All emulator predictive std devs are in physical units (mm) and feed the
likelihood variance in objective.py.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Optional

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import (
    GaussianProcessClassifier,
    GaussianProcessRegressor,
)
from sklearn.gaussian_process.kernels import (
    RBF,
    ConstantKernel,
    Matern,
    WhiteKernel,
)
from sklearn.model_selection import KFold


def _make_gp(ndim_in: int, seed: int = 0) -> GaussianProcessRegressor:
    """Matern-5/2 ARD + white-noise jitter GP on standardized inputs."""
    kernel = (
        ConstantKernel(1.0, (1e-3, 1e3))
        * Matern(length_scale=np.ones(ndim_in),
                 length_scale_bounds=(1e-2, 1e3), nu=2.5)
        + WhiteKernel(noise_level=1e-6, noise_level_bounds=(1e-12, 1e-1))
    )
    return GaussianProcessRegressor(
        kernel=kernel, normalize_y=True, n_restarts_optimizer=2,
        random_state=seed)


def _standardize_fit(X: np.ndarray):
    """Column mean/std with zero-variance guard (e.g. fixed-velocity column)."""
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0.0] = 1.0
    return mean, std


class ProfileEmulator:
    """PCA + per-mode GP emulator for full radial profiles r(zs) [mm].

    fit(X, profiles, zs_grid):
        X        : (n, d) inputs, theta columns + velocity [m/s] last.
        profiles : (n, m) radii [mm] on the common zs grid.
        zs_grid  : (m,) distance from impact face [mm].
    Keeps k modes for >= `var_target` variance, capped at `max_modes`.
    """

    def __init__(self, var_target: float = 0.995, max_modes: int = 6,
                 seed: int = 0):
        self.var_target = var_target
        self.max_modes = max_modes
        self.seed = seed
        self.zs_grid: Optional[np.ndarray] = None
        self.n_modes: int = 0
        self.explained: float = 0.0

    def _clone(self) -> "ProfileEmulator":
        return ProfileEmulator(var_target=self.var_target,
                               max_modes=self.max_modes, seed=self.seed)

    def fit(self, X, profiles, zs_grid) -> "ProfileEmulator":
        X = np.atleast_2d(np.asarray(X, dtype=float))
        P = np.asarray(profiles, dtype=float)
        if P.shape[0] != X.shape[0]:
            raise ValueError(f"X has {X.shape[0]} rows, profiles {P.shape[0]}")
        self.zs_grid = np.asarray(zs_grid, dtype=float)

        self._xm, self._xs = _standardize_fit(X)
        Xs = (X - self._xm) / self._xs

        self._pm = P.mean(axis=0)                       # mean profile [mm]
        Yc = P - self._pm
        scale = Yc.std()
        self._scale = scale if scale > 0.0 else 1.0
        Y = Yc / self._scale

        U, S, Vt = np.linalg.svd(Y, full_matrices=False)
        var_frac = S**2 / max((S**2).sum(), 1e-300)
        k = int(np.searchsorted(np.cumsum(var_frac), self.var_target)) + 1
        k = min(k, self.max_modes, len(S))
        self.n_modes = k
        self.explained = float(np.cumsum(var_frac)[k - 1])

        self._basis = Vt[:k]                            # (k, m)
        W = U[:, :k] * S[:k]                            # (n, k) mode weights
        # per-column PCA truncation residual variance (scaled units)
        self._resid_var = ((Y - W @ self._basis) ** 2).mean(axis=0)

        self._gps = []
        with warnings.catch_warnings():
            # flat (irrelevant-input) ARD length scales pinning at their
            # bound are expected and harmless
            warnings.simplefilter("ignore", ConvergenceWarning)
            for j in range(k):
                gp = _make_gp(X.shape[1], seed=self.seed + j)
                gp.fit(Xs, W[:, j])
                self._gps.append(gp)
        return self

    def predict(self, Xq):
        """Return (profiles_mean, profiles_std), each (q, m) in mm.

        Variance = propagated per-mode GP variance (independent modes)
        + PCA truncation residual variance.
        """
        Xq = np.atleast_2d(np.asarray(Xq, dtype=float))
        Xs = (Xq - self._xm) / self._xs
        mus, var = [], []
        for gp in self._gps:
            mu_j, sd_j = gp.predict(Xs, return_std=True)
            mus.append(mu_j)
            var.append(sd_j**2)
        M = np.stack(mus, axis=1)                       # (q, k)
        V = np.stack(var, axis=1)                       # (q, k)
        mean = self._pm + self._scale * (M @ self._basis)
        pvar = self._scale**2 * (V @ self._basis**2 + self._resid_var)
        return mean, np.sqrt(pvar)


class ScalarEmulator:
    """Single-output GP emulator (e.g. final length L [mm], foot_r [mm])."""

    def __init__(self, seed: int = 0):
        self.seed = seed

    def _clone(self) -> "ScalarEmulator":
        return ScalarEmulator(seed=self.seed)

    def fit(self, X, y) -> "ScalarEmulator":
        X = np.atleast_2d(np.asarray(X, dtype=float))
        y = np.asarray(y, dtype=float).ravel()
        self._xm, self._xs = _standardize_fit(X)
        self._gp = _make_gp(X.shape[1], seed=self.seed)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            self._gp.fit((X - self._xm) / self._xs, y)
        return self

    def predict(self, Xq):
        """Return (mean, std), each (q,) in the training units [mm]."""
        Xq = np.atleast_2d(np.asarray(Xq, dtype=float))
        mu, sd = self._gp.predict((Xq - self._xm) / self._xs, return_std=True)
        return mu, sd


class FeasibilityClassifier:
    """Feasibility (status != 'blowup') classifier gating the sampler.

    GP classifier by default; RandomForest fallback if the GPC fails.
    Degenerate single-class training data yields a constant probability.
    """

    def __init__(self, seed: int = 0):
        self.seed = seed
        self._const: Optional[float] = None
        self._clf = None

    def fit(self, X, status) -> "FeasibilityClassifier":
        X = np.atleast_2d(np.asarray(X, dtype=float))
        s = np.asarray(status)
        if s.dtype.kind in ("U", "S", "O"):
            y = np.array([str(v) != "blowup" for v in s], dtype=bool)
        else:
            y = s.astype(bool)
        self._xm, self._xs = _standardize_fit(X)
        Xs = (X - self._xm) / self._xs

        if y.all() or (~y).all():
            self._const = 1.0 if y.all() else 0.0
            return self
        try:
            kernel = ConstantKernel(1.0) * RBF(np.ones(X.shape[1]))
            clf = GaussianProcessClassifier(kernel=kernel,
                                            random_state=self.seed)
            clf.fit(Xs, y)
            self._clf = clf
        except Exception:
            from sklearn.ensemble import RandomForestClassifier
            clf = RandomForestClassifier(n_estimators=200,
                                         random_state=self.seed)
            clf.fit(Xs, y)
            self._clf = clf
        return self

    def predict_proba(self, Xq) -> np.ndarray:
        """Return (q,) probability of feasibility (status != blowup)."""
        Xq = np.atleast_2d(np.asarray(Xq, dtype=float))
        if self._const is not None:
            return np.full(Xq.shape[0], self._const)
        Xs = (Xq - self._xm) / self._xs
        proba = self._clf.predict_proba(Xs)
        icol = list(self._clf.classes_).index(True)
        return proba[:, icol]


@dataclass
class ShotEmulator:
    """Bundle of emulators for one shot family (velocity/geometry group)."""

    profile: ProfileEmulator
    L: Optional[ScalarEmulator] = None
    foot_r: Optional[ScalarEmulator] = None
    feasibility: Optional[FeasibilityClassifier] = None


def cv_report(emulator, X, Y, k: int = 5, seed: int = 0):
    """k-fold CV of a fitted ProfileEmulator or ScalarEmulator.

    Returns a pandas DataFrame with one row per output (per zs station [mm]
    for profiles; a single row for scalars) and columns
    ('output', 'rmse_mm'). Gate (spec Section 6): holdout RMSE per output
    < min(scan sigma, 0.1 mm).
    """
    import pandas as pd

    X = np.atleast_2d(np.asarray(X, dtype=float))
    Y = np.asarray(Y, dtype=float)
    is_profile = Y.ndim == 2
    preds = np.empty_like(Y, dtype=float)

    kf = KFold(n_splits=k, shuffle=True, random_state=seed)
    for tr, te in kf.split(X):
        em = emulator._clone()
        if is_profile:
            em.fit(X[tr], Y[tr], emulator.zs_grid)
        else:
            em.fit(X[tr], Y[tr])
        mu, _ = em.predict(X[te])
        preds[te] = mu

    rmse = np.sqrt(((preds - Y) ** 2).mean(axis=0))
    if is_profile:
        labels = [f"zs={z:.2f}mm" for z in emulator.zs_grid]
        rmse = np.atleast_1d(rmse)
    else:
        labels = ["value"]
        rmse = np.atleast_1d(rmse)
    return pd.DataFrame({"output": labels, "rmse_mm": rmse})
