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
redevelopment projects by status and greenfield lots by development status. Committing that file
is the licence holder's decision (see data/static/udp2025/README.md). The forecast uses it when present.

Pieces: data/static/sa2_council_pieces_7855.geojson (ABS SA2s cut by the 31 councils, EPSG:7855,
from boundary.yml).
"""
import glob, os, sys, tempfile, zipfile
import geopandas as gpd

PRIV = os.path.join("data", "private", "udp")
PIECES = os.path.join("data", "static", "sa2_council_pieces_7855.geojson")
OUT = os.path.join("data", "static", "udp2025", "udp2025_pieces.csv")


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
    m = layer("MRS2025").to_crs(7855)
    m = m.set_geometry(m.geometry.representative_point())
    j = gpd.sjoin(m[["STATUS", "TOTAL_DWEL", "geometry"]], pc, predicate="within", how="inner")
    mrs = j.pivot_table(index="piece", columns="STATUS", values="TOTAL_DWEL", aggfunc="sum", fill_value=0)
    mrs.columns = ["mrs_" + c.lower().replace(" ", "_") for c in mrs.columns]
    print(f"MRS2025: {len(m):,} projects, {len(j):,} inside the study councils, {int(j['TOTAL_DWEL'].sum()):,} dwellings")

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


if __name__ == "__main__":
    main()
