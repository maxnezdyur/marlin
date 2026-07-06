"""G2 (frictionless): single-shot CuH04 posterior from the Round-1 DOE.

Same pipeline as campaign_r0/fit_g2.py but with mu removed from the sampled
parameters (pinned to 0 in the forward runs); 5 constitutive params + sigma_d.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np

PARAMS = ("A", "B", "n", "C", "ipe")


def main():
    from taylor_cal import ledger, emulator, objective, inference, scan_qa
    here = os.path.dirname(os.path.abspath(__file__))

    tgt, qa = scan_qa.build_target(
        '/Users/maxnezdyur/projects/exp-dyn/marlin/examples/impact/stl_results/CuH04_235.9.stl',
        r0_mm=3.81, L0_mm=38.1)
    print(f'target: L_est={tgt.L_est:.2f}+-{tgt.sigma_L:.2f} foot={tgt.foot_r:.3f} trusted={tgt.trusted.sum()}')

    df = ledger.load(os.path.join(here, 'ledger.parquet'))
    ok = df[df.status.isin(['ok', 'marginal'])].reset_index(drop=True)
    cols = list(PARAMS) + ['velocity']
    X = ok[cols].to_numpy(dtype=float)
    npz = ["" if not p else str(p) for p in ok['profile_npz']]
    zs_grid = np.linspace(0.7, 20.0, 90)
    profs = np.array([np.interp(zs_grid, np.load(p)['zs'], np.load(p)['r']) for p in npz])

    pe = emulator.ProfileEmulator().fit(X, profs, zs_grid)
    Le = emulator.ScalarEmulator().fit(X, ok.L.values)
    Fe = emulator.ScalarEmulator().fit(X, ok.foot_r.values)
    Xall = df[cols].to_numpy(dtype=float)
    fc = emulator.FeasibilityClassifier().fit(Xall, df.status.isin(['ok', 'marginal']).values)
    em = emulator.ShotEmulator(profile=pe, L=Le, foot_r=Fe, feasibility=fc)
    print(f'emulator: {pe.n_modes} profile modes on {len(ok)} runs')

    cv = emulator.cv_report(pe, X, profs)
    print(f'profile CV RMSE: mean {cv.rmse_mm.mean():.4f} mm, max {cv.rmse_mm.max():.4f} mm')

    lp = objective.make_log_prob([tgt], [em], param_names=PARAMS)
    sampler = inference.run_mcmc(lp, ndim=len(PARAMS) + 1,
                                 bounds=objective.prior_bounds(PARAMS),
                                 nsteps=12000)
    diag = inference.diagnostics(sampler)
    print(f"acceptance {diag['acceptance_fraction']:.3f}")
    chain = diag['chain']
    names = list(PARAMS) + ['sigma_d']
    inference.corner_plot(chain, names, os.path.join(here, 'g2_corner.png'))
    np.save(os.path.join(here, 'g2_chain.npy'), chain)

    import json
    med = {nm: float(np.percentile(chain[:, i], 50)) for i, nm in enumerate(names[:-1])}
    med['mu'] = 0.0
    with open(os.path.join(here, 'g2_median.json'), 'w') as f:
        json.dump(med, f)

    r0 = dict(A=84809815.4, B=300361171.0, n=0.3872, C=0.03750, ipe=0.1402, mu=0.0362)
    print(f"\n{'param':8s} {'median':>12s} {'16%':>12s} {'84%':>12s} {'r0(w/ fric)':>12s}")
    for i, nm in enumerate(names):
        q = np.percentile(chain[:, i], [16, 50, 84])
        h = r0.get(nm, float('nan'))
        print(f'{nm:8s} {q[1]:12.4g} {q[0]:12.4g} {q[2]:12.4g} {h:12.4g}')
    import itertools
    print('\nposterior correlations:')
    for a, b in itertools.combinations(range(len(PARAMS)), 2):
        c = np.corrcoef(chain[:, a], chain[:, b])[0, 1]
        if abs(c) > 0.4:
            print(f'  {names[a]} - {names[b]}: {c:+.2f}')


if __name__ == '__main__':
    main()
