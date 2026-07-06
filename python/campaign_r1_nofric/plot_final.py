"""Final r1 comparison figure in the g2_vs_hand.png style: mirrored silhouette
over the dense axis-corrected scan (left) + residuals vs scan noise (right)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = "Arial"
import matplotlib.pyplot as plt

INL_BLUE = "#06509D"
CRIMSON = "#B31B1B"
ORANGE = "#E37222"


def main():
    from taylor_cal import scan_qa
    here = os.path.dirname(os.path.abspath(__file__))

    tgt, qa = scan_qa.build_target(
        '/Users/maxnezdyur/projects/exp-dyn/marlin/examples/impact/stl_results/CuH04_235.9.stl',
        r0_mm=3.81, L0_mm=38.1)
    m = tgt.trusted

    runs = [
        ('r0 median, mu=0.036', f'{here}/../campaign_r0/median_check/profile.npz', INL_BLUE, '-'),
        ('r0 median, mu=0', f'{here}/r0median_mu0/profile.npz', ORANGE, '--'),
        ('r1 frictionless median', f'{here}/median_check/profile.npz', CRIMSON, '-'),
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5.5))

    # left: mirrored silhouette, dense axis-corrected scan as filled body
    ax1.fill_between(tgt.zs, -tgt.R, tgt.R, color="0.8", lw=0,
                     label="scan (axis-corrected)")
    for name, path, c, ls in runs:
        p = np.load(path)
        r_t = np.interp(tgt.zs[m], p['zs'], p['r'])
        rms = np.sqrt(np.mean((r_t - tgt.r[m]) ** 2))
        lbl = f"{name} (RMS {rms:.3f} mm)"
        ax1.plot(p['zs'], p['r'], ls, color=c, lw=2.0, label=lbl)
        ax1.plot(p['zs'], -p['r'], ls, color=c, lw=2.0)
        ax2.plot(tgt.zs[m], (r_t - tgt.r[m]) * 1e3, ls, color=c, lw=1.8, label=name)
    ax1.axhline(0.0, color="0.75", lw=0.8, zorder=0)
    ax1.set_aspect("equal")
    ax1.set_xlabel("distance from impact face (mm)")
    ax1.set_ylabel("radius (mm)")
    ax1.set_title("CuH04 235.9 m/s - final profile")
    ax1.legend(loc="upper right", frameon=False, fontsize=9)

    # right: residuals vs scan noise band
    ax2.fill_between(tgt.zs[m], -tgt.sigma[m] * 1e3, tgt.sigma[m] * 1e3,
                     color="0.85", lw=0, label="scan noise band")
    ax2.axhline(0.0, color="0.75", lw=0.8, zorder=0)
    ax2.set_xlabel("distance from impact face (mm)")
    ax2.set_ylabel("radius residual (um)")
    ax2.set_title("sim - scan residuals")
    ax2.legend(frameon=False, fontsize=9)

    fig.tight_layout()
    out = os.path.join(here, "r1_final_compare.png")
    fig.savefig(out, dpi=160)
    print("wrote", out)


if __name__ == "__main__":
    main()
