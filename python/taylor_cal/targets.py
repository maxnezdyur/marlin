"""Calibration-target container for scanned Taylor-impact specimens.

A :class:`CalTarget` is the per-shot experimental record consumed by the
likelihood: an axis-corrected radial profile R(zs) with per-slice noise,
plus the scalar audit quantities (true-length estimate, foot/rear radii,
truncation and axis-wander flags).

Units: lengths in mm, velocity in m/s.

Serialization is split by content type: numpy arrays go to ``<stem>.npz``
and scalars/metadata to a ``<stem>.json`` sidecar.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np

_ARRAY_FIELDS = ("zs", "R", "sigma", "trusted")


def _jsonable(obj):
    """Recursively convert numpy scalars/arrays to plain Python for JSON."""
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _jsonable(obj.tolist())
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def _split_path(path: str) -> tuple[str, str]:
    """Return (npz_path, json_path) for a target stem or .npz/.json path."""
    stem, ext = os.path.splitext(path)
    if ext.lower() not in (".npz", ".json"):
        stem = path
    return stem + ".npz", stem + ".json"


@dataclass(eq=False)
class CalTarget:
    """Experimental calibration target extracted from one post-test STL scan.

    Attributes
    ----------
    shot_id : str
        Specimen identifier parsed from the filename (e.g. ``"CuH04"``).
    velocity : float
        Impact velocity [m/s].
    r0, L0 : float
        Nominal (pre-test) specimen radius and length [mm].
    zs : np.ndarray
        Axial slice centers measured from the foot (impact) plane [mm],
        ascending.
    R : np.ndarray
        Axis-corrected radius per slice from the Kasa circle fit [mm].
    sigma : np.ndarray
        Per-slice noise estimate = max(circle-fit rms, 0.02 mm floor) [mm].
    trusted : np.ndarray
        Boolean mask of slices admitted to the likelihood (foot-lip mixing
        zone, cut-face neighborhood, and poorly fit slices excluded).
    L_extent : float
        Raw axial extent of the scan [mm].
    L_est : float
        Volume-corrected true final length estimate [mm].
    sigma_L : float
        1-sigma uncertainty on ``L_est`` [mm].
    foot_r : float
        Max fitted radius for zs < 1 mm (impact-face lip) [mm].
    rear_r : float
        Mean fitted radius over the last 2 trusted mm [mm].
    truncated : bool
        True when a closed cut face (end cap) was detected at the rear.
    axis_wander : float
        Max pairwise distance between slice centerline points [mm].
    meta : dict
        Free-form JSON-serializable provenance/per-slice extras
        (e.g. source path, slice centers, fit rms).
    """

    shot_id: str
    velocity: float
    r0: float
    L0: float
    zs: np.ndarray
    R: np.ndarray
    sigma: np.ndarray
    trusted: np.ndarray
    L_extent: float
    L_est: float
    sigma_L: float
    foot_r: float
    rear_r: float
    truncated: bool
    axis_wander: float
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        self.zs = np.asarray(self.zs, dtype=np.float64)
        self.R = np.asarray(self.R, dtype=np.float64)
        self.sigma = np.asarray(self.sigma, dtype=np.float64)
        self.trusted = np.asarray(self.trusted, dtype=bool)

    # ------------------------------------------------------------- I/O

    @property
    def r(self):
        """Alias for R: objective.py duck-types targets with lowercase .r."""
        return self.R

    def save(self, path: str) -> tuple[str, str]:
        """Write arrays to ``<stem>.npz`` and scalars/meta to ``<stem>.json``.

        ``path`` may be a stem or end in ``.npz``/``.json``. Returns the
        (npz_path, json_path) pair actually written.
        """
        npz_path, json_path = _split_path(path)
        d = os.path.dirname(npz_path)
        if d:
            os.makedirs(d, exist_ok=True)
        np.savez(npz_path, **{k: getattr(self, k) for k in _ARRAY_FIELDS})
        scalars = {
            "shot_id": self.shot_id,
            "velocity": float(self.velocity),
            "r0": float(self.r0),
            "L0": float(self.L0),
            "L_extent": float(self.L_extent),
            "L_est": float(self.L_est),
            "sigma_L": float(self.sigma_L),
            "foot_r": float(self.foot_r),
            "rear_r": float(self.rear_r),
            "truncated": bool(self.truncated),
            "axis_wander": float(self.axis_wander),
            "meta": _jsonable(self.meta),
        }
        with open(json_path, "w") as fh:
            json.dump(scalars, fh, indent=2)
        return npz_path, json_path

    @classmethod
    def load(cls, path: str) -> "CalTarget":
        """Load a target saved by :meth:`save` (pass stem, .npz, or .json)."""
        npz_path, json_path = _split_path(path)
        with open(json_path) as fh:
            scalars = json.load(fh)
        with np.load(npz_path) as npz:
            arrays = {k: npz[k] for k in _ARRAY_FIELDS}
        return cls(**scalars, **arrays)
