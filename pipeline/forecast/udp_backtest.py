"""Back-test of the Urban Development Program step: would the UDP have placed growth better?

The forecast places council growth on Urban Development Program supply (major redevelopment projects
and greenfield land, weighted by status) and the remainder where addresses were recently created.
UDP 2025 cannot be tested (its future has not happened), but the 2017 and 2018 editions can: they are
CC BY 4.0 (DataVic; Department of Transport and Planning), kept in data/static/udp_history/.

From base 2017 (and 2018) to 2021 and the latest ERP year, council totals known ("oracle", as in
ensemble.py), each SA2 x council piece's population is predicted by
  HU     growth where addresses were created in the previous 5 years (the open-data method)
  UDP    UDP supply of that edition, weighted by status and timing, capped at the council's growth;
         the remainder by recent addresses (the forecast's method)
  CS     constant share (yardstick)
and scored against actual SA2 ERP. Greenfield 2017 comes with expected timing bands, so the weights
assumed for 2025 (forecast.STATUS) can be checked against what was built.

    python pipeline/forecast/udp_backtest.py   ->  data/processed/forecast_udp_backtest.json
"""
import json, os, re, sys, zipfile
import numpy as np, pandas as pd, geopandas as gpd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, HERE)
from ensemble import read_erp, pieces, rescale, addr_count, score, FC

H = "data/static/udp_history"
PIECES = "data/static/sa2_council_pieces_7855.geojson"
PPD = 2.6                                # residents per new dwelling (Greater Melbourne, roughly)
# (share built, years to build): major redevelopment status; greenfield timing band (2017) or status (2018)
MRS_W = {"Under Construction": (0.95, 2), "Firm": (0.80, 5), "Likely": (0.50, 8), "Possible": (0.25, 11)}
BH17_W = {"1-2years": (0.95, 2), "3-5years": (0.90, 5), "6-10years": (0.60, 10), "11+ years": (0.15, 11),
          "UGZ (PSP Required)": (0.10, 11), "No Timing": (0.10, 11), "Potential Residential": (0.05, 11)}
BH18_W = {"Lots with a title": (0.95, 2), "Proposed lots": (0.85, 5), "Zoned englobo land": (0.60, 11),
          "Unzoned englobo land requiring a PSP": (0.15, 11)}


def layer(edition):
    z = f"{H}/{edition}.zip"
    inner = next(n for n in zipfile.ZipFile(z).namelist() if n.endswith(f"/{edition}.shp"))
    return gpd.read_file(f"zip://{z}!{inner}").to_crs(7855)


def supply(edition_mrs, edition_bh, wts_bh, pc):
    """Weighted UDP supply per piece key, as {key: [(dwellings, share built, years)]} frames."""
    m = layer(edition_mrs)
    m = m[m["STATUS"].isin(MRS_W)]
    m = m.set_geometry(m.geometry.representative_point())
    j = gpd.sjoin(m[["STATUS", "TOTAL_DWEL", "APARTMENTS", "geometry"]], pc, predicate="within", how="inner")
    rows = [pd.DataFrame({"key": j["key"], "n": j["TOTAL_DWEL"].astype(float), "status": "mrs:" + j["STATUS"]})]
    b = layer(edition_bh)
    col = "DEV_STATUS"
    if "RECENTDEV" in b.columns:                       # 2017: developed but still under construction -> 1-2 years
        b.loc[(b[col] == "Developed") & (b["RECENTDEV"].astype(str) == "Under Construction"), col] = "1-2years"
    b = b[b[col].isin(wts_bh)][[col, "TOTALLOTS", "geometry"]]
    b["a0"] = b.area
    x = gpd.overlay(b, pc, how="intersection", keep_geom_type=True)
    x["n"] = x["TOTALLOTS"].astype(float) * x.area / x["a0"].where(x["a0"] > 0, 1)
    rows.append(pd.DataFrame({"key": x["key"], "n": x["n"], "status": "bh:" + x[col]}))
    s = pd.concat(rows)
    print(f"  {edition_mrs} + {edition_bh}: " + ", ".join(f"{k} {v:,.0f}" for k, v in s.groupby("status")["n"].sum().items()))
    return s


def udp_model(P, p, addr, b, t, s, wts):
    """The forecast's placement: expected UDP dwellings by t (capped at council growth), remainder by recent addresses."""
    lga = p["lga"].values
    Lb, Lt = (pd.Series(P[y]).groupby(lga).sum() for y in (b, t))
    dL = pd.Series(lga).map(Lt - Lb).values
    w = {**{"mrs:" + k: v for k, v in MRS_W.items()}, **{"bh:" + k: v for k, v in wts.items()}}
    s = s.assign(e=[n * w[st][0] * min(1.0, (t - b) / w[st][1]) for n, st in zip(s["n"], s["status"])])
    E = p["key"].map(s.groupby("key")["e"].sum()).fillna(0).values * PPD          # residents
    E_l = pd.Series(E).groupby(lga).transform("sum").values
    scale = np.where((E_l > dL) & (E_l > 0), np.clip(dL, 0, None) / np.where(E_l > 0, E_l, 1), 1.0)
    E = E * scale
    R = np.clip(dL - pd.Series(E).groupby(lga).transform("sum").values, 0, None)   # council growth not covered by UDP
    a5 = addr_count(p, addr, f"{b - 5}-07-01", f"{b}-07-01")
    A5 = pd.Series(a5).groupby(lga).transform("sum").values
    Pl = pd.Series(lga).map(Lb).values
    infill = np.where(A5 > 0, R * a5 / np.where(A5 > 0, A5, 1), R * P[b] / np.where(Pl > 0, Pl, 1))
    neg = np.where(dL < 0, dL * P[b] / np.where(Pl > 0, Pl, 1), 0)                   # shrinking councils: pro rata
    return rescale(P[b] + E + infill + neg, lga, Lt), float(E.sum())


def built_out():
    """Share of each 2017 status / timing band actually built: addresses created on the site after mid-2017,
    by mid-2021 and mid-2025, against its dwellings (redevelopment) or lots (greenfield), capped at 1 per site.
    Compare with the share-built weights assumed for 2025 (forecast.STATUS: under construction .95 in 2
    years, firm .80 in 5, likely .50 in 8, possible .25 in 11; titled .95, proposed .85, zoned .60, unzoned .15)."""
    a = np.load(f"{FC}/addresses_new.npy")
    day = a[:, 2].astype("int64").astype("datetime64[D]")
    sel = day >= np.datetime64("2017-07-01")
    pts = gpd.GeoDataFrame({"day": day[sel]}, geometry=gpd.points_from_xy(a[sel, 0], a[sel, 1]), crs=4326).to_crs(7855)
    res = {}
    print("\nUDP 2017: share of supply built (addresses created on the site since mid-2017 / dwellings or lots)")
    for ed, col, n in (("MRS2017", "STATUS", "TOTAL_DWEL"), ("BH2017", "DEV_STATUS", "TOTALLOTS")):
        g = layer(ed)
        if "RECENTDEV" in g.columns:
            g.loc[(g[col] == "Developed") & (g["RECENTDEV"].astype(str) == "Under Construction"), col] = "1-2years"
        g = g[g[n].astype(float) > 0].reset_index(drop=True)
        if "APARTMENTS" in g.columns:                  # houses and townhouses only: one address per dwelling, no shared addresses
            g = pd.concat([g.assign(**{col: g[col]}),
                           g[g["APARTMENTS"].fillna(0).astype(float) == 0].assign(**{col: g[col] + " (no apartments)"})], ignore_index=True)
        j = gpd.sjoin(pts, g[[col, n, "geometry"]], predicate="within", how="inner")
        res[ed] = {}
        for y in (2021, 2025):
            c = j[j["day"] < np.datetime64(f"{y}-07-01")].groupby("index_right").size().reindex(g.index).fillna(0)
            share = np.minimum(c.values, g[n].astype(float).values)
            t = pd.DataFrame({"st": g[col], "built": share, "n": g[n].astype(float)}).groupby("st").sum()
            for st, r in t.iterrows():
                res[ed].setdefault(st, {"supply": round(float(r["n"]))})[str(y)] = round(float(r["built"] / max(r["n"], 1)), 3)
        print(f"  {ed:8} {'status':24} {'supply':>9} {'built by 2021':>14} {'by 2025':>8}")
        for st, r in sorted(res[ed].items(), key=lambda kv: -kv[1]["supply"]):
            print(f"  {'':8} {st:24} {r['supply']:>9,} {r.get('2021', 0):>14.0%} {r.get('2025', 0):>8.0%}")
    print("  Addresses undercount apartment buildings that share one street address, so redevelopment shares are lower bounds.")
    return res


def main():
    erp = read_erp(f"{FC}/erp_sa2.csv")
    e = erp[next(k for k in erp if re.fullmatch(r"SA2.*", k, re.I))].pivot_table(index="code", columns="year", values="erp", aggfunc="first")
    e.columns = e.columns.astype(int)
    e = e.T.interpolate(limit_direction="both").T.fillna(0)
    p, addr = pieces()
    p = p[p["sa2"].isin(e.index)].reset_index(drop=True)
    years = [int(y) for y in e.columns]
    P = {y: e.loc[p["sa2"], y].values.astype(float) * p["w"].values for y in years}
    last, sa2, lga = max(years), p["sa2"].values, p["lga"].values
    pc = gpd.read_file(PIECES).to_crs(7855)
    pc["key"] = pc["sa2_code_2021"].astype(str) + "|" + pc["lga_code"].astype(str)
    pc = pc[["key", "geometry"]]

    out, rows = {"ppd": PPD, "weights": {"mrs": MRS_W, "bh2017": BH17_W, "bh2018": BH18_W}, "tests": {}}, []
    print("\nUDP back-test: council totals known; SA2 error")
    print(f"  {'test':22} {'model':5} {'SA2s':>5} {'WAPE':>7} {'median':>7} {'p80':>7} {'<=10%':>6}   {'fast-growing SA2s (30%+)':>26}")
    for b, mrs, bh, wts in ((2017, "MRS2017", "BH2017", BH17_W), (2018, "MRS2018", "BH2018", BH18_W)):
        s = supply(mrs, bh, wts, pc)
        for t in (2021, last):
            if t not in P or b not in P:
                continue
            name = f"{b}->{t} (h={t - b}), {mrs}"
            dL = pd.Series(lga).map(pd.Series(P[t]).groupby(lga).sum() - pd.Series(P[b]).groupby(lga).sum()).values
            a5 = addr_count(p, addr, f"{b - 5}-07-01", f"{b}-07-01")
            A5 = pd.Series(a5).groupby(lga).transform("sum").values
            Pl = pd.Series(lga).map(pd.Series(P[b]).groupby(lga).sum()).values
            models = {"CS": rescale(P[b], lga, pd.Series(P[t]).groupby(lga).sum()),
                      "HU": rescale(P[b] + np.where((dL > 0) & (A5 > 0), dL * a5 / np.where(A5 > 0, A5, 1), dL * P[b] / Pl), lga, pd.Series(P[t]).groupby(lga).sum())}
            models["UDP"], used = udp_model(P, p, addr, b, t, s, wts)
            grow = (pd.Series(P[t]).groupby(sa2).sum() / pd.Series(P[b]).groupby(sa2).sum().clip(lower=1)) >= 1.3
            cg = float((pd.Series(P[t]).groupby(lga).sum() - pd.Series(P[b]).groupby(lga).sum()).clip(lower=0).sum())   # once per council
            out["tests"][name] = {"udp_residents_placed": round(used), "council_growth": round(cg)}
            for m_, v in models.items():
                sc, ape = score(v, P[t], sa2)
                fast = ape[ape.index.isin(grow[grow].index)]
                sc["fast_growing"] = {"sa2s": int(len(fast)), "median_ape": round(float(fast.median()), 4) if len(fast) else None,
                                      "p80_ape": round(float(fast.quantile(.8)), 4) if len(fast) else None}
                out["tests"][name][m_] = sc
                print(f"  {name:22} {m_:5} {sc['sa2s']:>5} {sc['wape']:>7.1%} {sc['median_ape']:>7.1%} {sc['p80_ape']:>7.1%} {sc['within_10pct']:>6.0%}   "
                      f"n={sc['fast_growing']['sa2s']:>3} median {sc['fast_growing']['median_ape'] or 0:>6.1%} p80 {sc['fast_growing']['p80_ape'] or 0:>6.1%}")
            print(f"    UDP-placed residents {used:,.0f} of {cg:,.0f} council growth")
    out["built"] = built_out()
    os.makedirs("data/processed", exist_ok=True)
    json.dump(out, open("data/processed/forecast_udp_backtest.json", "w"), indent=1)
    print("  WAPE over SA2s with 100+ residents; fast-growing = SA2s that grew 30%+ over the test period.")


if __name__ == "__main__":
    main()
