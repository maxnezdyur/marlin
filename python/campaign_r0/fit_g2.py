"""G2: single-shot CuH04 posterior from the Round-0 DOE (RI forward model)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np


def main():
    from taylor_cal import ledger, emulator, objective, inference, scan_qa
    here = os.path.dirname(os.path.abspath(__file__))

    tgt, qa = scan_qa.build_target(
        '/Users/maxnezdyur/projects/exp-dyn/marlin/examples/impact/stl_results/CuH04_235.9.stl',
        r0_mm=3.81, L0_mm=38.1)
    print(f'target: L_est={tgt.L_est:.2f}+-{tgt.sigma_L:.2f} foot={tgt.foot_r:.3f} trusted={tgt.trusted.sum()}')

    df = ledger.load(os.path.join(here, 'ledger.parquet'))
    ok = df[df.status.isin(['ok', 'marginal'])].reset_index(drop=True)
    X, npz = ledger.theta_matrix(ok)
    zs_grid = np.linspace(0.7, 20.0, 90)
    profs = np.array([np.interp(zs_grid, np.load(p)['zs'], np.load(p)['r']) for p in npz])

    pe = emulator.ProfileEmulator().fit(X, profs, zs_grid)
    Le = emulator.ScalarEmulator().fit(X, ok.L.values)
    Fe = emulator.ScalarEmulator().fit(X, ok.foot_r.values)
    Xall, _ = ledger.theta_matrix(df)
    fc = emulator.FeasibilityClassifier().fit(Xall, df.status.isin(['ok', 'marginal']).values)
    em = emulator.ShotEmulator(profile=pe, L=Le, foot_r=Fe, feasibility=fc)
    print(f'emulator: {pe.n_modes} profile modes on {len(ok)} runs')

    cv = emulator.cv_report(pe, X, profs)
    print(f'profile CV RMSE: mean {cv.rmse_mm.mean():.4f} mm, max {cv.rmse_mm.max():.4f} mm')

    lp = objective.make_log_prob([tgt], [em])
    sampler = inference.run_mcmc(lp, ndim=7, bounds=objective.prior_bounds(), nsteps=12000)
    diag = inference.diagnostics(sampler)
    print(f"acceptance {diag['acceptance_fraction']:.3f}")
    chain = diag['chain']
    names = list(objective.DEFAULT_PARAMS) + ['sigma_d']
    inference.corner_plot(chain, names, os.path.join(here, 'g2_corner.png'))
    np.save(os.path.join(here, 'g2_chain.npy'), chain)

    hand = dict(A=89.73e6, B=236.52e6, n=0.30, C=0.029, ipe=0.25, mu=0.2)
    print(f"\n{'param':8s} {'median':>12s} {'16%':>12s} {'84%':>12s} {'hand-cal':>12s}")
    for i, nm in enumerate(names):
        q = np.percentile(chain[:, i], [16, 50, 84])
        h = hand.get(nm, float('nan'))
        print(f'{nm:8s} {q[1]:12.4g} {q[0]:12.4g} {q[2]:12.4g} {h:12.4g}')
    # posterior correlation of the hardening trio
    import itertools
    print('\nposterior correlations:')
    for a, b in itertools.combinations(range(6), 2):
        c = np.corrcoef(chain[:, a], chain[:, b])[0, 1]
        if abs(c) > 0.4:
            print(f'  {names[a]} - {names[b]}: {c:+.2f}')


if __name__ == '__main__':
    main()
