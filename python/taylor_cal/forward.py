"""taylor_cal.forward -- forward-model wrapper for RZ Taylor-impact runs.

Builds HIT CLI overrides for the marlin Johnson-Cook slug inputs, shells out to
``marlin-opt``, and extracts profile + arrest metrics from the Exodus/CSV
outputs.

Units: profile coordinates and radii in mm, velocities in m/s, stresses in Pa,
``t_end_us`` in microseconds, ``wall_s`` in seconds. The Exodus files store
meters; conversion happens in :func:`read_exodus_rz`.
"""

from __future__ import annotations

import glob
import os
import shutil
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field

import numpy as np
from scipy.io import netcdf_file

# ----------------------------------------------------------------- constants

#: Calibrated parameter names, in canonical order (m is FIXED at 0.98 in the
#: input files and is not part of theta).
THETA_KEYS = ("A", "B", "n", "C", "ipe", "mu")

#: Baseline full-hard OFHC copper constants (Pa where stress-like).
BASELINE = dict(A=99.7e6, B=262.8e6, n=0.23, C=0.029, ipe=0.37, mu=0.1)

IMPACT_DIR = "/Users/maxnezdyur/projects/exp-dyn/marlin/examples/impact"
DEFAULT_INPUT = os.path.join(IMPACT_DIR, "rz_slug_thermal_simo.i")

# Reduced-integration NEML2 forward model (fidelity "RI"): ~21 min/run vs
# ~55 min for the 4-qp F-bar NEML2 run and ~14 min for the Simo twin, and it
# IS the production model (no cross-code transfer). Constitutive constants
# live in the NEML2 model file, so each run gets a generated copy passed via
# the CLI-overridable NEML2/all/input parameter.
RI_INPUT = os.path.join(IMPACT_DIR, "rz_slug_thermal_mult_ri.i")
NEML2_MODEL_TEMPLATE = os.path.join(IMPACT_DIR, "johnson_cook_neml2_mult_thermal_cal.i")
DEFAULT_EXE = "/Users/maxnezdyur/projects/exp-dyn/marlin/marlin-opt"

#: Arrest / runaway thresholds (see spec Section 4).
VEL_ARREST = 1.0     # m/s   -- |vel_end| below this = physically arrested
EP_MELT = 8.0        # --    -- max effective plastic strain above this = localized melt
VEL_BLOWUP = 100.0   # m/s
EP_BLOWUP = 100.0

NBINS = 120  # axial bins for the outer profile


def full_theta(theta: dict) -> dict:
    """Merge ``theta`` over :data:`BASELINE`; reject unknown keys."""
    unknown = set(theta) - set(THETA_KEYS)
    if unknown:
        raise KeyError(f"unknown theta keys {sorted(unknown)}; allowed {THETA_KEYS}")
    out = dict(BASELINE)
    out.update(theta)
    return out


# ----------------------------------------------------------------- CLI build


def build_cli(theta: dict, velocity: float, file_base: str) -> list:
    """HIT command-line overrides for ``rz_slug_thermal_simo.i`` (and its F2
    twin, which uses the same top-level variable names).

    A, B in Pa; velocity in m/s; ``mu`` targets the friction nodal kernel
    parameter directly since it is not a top-level HIT variable.
    """
    th = full_theta(theta)
    return [
        f"A={th['A']:.12g}",
        f"B={th['B']:.12g}",
        f"n={th['n']:.12g}",
        f"C={th['C']:.12g}",
        f"ipe={th['ipe']:.12g}",
        f"v={float(velocity):.12g}",
        f"NodalKernels/anvil_friction/mu={th['mu']:.12g}",
        f"Outputs/file_base={file_base}",
    ]


_NEML2_SUB_KEYS = {"A": "A", "B": "B", "n": "n", "C": "C",
                   "ipe": "initial_plastic_strain"}


def write_neml2_model(theta: dict, path: str,
                      template: str = NEML2_MODEL_TEMPLATE) -> str:
    """Write a per-run NEML2 model file with theta's constitutive constants
    substituted inside the [jc_flowrate] block (A, B in Pa; ipe maps to
    initial_plastic_strain). Scoped to the block because bare names like
    'A =' also appear as R2Multiplication parameters elsewhere."""
    th = full_theta(theta)
    src = open(template).read()

    start = src.index("[jc_flowrate]")
    end = src.index("[]", start) + 2
    block = src[start:end]

    for key, hit in _NEML2_SUB_KEYS.items():
        pat = re.compile(rf"^(\s*){re.escape(hit)} = \S+(.*)$", re.M)
        block, nsub = pat.subn(rf"\g<1>{hit} = {th[key]:.12g}\g<2>", block)
        if nsub != 1:
            raise RuntimeError(
                f"NEML2 template substitution for '{hit}' matched {nsub} lines "
                f"(expected exactly 1) in the [jc_flowrate] block of {template}")

    with open(path, "w") as f:
        f.write(src[:start] + block + src[end:])
    return path


def build_cli_ri(theta: dict, velocity: float, file_base: str,
                 model_path: str) -> list:
    """HIT overrides for the reduced-integration NEML2 input: constitutive
    constants travel via the generated model file; only velocity, friction,
    the model path, and the file base are CLI."""
    th = full_theta(theta)
    return [
        f"v={float(velocity):.12g}",
        f"NodalKernels/anvil_friction/mu={th['mu']:.12g}",
        f"NEML2/all/input={os.path.abspath(model_path)}",
        f"Outputs/file_base={file_base}",
    ]


# ------------------------------------------------------------ exodus reader
# Copied from marlin/examples/impact/rz_profile_compare.py (the validated
# objective kernel) so the package is self-contained.


def _decode_names(raw) -> list:
    """Decode an Exodus char-array variable into a list of stripped strings."""
    return [
        bytes(row).decode("ascii", "ignore").strip().strip("\x00").strip()
        for row in np.asarray(raw)
    ]


def read_exodus_rz(path: str, units_to_mm: float = 1000.0):
    """Read a 2D RZ Exodus file; return displaced (r, z) node coords in mm at
    the LAST timestep, plus a densely resampled outer-boundary contour
    (cr, cz). coordx = r, coordy = z."""
    nc = netcdf_file(path, "r", mmap=False)
    try:
        r0 = np.asarray(nc.variables["coordx"][:], dtype=np.float64)
        z0 = np.asarray(nc.variables["coordy"][:], dtype=np.float64)
        names = _decode_names(nc.variables["name_nod_var"][:])
        nidx = {nm: i for i, nm in enumerate(names)}
        for comp in ("disp_x", "disp_y"):
            if comp not in nidx:
                raise KeyError(f"Exodus file lacks nodal variable {comp!r}; have {names}")
        dr = np.asarray(nc.variables[f"vals_nod_var{nidx['disp_x'] + 1}"][-1],
                        dtype=np.float64)
        dz = np.asarray(nc.variables[f"vals_nod_var{nidx['disp_y'] + 1}"][-1],
                        dtype=np.float64)
    finally:
        nc.close()
    r = (r0 + dr) * units_to_mm
    z = (z0 + dz) * units_to_mm

    # Outer-boundary polyline (structured GeneratedMeshGenerator grid): the
    # bottom face (ordered axis -> edge) followed by the lateral surface
    # (ordered bottom -> top). Sampling the polyline densely avoids the
    # zigzag artifact of node-binning when surface nodes cluster in z.
    eps = 1e-12
    bot = np.where(np.abs(z0 - z0.min()) < eps)[0]
    side = np.where(np.abs(r0 - r0.max()) < eps)[0]
    bot = bot[np.argsort(r0[bot])]
    side = side[np.argsort(z0[side])]
    contour = np.concatenate([bot, side])
    cr, cz = r[contour], z[contour]
    rs, zs = [], []
    for a in range(len(cr) - 1):
        t = np.linspace(0.0, 1.0, 30, endpoint=False)
        rs.append(cr[a] + t * (cr[a + 1] - cr[a]))
        zs.append(cz[a] + t * (cz[a + 1] - cz[a]))
    rs.append(cr[-1:])
    zs.append(cz[-1:])
    return r, z, np.concatenate(rs), np.concatenate(zs)


def binned_max_radius(zs: np.ndarray, r: np.ndarray, nbins: int = NBINS):
    """Outer profile: max radius per occupied axial bin (mm).
    Returns (bin centers, rmax)."""
    edges = np.linspace(zs.min(), zs.max(), nbins + 1)
    idx = np.clip(np.digitize(zs, edges) - 1, 0, nbins - 1)
    rmax = np.full(nbins, -np.inf)
    np.maximum.at(rmax, idx, r)
    centers = 0.5 * (edges[:-1] + edges[1:])
    keep = np.isfinite(rmax)
    return centers[keep], rmax[keep]


# ------------------------------------------------------------------ results


@dataclass
class SimResult:
    """One forward run. Profile arrays live in ``profile_npz`` on disk; the
    ledger row (:meth:`to_row`) is flat scalars + that path."""

    theta: dict
    velocity: float          # m/s (nominal impact velocity)
    fidelity: str            # 'F1' | 'F1c' | 'F2'
    status: str              # 'ok' | 'marginal' | 'blowup' | 'timeout' | 'error'
    zs: np.ndarray = None    # mm, distance from impact face (binned profile)
    r: np.ndarray = None     # mm, outer radius at zs
    L: float = np.nan        # mm, final length
    foot_r: float = np.nan   # mm, max contour radius for zs < 1 mm
    rear_r: float = np.nan   # mm, max contour radius within 2 mm of the rear
    t_end_us: float = np.nan  # us, last CSV time
    vel_end: float = np.nan  # m/s, COM axial velocity at last CSV row
    max_ep: float = np.nan   # max effective plastic strain over the run
    max_dT: float = np.nan   # K, max adiabatic temperature rise over the run
    wall_s: float = np.nan   # s, subprocess wall time
    run_dir: str = ""
    profile_npz: str = ""

    def to_row(self) -> dict:
        """Flat dict for the parquet ledger (theta expanded to columns)."""
        th = full_theta(self.theta)
        row = {k: float(th[k]) for k in THETA_KEYS}
        row.update(
            velocity=float(self.velocity),
            fidelity=str(self.fidelity),
            status=str(self.status),
            L=float(self.L),
            foot_r=float(self.foot_r),
            rear_r=float(self.rear_r),
            t_end_us=float(self.t_end_us),
            vel_end=float(self.vel_end),
            max_ep=float(self.max_ep),
            max_dT=float(self.max_dT),
            wall_s=float(self.wall_s),
            run_dir=str(self.run_dir),
            profile_npz=str(self.profile_npz),
        )
        return row


def classify_status(vel_end: float, max_ep: float) -> str:
    """Arrest/runaway classification from the CSV endpoint (spec Section 4).

    ok       : arrested (|vel_end| < 1 m/s) and max_ep < 8
    marginal : arrested but max_ep >= 8 (localized melt element)
    blowup   : |vel_end| > 100 m/s or max_ep > 100 (adiabatic extrusion runaway)
    error    : anything else (non-finite, or stopped mid-flight)
    """
    if not (np.isfinite(vel_end) and np.isfinite(max_ep)):
        return "error"
    if abs(vel_end) > VEL_BLOWUP or max_ep > EP_BLOWUP:
        return "blowup"
    if abs(vel_end) < VEL_ARREST:
        return "ok" if max_ep < EP_MELT else "marginal"
    return "error"


def extract_result(exodus_path: str, csv_path: str) -> dict:
    """Extract SimResult fields from a finished run's Exodus + CSV pair.

    Returns a dict with keys zs, r, L, foot_r, rear_r (mm; from the displaced
    outer-boundary contour at the last Exodus timestep) and t_end_us, vel_end,
    max_ep, max_dT, status (from the CSV postprocessor history). Missing or
    unreadable files leave the corresponding fields NaN/None; status falls
    back to 'error'.
    """
    out = dict(zs=None, r=None, L=np.nan, foot_r=np.nan, rear_r=np.nan,
               t_end_us=np.nan, vel_end=np.nan, max_ep=np.nan, max_dT=np.nan,
               status="error")

    if exodus_path and os.path.exists(exodus_path):
        try:
            _, z, cr, cz = read_exodus_rz(exodus_path)
            z_min = z.min()
            L = z.max() - z_min
            czs = cz - z_min
            zs, rp = binned_max_radius(czs, cr)
            out.update(
                zs=zs, r=rp, L=float(L),
                foot_r=float(cr[czs < 1.0].max()),
                rear_r=float(cr[czs > L - 2.0].max()),
            )
        except Exception:
            pass  # profile stays empty; CSV may still classify the run

    if csv_path and os.path.exists(csv_path):
        try:
            data = np.genfromtxt(csv_path, delimiter=",", names=True)
            t = np.atleast_1d(data["time"])
            vel = np.atleast_1d(data["vel_y_avg"])
            ep = np.atleast_1d(data["max_ep"])
            dT = np.atleast_1d(data["max_dT"])
            out.update(
                t_end_us=float(t[-1] * 1e6),
                vel_end=float(vel[-1]),
                max_ep=float(np.nanmax(ep)),
                max_dT=float(np.nanmax(dT)),
            )
            out["status"] = classify_status(out["vel_end"], out["max_ep"])
        except Exception:
            pass

    return out


# ------------------------------------------------------------------- runner


def run_forward(theta: dict, velocity: float, workdir: str, fidelity: str = "F1",
                exe: str = DEFAULT_EXE, input_file: str = DEFAULT_INPUT,
                timeout_s: float = 7200, extra_cli=None) -> SimResult:
    """Run one forward simulation and extract its result.

    The subprocess runs with ``cwd`` = the input file's directory (the F2
    input references its NEML2 model file relative to that dir) and a unique
    ``Outputs/file_base`` there; outputs are then moved into ``workdir``
    (created if missing), which also receives ``run.log`` and
    ``profile.npz``. ``extra_cli`` appends raw HIT overrides (e.g.
    ``['Executioner/num_steps=200']``).
    """
    workdir = os.path.abspath(workdir)
    os.makedirs(workdir, exist_ok=True)
    if fidelity == "RI" and input_file == DEFAULT_INPUT:
        input_file = RI_INPUT
    input_file = os.path.abspath(input_file)
    run_cwd = os.path.dirname(input_file)
    base = "tc_" + uuid.uuid4().hex[:10]

    if fidelity == "RI":
        model_path = write_neml2_model(theta, os.path.join(workdir, "jc_model.i"))
        cli = build_cli_ri(theta, velocity, base, model_path)
    else:
        cli = build_cli(theta, velocity, base)
    cmd = [exe, "-i", input_file] + cli
    cmd += list(extra_cli or [])

    timed_out = False
    log_path = os.path.join(workdir, "run.log")
    t0 = time.monotonic()
    with open(log_path, "w") as log:
        log.write(" ".join(cmd) + f"\n(cwd: {run_cwd})\n\n")
        log.flush()
        try:
            env = dict(os.environ)
            # one BLAS/torch thread per process: the campaign packs 8 runs
            env.update(OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                       VECLIB_MAXIMUM_THREADS="1")
            subprocess.run(cmd, cwd=run_cwd, stdout=log,
                           stderr=subprocess.STDOUT, timeout=timeout_s, env=env)
        except subprocess.TimeoutExpired:
            timed_out = True
        except OSError as err:
            log.write(f"\nlaunch failed: {err}\n")
    wall_s = time.monotonic() - t0

    # sweep this run's outputs (file_base is unique) into workdir
    for f in sorted(glob.glob(os.path.join(run_cwd, base + "*"))):
        shutil.move(f, os.path.join(workdir, os.path.basename(f)))

    def _find(preferred, pattern):
        p = os.path.join(workdir, preferred)
        if os.path.exists(p):
            return p
        hits = sorted(glob.glob(os.path.join(workdir, pattern)))
        return hits[0] if hits else None

    exo = _find(base + "_exodus.e", base + "*.e")
    csvf = _find(base + "_csv.csv", base + "*.csv")
    fields = extract_result(exo, csvf)
    status = "timeout" if timed_out else fields["status"]

    profile_npz = ""
    if fields["zs"] is not None:
        profile_npz = os.path.join(workdir, "profile.npz")
        np.savez(profile_npz, zs=fields["zs"], r=fields["r"])

    return SimResult(
        theta=dict(theta), velocity=float(velocity), fidelity=fidelity,
        status=status, zs=fields["zs"], r=fields["r"], L=fields["L"],
        foot_r=fields["foot_r"], rear_r=fields["rear_r"],
        t_end_us=fields["t_end_us"], vel_end=fields["vel_end"],
        max_ep=fields["max_ep"], max_dT=fields["max_dT"],
        wall_s=wall_s, run_dir=workdir, profile_npz=profile_npz,
    )
