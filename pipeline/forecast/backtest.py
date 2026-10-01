"""Back-test: can growth be placed at mesh-block and SA1 level? Predict 2021 from 2016, compare.

The forecast will take SA2 totals from official projections and place the growth inside each
SA2. This script measures how well that placement works on a period we know the answer for:
starting from the 2016 Census, predict every 2021 mesh block's residents and compare with the
2021 Census. SA2 totals are given the true 2021 values ("oracle"), so the error measured here is
the placement error alone, not the error of the SA2 projections themselves.

  A  uniform:  each mesh block grows at its SA2's rate (no local information)
  B  address:  existing homes grow at a common SA2 rate; addresses created between the two
               Censuses (Vicmap pfi_created) add residents at the SA2's persons per dwelling
  C  address only where it matters: as B, but a mesh block's existing stock keeps its 2016 count
               (rate 1) and the SA2 remainder goes to new addresses

Run after pipeline/forecast/fetch.py and the main 01_fetch.py (mesh blocks, 2021 counts):
    python pipeline/forecast/backtest.py   ->  data/processed/forecast_backtest.json, prints a report
"""
import json, os, re, sys
import numpy as np, pandas as pd, geopandas as gpd

RAW, FC = "data/raw/metro", "data/raw/forecast"
CENSUS_2016, CENSUS_2021 = np.datetime64("2016-08-09"), np.datetime64("2021-08-10")


def table(path, key, cols):
    """Read an ABS csv or xlsx whose header row contains `key` (ABS files carry title rows)."""
    if path.endswith(".csv"):
        import csv                                            # ragged: title rows are narrower than the table
        rows = list(csv.reader(open(path, encoding="latin-1", newline="")))
        width = max(len(r) for r in rows)
        frames = [pd.DataFrame([r + [""] * (width - len(r)) for r in rows], dtype=str)]
    else:
        frames = list(pd.read_excel(path, sheet_name=None, header=None, dtype=str).values())
    parts, seen = [], []
    for df in frames:
        h = df.index[df.apply(lambda r: r.astype(str).str.strip().str.upper().eq(key.upper()).any(), axis=1)]
        if not len(h):
            continue
        hdr = [str(x).strip() for x in df.loc[h[0]]]
        up = [x.upper() for x in hdr]
        pick = {}
        for want in cols:
            m = [i for i, x in enumerate(up) if re.fullmatch(want, x, re.I)]
            if m:
                pick[want] = m[0]
        if len(pick) < len(cols):                             # e.g. a data-dictionary sheet naming the column
            seen.append(hdr[:8]); continue
        d = df.loc[h[0] + 1:, list(pick.values())]; d.columns = list(pick.keys()); parts.append(d)
    if not parts:
        raise KeyError(f"{path}: no sheet has all of {cols}; header rows seen: {seen}")
    return pd.concat(parts)


def codes(s):
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


def metrics(pred, act, label):
    """Weighted absolute % error, share within tolerance, median absolute error."""
    keep = (act > 0) | (pred > 0.5)
    p, a = pred[keep], act[keep]
    err = np.abs(p - a)
    tol = err <= np.maximum(10, 0.2 * a)                     # within 10 people or 20%
    return {"level": label, "units": int(keep.sum()), "wape": round(float(err.sum() / max(a.sum(), 1)), 4),
            "within_10_or_20pct": round(float(tol.mean()), 4), "median_abs_err": round(float(np.median(err)), 1)}


def main():
    # 2021 truth: mesh blocks in the study area with their 2021 Census residents and dwellings
    mb = gpd.read_file(f"{RAW}/mb.geojson")
    code = next(c for c in mb.columns if re.fullmatch(r"mb_code_2021|mb_code.*", c, re.I))
    sa1c = next((c for c in mb.columns if re.fullmatch(r"sa1_code_2021|sa1_code.*", c, re.I)), None)
    mb["mb21"] = codes(mb[code])
    c21 = table("data/raw/shared/mb_counts_2021.xlsx", "MB_CODE_2021", ["MB_CODE_2021", "DWELLING", "PERSON"])
    c21["mb21"] = codes(c21["MB_CODE_2021"])
    c21 = c21[c21["mb21"].str.fullmatch(r"\d{11}")].drop_duplicates("mb21").set_index("mb21")
    mb["p21"] = pd.to_numeric(mb["mb21"].map(c21["PERSON"]), errors="coerce").fillna(0)
    mb["d21"] = pd.to_numeric(mb["mb21"].map(c21["DWELLING"]), errors="coerce").fillna(0)
    if sa1c:
        mb["sa1"] = codes(mb[sa1c])
    else:
        raise SystemExit("mesh blocks carry no SA1 code; add a spatial join here")
    mb["sa2"] = mb["sa1"].str[:9]                             # ASGS 2021: SA1 code = SA2 code + 2 digits
    mb = mb[mb["sa1"].str.fullmatch(r"\d{11}")].reset_index(drop=True)
    print(f"2021: {len(mb):,} mesh blocks, {int(mb['p21'].sum()):,} residents, {mb['sa2'].nunique()} SA2s")

    # 2016 baseline, carried onto 2021 mesh blocks with the ABS correspondence
    c16 = table(f"{FC}/mb_counts_2016.csv", "MB_CODE_2016", ["MB_CODE_2016", "PERSON"])
    c16["mb16"] = codes(c16["MB_CODE_2016"]); c16["p16"] = pd.to_numeric(c16["PERSON"], errors="coerce").fillna(0)
    c16 = c16[c16["mb16"].str.fullmatch(r"\d{11}")].drop_duplicates("mb16")
    cg = pd.read_csv(f"{FC}/cg_mb2016_mb2021.csv", dtype=str)
    cg.columns = [c.upper() for c in cg.columns]
    fr = next(c for c in cg.columns if re.fullmatch(r"MB_CODE_2016", c)); to = next(c for c in cg.columns if re.fullmatch(r"MB_CODE_2021", c))
    rc = next(c for c in cg.columns if re.search(r"RATIO", c))
    cg = cg.assign(mb16=codes(cg[fr]), mb21=codes(cg[to]), r=pd.to_numeric(cg[rc], errors="coerce").fillna(0))
    x = cg.merge(c16[["mb16", "p16"]], on="mb16", how="inner")
    p16 = (x["p16"] * x["r"]).groupby(x["mb21"]).sum()
    mb["p16"] = mb["mb21"].map(p16).fillna(0)
    print(f"2016 on 2021 mesh blocks: {int(mb['p16'].sum()):,} residents "
          f"({cg['mb21'].isin(mb['mb21']).sum():,} correspondence rows touch the study area; ratio column `{rc}`)")

    # Addresses created between the two Census nights, joined to 2021 mesh blocks
    a = np.load(f"{FC}/addresses_new.npy")
    when = a[:, 2].astype("int64").astype("datetime64[D]")
    sel = (when >= CENSUS_2016) & (when < CENSUS_2021)
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(a[sel, 0], a[sel, 1]), crs=4326).to_crs(mb.crs)
    j = gpd.sjoin(pts, mb[["geometry"]], predicate="within", how="inner")
    mb["new"] = j.groupby("index_right").size().reindex(range(len(mb))).fillna(0).values
    print(f"addresses created {CENSUS_2016} to {CENSUS_2021}: {int(sel.sum()):,}; {int(mb['new'].sum()):,} inside study mesh blocks")

    # SA2 control totals (oracle: the true 2021 values) and persons per dwelling
    g = mb.groupby("sa2")
    P21, P16, N = g["p21"].transform("sum"), g["p16"].transform("sum"), g["new"].transform("sum")
    ppd = (g["p21"].transform("sum") / g["d21"].transform("sum").clip(lower=1)).clip(1.2, 4.0)

    def to_total(pred):                                       # rescale so each SA2 hits its total
        s = pred.groupby(mb["sa2"]).transform("sum")
        return np.where(s > 0, pred * P21 / s, 0.0)

    A = to_total(mb["p16"] * np.where(P16 > 0, P21 / P16.clip(lower=1), 0))
    r = ((P21 - ppd * N) / P16.clip(lower=1)).clip(0.7, 1.3)
    B = to_total(mb["p16"] * r + mb["new"] * ppd)
    C = to_total(mb["p16"] + mb["new"] * ppd)

    out = {"period": "2016 -> 2021", "sa2_totals": "true 2021 values (placement error only)",
           "mesh_blocks": len(mb), "residents_2021": int(mb["p21"].sum()), "new_addresses": int(mb["new"].sum()), "models": {}}
    act = mb["p21"].values
    grow = (mb["new"] >= 10).values                           # where most of the growth landed
    sa1_act = mb.groupby("sa1")["p21"].sum()
    for name, pred in (("A_uniform", A), ("B_address", B), ("C_address_stock_fixed", C)):
        pred = np.asarray(pred, dtype=float)
        sa1_pred = pd.Series(pred).groupby(mb["sa1"].values).sum().reindex(sa1_act.index).values
        out["models"][name] = [metrics(pred, act, "mesh block"), metrics(pred[grow], act[grow], "mesh block, >=10 new addresses"),
                               metrics(sa1_pred, sa1_act.values, "SA1")]
    os.makedirs("data/processed", exist_ok=True)
    json.dump(out, open("data/processed/forecast_backtest.json", "w"), indent=1)

    print("\nBack-test 2016 -> 2021 (SA2 totals known; placement error only)")
    print(f"{'model':24} {'level':32} {'units':>7} {'WAPE':>7} {'within':>7} {'median':>7}")
    for name, rows in out["models"].items():
        for m in rows:
            print(f"{name:24} {m['level']:32} {m['units']:>7,} {m['wape']:>7.1%} {m['within_10_or_20pct']:>7.1%} {m['median_abs_err']:>7.1f}")
    print("WAPE = total absolute error / total residents; within = share of units within 10 people or 20%.")


if __name__ == "__main__":
    main()
