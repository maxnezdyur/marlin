"""Round-0 DOE: 96 Sobol points over the spec priors, RI forward model."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def main():
    from taylor_cal import campaign
    here = os.path.dirname(os.path.abspath(__file__))
    thetas = campaign.sobol_doe(96, seed=0)
    res = campaign.run_batch(
        thetas, velocity=235.9, max_parallel=8, fidelity="RI",
        ledger_path=os.path.join(here, "ledger.parquet"),
        run_root=os.path.join(here, "runs"),
        timeout_s=7200)
    print(f"DONE: {len(res)} runs executed")


if __name__ == "__main__":
    main()
