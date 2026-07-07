"""Run the 3-D production input at the calibrated posterior median.

Writes the NEML2 model file from g2_median.json (same templating the
calibration used), runs examples/impact/3d_slug_thermal_mult_ri.i with it,
and prints the endpoint metrics. Outputs land in median_3d/.

Usage:  python run_3d_median.py [extra HIT overrides...]
        e.g.  python run_3d_median.py Executioner/num_steps=2000
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from taylor_cal import forward

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.join(forward.IMPACT_DIR, "3d_slug_thermal_mult_ri.i")


def main():
    th = json.load(open(os.path.join(HERE, "g2_median.json")))
    outdir = os.path.join(HERE, "median_3d")
    os.makedirs(outdir, exist_ok=True)
    model = forward.write_neml2_model(th, os.path.join(outdir, "jc_model.i"))
    base = os.path.join(outdir, "median_3d")

    cmd = [forward.DEFAULT_EXE, "-i", INPUT,
           "v=235.9",
           f"NEML2/all/input={os.path.abspath(model)}",
           f"Outputs/file_base={base}"] + sys.argv[1:]
    print(" ".join(cmd))
    with open(os.path.join(outdir, "run.log"), "w") as log:
        subprocess.run(cmd, cwd=forward.IMPACT_DIR, stdout=log,
                       stderr=subprocess.STDOUT, check=False)

    import numpy as np
    d = np.genfromtxt(base + ".csv", delimiter=",", names=True)
    print(f"steps={len(d['time']) - 1} t_end={d['time'][-1] * 1e6:.1f} us "
          f"max_dT={np.nanmax(d['max_dT']):.0f} K max_ep={np.nanmax(d['max_ep']):.2f}")
    print(f"outputs: {base}.e  {base}.csv  {outdir}/run.log")


if __name__ == "__main__":
    main()
