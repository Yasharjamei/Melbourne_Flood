"""Export the study area's boundary as zipped shapefiles, for ordering clipped data from DataShare
(or any GIS use). The study area is the 31 councils in pipeline/config.py (ABS ASGS 2021 LGAs),
the same boundary every figure on the site uses.

Writes to boundary/:
  greater_melbourne_MGA2020_z55.zip           one dissolved polygon, EPSG:7855 (what DataShare delivers in)
  greater_melbourne_MGA2020_z55_simple.zip    the same, simplified to 20 m, small enough for upload forms
  greater_melbourne_councils_MGA2020_z55.zip  the 31 councils, with names
  greater_melbourne_WGS84.zip                 the dissolved polygon in EPSG:4326
"""
import importlib.util, os, sys, tempfile, zipfile
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "pipeline"))
spec = importlib.util.spec_from_file_location("f01", os.path.join(HERE, "..", "..", "pipeline", "01_fetch.py"))
f01 = importlib.util.module_from_spec(spec); spec.loader.exec_module(f01)
from config import GREATER_MELBOURNE, norm_lga

OUT = "boundary"
os.makedirs(OUT, exist_ok=True)
src = "data/raw/metro/lga.geojson"                     # the pipeline's cached copy, if restored
if not os.path.exists(src):
    src = os.path.join(tempfile.mkdtemp(), "lga.geojson")
    f01.arcgis("LGA", "state_code_2021='2'", None, 0.00001, src, page_max=10)

lga = gpd.read_file(src)
lga = lga[lga["lga_name_2021"].map(norm_lga).isin({norm_lga(n) for n in GREATER_MELBOURNE})].copy()
if len(lga) != len(GREATER_MELBOURNE):
    sys.exit(f"expected {len(GREATER_MELBOURNE)} councils, found {len(lga)}")
lga["name"] = lga["lga_name_2021"].str.replace(" (Vic.)", "", regex=False)
lga = lga[["name", "lga_code_2021", "geometry"]].rename(columns={"lga_code_2021": "lga_code"}).to_crs(7855)

def no_holes(g):
    parts = g.geoms if isinstance(g, MultiPolygon) else [g]
    parts = [Polygon(p.exterior) for p in parts if p.area > 1e4]   # drop slivers under 1 ha
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)

whole = no_holes(lga.union_all().buffer(0))
attrs = {"name": ["Greater Melbourne (31 councils)"]}

def save(gdf, name):
    d = tempfile.mkdtemp(); gdf.to_file(os.path.join(d, name + ".shp"))
    with zipfile.ZipFile(os.path.join(OUT, name + ".zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(d)):
            z.write(os.path.join(d, f), f)
    g = gdf.geometry.iloc[0]
    n = sum(len(p.exterior.coords) for p in (g.geoms if hasattr(g, "geoms") else [g]))
    print(f"{name}.zip: {len(gdf)} feature(s), {os.path.getsize(os.path.join(OUT, name + '.zip')) / 1e6:.2f} MB"
          + ("" if len(gdf) > 1 else f", {n:,} vertices"))

save(gpd.GeoDataFrame(attrs, geometry=[whole], crs=7855), "greater_melbourne_MGA2020_z55")
save(gpd.GeoDataFrame(attrs, geometry=[no_holes(whole.simplify(20))], crs=7855), "greater_melbourne_MGA2020_z55_simple")
save(lga.reset_index(drop=True), "greater_melbourne_councils_MGA2020_z55")
save(gpd.GeoDataFrame(attrs, geometry=[whole], crs=7855).to_crs(4326), "greater_melbourne_WGS84")
# SA2 x council pieces (ABS SA2s cut by the councils), for placing data that arrives without SA2 codes.
# Also printed to the log as gzip+base64 GeoJSON between markers, so a session that can read logs but
# not artifacts can still get them.
import base64, gzip, json
sa2_src = os.path.join(tempfile.mkdtemp(), "sa2.geojson")
lon0, lat0, lon1, lat1 = lga.to_crs(4326).total_bounds
f01.arcgis("SA2", "state_code_2021='2'", (lon0, lat0, lon1, lat1), 0.00002, sa2_src)
sa2 = gpd.read_file(sa2_src).to_crs(7855)
sa2 = sa2[["sa2_code_2021", "sa2_name_2021", "geometry"]]
pc = gpd.overlay(sa2, lga[["name", "lga_code", "geometry"]], how="intersection", keep_geom_type=True)
pc = pc[pc.area > 1e4].copy()
pc["geometry"] = pc.geometry.simplify(10)
save(pc.reset_index(drop=True), "greater_melbourne_sa2_council_pieces_MGA2020_z55")
gj = json.loads(pc.to_json(drop_id=True))
for f in gj["features"]:
    def rnd(c):
        return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0]), round(c[1])]
    f["geometry"]["coordinates"] = rnd(f["geometry"]["coordinates"])
blob = base64.b64encode(gzip.compress(json.dumps(gj, separators=(",", ":")).encode())).decode()
print(f"PIECES {len(pc)} pieces, {pc['sa2_code_2021'].nunique()} SA2s, {len(blob):,} chars (EPSG:7855, gzip+base64 GeoJSON)")
print("BEGIN_PIECES")
for i in range(0, len(blob), 8000):
    print(blob[i:i + 8000])
print("END_PIECES")
print(f"area {whole.area / 1e6:,.0f} km², bounds (lon/lat) {gpd.GeoSeries([whole], crs=7855).to_crs(4326).total_bounds.round(3)}")
