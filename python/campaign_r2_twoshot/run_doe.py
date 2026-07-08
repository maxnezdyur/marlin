"""Round-2 DOE: the same 96 Sobol points as round 1 (5 constitutive params,
mu pinned to 0), run at the second shot velocity 132.3 m/s. The 235.9 m/s
runs are reused from campaign_r1_nofric."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

PARAMS = ("A", "B", "n", "C", "ipe")


def main():
    from taylor_cal import campaign
    here = os.path.dirname(os.path.abspath(__file__))
    priors = {k: campaign.PRIORS[k] for k in PARAMS}
    thetas = campaign.sobol_doe(96, priors=priors, seed=0)
    for th in thetas:
        th["mu"] = 0.0
    res = campaign.run_batch(
        thetas, velocity=132.3, max_parallel=8, fidelity="RI",
        ledger_path=os.path.join(here, "ledger.parquet"),
        run_root=os.path.join(here, "runs"),
        timeout_s=7200)
    print(f"DONE: {len(res)} runs executed")


if __name__ == "__main__":
    main()
