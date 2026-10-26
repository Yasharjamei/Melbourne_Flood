"""Two checks on the "residents in flood areas" count, which the population back-tests do not cover.

1. Flood-count back-test, 2016 -> 2021. Predict each SA2's 2021 residents in today's flood areas the way
   forecast.py does (residents already there at their address share inside the flood areas, growth at the
   share of new addresses inside them) and compare with 2021 counted from the Census:
     a. method-consistent: 2021 Census mesh-block residents x share of the mesh block's addresses inside;
        measures the forecast's own error, given the counting method;
     b. exact: mesh blocks lying wholly inside the flood areas (all addresses and 95%+ of the area), where
        every Census resident is in a flood area whatever the counting method; measures how well residents
        are placed there.
   SA2 totals are given their true 2021 values, as in backtest.py: the population error of the SA2
   totals themselves (6.0% WAPE over 5 years, ensemble.py) comes on top.
   Also: how much the count depends on the counting method (address share vs area share of each mesh block).

2. Ground-level residents. The count includes everyone whose address is in a flood area, including people
   on the 30th floor. With the 2021 Census dwelling structure of each SA1 (houses, townhouses, flats in
   blocks of 1-2, 3, 4-8 and 9+ storeys) and an assumed share of each type's residents living at ground
   level, estimate how many of the residents in flood areas live at ground level, by council, 2025 and 2036.

    python pipeline/forecast/floodtest.py   (after forecast.py)  ->  data/processed/forecast_floodtest.json
"""
import json, os, re, sys
import numpy as np, pandas as pd, geopandas as gpd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, HERE)
from config import STUDIES, norm_lga
from backtest import table, codes
from forecast import polys, slr_layer, inside, SLR, CRS, RAW, FC, GROUND, g36_table

C16, C21 = np.datetime64("2016-08-09"), np.datetime64("2021-08-10")
INNER = ("Melbourne", "Port Phillip", "Yarra", "Stonnington")   # where Census night 2021 (lockdown, students away) emptied apartments


def wape(p, a):
    return float(np.abs(p - a).sum() / max(a.sum(), 1))


def summary(pred, obs, label, min_obs=100):
    keep = obs >= min_obs
    pe = np.abs(pred[keep] - obs[keep]) / obs[keep]
    return {"level": label, "units": int(keep.sum()), "wape": round(wape(pred[keep], obs[keep]), 4),
            "median_pct": round(float(np.median(pe)), 4) if keep.any() else None,
            "p80_pct": round(float(np.quantile(pe, .8)), 4) if keep.any() else None,
            "within_10pct": round(float((pe <= .1).mean()), 4) if keep.any() else None}


def backtest_flood():
    lgas = {norm_lga(n) for n in STUDIES["metro"]["lgas"]}
    mb = gpd.read_file(f"{RAW}/mb.geojson").to_crs(CRS)
    code = next(c for c in mb.columns if re.fullmatch(r"mb_code_2021|mb_code.*", c, re.I))
    sa1c = next(c for c in mb.columns if re.fullmatch(r"sa1_code_2021|sa1_code.*", c, re.I))
    mb["mb21"], mb["sa1"] = codes(mb[code]), codes(mb[sa1c])
    mb = mb[mb["sa1"].str.fullmatch(r"\d{11}")].reset_index(drop=True)
    mb["sa2"] = mb["sa1"].str[:9]
    c21 = table("data/raw/shared/mb_counts_2021.xlsx", "MB_CODE_2021", ["MB_CODE_2021", "PERSON"])
    c21["mb21"] = codes(c21["MB_CODE_2021"])
    c21 = c21[c21["mb21"].str.fullmatch(r"\d{11}")].drop_duplicates("mb21").set_index("mb21")
    mb["p21"] = pd.to_numeric(mb["mb21"].map(c21["PERSON"]), errors="coerce").fillna(0)
    lga = gpd.read_file(f"{RAW}/lga.geojson").to_crs(CRS)
    lga = lga[lga["lga_name_2021"].map(norm_lga).isin(lgas)]
    j = gpd.sjoin(mb.set_geometry(mb.geometry.representative_point())[["geometry"]], lga[["lga_name_2021", "geometry"]],
                  predicate="within", how="inner")
    mb["lga"] = j[~j.index.duplicated()]["lga_name_2021"].reindex(mb.index)
    mb = mb.dropna(subset=["lga"]).reset_index(drop=True)
    study = polys(lga.geometry)

    # 2016 residents on 2021 mesh blocks (ABS correspondence), as in backtest.py
    c16 = table(f"{FC}/mb_counts_2016.csv", "MB_CODE_2016", ["MB_CODE_2016", "PERSON"])
    c16["mb16"] = codes(c16["MB_CODE_2016"]); c16["p16"] = pd.to_numeric(c16["PERSON"], errors="coerce").fillna(0)
    c16 = c16[c16["mb16"].str.fullmatch(r"\d{11}")].drop_duplicates("mb16")
    cg = pd.read_csv(f"{FC}/cg_mb2016_mb2021.csv", dtype=str); cg.columns = [c.upper() for c in cg.columns]
    rc = next(c for c in cg.columns if re.search(r"RATIO", c))
    cg = cg.assign(mb16=codes(cg["MB_CODE_2016"]), mb21=codes(cg["MB_CODE_2021"]), r=pd.to_numeric(cg[rc], errors="coerce").fillna(0))
    x = cg.merge(c16[["mb16", "p16"]], on="mb16", how="inner")
    mb["p16"] = mb["mb21"].map((x["p16"] * x["r"]).groupby(x["mb21"]).sum()).fillna(0)

    # today's flood areas, as in forecast.py
    fl = gpd.read_file(f"{RAW}/flood.geojson").to_crs(CRS)
    ov = polys(polys(fl[fl.scheme_code.isin(["LSIO", "FO", "SBO"])].geometry).intersection(study))
    zone = polys([ov] + [slr_layer(n) for n in SLR[0][3]])

    def join(points):
        g = gpd.GeoDataFrame(geometry=gpd.points_from_xy(points[:, 0], points[:, 1]), crs=4326).to_crs(CRS)
        g = gpd.sjoin(g, mb[["geometry"]], predicate="within", how="inner")
        g = g[~g.index.duplicated()].rename(columns={"index_right": "m"})[["m", "geometry"]]
        g["in"] = inside(g, zone)
        return g
    a = join(np.load(f"{RAW}/addr.npy"))
    an = np.load(f"{FC}/addresses_new.npy")
    day = an[:, 2].astype("int64").astype("datetime64[D]")
    n = join(an); n["day"] = day[n.index.values]
    cnt = lambda g: (g.groupby("m").size().reindex(mb.index).fillna(0).values, g.groupby("m")["in"].sum().reindex(mb.index).fillna(0).values)
    n_all, i_all = cnt(a)
    n_p16, i_p16 = cnt(n[n["day"] >= C16]); n_p21, i_p21 = cnt(n[n["day"] >= C21])
    n_mid, i_mid = cnt(n[(n["day"] >= C16) & (n["day"] < C21)])

    # area share of every mesh block inside the flood areas (used where a mesh block has no addresses, and
    # for the counting-method comparison)
    parts = gpd.GeoDataFrame(geometry=list(getattr(zone, "geoms", [zone])), crs=CRS)
    cut = gpd.overlay(mb[["geometry"]].reset_index(names="m"), parts, how="intersection", keep_geom_type=True)
    area = (cut.area.groupby(cut["m"]).sum().reindex(mb.index).fillna(0) / mb.area.where(mb.area > 0, 1)).clip(0, 1).values

    def share(i, n_):
        return np.where(n_ > 0, i / np.where(n_ > 0, n_, 1), area)
    s16 = share(i_all - i_p16, n_all - n_p16)           # addresses that existed by Census 2016
    s21 = share(i_all - i_p21, n_all - n_p21)           # ... by Census 2021
    obs = mb["p21"].values * s21                          # 2021, counted the forecast's way
    obs_area = mb["p21"].values * area

    # prediction per SA2, the forecast's way, SA2 totals known
    g = pd.DataFrame({"sa2": mb["sa2"], "lga": mb["lga"], "p16": mb["p16"], "p21": mb["p21"], "e16": mb["p16"] * s16,
                      "nm": n_mid, "im": i_mid, "obs": obs, "obs_area": obs_area}).groupby("sa2")
    S = g.agg(lga=("lga", lambda v: v.value_counts().index[0]), p16=("p16", "sum"), p21=("p21", "sum"), e16=("e16", "sum"),
              nm=("nm", "sum"), im=("im", "sum"), obs=("obs", "sum"), obs_area=("obs_area", "sum"))
    se = np.where(S["p16"] > 0, S["e16"] / S["p16"].where(S["p16"] > 0, 1), 0)
    sn = np.where(S["nm"] >= 20, S["im"] / S["nm"].where(S["nm"] > 0, 1), se)
    d = S["p21"] - S["p16"]
    S["pred"] = S["p16"] * se + np.where(d > 0, d * sn, d * se)
    S["naive"] = S["p21"] * se                           # growth at the existing share (no new-address information)
    S["held"] = S["e16"]                                  # 2016 count carried forward unchanged
    C = S.groupby("lga")[["obs", "pred", "naive", "held", "obs_area"]].sum()

    # exact subset: mesh blocks wholly inside the flood areas
    whole = (n_all - n_p21 > 0) & (i_all - i_p21 == n_all - n_p21) & (area >= .95)
    k = max(0.0, (mb["p21"].sum() - mb["p16"].sum()) / max(n_mid.sum(), 1))
    raw = mb["p16"].values + n_mid * k                    # backtest.py model D placement, scaled to SA2 totals
    rs = pd.Series(raw).groupby(mb["sa2"].values).transform("sum").values
    P21 = pd.Series(mb["p21"].values).groupby(mb["sa2"].values).transform("sum").values
    placed = np.where(rs > 0, raw * P21 / np.where(rs > 0, rs, 1), 0)
    W = pd.DataFrame({"sa2": mb["sa2"][whole], "pred": placed[whole], "act": mb["p21"].values[whole]}).groupby("sa2").sum()

    out = {"period": "2016 -> 2021", "sa2_totals": "true 2021 values (population error of SA2 totals comes on top)",
           "total": {"observed_2021": round(float(S["obs"].sum())), "predicted": round(float(S["pred"].sum())),
                     "growth_at_existing_share": round(float(S["naive"].sum())), "count_2016": round(float(S["held"].sum()))},
           "sa2": {m: summary(S[m].values, S["obs"].values, "SA2s with 100+ residents in flood areas") for m in ("pred", "naive", "held")},
           "council": {m: summary(C[m].values, C["obs"].values, "councils") for m in ("pred", "naive", "held")},
           "exact": {"mesh_blocks": int(whole.sum()), "residents_2021": round(float(W["act"].sum())), "predicted": round(float(W["pred"].sum())),
                     "mesh_block": summary(placed[whole], mb["p21"].values[whole], "mesh blocks wholly in flood areas", min_obs=10),
                     "sa2": summary(W["pred"].values, W["act"].values, "SA2s, their wholly-flooded mesh blocks", min_obs=100)},
           "counting": {"address_share_2021": round(float(obs.sum())), "area_share_2021": round(float(obs_area.sum())),
                        "by_council": {l: [round(float(r.obs)), round(float(r.obs_area))] for l, r in C.sort_values("obs", ascending=False).iterrows()}},
           "growth": {"observed": round(float(S["obs"].sum() - S["held"].sum())), "predicted": round(float(S["pred"].sum() - S["held"].sum()))}}

    t = out["total"]
    print("1. Flood-count back-test, 2016 -> 2021 (SA2 totals known)")
    print(f"  residents in today's flood areas, 2021 counted from the Census: {t['observed_2021']:,}")
    print(f"  predicted from 2016 the forecast's way: {t['predicted']:,} ({t['predicted'] / t['observed_2021'] - 1:+.1%}); "
          f"growth at the existing share: {t['growth_at_existing_share']:,}; 2016 count unchanged: {t['count_2016']:,}")
    print(f"  growth in flood areas 2016 -> 2021: observed {out['growth']['observed']:+,}, predicted {out['growth']['predicted']:+,}")
    inner = C.index.to_series().str.replace(r" \(.*\)$", "", regex=True).isin(INNER).values
    gr = {"inner": inner, "rest": ~inner}
    out["growth_by_group"] = {}
    for nm, m_ in gr.items():
        o_, p_ = float(C["obs"][m_].sum() - C["held"][m_].sum()), float(C["pred"][m_].sum() - C["held"][m_].sum())
        out["growth_by_group"][nm] = {"observed": round(o_), "predicted": round(p_)}
        print(f"    {'inner 4 councils (' + ', '.join(INNER) + ')' if nm == 'inner' else 'other councils':60} observed {o_:+9,.0f}  predicted {p_:+9,.0f}")
    gc = (C["pred"] - C["held"]) - (C["obs"] - C["held"])
    print("    largest overstatements of growth: " + ", ".join(f"{l} {v:+,.0f}" for l, v in gc.sort_values(ascending=False).head(5).items()))
    print(f"  {'method':34} {'level':10} {'units':>6} {'WAPE':>7} {'median':>7} {'p80':>7} {'<=10%':>7}")
    names = {"pred": "forecast method", "naive": "growth at existing share", "held": "2016 count unchanged"}
    for lvl in ("sa2", "council"):
        for m_, r in out[lvl].items():
            print(f"  {names[m_]:34} {lvl:10} {r['units']:>6} {r['wape']:>7.1%} {r['median_pct']:>7.1%} {r['p80_pct']:>7.1%} {r['within_10pct']:>7.1%}")
    e = out["exact"]
    print(f"  exact subset: {e['mesh_blocks']:,} mesh blocks wholly in flood areas, {e['residents_2021']:,} residents in 2021, predicted {e['predicted']:,}; "
          f"mesh-block WAPE {e['mesh_block']['wape']:.1%}, SA2 WAPE {e['sa2']['wape']:.1%} ({e['sa2']['units']} SA2s)")
    c = out["counting"]
    print(f"  counting method, 2021: address share {c['address_share_2021']:,} vs area share {c['area_share_2021']:,} "
          f"({c['area_share_2021'] / max(c['address_share_2021'], 1) - 1:+.1%})")
    for l, (o, ar) in list(c["by_council"].items())[:8]:
        print(f"    {l:28} {o:>8,} {ar:>8,} ({ar / max(o, 1) - 1:+.0%})")
    return out


def ground_level():
    txt = open("data/processed/scenarios_sa1.js").read()
    A = json.loads(txt[txt.index("=") + 1:].rstrip().rstrip(";"))
    D = json.load(open("data/processed/scenarios.json"))
    lname = {c["code"]: c["name"] for c in D.get("councils", [])}
    years = A["years"]; codes1 = pd.Index(A["codes"])
    T = g36_table().reindex(codes1).fillna(0)
    res = {}
    for j, lab in enumerate(("central", "low", "high")):
        f = pd.Series({k: v[j] for k, v in GROUND.items()})
        tot, grd = T.sum(axis=1), (T * f).sum(axis=1)
        sa2 = pd.Series(codes1.str[:9], index=codes1)
        g2 = grd.groupby(sa2).transform("sum") / tot.groupby(sa2).transform("sum").replace(0, np.nan)
        g = (grd / tot.replace(0, np.nan)).where(tot >= 30, g2).fillna(g2).fillna(1.0)   # small SA1s: their SA2's mix
        res[lab] = g.values
    v = np.array(A["v"]["none"], dtype=float)          # SA1 x year, today's flood areas
    lg = pd.Series(A["lga"])
    rows = {}
    for y in (0, len(years) - 1):
        for lab, g in res.items():
            s = pd.Series(v[:, y] * g).groupby(lg).sum()
            for l, x in s.items():
                rows.setdefault(l, {}).setdefault(years[y], {})[lab] = round(float(x))
        for l, x in pd.Series(v[:, y]).groupby(lg).sum().items():
            rows[l][years[y]]["all"] = round(float(x))
    y0, y1 = years[0], years[-1]
    order = sorted(rows, key=lambda l: -rows[l][y1]["all"])
    tot = {y: {k: sum(rows[l][y][k] for l in rows) for k in ("all", "central", "low", "high")} for y in (y0, y1)}
    print(f"\n2. Residents in today's flood areas living at ground level (2021 dwelling mix of each SA1; assumed ground-level shares: "
          + ", ".join(f"{k} {v[0]:g}" for k, v in GROUND.items()) + ")")
    print(f"  all councils: {y0} {tot[y0]['all']:,} in flood areas, {tot[y0]['central']:,} at ground level ({tot[y0]['low']:,}-{tot[y0]['high']:,}); "
          f"{y1} {tot[y1]['all']:,}, {tot[y1]['central']:,} ({tot[y1]['low']:,}-{tot[y1]['high']:,})")
    print(f"  {'council':24} {y0:>9} {'ground':>9} {y1:>9} {'ground':>9} {'range':>15} {'share':>6}")
    for l in order[:15]:
        a, b = rows[l][y0], rows[l][y1]
        print(f"  {lname.get(l, l)[:24]:24} {a['all']:>9,} {a['central']:>9,} {b['all']:>9,} {b['central']:>9,} {str(b['low']) + '-' + str(b['high']):>15} {b['central'] / max(b['all'], 1):>6.0%}")
    print("  Growth is given each SA1's 2021 dwelling mix; where towers replace houses or industry (Fishermans Bend, Arden)"
          " this overstates the ground-level share of the new residents.")
    return {"assumed_ground_share": GROUND, "total": tot, "by_council": {lname.get(l, l): rows[l] for l in order}}


def main():
    out = {}
    for name, f in (("backtest", backtest_flood), ("ground_level", ground_level)):
        try:
            out[name] = f()
        except Exception as e:                            # one check failing must not hide the other
            import traceback; traceback.print_exc()
            out[name] = {"error": str(e)}
    os.makedirs("data/processed", exist_ok=True)
    json.dump(out, open("data/processed/forecast_floodtest.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
