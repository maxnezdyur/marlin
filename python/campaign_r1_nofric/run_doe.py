"""Round-1 DOE: frictionless anvil (mu = 0, friction kernel inert).

96 Sobol points over the 5 constitutive priors (A, B, n, C, ipe); mu is
pinned to 0.0 in every theta so the friction nodal kernel contributes exactly
zero force. RI forward model, CuH04 shot velocity.
"""
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
        thetas, velocity=235.9, max_parallel=8, fidelity="RI",
        ledger_path=os.path.join(here, "ledger.parquet"),
        run_root=os.path.join(here, "runs"),
        timeout_s=7200)
    print(f"DONE: {len(res)} runs executed")


if __name__ == "__main__":
    main()
