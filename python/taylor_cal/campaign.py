"""taylor_cal.campaign -- DOE generation and local batch scheduling.

Sobol quasi-random designs over the spec Section 5 priors, and a re-entrant
local batch runner: ProcessPoolExecutor over run_forward, ledger append on
each completion, content-hash skip for points already evaluated.
"""

from __future__ import annotations

import hashlib
import os
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
from scipy import stats
from scipy.stats import qmc

from . import ledger as _ledger
from .forward import DEFAULT_EXE, DEFAULT_INPUT, run_forward

# --------------------------------------------------------------------- DOE

#: Spec Section 5 priors. ('lognormal', median, sd_decades) uses a normal in
#: log10-space (sd in decades); ('uniform', lo, hi) is flat. A, B in Pa.
PRIORS = {
    "A": ("lognormal", 99.7e6, 0.2),
    "B": ("lognormal", 262.8e6, 0.2),
    "n": ("uniform", 0.1, 0.5),
    "C": ("uniform", 0.01, 0.05),
    "ipe": ("uniform", 0.1, 0.5),
    "mu": ("uniform", 0.03, 0.3),
}


def sobol_doe(n: int, priors: dict = None, seed: int = 0) -> list:
    """n theta dicts from a scrambled Sobol sequence mapped through the prior
    inverse CDFs (lognormal via norm.ppf in log10-space; uniform via affine).
    """
    priors = PRIORS if priors is None else priors
    keys = list(priors)
    sampler = qmc.Sobol(d=len(keys), scramble=True, seed=seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # non-power-of-2 balance
        u = sampler.random(n)
    u = np.clip(u, 1e-12, 1.0 - 1e-12)

    thetas = []
    for row in u:
        th = {}
        for j, k in enumerate(keys):
            kind, a, b = priors[k]
            if kind == "lognormal":
                th[k] = float(10.0 ** stats.norm.ppf(row[j], loc=np.log10(a), scale=b))
            elif kind == "uniform":
                th[k] = float(a + (b - a) * row[j])
            else:
                raise ValueError(f"unknown prior kind {kind!r} for {k!r}")
        thetas.append(th)
    return thetas


# ------------------------------------------------------------------- batch


def file_sha256(path: str) -> str:
    """sha256 hex digest of a file's bytes (input-file identity for hashing)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_batch(thetas, velocity: float, max_parallel: int = 8,
              fidelity: str = "F1", ledger_path: str = "ledger.parquet",
              run_root: str = "runs", exe: str = DEFAULT_EXE,
              input_file: str = DEFAULT_INPUT, timeout_s: float = 7200,
              extra_cli=None, verbose: bool = True) -> list:
    """Evaluate a batch of theta points at one velocity (m/s).

    Content-hash caching: points whose hash is already in the ledger with a
    terminal status (ok/marginal/blowup) are skipped, as are duplicates within
    the batch, so re-entrant campaigns never re-run. Each completed run is
    appended to the ledger immediately (atomic write), so a crash loses at
    most the in-flight runs. Run dirs are ``run_root/<hash12>``.

    Returns the list of SimResults actually run (skipped points excluded).
    """
    input_file = os.path.abspath(input_file)
    input_sha = file_sha256(input_file)

    seen = set()
    if os.path.exists(ledger_path):
        seen = _ledger.done_hashes(_ledger.load(ledger_path))

    jobs = []
    for th in thetas:
        h = _ledger.hash_theta(th, velocity, fidelity, input_sha)
        if h in seen:
            continue
        seen.add(h)  # dedupe within the batch too
        jobs.append((h, dict(th)))
    if verbose:
        print(f"run_batch: {len(jobs)} to run, {len(thetas) - len(jobs)} skipped "
              f"(cached/duplicate), fidelity={fidelity}, v={velocity} m/s")
    if not jobs:
        return []

    os.makedirs(run_root, exist_ok=True)
    results = []
    with ProcessPoolExecutor(max_workers=max_parallel) as pool:
        futs = {}
        for h, th in jobs:
            run_dir = os.path.join(run_root, h[:12])
            fut = pool.submit(run_forward, th, velocity, run_dir,
                              fidelity=fidelity, exe=exe, input_file=input_file,
                              timeout_s=timeout_s, extra_cli=extra_cli)
            futs[fut] = h
        for fut in as_completed(futs):
            h = futs[fut]
            res = fut.result()
            row = res.to_row()
            row["hash"] = h
            row["input_sha"] = input_sha
            _ledger.append_rows([row], ledger_path)
            results.append(res)
            if verbose:
                print(f"  [{len(results)}/{len(jobs)}] {h[:12]} "
                      f"status={res.status} L={res.L:.2f} mm "
                      f"wall={res.wall_s:.0f} s")
    return results
