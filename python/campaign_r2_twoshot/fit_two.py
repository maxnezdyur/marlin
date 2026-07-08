"""G3: joint two-shot posterior (CuH04 at 235.9 and 132.3 m/s).

Reuses the round-1 ledger for the 235.9 m/s runs and this campaign's ledger
for the 132.3 m/s runs. One emulator per shot; joint likelihood over both
scans; 5 constitutive parameters + sigma_d.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np

PARAMS = ("A", "B", "n", "C", "ipe")
STL = "/Users/maxnezdyur/projects/exp-dyn/marlin/examples/impact/stl_results"


def shot_emulator(df, zs_grid, emulator):
    ok = df[df.status.isin(["ok", "marginal"])].reset_index(drop=True)
    cols = list(PARAMS) + ["velocity"]
    X = ok[cols].to_numpy(dtype=float)
    profs = np.array([np.interp(zs_grid, np.load(p)["zs"], np.load(p)["r"])
                      for p in ok["profile_npz"]])
    pe = emulator.ProfileEmulator().fit(X, profs, zs_grid)
    Le = emulator.ScalarEmulator().fit(X, ok.L.values)
    Fe = emulator.ScalarEmulator().fit(X, ok.foot_r.values)
    Xall = df[cols].to_numpy(dtype=float)
    fc = emulator.FeasibilityClassifier().fit(Xall, df.status.isin(["ok", "marginal"]).values)
    cv = emulator.cv_report(pe, X, profs)
    print(f"  emulator: {pe.n_modes} modes on {len(ok)} runs, "
          f"CV RMSE mean {cv.rmse_mm.mean():.4f} mm")
    return emulator.ShotEmulator(profile=pe, L=Le, foot_r=Fe, feasibility=fc)


def main():
    from taylor_cal import ledger, emulator, objective, inference, scan_qa
    here = os.path.dirname(os.path.abspath(__file__))

    t235, _ = scan_qa.build_target(f"{STL}/CuH04_235.9.stl", r0_mm=3.81, L0_mm=38.1)
    t132, _ = scan_qa.build_target(f"{STL}/CuH04_132.3.stl", r0_mm=3.81, L0_mm=38.1)
    print(f"targets: 235.9 L={t235.L_est:.2f} foot={t235.foot_r:.3f} | "
          f"132.3 L={t132.L_est:.2f} foot={t132.foot_r:.3f}")

    df235 = ledger.load(os.path.join(here, "..", "campaign_r1_nofric", "ledger.parquet"))
    df132 = ledger.load(os.path.join(here, "ledger.parquet"))

    print("shot 235.9:")
    em235 = shot_emulator(df235, np.linspace(0.7, 20.0, 90), emulator)
    print("shot 132.3:")
    em132 = shot_emulator(df132, np.linspace(0.7, 29.0, 90), emulator)

    lp = objective.make_log_prob([t235, t132], [em235, em132], param_names=PARAMS)
    sampler = inference.run_mcmc(lp, ndim=len(PARAMS) + 1,
                                 bounds=objective.prior_bounds(PARAMS), nsteps=12000)
    diag = inference.diagnostics(sampler)
    print(f"acceptance {diag['acceptance_fraction']:.3f}")
    chain = diag["chain"]
    names = list(PARAMS) + ["sigma_d"]
    inference.corner_plot(chain, names, os.path.join(here, "g3_corner.png"))
    np.save(os.path.join(here, "g3_chain.npy"), chain)

    import json
    med = {nm: float(np.percentile(chain[:, i], 50)) for i, nm in enumerate(names[:-1])}
    med["mu"] = 0.0
    with open(os.path.join(here, "g3_median.json"), "w") as f:
        json.dump(med, f)

    r1 = dict(A=1.286e8, B=3.080e8, n=0.4715, C=0.02235, ipe=0.1408)
    print(f"\n{'param':8s} {'median':>12s} {'16%':>12s} {'84%':>12s} {'r1(1 shot)':>12s}")
    for i, nm in enumerate(names):
        q = np.percentile(chain[:, i], [16, 50, 84])
        print(f"{nm:8s} {q[1]:12.4g} {q[0]:12.4g} {q[2]:12.4g} {r1.get(nm, float('nan')):12.4g}")


if __name__ == "__main__":
    main()
