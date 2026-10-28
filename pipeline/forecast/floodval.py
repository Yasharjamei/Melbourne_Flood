"""Our flood areas against a real flood: the October 2022 event.

The Victorian Flood History October 2022 extent (DEECA, CC BY 4.0) maps where water actually went. For the
residents inside it (2021 Census mesh-block counts, placed by address points as everywhere in this
project), how many were inside our flood areas beforehand?
  - planning-scheme flood overlays (LSIO, FO, SBO), the main definition used on the site and the forecast;
  - the modelled 1% AEP (1-in-100-year) extent from the Victorian Flood Database;
  - either of the two.
A high share means the flood areas catch the people a real flood reaches. The reverse (residents in flood
areas the October 2022 water did not reach) is not an error: one flood is not every flood, and the event was
a 1-in-100-year flood or larger only on some rivers (the Maribyrnong among them).

    python pipeline/forecast/floodval.py   (after forecast.py's inputs)  ->  data/processed/forecast_floodval.json
"""
import json, os, re, sys
import numpy as np, pandas as pd, geopandas as gpd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, HERE)
from config import STUDIES, norm_lga
from backtest import table, codes
from forecast import polys, inside, CRS, RAW

OCT = f"{RAW}/flood_oct2022.geojson"
HIST = "data/raw/forecast/flood_history.geojson"
AEP = next((f for f in ("data/raw/forecast/aep100.geojson", "data/raw/shared/aep1.geojson") if os.path.exists(f)), "data/raw/shared/aep1.geojson")


def main():
    if not os.path.exists(OCT):
        raise SystemExit(f"{OCT} missing (fetch.py --main downloads it)")
    lgas = {norm_lga(n) for n in STUDIES["metro"]["lgas"]}
    mb = gpd.read_file(f"{RAW}/mb.geojson").to_crs(CRS)
    code = next(c for c in mb.columns if re.fullmatch(r"mb_code_2021|mb_code.*", c, re.I))
    mb["mb21"] = codes(mb[code])
    c21 = table("data/raw/shared/mb_counts_2021.xlsx", "MB_CODE_2021", ["MB_CODE_2021", "PERSON"])
    c21["mb21"] = codes(c21["MB_CODE_2021"])
    c21 = c21[c21["mb21"].str.fullmatch(r"\d{11}")].drop_duplicates("mb21").set_index("mb21")
    mb["p21"] = pd.to_numeric(mb["mb21"].map(c21["PERSON"]), errors="coerce").fillna(0)
    lga = gpd.read_file(f"{RAW}/lga.geojson").to_crs(CRS)
    lga = lga[lga["lga_name_2021"].map(norm_lga).isin(lgas)]
    j = gpd.sjoin(mb.set_geometry(mb.geometry.representative_point())[["geometry"]], lga[["lga_name_2021", "geometry"]], predicate="within", how="inner")
    mb["lga"] = j[~j.index.duplicated()]["lga_name_2021"].reindex(mb.index)
    mb = mb.dropna(subset=["lga"]).reset_index(drop=True)
    study = polys(lga.geometry)

    fl = gpd.read_file(f"{RAW}/flood.geojson").to_crs(CRS)
    zones = {"overlays": polys(polys(fl[fl.scheme_code.isin(["LSIO", "FO", "SBO"])].geometry).intersection(study)),
             "oct2022": polys(polys(gpd.read_file(OCT).to_crs(CRS).geometry).intersection(study))}
    if os.path.exists(AEP):
        zones["aep"] = polys(polys(gpd.read_file(AEP).to_crs(CRS).geometry).intersection(study))
    print("Areas (km2): " + ", ".join(f"{k} {z.area / 1e6:,.1f}" for k, z in zones.items()))

    a = np.load(f"{RAW}/addr.npy")
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(a[:, 0], a[:, 1]), crs=4326).to_crs(CRS)
    pts = gpd.sjoin(pts, mb[["geometry"]], predicate="within", how="inner")
    pts = pts[~pts.index.duplicated()].rename(columns={"index_right": "m"})[["m", "geometry"]]
    for k, z in zones.items():
        pts[k] = inside(pts, z)
    combos = {"oct2022": pts["oct2022"], "oct_and_overlays": pts["oct2022"] & pts["overlays"], "overlays": pts["overlays"]}
    if "aep" in zones:
        combos.update({"oct_and_aep": pts["oct2022"] & pts["aep"], "oct_and_either": pts["oct2022"] & (pts["overlays"] | pts["aep"]), "aep": pts["aep"]})
    n = pts.groupby("m").size().reindex(mb.index)
    res = pd.DataFrame({"lga": mb["lga"]})
    for k, flag in combos.items():
        share = flag.groupby(pts["m"]).mean().reindex(mb.index)
        res[k] = mb["p21"] * share.fillna(0)                 # mesh blocks without addresses: no residents placed
    C = res.groupby("lga").sum()
    C = C[C["oct2022"] >= 20].sort_values("oct2022", ascending=False)
    tot = res.drop(columns="lga").sum()

    pct = lambda a_, b_: a_ / b_ if b_ > 0 else float("nan")
    print("\nResidents (Census 2021, placed by address) inside the observed October 2022 flood, and how many of them")
    print("were inside our flood areas beforehand")
    hdr = f"  {'council':26} {'in Oct 2022 flood':>17} {'in overlays':>12}" + (f" {'in 1% AEP':>10} {'in either':>10}" if "aep" in zones else "")
    print(hdr)
    rows = list(C.iterrows()) + [("all 31 councils", tot)]
    out = {"councils": {}}
    for l, r in rows:
        line = f"  {str(l)[:26]:26} {r['oct2022']:>17,.0f} {pct(r['oct_and_overlays'], r['oct2022']):>12.0%}"
        rec = {"in_oct2022": round(float(r["oct2022"])), "share_in_overlays": round(float(pct(r["oct_and_overlays"], r["oct2022"])), 3)}
        if "aep" in zones:
            line += f" {pct(r['oct_and_aep'], r['oct2022']):>10.0%} {pct(r['oct_and_either'], r['oct2022']):>10.0%}"
            rec.update({"share_in_aep": round(float(pct(r["oct_and_aep"], r["oct2022"])), 3), "share_in_either": round(float(pct(r["oct_and_either"], r["oct2022"])), 3)})
        print(line); out["councils"][str(l)] = rec
    print(f"  For scale: residents in planning overlays, all councils, {tot['overlays']:,.0f}"
          + (f"; in the 1% AEP extent {tot['aep']:,.0f}" if "aep" in zones else ""))
    print("  A resident outside our flood areas but inside the October 2022 water is a miss. The reverse is not an error"
          " (one flood is not every flood).")
    out["past_floods"] = past_floods(pts, mb, study, "aep" in zones, zones["overlays"], dict(zip(lga["lga_name_2021"], lga.geometry)))
    os.makedirs("data/processed", exist_ok=True)
    json.dump(out, open("data/processed/forecast_floodval.json", "w"), indent=1)


def label_cols(h):
    """Columns naming the event and its date in the Victorian Flood Database history layer (names vary)."""
    cols = [c for c in h.columns if c != "geometry"]
    txt = lambda c: h[c].dtype == object or str(h[c].dtype).startswith("str")
    name = next((c for c in cols if re.search(r"event|flood_?name|^name$|descr|title", c, re.I) and txt(c)), None)
    date = next((c for c in cols if re.search(r"date|year|yr", c, re.I)), None)
    return name, date


def past_floods(pts, mb, study, has_aep, zones_ov=None, lga_geom=None):
    """The same test against every past flood recorded in the Victorian Flood Database history layer."""
    if not os.path.exists(HIST):
        print("\nPast flood extents: not present"); return {}
    h = gpd.read_file(HIST).to_crs(CRS)
    name, date = label_cols(h)
    print(f"\nPast flood extents: {len(h)} polygons; fields {[c for c in h.columns if c != 'geometry']}; event from {name!r}, date from {date!r}")
    # START_DATE is YYYYMMDD in this layer, 0 when unknown; the layer has no event names, so undated
    # extents are told apart by gauge and survey plan
    if date:
        v = pd.to_numeric(h[date], errors="coerce")
        dt = pd.to_datetime(v.where(v > 18000101).astype("Int64").astype(str), format="%Y%m%d", errors="coerce")
        if dt.isna().all() and not pd.api.types.is_numeric_dtype(h[date]):
            dt = pd.to_datetime(h[date], errors="coerce")
        dlab = dt.dt.strftime("%Y-%m-%d").fillna("undated")
    else:
        dlab = pd.Series("undated", index=h.index)
    extra = [c for c in ("GAUGEID", "PLAN_NO") if c in h.columns]
    tail = h[extra].astype(str).agg(" ".join, axis=1).str.strip() if extra else ""
    lab = (dlab + (", gauge/plan " + tail if extra else "")) if not name else (dlab + " " + h[name].fillna("").astype(str)).str.strip()
    h["event"] = lab.values
    h = h[h.geometry.intersects(study)]
    # residents per address: 2021 mesh-block persons spread over its addresses
    n = pts.groupby("m").size()
    w = (pts["m"].map(mb["p21"]) / pts["m"].map(n)).fillna(0)
    j = gpd.sjoin(pts[["geometry"]], h[["event", "geometry"]], predicate="within", how="inner")
    j = j.assign(_i=j.index).drop_duplicates(["_i", "event"])                    # once per address and event
    ix = j.index
    d = pd.DataFrame({"event": j["event"].values, "w": w.reindex(ix).values, "ov": pts.loc[ix, "overlays"].values})
    if has_aep:
        d["aep"] = pts.loc[ix, "aep"].values
        d["either"] = d["ov"] | d["aep"]
    anyev = pts.index.isin(ix)
    tot = {"w": w[anyev].sum(), "ov": (w * pts["overlays"])[anyev].sum()}
    if has_aep:
        tot.update({"aep": (w * pts["aep"])[anyev].sum(), "either": (w * (pts["overlays"] | pts["aep"]))[anyev].sum()})
    g = d.assign(wov=d.w * d.ov, **({"waep": d.w * d.aep, "weit": d.w * d.either} if has_aep else {})).groupby("event").sum(numeric_only=True)
    g = g[g["w"] >= 20].sort_values("w", ascending=False)
    pct = lambda a_, b_: a_ / b_ if b_ > 0 else float("nan")
    print("Residents (Census 2021, placed by address) inside each recorded past flood, and the share of them inside our flood areas")
    print(f"  {'event':40} {'residents':>10} {'in overlays':>12}" + (f" {'in 1% AEP':>10} {'in either':>10}" if has_aep else ""))
    res = {}
    rows = [(e, r["w"], r["wov"], r.get("waep", 0), r.get("weit", 0)) for e, r in g.iterrows()]
    rows.append(("any recorded flood (each person once)", tot["w"], tot["ov"], tot.get("aep", 0), tot.get("either", 0)))
    for e, a_, o_, p_, x_ in rows:
        print(f"  {str(e)[:40]:40} {a_:>10,.0f} {pct(o_, a_):>12.0%}" + (f" {pct(p_, a_):>10.0%} {pct(x_, a_):>10.0%}" if has_aep else ""))
        res[str(e)] = {"residents": round(float(a_)), "share_in_overlays": round(float(pct(o_, a_)), 3)}
        if has_aep:
            res[str(e)].update({"share_in_aep": round(float(pct(p_, a_)), 3), "share_in_either": round(float(pct(x_, a_)), 3)})
    miss = pts.loc[anyev & ~pts["overlays"].values]
    if len(miss):
        zones_ov = zones_ov if zones_ov is not None else polys([])
        lga_geom = lga_geom or {}
        mc = (w[miss.index]).groupby(mb.loc[miss["m"], "lga"].values).sum().sort_values(ascending=False).head(10)
        print("  Residents inside a recorded flood but outside the overlays, by council: " + ", ".join(f"{k} {v:,.0f}" for k, v in mc.items()))
        for c in mc.index[:3]:
            lg = lga_geom.get(c)
            if lg is not None:
                print(f"    {c}: overlays {zones_ov.intersection(lg).area / 1e6:,.1f} km2, recorded past floods {polys(h.geometry).intersection(lg).area / 1e6:,.1f} km2, "
                      f"of which inside overlays {polys(h.geometry).intersection(lg).intersection(zones_ov).area / 1e6:,.1f} km2")
    info = [c for c in ("GAUGEID", "PLAN_NO", "SOURCE", "RELIABILITY", "METHOD", "SCALE", "MODIFIED") if c in h.columns]
    if info:
        print("  Extents with the most residents: " + "; ".join(
            f"{e}: " + ", ".join(f"{c} {h.loc[h['event'] == e, c].iloc[0]}" for c in info) for e in g.index[:5]))
    print("  Old floods predate drainage works, levees and retarding basins; a miss may be a place since protected, not an error.")
    return res


if __name__ == "__main__":
    main()
