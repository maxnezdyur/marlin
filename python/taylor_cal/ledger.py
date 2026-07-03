"""taylor_cal.ledger -- parquet run ledger with content-hash caching.

One row per forward run: theta columns (Pa for A/B), velocity (m/s), fidelity,
status, scalar metrics (mm / us / K), wall time (s), run_dir and the path to
the per-run profile NPZ. Appends are atomic (write tmp + rename) so a crashed
campaign never corrupts the ledger.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile

import pandas as pd

from .forward import THETA_KEYS, full_theta

DEFAULT_PATH = "ledger.parquet"

#: statuses that count as "this point has been evaluated" for cache purposes
#: (blowups are kept -- they feed the feasibility classifier, spec Section 5).
DONE_STATUSES = ("ok", "marginal", "blowup")


# ------------------------------------------------------------- content hash


def _canon(x: float) -> float:
    """Round to 1e-9 relative (10 significant digits) for a stable hash."""
    x = float(x)
    return 0.0 if x == 0.0 else float(f"{x:.9e}")


def hash_theta(theta: dict, velocity: float, fidelity: str,
               input_sha: str = "") -> str:
    """sha256 hex digest of the canonicalized run request.

    theta is completed with BASELINE defaults first, so partial and full dicts
    of the same point hash identically. ``input_sha`` should identify the
    input file content (e.g. sha256 of the .i file) so edited inputs re-run.
    """
    th = full_theta(theta)
    payload = {
        "theta": {k: _canon(th[k]) for k in THETA_KEYS},
        "velocity": _canon(velocity),
        "fidelity": str(fidelity),
        "input_sha": str(input_sha),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


# ------------------------------------------------------------------ ledger


def append_rows(rows, path: str = DEFAULT_PATH) -> pd.DataFrame:
    """Append flat row dicts (see SimResult.to_row) to the parquet ledger.

    Atomic: reads the existing ledger, concatenates, writes to a temp file in
    the same directory, then os.replace()s it over the target. Returns the
    full updated DataFrame.
    """
    new = pd.DataFrame(list(rows))
    if os.path.exists(path):
        old = pd.read_parquet(path)
        df = pd.concat([old, new], ignore_index=True) if len(new) else old
    else:
        df = new
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".ledger-", suffix=".parquet.tmp")
    os.close(fd)
    try:
        df.to_parquet(tmp, index=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return df


def load(path: str = DEFAULT_PATH) -> pd.DataFrame:
    """Load the ledger parquet as a DataFrame."""
    return pd.read_parquet(path)


def by_status(df: pd.DataFrame, *statuses: str) -> pd.DataFrame:
    """Rows whose status is one of ``statuses`` (e.g. by_status(df, 'ok'))."""
    return df[df["status"].isin(statuses)].copy()


def done_hashes(df: pd.DataFrame, statuses=DONE_STATUSES) -> set:
    """Hashes already evaluated to a terminal status (cache-hit set)."""
    if "hash" not in df.columns:
        return set()
    return set(df.loc[df["status"].isin(statuses), "hash"].astype(str))


def theta_matrix(df: pd.DataFrame):
    """Design matrix for the emulator.

    Returns (X, npz_paths): X is (n, 7) float with columns THETA_KEYS +
    velocity; npz_paths is the parallel list of per-run profile NPZ paths
    ('' where the run produced no profile).
    """
    cols = list(THETA_KEYS) + ["velocity"]
    X = df[cols].to_numpy(dtype=float)
    npz_paths = ["" if pd.isna(p) else str(p) for p in df["profile_npz"]]
    return X, npz_paths
