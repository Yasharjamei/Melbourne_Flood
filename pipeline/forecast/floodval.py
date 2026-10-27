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
    os.makedirs("data/processed", exist_ok=True)
    json.dump(out, open("data/processed/forecast_floodval.json", "w"), indent=1)


if __name__ == "__main__":
    main()
