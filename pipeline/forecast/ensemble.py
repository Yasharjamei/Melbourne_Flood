"""Ensemble back-test: split council totals into SA2s, and check VIF2023 against what happened.

VIF2023 publishes council (LGA) totals, not SA2s, so the forecast needs a council -> SA2 step.
This script measures that step on periods with known answers, using ABS Estimated Resident
Population (ERP) by SA2 on 2021 boundaries, 2001-2025, and Vicmap address creation dates.

Units are SA2 x council pieces: SA2s do not nest exactly in councils, so each SA2's ERP is split
across the councils it touches by its 2021 Census residents (mesh blocks). Council totals are set
to their true values ("oracle"), so the error measured is the split alone.

Models (each piece's value at the target year, then rescaled so each council hits its total):
  CS   constant share: every piece keeps its share of the council
  SG   share of growth: a piece gets the share of council growth it had over the previous window
  LIN  linear: the previous window's change per year continues
  EXP  exponential: the previous window's growth rate continues (clipped)
  HU   housing unit: council growth goes where addresses were created in the previous 5 years
  ENS  the mean of CS, SG, LIN, EXP and HU (the combination the literature recommends)
  ML   gradient boosting on the growth ratio, trained on earlier windows only
  ENS+ML the mean of ENS's members and ML
  HUK  nowcast: as HU but with addresses created after the base year (12-month lag). Not usable
       for 2036 (those addresses don't exist yet); shown as the best case for the near years.

Tests (base -> target): 2011->2016, 2016->2021, 2021->2025 (h = 5, 5, 4), and 2011->2021,
2011->2025 (h = 10, 14) for how error grows with the horizon; 2036 is 15 years from 2021.
Then: VIF2023 interpolated to 2025 against actual council ERP 2025, and the end-to-end error at
SA2 (VIF council totals + ensemble split) against actual SA2 ERP 2025.

Run after fetch.py and the main 01_fetch.py (mesh blocks, 2021 counts, councils):
    python pipeline/forecast/ensemble.py  ->  data/processed/forecast_ensemble.json, prints a report
"""
import csv, json, os, re, sys
import numpy as np, pandas as pd, geopandas as gpd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import STUDIES, norm_lga
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest import table, codes

RAW, FC, VIF = "data/raw/metro", "data/raw/forecast", "data/static/vif2023"
CBD = (144.9631, -37.8136)                                    # Melbourne GPO


# ---------------------------------------------------------------- inputs
def read_erp(path):
    """ABS SDMX csv (with labels) -> {region type: DataFrame(code, year, erp)}. Defensive: the
    column layout is discovered, and anything unexpected stops the run with what was seen."""
    rows = list(csv.reader(open(path, encoding="utf-8-sig", newline="")))
    hdr, body = rows[0], rows[1:]
    df = pd.DataFrame(body, columns=hdr[:len(body[0])] if body else hdr)
    up = {c: c.upper() for c in df.columns}
    tcol = next((c for c in df.columns if up[c] in ("TIME_PERIOD", "TIME_PERIOD: TIME PERIOD")), None) or \
        next((c for c in df.columns if "TIME" in up[c]), None)
    vcol = next((c for c in df.columns if up[c].startswith("OBS_VALUE")), None)
    rtcol = next((c for c in df.columns if up[c].startswith("REGION_TYPE")), None)
    rcol = next((c for c in df.columns if up[c].startswith("ASGS_2021") or up[c] == "REGION" or up[c].startswith("REGION:")), None)
    mcol = next((c for c in df.columns if up[c].startswith("MEASURE")), None)
    if not (tcol and vcol and rtcol and rcol):
        raise SystemExit(f"erp_sa2.csv: unexpected columns {list(df.columns)[:20]}; first row {body[:1]}")
    split = lambda s: s.astype(str).str.split(":").str[0].str.strip()
    df["rt"], df["code"] = split(df[rtcol]), split(df[rcol])
    df["year"] = pd.to_numeric(df[tcol].astype(str).str[:4], errors="coerce")
    df["erp"] = pd.to_numeric(df[vcol], errors="coerce")
    if mcol:
        ms = df[mcol].astype(str)
        print(f"  ERP measures: {ms.value_counts().to_dict()}")
        keep = ms[~ms.str.contains("change|growth|%|rate", case=False)].unique()
        df = df[ms.isin(keep[:1])]
    df = df.dropna(subset=["year", "erp"])
    print(f"  ERP region types: {df['rt'].value_counts().to_dict()}; years {int(df['year'].min())}-{int(df['year'].max())}")
    return {rt: g[["code", "year", "erp"]] for rt, g in df.groupby("rt")}


def vif_lga():
    """VIF2023 council population, 2021/26/31/36 -> DataFrame indexed by LGA code."""
    t = pd.read_excel(f"{VIF}/VIF2023_LGA_Pop_Hhold_Dwelling_Projections_to_2036.xlsx", sheet_name="Total_Population", header=None)
    h = t.index[t.iloc[:, 0].astype(str).str.contains("LGA", case=False) & t.iloc[:, 2].astype(str).str.startswith("2021")][0]
    d = t.loc[h + 1:, :5].dropna(subset=[0]); d.columns = ["code", "name", 2021, 2026, 2031, 2036]
    d["code"] = codes(d["code"])
    d = d[d["code"].str.fullmatch(r"\d{5}")]
    return d.set_index("code")


def pieces():
    """Mesh blocks in the study councils -> SA2 x council pieces with their share of the SA2's 2021
    residents, plus addresses and coordinates per piece."""
    lgas = [norm_lga(n) for n in STUDIES["metro"]["lgas"]]
    mb = gpd.read_file(f"{RAW}/mb.geojson")
    code = next(c for c in mb.columns if re.fullmatch(r"mb_code_2021|mb_code.*", c, re.I))
    sa1c = next(c for c in mb.columns if re.fullmatch(r"sa1_code_2021|sa1_code.*", c, re.I))
    mb["mb21"], mb["sa1"] = codes(mb[code]), codes(mb[sa1c])
    mb = mb[mb["sa1"].str.fullmatch(r"\d{11}")].reset_index(drop=True)
    mb["sa2"] = mb["sa1"].str[:9]
    c21 = table("data/raw/shared/mb_counts_2021.xlsx", "MB_CODE_2021", ["MB_CODE_2021", "PERSON"])
    c21["mb21"] = codes(c21["MB_CODE_2021"])
    c21 = c21[c21["mb21"].str.fullmatch(r"\d{11}")].drop_duplicates("mb21").set_index("mb21")
    mb["p21"] = pd.to_numeric(mb["mb21"].map(c21["PERSON"]), errors="coerce").fillna(0)
    lga = gpd.read_file(f"{RAW}/lga.geojson").to_crs(mb.crs)
    lga = lga[lga["lga_name_2021"].map(norm_lga).isin(lgas)]
    pt = mb.set_geometry(mb.geometry.representative_point())[["geometry"]]
    j = gpd.sjoin(pt, lga[["lga_code_2021", "geometry"]], predicate="within", how="inner")
    j = j[~j.index.duplicated()]
    mb["lga"] = j["lga_code_2021"].astype(str).reindex(mb.index)
    sa2_all = mb.groupby("sa2")["p21"].sum()                  # incl. any part outside the study councils
    mb = mb.dropna(subset=["lga"]).reset_index(drop=True)
    p = mb.groupby(["sa2", "lga"]).agg(p21=("p21", "sum"), n=("p21", "size")).reset_index()
    nmb = mb.groupby("sa2").size()
    p["w"] = np.where(p["sa2"].map(sa2_all) > 0, p["p21"] / p["sa2"].map(sa2_all).clip(lower=1), p["n"] / p["sa2"].map(nmb))
    xy = mb.to_crs(4326).geometry.representative_point()
    mb["lon"], mb["lat"] = xy.x.values, xy.y.values
    mb["area"] = mb.to_crs(7855).area / 1e6
    g = mb.groupby(["sa2", "lga"])
    p = p.merge(g.agg(lon=("lon", "mean"), lat=("lat", "mean"), area=("area", "sum")).reset_index(), on=["sa2", "lga"])
    p["dist_cbd"] = np.hypot((p["lon"] - CBD[0]) * 88.0, (p["lat"] - CBD[1]) * 111.0)   # km, good enough at this latitude
    # addresses by creation date, counted per piece
    a = np.load(f"{FC}/addresses_new.npy")
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(a[:, 0], a[:, 1]), crs=4326).to_crs(mb.crs)
    k = gpd.sjoin(pts, mb[["geometry"]], predicate="within", how="inner")
    day = a[k.index.values, 2].astype("int64").astype("datetime64[D]")
    key = (mb.loc[k["index_right"].values, "sa2"].values + "|" + mb.loc[k["index_right"].values, "lga"].values)
    addr = pd.DataFrame({"key": key, "day": day})
    yrs = pd.Series(day.astype("datetime64[Y]").astype(int) + 1970).value_counts().sort_index()
    print(f"  addresses in study mesh blocks by creation year: {yrs.to_dict()}")
    p["key"] = p["sa2"] + "|" + p["lga"]
    return p, addr


# ---------------------------------------------------------------- models
def rescale(pred, lga, target):
    pred = np.clip(np.asarray(pred, float), 0, None)
    s = pd.Series(pred).groupby(lga).transform("sum").values
    t = pd.Series(lga).map(target).values
    n = pd.Series(pred).groupby(lga).transform("size").values
    return np.where(s > 0, pred * t / np.where(s > 0, s, 1), t / n)


def addr_count(p, addr, start, end):
    """Addresses per piece created in [start, end) (dates as 'YYYY-MM-DD')."""
    m = (addr["day"] >= np.datetime64(start)) & (addr["day"] < np.datetime64(end))
    return p["key"].map(addr[m].groupby("key").size()).fillna(0).values


def features(P, p, addr, b, prev):
    """Per-piece features known at base year b."""
    with np.errstate(divide="ignore", invalid="ignore"):
        f = pd.DataFrame({
            "lp": np.log1p(P[b]),
            "g5": np.log((P[b] + 50) / (P[b - 5] + 50)),
            "g10": np.log((P[b] + 50) / (P[b - 10] + 50)) if b - 10 in P else 0.0,
            "a5": addr_count(p, addr, f"{b - 5}-07-01", f"{b}-07-01") / (P[b] + 50),
            "dens": np.log1p(P[b] / p["area"].clip(lower=0.01).values),
            "dist": p["dist_cbd"].values,
        })
    return f.fillna(0)


def run(P, p, addr, b, t, prev, ml_windows=()):
    """All models for base year b -> target t, council totals true (oracle). Returns {model: piece values}."""
    lga = p["lga"].values
    L = lambda y: pd.Series(P[y]).groupby(lga).sum()
    Lb, Lt, Lp = L(b), L(t), L(prev)
    h, hp = t - b, b - prev
    dL, dLp = pd.Series(lga).map(Lt - Lb).values, pd.Series(lga).map(Lb - Lp).values
    out = {}
    out["CS"] = rescale(P[b], lga, Lt)
    sg = P[b] + np.where(np.abs(dLp) > 0.02 * pd.Series(lga).map(Lb).values, (P[b] - P[prev]) / np.where(dLp == 0, 1, dLp) * dL, dL * P[b] / pd.Series(lga).map(Lb).values)
    out["SG"] = rescale(sg, lga, Lt)
    out["LIN"] = rescale(P[b] + (P[b] - P[prev]) * h / hp, lga, Lt)
    ratio = np.clip((P[b] + 1) / (P[prev] + 1), 0.6, 2.5) ** (h / hp)
    out["EXP"] = rescale(P[b] * ratio, lga, Lt)
    a5 = addr_count(p, addr, f"{b - 5}-07-01", f"{b}-07-01")
    A5 = pd.Series(a5).groupby(lga).transform("sum").values
    out["HU"] = rescale(P[b] + np.where((dL > 0) & (A5 > 0), dL * a5 / np.where(A5 > 0, A5, 1), dL * P[b] / pd.Series(lga).map(Lb).values), lga, Lt)
    members = ["CS", "SG", "LIN", "EXP", "HU"]
    out["ENS"] = np.mean([out[m] for m in members], axis=0)
    if ml_windows:
        from sklearn.ensemble import GradientBoostingRegressor
        X, y = [], []
        for (b0, t0, p0) in ml_windows:                        # earlier windows only: no peeking
            X.append(features(P, p, addr, b0, p0)); y.append(np.log((P[t0] + 50) / (P[b0] + 50)) * 5 / (t0 - b0))
        X, y = pd.concat(X), np.concatenate(y)
        w = np.concatenate([P[b0] for (b0, _, _) in ml_windows]) + 50
        gb = GradientBoostingRegressor(n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8, random_state=1)
        gb.fit(X, y, sample_weight=w)
        g = gb.predict(features(P, p, addr, b, prev)) * h / 5
        out["ML"] = rescale((P[b] + 50) * np.exp(g) - 50, lga, Lt)
        out["ENS+ML"] = np.mean([out[m] for m in members + ["ML"]], axis=0)
    ak = addr_count(p, addr, f"{b - 1}-07-01", f"{t - 1}-07-01")
    AK = pd.Series(ak).groupby(lga).transform("sum").values
    out["HUK"] = rescale(P[b] + np.where((dL > 0) & (AK > 0), dL * ak / np.where(AK > 0, AK, 1), dL * P[b] / pd.Series(lga).map(Lb).values), lga, Lt)
    return out


def score(pred_piece, act_piece, sa2):
    """SA2-level errors (pieces summed back to SA2s)."""
    pr = pd.Series(pred_piece).groupby(sa2).sum(); ac = pd.Series(act_piece).groupby(sa2).sum()
    keep = ac > 100
    pr, ac = pr[keep], ac[keep]
    ape = (pr - ac).abs() / ac
    return {"sa2s": int(keep.sum()), "wape": round(float((pr - ac).abs().sum() / ac.sum()), 4),
            "median_ape": round(float(ape.median()), 4), "p80_ape": round(float(ape.quantile(0.8)), 4),
            "p90_ape": round(float(ape.quantile(0.9)), 4), "within_5pct": round(float((ape <= 0.05).mean()), 4),
            "within_10pct": round(float((ape <= 0.10).mean()), 4)}, ape


# ---------------------------------------------------------------- main
def main():
    print("Inputs")
    erp = read_erp(f"{FC}/erp_sa2.csv")
    sa2_key = next(k for k in erp if re.fullmatch(r"SA2.*", k, re.I))
    e = erp[sa2_key].pivot_table(index="code", columns="year", values="erp", aggfunc="first")
    e.columns = e.columns.astype(int)
    e = e.T.interpolate(limit_direction="both").T.fillna(0)    # the odd missing year
    p, addr = pieces()
    years = [int(y) for y in e.columns]
    miss = ~p["sa2"].isin(e.index)
    print(f"  {len(p):,} SA2 x council pieces in {p['lga'].nunique()} councils; {int(miss.sum())} pieces lack ERP "
          f"({p.loc[miss, 'p21'].sum():,.0f} 2021 residents), dropped")
    p = p[~miss].reset_index(drop=True)
    if p["lga"].nunique() < len(STUDIES["metro"]["lgas"]) or not len(p):
        raise SystemExit(f"only {p['lga'].nunique()} of {len(STUDIES['metro']['lgas'])} councils have pieces with ERP")
    P = {y: (e.loc[p["sa2"], y].values.astype(float) * p["w"].values) for y in years}
    tot = {y: int(P[y].sum()) for y in (2001, 2006, 2011, 2016, 2021, max(years)) if y in P}
    print(f"  study-area ERP from SA2s: {tot}")
    last = max(years)
    sa2 = p["sa2"].values

    tests = [  # base, target, previous (history window start), ML training windows (earlier only)
        (2011, 2016, 2006, ()),
        (2016, 2021, 2011, ((2011, 2016, 2006),)),
        (2021, last, 2016, ((2011, 2016, 2006), (2016, 2021, 2011))),
        (2011, 2021, 2001, ()),
        (2011, last, 2001, ()),
    ]
    res = {"erp_last_year": last, "pieces": len(p), "councils": int(p["lga"].nunique()), "tests": {}}
    ape_store = {}
    print("\nCouncil -> SA2 split, council totals known (SA2 error)")
    print(f"{'test':14} {'model':7} {'SA2s':>5} {'WAPE':>7} {'median':>7} {'p80':>7} {'p90':>7} {'<=5%':>6} {'<=10%':>6}")
    for b, t, prev, mlw in tests:
        if t not in P or prev not in P:
            continue
        name = f"{b}->{t} (h={t - b})"
        out = run(P, p, addr, b, t, prev, mlw)
        res["tests"][name] = {}
        for m, v in out.items():
            s, ape = score(v, P[t], sa2)
            res["tests"][name][m] = s; ape_store[(name, m)] = ape
            print(f"{name:14} {m:7} {s['sa2s']:>5} {s['wape']:>7.1%} {s['median_ape']:>7.1%} {s['p80_ape']:>7.1%} {s['p90_ape']:>7.1%} {s['within_5pct']:>6.0%} {s['within_10pct']:>6.0%}")
        print()

    # Error by SA2 size and growth, for ranges: 2011 -> last (the horizon closest to 2036)
    name = f"2011->{last} (h={last - 2011})"
    if (name, "ENS") in ape_store:
        ape = ape_store[(name, "ENS")]
        s21 = pd.Series(P[2011]).groupby(sa2).sum().reindex(ape.index)
        g = (pd.Series(P[last]).groupby(sa2).sum() / pd.Series(P[2011]).groupby(sa2).sum().clip(lower=1)).reindex(ape.index)
        size = pd.cut(s21, [0, 5000, 10000, 15000, 1e9], labels=["<5k", "5-10k", "10-15k", "15k+"])
        grow = pd.cut(g, [0, 1.1, 1.3, 1.6, 1e9], labels=["<10%", "10-30%", "30-60%", "60%+"])
        res["ens_error_by_class"] = {
            "size": {str(k): {"sa2s": int(len(v)), "median_ape": round(float(v.median()), 4), "p80_ape": round(float(v.quantile(.8)), 4)} for k, v in ape.groupby(size, observed=True)},
            "growth": {str(k): {"sa2s": int(len(v)), "median_ape": round(float(v.median()), 4), "p80_ape": round(float(v.quantile(.8)), 4)} for k, v in ape.groupby(grow, observed=True)}}
        print(f"ENS error by class, {name}:")
        for kind, d in res["ens_error_by_class"].items():
            print("  " + kind + ": " + "; ".join(f"{k} n={v['sa2s']} median {v['median_ape']:.1%} p80 {v['p80_ape']:.1%}" for k, v in d.items()))

    # VIF2023 against what happened (councils), then end to end at SA2
    vif = vif_lga()
    lga_codes = sorted(p["lga"].unique())
    lg_rows = erp.get(next((k for k in erp if re.fullmatch(r"LGA.*", k, re.I)), ""), None)
    if lg_rows is not None and len(lg_rows):
        le = lg_rows.pivot_table(index="code", columns="year", values="erp", aggfunc="first")
        le.columns = le.columns.astype(int)
        act = {y: le.reindex(lga_codes)[y] for y in (2021, last)}
        src = "ABS ERP by LGA"
    else:
        act = {y: pd.Series(P[y]).groupby(p["lga"].values).sum().reindex(lga_codes) for y in (2021, last)}
        src = "ABS ERP by SA2, split to councils"
    v21, v26 = vif.reindex(lga_codes)[2021].astype(float), vif.reindex(lga_codes)[2026].astype(float)
    f = (last - 2021) / 5
    vlast = v21 + f * (v26 - v21)
    err = (vlast - act[last]) / act[last]
    gv, ga = (vlast - v21), (act[last] - act[2021])
    res["vif_check"] = {"year": last, "actual_source": src, "councils": len(lga_codes),
                        "vif_total": int(vlast.sum()), "actual_total": int(act[last].sum()),
                        "wape": round(float((vlast - act[last]).abs().sum() / act[last].sum()), 4),
                        "median_abs_pct": round(float(err.abs().median()), 4),
                        "growth_vif": int(gv.sum()), "growth_actual": int(ga.sum()),
                        "by_council": {vif.loc[c, "name"]: round(float(err[c]), 4) for c in lga_codes if c in vif.index}}
    print(f"\nVIF2023 vs actual, {last} ({src}; VIF interpolated 2021->2026):")
    print(f"  31-council total: VIF {vlast.sum():,.0f}, actual {act[last].sum():,.0f} ({vlast.sum() / act[last].sum() - 1:+.1%}); "
          f"growth since 2021 VIF {gv.sum():,.0f} vs actual {ga.sum():,.0f}")
    print(f"  council WAPE {res['vif_check']['wape']:.1%}, median |error| {res['vif_check']['median_abs_pct']:.1%}")
    worst = err.abs().sort_values(ascending=False).index[:6]
    print("  largest: " + "; ".join(f"{vif.loc[c, 'name']} {err[c]:+.1%}" for c in worst if c in vif.index))

    # End to end: VIF council totals (interpolated to last) split by each model from base 2021
    lg = p["lga"].values
    share = pd.Series(P[2021]).groupby(lg).sum()
    target = vlast * (share / act[2021])                       # the study part of each council
    out = run({**P, last: rescale(P[last], lg, target)}, p, addr, 2021, last, 2016, ((2011, 2016, 2006), (2016, 2021, 2011)))
    res["end_to_end"] = {}
    print(f"\nEnd to end, 2021 -> {last}: VIF council totals + split, against actual SA2 ERP")
    for m in ("CS", "ENS", "ENS+ML", "HUK"):
        if m in out:
            s, _ = score(out[m], P[last], sa2); res["end_to_end"][m] = s
            print(f"  {m:7} WAPE {s['wape']:.1%}, median {s['median_ape']:.1%}, p80 {s['p80_ape']:.1%}, within 10% {s['within_10pct']:.0%}")

    os.makedirs("data/processed", exist_ok=True)
    json.dump(res, open("data/processed/forecast_ensemble.json", "w"), indent=1)
    print("\nWAPE = total |error| / total residents, over SA2s with 100+ residents. Council totals are true values in the")
    print("split tests; in the end-to-end test they are VIF2023's. p80/p90 = 80th/90th percentile of SA2 % error.")


if __name__ == "__main__":
    main()
