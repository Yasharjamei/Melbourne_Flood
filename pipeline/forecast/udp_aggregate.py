"""Aggregate the Urban Development Program 2025 to SA2 x council pieces. Run on the licence holder's
own computer: the raw UDP files are never in this repository.

UDP 2025 (Department of Transport and Planning; supplied through DataShare by DEECA) comes under a
DEECA Data Access Licence Agreement, not CC BY. Put the two DataShare zips, as delivered, in
data/private/udp/ (git-ignored):
    Order_KR7TGF.zip   Major Residential Redevelopment Sites 2025 (MRS2025)
    Order_EQKZCF.zip   Greenfield Residential Land 2025 (GF2025)
Then, from the repository root:
    python pipeline/forecast/udp_aggregate.py
It writes data/static/udp2025/udp2025_pieces.csv: for each SA2 x council piece, dwellings in major
redevelopment projects by status (all sizes, and again for projects of 100-499 and 500+ dwellings) and
greenfield lots by development status. Committing that file is the licence holder's decision (see
data/static/udp2025/README.md). The forecast uses it when present.

It also writes data/static/udp2025/udp_transition_2017_2025.csv: the 2017 pipeline (MRS2017, CC BY, in
data/static/udp_history/) followed into 2025, by 2017 status and project size: the share of dwellings
whose project is still unfinished in 2025 (under construction, firm, likely or possible), completed, or
no longer listed (completed before 2023, when UDP 2025's completions start, or abandoned). Totals only.

Pieces: data/static/sa2_council_pieces_7855.geojson (ABS SA2s cut by the 31 councils, EPSG:7855,
from boundary.yml).
"""
import glob, os, sys, tempfile, zipfile
import geopandas as gpd, pandas as pd

PRIV = os.path.join("data", "private", "udp")
PIECES = os.path.join("data", "static", "sa2_council_pieces_7855.geojson")
OUT = os.path.join("data", "static", "udp2025", "udp2025_pieces.csv")
TRANS = os.path.join("data", "static", "udp2025", "udp_transition_2017_2025.csv")
HIST = os.path.join("data", "static", "udp_history")
SIZES = [("10-99", 0, 100), ("100-499", 100, 500), ("500+", 500, 10**9)]      # dwellings per project


def layer(name):
    """A UDP layer from an extracted shapefile or a DataShare zip under data/private/udp/."""
    hits = glob.glob(os.path.join(PRIV, "**", f"{name}.shp"), recursive=True)
    if hits:
        return gpd.read_file(hits[0])
    for z in glob.glob(os.path.join(PRIV, "*.zip")):
        with zipfile.ZipFile(z) as zf:
            parts = [n for n in zf.namelist() if os.path.basename(n).split(".")[0] == name]
            if any(n.endswith(".shp") for n in parts):
                tmp = tempfile.mkdtemp()
                zf.extractall(tmp, parts)
                return gpd.read_file(glob.glob(os.path.join(tmp, "**", f"{name}.shp"), recursive=True)[0])
    raise SystemExit(f"{name}.shp not found in {PRIV} (put the DataShare zip there, as delivered)")


def main():
    pc = gpd.read_file(sys.argv[1] if len(sys.argv) > 1 else PIECES).to_crs(7855)
    pc = pc[["sa2_code_2021", "lga_code", "geometry"]].reset_index(drop=True)
    pc["piece"] = pc.index

    # Major redevelopment sites: small polygons, each placed at its representative point
    m25 = layer("MRS2025").to_crs(7855)
    print(f"MRS2025 fields: {[c for c in m25.columns if c != 'geometry']}")
    m = m25.set_geometry(m25.geometry.representative_point())
    j = gpd.sjoin(m[["STATUS", "TOTAL_DWEL", "geometry"]], pc, predicate="within", how="inner")
    mrs = j.pivot_table(index="piece", columns="STATUS", values="TOTAL_DWEL", aggfunc="sum", fill_value=0)
    mrs.columns = ["mrs_" + c.lower().replace(" ", "_") for c in mrs.columns]
    # the same again for big projects only (large apartment schemes take longer to finish: Lichfields 2024)
    for tag, lo, hi in SIZES[1:]:
        b = j[(j["TOTAL_DWEL"].astype(float) >= lo) & (j["TOTAL_DWEL"].astype(float) < hi)]
        t = b.pivot_table(index="piece", columns="STATUS", values="TOTAL_DWEL", aggfunc="sum", fill_value=0)
        t.columns = ["mrs_" + c.lower().replace(" ", "_") + "_" + tag.rstrip("+").split("-")[0] for c in t.columns]
        mrs = mrs.join(t, how="left")
    print(f"MRS2025: {len(m):,} projects, {len(j):,} inside the study councils, {int(j['TOTAL_DWEL'].sum()):,} dwellings")
    sz = pd.cut(j["TOTAL_DWEL"].astype(float), [lo for _, lo, _ in SIZES] + [10**9], labels=[t for t, _, _ in SIZES], right=False)
    print("  dwellings by project size and status:")
    print(j.assign(size=sz).pivot_table(index="size", columns="STATUS", values="TOTAL_DWEL", aggfunc="sum", fill_value=0, observed=False).to_string())

    # Greenfield: lots split by area where a parcel or englobo polygon crosses a piece boundary
    g = layer("GF2025").to_crs(7855)[["DEVELOPMEN", "TOTAL_LOTS", "geometry"]]
    g["a0"] = g.area
    x = gpd.overlay(g, pc, how="intersection", keep_geom_type=True)
    x["lots"] = x["TOTAL_LOTS"].astype(float) * x.area / x["a0"].where(x["a0"] > 0, 1)
    gf = x.pivot_table(index="piece", columns="DEVELOPMEN", values="lots", aggfunc="sum", fill_value=0)
    gf.columns = ["gf_" + c.lower() for c in gf.columns]
    print(f"GF2025: {int(g['TOTAL_LOTS'].sum()):,} lots, {x['lots'].sum():,.0f} inside the study councils")

    out = pc.drop(columns="geometry").set_index("piece").join(mrs).join(gf).fillna(0)
    num = list(out.columns.difference(["sa2_code_2021", "lga_code"]))
    out[num] = out[num].round().astype(int)
    out = out[out[num].sum(axis=1) > 0].sort_values(["lga_code", "sa2_code_2021"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"{OUT}: {len(out)} pieces with UDP supply")
    print("totals: " + ", ".join(f"{c} {v:,}" for c, v in out[num].sum().items()))
    transition(m25, pc)


def transition(m25, pc):
    """MRS2017 projects followed into MRS2025: what share of each 2017 status and size is still unfinished."""
    z = os.path.join(HIST, "MRS2017.zip")
    if not os.path.exists(z):
        print(f"{z} missing: no 2017 -> 2025 transition (git pull)"); return
    inner = next(n for n in zipfile.ZipFile(z).namelist() if n.endswith("/MRS2017.shp"))
    m17 = gpd.read_file(f"zip://{z}!{inner}").to_crs(7855)
    m17 = m17[m17["TOTAL_DWEL"].astype(float) > 0].reset_index(drop=True)
    m17 = m17.set_geometry(m17.geometry.representative_point())
    m17 = m17[m17.index.isin(gpd.sjoin(m17[["geometry"]], pc[["geometry"]], predicate="within").index)].reset_index(drop=True)
    # a 2017 project is followed to the 2025 project whose site contains its point (the largest if several)
    hit = gpd.sjoin(m17[["geometry"]], m25[["STATUS", "TOTAL_DWEL", "geometry"]], predicate="within", how="left")
    hit = hit.sort_values("TOTAL_DWEL", ascending=False, na_position="last")
    st25 = hit[~hit.index.duplicated()]["STATUS"].reindex(m17.index).fillna("not listed")
    st25 = st25.replace({"Under Construction": "unfinished", "Firm": "unfinished", "Likely": "unfinished", "Possible": "unfinished"})
    size = pd.cut(m17["TOTAL_DWEL"].astype(float), [lo for _, lo, _ in SIZES] + [10**9], labels=[t for t, _, _ in SIZES], right=False)
    d = pd.DataFrame({"status_2017": m17["STATUS"], "size": size.astype(str), "in_2025": st25, "dwellings": m17["TOTAL_DWEL"].astype(float)})
    t = d.pivot_table(index=["status_2017", "size"], columns="in_2025", values="dwellings", aggfunc="sum", fill_value=0)
    n = d.groupby(["status_2017", "size"]).size().rename("projects")
    t = t.div(t.sum(axis=1), axis=0).round(3).join(t.sum(axis=1).round().astype(int).rename("dwellings_2017")).join(n)
    t = t[t["projects"] >= 3]                                  # no row describes fewer than 3 projects
    t.reset_index().to_csv(TRANS, index=False)
    print(f"\n{TRANS}: 2017 pipeline in 2025, share of dwellings (rows with 3+ projects)")
    print(t.to_string())


if __name__ == "__main__":
    main()
