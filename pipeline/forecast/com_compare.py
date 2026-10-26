"""Compare the forecast with the City of Melbourne's own small-area population forecasts.

The City of Melbourne publishes population forecasts by its 13 CLUE small areas (Census of Land Use and
Employment), single years 2023-2043, prepared by SGS Economics and Planning, as open data
(data.melbourne.vic.gov.au; credit: City of Melbourne). Our SA1 figures (scenarios_sa1.js) are summed
to CLUE areas (each SA1 by its representative point) and set beside theirs for the forecast years.
This is a comparison, not a test: either forecast can be wrong; large gaps show where to look.

    python pipeline/forecast/com_compare.py   (after forecast.py)  ->  data/processed/forecast_com.json
"""
import io, json, os, re, sys, urllib.request
import numpy as np, pandas as pd, geopandas as gpd

ODS = "https://data.melbourne.vic.gov.au/api/v2/catalog/datasets/"
FCST = ODS + "city-of-melbourne-population-forecasts-by-small-area-2020-2040/exports/csv?delimiter=%2C"
CLUE = ODS + "small-areas-for-census-of-land-use-and-employment-clue/exports/geojson"
UA = {"User-Agent": "Mozilla/5.0 (melbourne-flood pipeline)"}
CRS = 7855


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read()


def main():
    f = pd.read_csv(io.BytesIO(get(FCST)))
    print(f"City of Melbourne forecast: {len(f):,} rows; areas {sorted(f['geography'].unique())}")
    print(f"  genders {f['gender'].unique().tolist()}; ages {sorted(f['age'].astype(str).unique().tolist())[:30]}")
    tot_g = [g for g in f["gender"].unique() if re.search(r"total|all|person", str(g), re.I)]
    tot_a = [a for a in f["age"].astype(str).unique() if re.search(r"total|all", a, re.I)]
    sel = f[f["gender"].isin(tot_g)] if tot_g else f
    sel = sel[sel["age"].astype(str).isin(tot_a)] if tot_a else sel
    theirs = sel.groupby(["geography", "year"])["value"].sum().unstack()
    print(f"  totals from {'total rows' if (tot_g or tot_a) else 'summing gender x age'}; municipality "
          + ", ".join(f"{y} {theirs[y].sum():,.0f}" for y in theirs.columns if y in (2025, 2026, 2031, 2036, 2041)))

    clue = gpd.read_file(io.BytesIO(get(CLUE))).to_crs(CRS)
    name = next((c for c in clue.columns if re.search(r"featurenam|name|small_area|area", c, re.I) and clue[c].dtype == object), None)
    print(f"  CLUE areas: {len(clue)}; name column {name}; names {sorted(clue[name].astype(str))}")

    txt = open("data/processed/scenarios_sa1.js").read()
    A = json.loads(txt[txt.index("=") + 1:].rstrip().rstrip(";"))
    years = A["years"]
    sa1 = gpd.read_file("data/raw/metro/sa1.geojson").to_crs(CRS)
    code = next(c for c in sa1.columns if re.fullmatch(r"sa1_code_2021|sa1_code.*", c, re.I))
    sa1["c"] = sa1[code].astype(str).str.replace(r"\.0$", "", regex=True)
    sa1 = sa1[sa1["c"].isin(A["codes"])]
    pt = sa1.set_geometry(sa1.geometry.representative_point())[["c", "geometry"]]
    j = gpd.sjoin(pt, clue[[name, "geometry"]], predicate="within", how="inner")
    area_of = j.drop_duplicates("c").set_index("c")[name]
    idx = {c: i for i, c in enumerate(A["codes"])}
    pop = np.array(A["pop"], dtype=float)
    ex = np.array(A["v"]["none"], dtype=float)
    ours = pd.DataFrame({y: pd.Series({c: pop[idx[c], k] for c in area_of.index}).groupby(area_of).sum() for k, y in enumerate(years)})
    flood = pd.Series({c: ex[idx[c], -1] for c in area_of.index}).groupby(area_of).sum()

    norm = lambda s: re.sub(r"[^a-z]", "", str(s).lower())
    tmap = {norm(g): g for g in theirs.index}
    rows, out = [], {"source": "City of Melbourne Population Forecasts by Small Area 2023-2043 (SGS), data.melbourne.vic.gov.au, credit City of Melbourne",
                     "areas": {}}
    print(f"\nCity of Melbourne small areas: our forecast vs the council's (residents)")
    print(f"  {'area':34} " + " ".join(f"{'ours ' + str(y):>11} {'theirs':>9} {'diff':>6}" for y in (years[0], years[-1])) + f" {'in flood areas ' + str(years[-1]):>20}")
    for a in ours.index:
        t = tmap.get(norm(a))
        r = {"ours": {y: round(float(ours.loc[a, y])) for y in years}, "flood_" + str(years[-1]): round(float(flood.get(a, 0)))}
        if t is not None:
            r["theirs"] = {y: round(float(theirs.loc[t, y])) for y in years if y in theirs.columns}
        out["areas"][a] = r
        cells = []
        for y in (years[0], years[-1]):
            o, th = r["ours"][y], r.get("theirs", {}).get(y)
            cells.append(f"{o:>11,} {th if th is None else f'{th:,}':>9} {'' if not th else f'{o / th - 1:+.0%}':>6}")
        print(f"  {str(a)[:34]:34} " + " ".join(cells) + f" {r['flood_' + str(years[-1])]:>20,}")
    tot = {y: (float(ours[y].sum()), float(theirs[y].sum()) if y in theirs.columns else None) for y in years}
    print("  " + "all".ljust(34) + " " + " ".join(f"{tot[y][0]:>11,.0f} {tot[y][1] or 0:>9,.0f} {tot[y][0] / tot[y][1] - 1 if tot[y][1] else 0:>+6.0%}" for y in (years[0], years[-1])))
    print("  Our SA1s are assigned to CLUE areas by representative point; CLUE areas follow the municipal boundary, ours the 2021 SA1s.")
    out["total"] = {str(y): v for y, v in tot.items()}
    json.dump(out, open("data/processed/forecast_com.json", "w"), indent=1)


if __name__ == "__main__":
    main()
