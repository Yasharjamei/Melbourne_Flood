"""Lama & Sun (2026) section 2.2.3 / Table 5 / Fig. 4: GWR and MGWR of flood depth on the ten
index indicators, per SA1. Called from 02_build.py for study areas with "mgwr": True.

The paper is inconsistent about the MGWR response: section 2.2.3 says flood depth is the dependent
variable with ten explanatory variables; section 3.2 says the model explains IFRI with flood depth
among eleven. Fig. 4 has ten coefficient maps (b-k), and IFRI is a deterministic function of the
same inputs (so regressing it on them would give R^2 ~ 1, not the reported 0.72). So this follows
2.2.3: y = flood depth (here: overlay-share proxy), X = the other ten indicators.
"""
import time
import numpy as np

EXPLANATORY = [("elev", "Elevation"), ("sand", "Sand % in soil"), ("urban", "Land use (built-up share)"),
               ("pop", "Population"), ("dwell", "Number of dwellings"), ("ltc", "Long-term health condition"),
               ("dep", "Dependent population"), ("emp", "Employed population"), ("edu", "Educated population"),
               ("incgen", "Mean income generating population")]
BW_MIN = 50
PAPER_TABLE5 = {"gwr": {"R2": 0.7546, "adjR2": 0.6838, "AICc": 916.095, "bw": 62},
                "mgwr": {"R2": 0.7669, "adjR2": 0.7242, "AICc": 831.622}}


def run(ind, coords):
    """ind: DataFrame with 'flood' and EXPLANATORY columns; coords: (n, 2) projected metres."""
    from mgwr.gwr import GWR, MGWR
    from mgwr.sel_bw import Sel_BW
    t0 = time.time()
    use = [(k, l) for k, l in EXPLANATORY if k in ind and ind[k].notna().all() and ind[k].std() > 0]
    dropped = [l for k, l in EXPLANATORY if (k, l) not in use]
    z = lambda a: (a - a.mean()) / a.std()
    y = z(ind["flood"].to_numpy(float)).reshape(-1, 1)
    X = np.column_stack([z(ind[k].to_numpy(float)) for k, _ in use])
    coords = np.asarray(coords, float)
    # Variance inflation factors: the paper's indicators are counts, so population, dwellings,
    # employed, educated and income earners all scale with SA1 size and are strongly collinear.
    vif = []
    for j in range(X.shape[1]):
        o = np.delete(X, j, axis=1); A = np.column_stack([np.ones(len(X)), o])
        beta, *_ = np.linalg.lstsq(A, X[:, j], rcond=None); r2 = 1 - ((X[:, j] - A @ beta) ** 2).sum() / ((X[:, j] - X[:, j].mean()) ** 2).sum()
        vif.append(round(float(1 / max(1e-9, 1 - r2)), 1))
    print("VIF:", dict(zip([l for _, l in use], vif)))

    gsel = Sel_BW(coords, y, X, kernel="bisquare", fixed=False)
    gbw = gsel.search()
    g = GWR(coords, y, X, gbw, kernel="bisquare", fixed=False).fit()

    # Bandwidth floor: with 11 collinear covariates, local fits on ~10 neighbours are singular
    # (the first real run chose 10-16 and diverged to R2 = -3.7e20). 50 is about 10% of the SA1s.
    msel = Sel_BW(coords, y, X, multi=True, kernel="bisquare", fixed=False)
    mbws = msel.search(multi_bw_min=[BW_MIN])
    m = MGWR(coords, y, X, msel, kernel="bisquare", fixed=False).fit()
    ok = bool(np.isfinite(m.R2) and -0.05 <= m.R2 <= 1 and np.isfinite(m.params).all() and np.abs(m.params).max() < 1e3)
    res = m if ok else g                      # never publish a diverged model's coefficients
    sig = res.filter_tvals() != 0             # corrected for multiple testing (da Silva & Fotheringham)
    try:
        mlocal = np.asarray(res.localR2).ravel(); mlocal_src = "MGWR" if ok else "GWR"
    except Exception:                         # older mgwr: local R2 only for GWR
        mlocal, mlocal_src = np.asarray(g.localR2).ravel(), "GWR"
    if not ok:
        print("WARNING MGWR did not converge; coefficient maps use GWR")

    r3 = lambda v: round(float(v), 3)
    print(f"GWR  bw={int(gbw)} R2={g.R2:.3f} adjR2={g.adj_R2:.3f} AICc={g.aicc:.1f}")
    print(f"MGWR bws={[int(b) for b in mbws]} R2={m.R2:.3f} adjR2={m.adj_R2:.3f} AICc={m.aicc:.1f}  ({time.time() - t0:.0f}s)")
    return dict(
        y="Flood depth (proxy: share of SA1 in LSIO/FO/SBO overlays)",
        vars=["Intercept"] + [l for _, l in use], dropped=dropped,
        gwr=dict(R2=r3(g.R2), adjR2=r3(g.adj_R2), AICc=r3(g.aicc), bw=int(gbw)),
        mgwr=dict(ok=ok, R2=r3(m.R2) if ok else None, adjR2=r3(m.adj_R2) if ok else None, AICc=r3(m.aicc) if ok else None,
                  bws=[int(b) for b in mbws], bw_min=BW_MIN),
        coef_model="MGWR" if ok else "GWR", gwr_bw=int(gbw),
        paper=PAPER_TABLE5, localR2_model=mlocal_src,
        coef=[[r3(v) for v in row] for row in res.params],
        sig=[[int(v) for v in row] for row in sig],
        localR2=[r3(v) for v in mlocal], vif=[None] + vif,
    )
