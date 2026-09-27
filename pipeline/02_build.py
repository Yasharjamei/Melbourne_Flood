"""Build one study area's dataset from data/raw/<study>/ -> data/processed/<study>.json

    python pipeline/02_build.py              # Greater Melbourne (the only study)

Per SA1: Census 2021 counts, flood-overlay shares, suburb, and the Lama & Sun (2026)
Exposure / Sensitivity / Adaptive capacity / FRI / Damage / IFRI indices.
Per mesh block: a population weight used to apportion SA1 counts to circles.
"""
import argparse, glob, json, os, re, sys
import numpy as np, pandas as pd, geopandas as gpd, shapely
from shapely.ops import unary_union
sys.path.insert(0, os.path.dirname(__file__))
from config import STUDIES, LAMA_SUN, DAMAGE_INDICATORS, norm_lga

ap = argparse.ArgumentParser(); ap.add_argument("--study", default="metro", choices=STUDIES)
STUDY = ap.parse_args().study
ST = STUDIES[STUDY]; RAW = f"data/raw/{STUDY}"; CRS = 7855
os.makedirs("data/processed", exist_ok=True)
NOTES = []  # substitutions and fallbacks, shown in the page footer


def col(df, *pats, required=True):
    for p in pats:
        m = [c for c in df.columns if re.fullmatch(p, c, flags=re.I)]
        if m:
            return m[0]
    if required:
        raise KeyError(f"none of {pats} in columns {list(df.columns)[:80]}")
    return None


def read(path):
    """Read a layer and repair geometry without losing area.

    Server-side generalisation can make rings cross themselves. buffer(0) "repairs" a
    self-crossing ring by keeping only one lobe, which silently dropped whole parts of
    councils (and every SA1 in them) in v0.3.0. make_valid keeps all of the area."""
    from shapely.geometry import MultiPolygon, Polygon
    g = gpd.read_file(path).to_crs(CRS)
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
    def poly(x):
        if x.is_valid:
            return x
        v = shapely.make_valid(x)
        parts = [p for p in getattr(v, "geoms", [v]) if isinstance(p, (Polygon, MultiPolygon))]
        return unary_union(parts) if parts else x.buffer(0)
    g["geometry"] = [poly(x) for x in g.geometry]
    return g[~g.geometry.is_empty]


# ---------------- geography
wanted = {norm_lga(n) for n in ST["lgas"]}
lga = read(f"{RAW}/lga.geojson")
lga = lga[lga["lga_name_2021"].map(norm_lga).isin(wanted)].reset_index(drop=True)
lga["name"] = lga["lga_name_2021"].str.replace(" (Vic.)", "", regex=False)
sa = read(f"{RAW}/sa1.geojson")
pt = sa.copy(); pt["geometry"] = sa.representative_point()
j = gpd.sjoin(pt, lga[["name", "geometry"]], predicate="within")
j = j[~j.index.duplicated()]
sa = sa.loc[j.index].copy(); sa["lga"] = j["name"].values
sa = sa.drop_duplicates("sa1_code_2021").reset_index(drop=True)
sa["area"] = sa.area
# Coverage check: every council should be (almost) fully tiled by its SA1s.
cov = []
for r in lga.itertuples():
    got = sa.loc[sa["lga"] == r.name, "area"].sum()
    cov.append((r.name, int((sa["lga"] == r.name).sum()), got / r.geometry.area))
print("SA1 coverage by council:", ", ".join(f"{n} {k} SA1s {c:.1%}" for n, k, c in cov))
warn = [f"{n} ({c:.1%})" for n, k, c in cov if not 0.97 <= c <= 1.03]
if warn:
    print("WARNING SA1 coverage outside 97-103% (boundary mismatch between SA1s and councils?):", warn)
bad = [f"{n} ({c:.1%})" for n, k, c in cov if not 0.9 <= c <= 1.1]
if bad:
    raise SystemExit(f"SA1s cover too little or too much of: {bad}. Check the council and SA1 geometry.")
codes = sa["sa1_code_2021"].astype(str).tolist(); idx = {c: i for i, c in enumerate(codes)}
print(f"{STUDY}: {len(lga)} LGAs, {len(sa)} SA1s")

# suburbs (ABS Suburbs and Localities): SA1 -> suburb by representative point
sal = read(f"{RAW}/sal.geojson")
sal["name"] = sal[col(sal, r"sal_name_2021", r".*sal.*name.*")].str.replace(r" \(Vic\.\)", "", regex=True)
pt = sa[["geometry"]].copy(); pt["geometry"] = sa.representative_point()
js = gpd.sjoin(pt, sal[["name", "geometry"]], predicate="within")
js = js[~js.index.duplicated()]
sa["sub"] = js["name"].reindex(sa.index).fillna(sa["sa2_name_2021"]).values
study_poly = unary_union(lga.geometry)
sal = sal[sal.intersects(study_poly.buffer(-50))].reset_index(drop=True)

# ---------------- Census 2021 GCP
G = lambda t: pd.read_csv(f"data/raw/gcp/2021Census_{t}_VIC_SA1.csv", dtype={"SA1_CODE_2021": str}).set_index("SA1_CODE_2021")
def GJ(*ts):
    d = G(ts[0])
    for t in ts[1:]:
        d = d.join(G(t), rsuffix="_" + t)
    return d.reindex(codes).fillna(0)
g1, g2, g13, g18, g34, g36, g43, g46 = (GJ(t) for t in ["G01", "G02", "G13E", "G18", "G34", "G36", "G43", "G46B"])
g4, g17, g20 = GJ("G04A", "G04B"), GJ("G17A", "G17B", "G17C"), GJ("G20A", "G20B")
bands = ["0_4", "5_9", "10_14", "15_19", "20_24", "25_29", "30_34", "35_39", "40_44", "45_49", "50_54",
         "55_59", "60_64", "65_69", "70_74", "75_79", "80_84"]
def band(sx):
    cs = [g4[f"Age_yr_{b}_{sx}"] for b in bands]
    cs.append(sum(g4[f"Age_yr_{b}_{sx}"] for b in ["85_89", "90_94", "95_99", "100_yr_over"]))
    return np.stack(cs, 1).astype(int)
M, F = band("M"), band("F")
# Lama & Sun's "mean income generating population" ($91,000-$103,999 a year) is exactly
# the ABS weekly personal income band $1,750-$1,999.
inc_col = col(g17, r"P_1750_1999_Tot", r"P_1750_1999.*Tot.*", r"P.*1750_1999.*")
# Non-school qualifications: postgrad, grad dip/cert, bachelor, adv dip/dip, and all certificates
# (CertTot already sums Cert III/IV, I/II and nfd, so those are not added again).
edu_cols = [c for c in g43.columns if re.fullmatch(
    r"non_sch_qual_(PostGrad_Dgre|Gr_Dip_Gr_Crt|Bchelr_Degree|Advnd_Dip_Dip|CertTot_Level)_P", c, flags=re.I)]
if not edu_cols:
    raise KeyError(f"no non-school qualification columns in G43: {list(g43.columns)}")
print("education columns:", edu_cols, "| income column:", inc_col)
dwell_cols = ["OPDs_Separate_house_Dwellings", "OPDs_SD_r_t_h_th_Tot_Dwgs", "OPDs_F_ap_I_1or2_sty_blk_Ds",
              "OPDs_F_ap_I_3_sty_blk_Dwgs", "OPDs_Flt_apt_Att_house_Ds", "OPDs_F_ap_I_4to8_sty_blk_Ds",
              "OPDs_F_ap_I_9_m_sty_blk_Ds", "OPDs_Other_dwelling_Tot_Dwgs"]

# ---------------- river basins (Melbourne Water, data/static) and waterway/drain subcatchments
basins = None
if os.path.exists("data/static/river_basins_melbourne.geojson"):
    basins = gpd.read_file("data/static/river_basins_melbourne.geojson").to_crs(CRS)
    basins["name"] = basins[col(basins, r"river_basin_catchment_name", r".*name.*")].astype(str)
    basins = basins.dissolve("name").reset_index()[["name", "geometry"]]   # e.g. the three Western Port islands stay separate names
    jb = gpd.sjoin(pt, basins, predicate="within")
    jb = jb[~jb.index.duplicated()]
    sa["basin"] = jb["name"].reindex(sa.index).fillna("").values
    basins = basins[basins["name"].isin(set(sa["basin"]))].reset_index(drop=True)
    print("river basins:", sa["basin"].value_counts().to_dict())
    NOTES.append("River basins: Melbourne Water major river basins; each SA1 is assigned by its representative point.")
else:
    sa["basin"] = ""
sa["drain"] = ""
if os.path.exists("data/raw/shared/subcatchments.geojson"):
    try:
        sc = gpd.read_file("data/raw/shared/subcatchments.geojson").to_crs(CRS)
        name_col = next((c for c in sc.columns if re.search(r"waterway|drain|receiv|name", c, re.I) and sc[c].dtype == object), None)
        js2 = gpd.sjoin(pt, sc[[name_col, "geometry"]] if name_col else sc[["geometry"]], predicate="within")
        js2 = js2[~js2.index.duplicated()]
        if name_col:
            sa["drain"] = js2[name_col].reindex(sa.index).fillna("").astype(str).str.strip().values
        print(f"subcatchments: {len(sc):,} polygons, name field {name_col!r}, {int((sa['drain'] != '').sum())} SA1s labelled")
        NOTES.append("Receiving waterway: Melbourne Water waterways and drains subcatchments, by SA1 representative point.")
    except Exception as e:
        print("WARNING could not use subcatchments:", e)

# ---------------- flood overlays
fl = read(f"{RAW}/flood.geojson")
def polys(g):
    """Keep only polygonal parts (intersections can leave stray lines/points)."""
    from shapely.geometry import MultiPolygon, Polygon
    parts = [p for p in getattr(g, "geoms", [g]) if isinstance(p, (Polygon, MultiPolygon)) and not p.is_empty]
    return unary_union(parts) if parts else MultiPolygon()
riv = polys(unary_union(fl[fl.scheme_code.isin(["LSIO", "FO"])].geometry).intersection(study_poly))
sbo = polys(unary_union(fl[fl.scheme_code == "SBO"].geometry).intersection(study_poly))

def share_in(g, zone):
    """Area share of each geometry inside zone, using overlay's spatial index."""
    parts = gpd.GeoDataFrame(geometry=list(getattr(zone, "geoms", [zone])), crs=CRS)
    parts = parts[~parts.is_empty]
    if parts.empty:
        return np.zeros(len(g))
    src = gpd.GeoDataFrame({"k": np.arange(len(g))}, geometry=g.geometry.values, crs=CRS)
    ov = gpd.overlay(src, parts, how="intersection", keep_geom_type=True)
    a = ov.assign(a=ov.area).groupby("k")["a"].sum().reindex(range(len(g))).fillna(0).values
    return np.clip(a / src.area.values, 0, 1)

# ---------------- mesh blocks: population weights, land use, flood shares
mb = read(f"{RAW}/mb.geojson")
mb["code"] = mb[col(mb, r"mb_code_2021", r"mb_code.*")].astype(str)
mb["cat"] = mb[col(mb, r"mb_category_name_2021", r"mb_cat.*name.*", r"mb_category_2021", r"mb_cat.*")].astype(str)
msa1 = col(mb, r"sa1_code_2021", r"sa1_code.*", required=False)
if msa1:
    mb["sa1"] = mb[msa1].astype(str)
else:
    p = mb[["geometry"]].copy(); p["geometry"] = mb.representative_point()
    s = gpd.sjoin(p, sa[["sa1_code_2021", "geometry"]], predicate="within")
    s = s[~s.index.duplicated()]
    mb["sa1"] = s["sa1_code_2021"].reindex(mb.index).astype(str)
mb = mb[mb["sa1"].isin(idx)].reset_index(drop=True)
mb["i"] = mb["sa1"].map(idx); mb["area"] = mb.area
pop = None
if os.path.exists("data/raw/shared/mb_counts_2021.xlsx"):
    try:
        parts = []
        for df in pd.read_excel("data/raw/shared/mb_counts_2021.xlsx", sheet_name=None, header=None, dtype=str).values():
            h = df.index[df.apply(lambda r: r.astype(str).str.strip().eq("MB_CODE_2021").any(), axis=1)]
            if not len(h):
                continue
            hdr = df.loc[h[0]].astype(str).str.strip().tolist()
            if "Person" not in hdr:
                continue
            d = df.loc[h[0] + 1:, [hdr.index("MB_CODE_2021"), hdr.index("Person")]]
            d.columns = ["code", "person"]
            parts.append(d)
        c = pd.concat(parts)
        c["code"] = c["code"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
        c = c[c["code"].str.fullmatch(r"\d{11}")]           # drop titles, notes and footers
        pop = pd.to_numeric(c["person"], errors="coerce").groupby(c["code"]).first()
        mb["pop"] = mb["code"].map(pop).fillna(0).values
        if mb["pop"].sum() <= 0:
            raise ValueError(f"no study mesh block matched the counts file ({len(pop)} codes read)")
        print(f"mesh-block counts: {len(pop)} codes read, {int((mb['pop'] > 0).sum())} study mesh blocks with residents, "
              f"{int(mb['pop'].sum())} residents (SA1 Census total {int(g1['Tot_P_P'].sum())})")
        NOTES.append("Mesh blocks weighted by 2021 Census resident counts (ABS Mesh Block Counts).")
    except Exception as e:
        print("WARNING could not read mesh-block counts:", e); pop = None
if pop is None:
    mb["pop"] = np.where(mb["cat"].str.lower().str.startswith("residential"), mb["area"], 0.0)
    NOTES.append("Mesh-block counts unavailable: residents placed on Residential mesh blocks in proportion to area.")
# ---------------- address points: where dwellings actually sit inside each mesh block
# A mesh block holds about 30-60 dwellings, but can also contain a park or creek reserve
# that is the only part in a flood overlay. Its area share then overstates how many
# residents are exposed. Vicmap Address has one point per property or unit, so the share
# of a mesh block's addresses inside an overlay is a closer estimate of its residents'.
mb["riv"] = share_in(mb, riv); mb["sbo"] = share_in(mb, sbo)
mb["any"] = np.minimum(1, mb["riv"] + mb["sbo"])
mb["naddr"] = 0
ADDR = f"{RAW}/addr.npy"
if os.path.exists(ADDR):
    try:
        a = np.load(ADDR)
        pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(a[:, 0], a[:, 1]), crs=4326).to_crs(CRS)
        pts = gpd.sjoin(pts, mb[["geometry"]], predicate="within", how="inner")
        pts = pts[~pts.index.duplicated()].rename(columns={"index_right": "m"})[["m", "geometry"]]
        def inside(zone):
            parts = gpd.GeoDataFrame(geometry=list(getattr(zone, "geoms", [zone])), crs=CRS)
            parts = parts[~parts.is_empty]
            if parts.empty:
                return np.zeros(len(pts), bool)
            hit = gpd.sjoin(pts, parts, predicate="within", how="inner").index.unique()
            return pts.index.isin(hit)
        pts["riv"] = inside(riv); pts["sbo"] = inside(sbo); pts["any"] = pts["riv"] | pts["sbo"]
        g = pts.groupby("m")
        n = g.size().reindex(mb.index).fillna(0)
        has = n > 0
        # Guard: a truncated download leaves most mesh blocks without addresses and would
        # silently mix two methods. Require addresses in 80% of populated mesh blocks.
        cover = float(has[mb["pop"] > 0].mean()) if (mb["pop"] > 0).any() else 0.0
        if cover < 0.8:
            raise RuntimeError(f"only {cover:.0%} of populated mesh blocks have an address point")
        for k in ("riv", "sbo", "any"):
            mb.loc[has, k] = (g[k].sum().reindex(mb.index)[has] / n[has]).values
        mb["naddr"] = n.astype(int).values
        print(f"address points: {len(a):,} read, {len(pts):,} in study mesh blocks, "
              f"{int(pts['any'].sum()):,} inside an overlay; {int(has.sum())} of {len(mb)} mesh blocks have addresses "
              f"({cover:.1%} of populated ones)")
        NOTES.append("Flood exposure: share of each mesh block's Vicmap Address points inside an overlay, "
                     "weighted by mesh-block residents (area share where a mesh block has no address).")
    except Exception as e:
        print("WARNING could not use address points:", e)
if not mb["naddr"].any():
    NOTES.append("Flood exposure: area share of each mesh block inside an overlay, weighted by mesh-block residents "
                 "(address points unavailable for this build).")
tot = mb.groupby("i")["pop"].transform("sum")
atot = mb.groupby("i")["area"].transform("sum")
mb["w"] = np.where(tot > 0, mb["pop"] / tot.where(tot > 0, 1), mb["area"] / atot)
area_i = mb.groupby("i")["area"].sum()
nonurban = mb["cat"].str.lower().str.contains("parkland|water|primary production")
urban = ((mb["area"] * ~nonurban).groupby(mb["i"]).sum() / area_i).reindex(range(len(sa))).fillna(0)
# Resident-weighted shares per SA1: w is each mesh block's share of the SA1's residents.
rw = lambda k: (mb["w"] * mb[k]).groupby(mb["i"]).sum().reindex(range(len(sa))).fillna(0)
rivA, sboA, anyA = rw("riv"), rw("sbo"), rw("any")
areaA = ((mb["area"] * mb["any"]).groupby(mb["i"]).sum() / area_i).reindex(range(len(sa))).fillna(0)
print(f"mesh blocks: {len(mb)}; categories: {mb['cat'].value_counts().head(8).to_dict()}")

# ---------------- rasters sampled at mesh-block points, area-weighted to SA1
mbp = mb.representative_point().to_crs(4326)
def sample(paths, scale=1.0):
    try:
        import rasterio
    except ImportError:
        return None
    v = np.full(len(mb), np.nan)
    for pth in paths:
        with rasterio.open(pth) as r:
            b = r.bounds
            xs, ys = mbp.x.values, mbp.y.values
            if r.crs and r.crs.to_epsg() != 4326:        # e.g. the statewide Vicmap DEM is in VicGrid (EPSG:3111)
                from rasterio.warp import transform as _tf
                xs, ys = map(np.asarray, _tf("EPSG:4326", r.crs, xs, ys))
            m = (xs >= b.left) & (xs < b.right) & (ys > b.bottom) & (ys <= b.top) & np.isnan(v)
            if m.any():
                vals = np.array([x[0] for x in r.sample(zip(xs[m], ys[m]))], float)
                if r.nodata is not None:
                    vals[vals == r.nodata] = np.nan
                v[m] = vals * scale
    if np.isnan(v).all():
        return None
    ok = ~np.isnan(v); w = mb["area"].where(ok, 0)
    return (pd.Series(np.nan_to_num(v) * w).groupby(mb["i"]).sum() / w.groupby(mb["i"]).sum()).reindex(range(len(sa)))
# Vicmap 10 m DEM, as the paper used: a statewide GeoTIFF placed by hand (the 12 GB DataVic download
# is Deflate64-zipped, so it can't be read remotely; see README), else chunks from the image service.
elev = sample(sorted(glob.glob("data/raw/shared/vmelev_dem10m*.tif")) + sorted(glob.glob(f"{RAW}/dem10*.tif")))
if elev is not None:
    NOTES.append("Elevation: Vicmap Elevation 10 m DEM (as in the paper), sampled at mesh-block points.")
else:
    elev = sample(sorted(glob.glob("data/raw/shared/dem_*.tif")))
    NOTES.append("Elevation: Copernicus GLO-30 surface model, 30 m (the Vicmap 10 m DEM was unavailable for this build)."
                 if elev is not None else "Elevation unavailable for this build, so the elevation term is left out of Exposure.")
sand = sample(glob.glob(f"{RAW}/sand.tif"), 0.1)  # SoilGrids g/kg -> %
NOTES.append("Sand: SoilGrids 250 m, 0-5 cm (the paper used the 30 m Victorian soil grid)." if sand is not None
             else "Soil sand % unavailable for this build, so the sand term is left out of Exposure.")
NOTES.append("Flood depth: share of each SA1's residents inside LSIO/FO/SBO planning overlays (the paper used HEC-RAS depth).")

# ---------------- tree canopy: zonal mean of the 10 m canopy grids per mesh block, area-weighted to SA1
def canopy_share():
    tifs = sorted(glob.glob("data/raw/shared/canopy10/*.tif"))
    if not tifs:
        return None
    import rasterio
    from rasterio.features import rasterize
    tot, cnt = np.zeros(len(mb)), np.zeros(len(mb))
    for t in tifs:
        with rasterio.open(t) as r:
            m = mb.to_crs(r.crs)
            b = r.bounds
            k = m.intersects(shapely.box(b.left, b.bottom, b.right, b.top)).values
            if not k.any():
                continue
            a = r.read(1)
            ids = rasterize(((g, i + 1) for i, g in zip(np.flatnonzero(k), m.geometry.values[k])),
                            out_shape=a.shape, transform=r.transform, fill=0, dtype="int32")
            ok = (ids > 0) & (a != 255)
            tot += np.bincount(ids[ok] - 1, weights=a[ok], minlength=len(mb))
            cnt += np.bincount(ids[ok] - 1, minlength=len(mb))
    if cnt.sum() == 0:
        return None
    mbc = np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)            # % canopy per mesh block
    w = mb["area"].where(cnt > 0, 0)
    out = (pd.Series(np.nan_to_num(mbc) * w).groupby(mb["i"]).sum() / w.groupby(mb["i"]).sum()).reindex(range(len(sa)))
    print(f"canopy: {len(tifs)} tiles, {int((cnt > 0).sum())} of {len(mb)} mesh blocks covered, "
          f"study mean {np.nanmean(out):.1f}%")
    return out
try:
    canopy = canopy_share()
except Exception as e:
    print("WARNING could not compute tree canopy:", e); canopy = None
if canopy is not None:
    NOTES.append("Tree canopy: Vicmap Vegetation tree extent (2020, 20 cm), as % of each SA1's area.")

# ---------------- road casement: share of each SA1 that is road reserve (Lee et al.'s transport density)
def polygon_share(polys, res=5.0, tile=10000.0):
    """Share of each SA1's area covered by polys, by rasterising both at res metres in
    tile x tile metre blocks (memory stays flat for the whole metro area)."""
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    tree = shapely.STRtree(polys)
    sgeom = sa.geometry.values; stree = shapely.STRtree(sgeom)
    hit, tot = np.zeros(len(sa)), np.zeros(len(sa))
    x0, y0, x1, y1 = sa.total_bounds
    n = int(tile / res)
    for tx in np.arange(x0, x1, tile):
        for ty in np.arange(y0, y1, tile):
            box = shapely.box(tx, ty, tx + tile, ty + tile)
            si = stree.query(box)
            if not len(si):
                continue
            tr = from_origin(tx, ty + tile, res, res)
            ids = rasterize(((sgeom[i], i + 1) for i in si), out_shape=(n, n), transform=tr, fill=0, dtype="int32")
            pi = tree.query(box)
            r = (rasterize(((polys[i], 1) for i in pi), out_shape=(n, n), transform=tr, fill=0, dtype="uint8")
                 if len(pi) else np.zeros((n, n), "uint8"))
            k = ids > 0
            tot += np.bincount(ids[k] - 1, minlength=len(sa))
            hit += np.bincount(ids[k] - 1, weights=r[k], minlength=len(sa))
    return pd.Series(np.where(tot > 0, hit / np.maximum(tot, 1), np.nan))
road = None
_rf = sorted(glob.glob("data/raw/shared/roads/*.shp")) or sorted(glob.glob("data/raw/shared/roads/*.geojson"))
if _rf:
    try:
        rd = gpd.read_file(_rf[0]).to_crs(CRS)
        rd = rd[rd.geometry.notna() & ~rd.geometry.is_empty]
        rd = rd[rd.intersects(study_poly)]
        road = polygon_share(np.asarray(shapely.make_valid(rd.geometry.values)))
        print(f"road casement: {len(rd):,} polygons in the study area, mean road-reserve share {np.nanmean(road):.1%}")
        NOTES.append("Road reserves: Vicmap Property road casement, as % of each SA1's area (5 m raster).")
    except Exception as e:
        print("WARNING could not use road casement:", e); road = None

# ---------------- building footprints: count and roof coverage per SA1
bcov = bcount = None
BLD = f"{RAW}/buildings.npy"
if os.path.exists(BLD):
    try:
        b = np.load(BLD)
        bp = gpd.GeoDataFrame({"area": b[:, 2]}, geometry=gpd.points_from_xy(b[:, 0], b[:, 1]), crs=4326).to_crs(CRS)
        j = gpd.sjoin(bp, sa[["geometry"]], predicate="within", how="inner")
        j = j[~j.index.duplicated()]
        bcount = j.groupby("index_right").size().reindex(range(len(sa))).fillna(0)
        bcov = (j.groupby("index_right")["area"].sum().reindex(range(len(sa))).fillna(0) / sa["area"]).clip(0, 1)
        print(f"buildings: {len(b):,} read, {len(j):,} in study SA1s, mean roof coverage {bcov.mean():.1%}")
        NOTES.append("Buildings: Microsoft Global ML Building Footprints (machine-learned from Bing imagery), "
                     "counted by footprint centroid.")
    except Exception as e:
        print("WARNING could not use building footprints:", e); bcov = bcount = None

# ---------------- SEIFA 2021 deciles by SA1 (1 = most disadvantaged tenth of Australia)
SEIFA_NAMES = [("IRSD", "Disadvantage"), ("IRSAD", "Advantage and Disadvantage"),
               ("IER", "Economic Resources"), ("IEO", "Education and Occupation")]
seifa = None
def which_index(name):
    """Map an ABS column title to IRSD / IRSAD / IER / IEO (IRSAD's title also contains 'Disadvantage')."""
    n = name.lower()
    if "advantage and disadvantage" in n or "irsad" in n: return "IRSAD"
    if "disadvantage" in n or "irsd" in n: return "IRSD"
    if "economic resources" in n or "ier" in n.split(): return "IER"
    if "education and occupation" in n or "ieo" in n.split(): return "IEO"
    return None
if os.path.exists("data/raw/shared/seifa_sa1_2021.xlsx"):
    try:
        book = pd.read_excel("data/raw/shared/seifa_sa1_2021.xlsx", sheet_name=None, header=None, dtype=object)
        df = book.get("Table 1") if "Table 1" in book else next(iter(v for k, v in book.items() if "1" in k))
        txt = df.map(lambda v: "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v).strip())
        # the sub-header row has both "Score" and "Decile"; the index names are in the row above it
        h = next(r for r in range(min(20, len(txt))) if {"Score", "Decile"} <= set(txt.iloc[r]))
        names = txt.iloc[h - 1].replace("", np.nan).ffill().fillna("")
        cols = {}
        for c in txt.columns:
            if txt.iat[h, c] == "Decile":
                k = which_index(names[c])
                if k and k not in cols:
                    cols[k] = c
        code_col = next(c for c in txt.columns if txt[c].str.fullmatch(r"\d{11}").sum() > 1000)
        body = txt[txt[code_col].str.fullmatch(r"\d{11}")]
        seifa = {k: pd.to_numeric(body[c], errors="coerce").groupby(body[code_col].values).first() for k, c in cols.items()}
        got = {k: int(v.reindex(codes).notna().sum()) for k, v in seifa.items()}
        print(f"SEIFA: header row {h}, decile columns {cols}; SA1s matched {got}")
        if not cols:
            raise ValueError("no decile columns found")
        NOTES.append("SEIFA 2021 (ABS) deciles by SA1: 1 = most disadvantaged 10% of Australian SA1s.")
    except Exception as e:
        print("WARNING could not read SEIFA:", repr(e))
        try:
            print("  sheets:", list(book)[:8]); [print("  row", r, list(txt.iloc[r])[:11]) for r in range(min(8, len(txt)))]
        except Exception:
            pass
        seifa = None

# ---------------- Lama & Sun (2026) indices
dwell = g36[dwell_cols].sum(axis=1).values
dep = M[:, :4].sum(axis=1) + F[:, :4].sum(axis=1) + M[:, 12:].sum(axis=1) + F[:, 12:].sum(axis=1)   # under 20 and 60+
flood = anyA.values   # residents, not land: a flooded park no longer counts as exposure
ind = pd.DataFrame({
    "flood": flood, "elev": elev.values if elev is not None else np.nan,
    "sand": sand.values if sand is not None else np.nan, "urban": urban.values, "dwell": dwell,
    "pop": g1["Tot_P_P"].values, "dep": dep, "ltc": g20["P_1m_cond_Tot_Tot"].values,
    "emp": g46["P_Tot_Emp_Tot"].values, "edu": g43[edu_cols].sum(axis=1).values, "incgen": g17[inc_col].values})

def mm(x):
    """Paper Appendix 2: standardise (z-score), then min-max to 0-1."""
    x = pd.Series(np.asarray(x, float))
    if x.isna().all() or x.max() == x.min():
        return pd.Series(np.zeros(len(x)))
    z = (x - x.mean()) / x.std()
    return ((z - z.min()) / (z.max() - z.min())).fillna(0)

def lama_sun(x):
    """The six indices for the SA1s in indicator table x, scaled within x (Lama & Sun section 2.2)."""
    dim = {}
    for d, items in LAMA_SUN.items():
        v = np.zeros(len(x))
        for k, w, sgn in items:
            if x[k].isna().all():
                continue
            n = mm(x[k]).values
            v += w * (1 - n if sgn < 0 else n)
        dim[d] = v
    fri = dim["adaptive"] - (dim["sensitivity"] + dim["exposure"])
    dmg = mm(sum(mm(x["flood"].values * x[k].values) for k in DAMAGE_INDICATORS)).values
    return dim, fri, dmg, 0.5 * fri - 0.5 * dmg

dim, FRI, DMG, IFRI = lama_sun(ind)
# The same indices scaled within the papers' own study area only, so they can be checked against
# the published ranges (min-max scaling makes every score relative to the SA1s it is computed over).
paper_ls = {}
if ST.get("paper"):
    _k = np.flatnonzero(sa["lga"].map(norm_lga).isin({norm_lga(x) for x in ST["paper"]["lgas"]}).values)
    if len(_k):
        _d, _f, _g, _i = lama_sun(ind.iloc[_k].reset_index(drop=True))
        for j, i in enumerate(_k):
            paper_ls[i] = [_d["exposure"][j], _d["sensitivity"][j], _d["adaptive"][j], _f[j], _g[j], _i[j]]
        print(f"Paper study area ({len(_k)} SA1s), scaled within it: Exposure max {_d['exposure'].max():.3f} | "
              f"FRI {_f.min():.3f} to {_f.max():.3f} | IFRI {_i.min():.3f} to {_i.max():.3f}")
print(f"Exposure max {dim['exposure'].max():.3f} | FRI {FRI.min():.3f} to {FRI.max():.3f} | IFRI {IFRI.min():.3f} to {IFRI.max():.3f}")

# ---------------- Lama & Sun GWR / MGWR (Table 5, Fig. 4), two-council study area only
# Two models, each a dict from lamasun_stats.run() plus "title", "unit" and where it applies:
#   1. the paper's own study area on SA1s (Lama & Sun Table 5 / Fig. 4, directly comparable);
#   2. all of Greater Melbourne on SA2s (MGWR's cost grows with n^2: 474 SA1s take ~7 min,
#      11,293 would take days). SA1 counts are summed, the flood share is resident-weighted and
#      elevation, sand and land use are area-weighted.
from lamasun_stats import run as run_mgwr
def paper_model():
    names = {norm_lga(x) for x in ST["paper"]["lgas"]}
    k = np.flatnonzero(sa["lga"].map(norm_lga).isin(names).values)
    rp = sa.iloc[k].representative_point()
    print(f"MGWR, paper study area: {len(k)} SA1s")
    m = run_mgwr(ind.iloc[k].reset_index(drop=True), np.column_stack([rp.x.values, rp.y.values]))
    return dict(m, title=f"{ST['paper']['label']}: {' + '.join(ST['paper']['lgas'])}", unit="SA1", idx=k.tolist(), paper_units=True)

def sa2_model():
    key = sa["sa2_name_2021"].values
    w_area, w_pop = sa["area"].values, ind["pop"].values.astype(float)
    agg = {}
    for c in ind.columns:
        v = ind[c].values.astype(float)
        if c == "flood":
            agg[c] = pd.Series(v * w_pop).groupby(key).sum() / pd.Series(w_pop).groupby(key).sum()
        elif c in ("elev", "sand", "urban"):
            ok = np.isfinite(v)
            agg[c] = pd.Series(np.where(ok, v, 0) * w_area * ok).groupby(key).sum() / pd.Series(w_area * ok).groupby(key).sum()
        else:
            agg[c] = pd.Series(v).groupby(key).sum()
    ind2 = pd.DataFrame(agg)
    ind2 = ind2[ind2["pop"] > 0]
    if len(ind2) < 60:                        # 11 coefficients per local fit need far more units than this
        raise ValueError(f"only {len(ind2)} SA2s: too few for GWR/MGWR")
    sa2 = sa.assign(k=key).dissolve("k").loc[ind2.index]
    rp2 = sa2.representative_point()
    print(f"MGWR, {ST['title']}: {len(ind2)} SA2s (from {len(sa)} SA1s)")
    m = run_mgwr(ind2.reset_index(drop=True), np.column_stack([rp2.x.values, rp2.y.values]))
    return dict(m, title=f"{ST['title']}, all {len(lga)} councils", unit="SA2",
                units=[{"name": n} for n in ind2.index], _geoms=list(sa2.geometry.values))

stats = []
for want, fn in ((ST.get("paper"), paper_model), (ST.get("mgwr") == "SA2", sa2_model)):
    if not want:
        continue
    try:
        stats.append(fn())
    except Exception as e:                    # a failed model must not take the maps down with it
        print(f"WARNING {fn.__name__} failed:", repr(e)[:300])
        NOTES.append(f"The {'paper-area' if fn is paper_model else 'metro-wide'} GWR/MGWR could not be fitted for this build.")

r4 = lambda v: None if not np.isfinite(v) else round(float(v), 4)
recs = []
for i, c in enumerate(codes):
    recs.append(dict(
        id=c, sa2=sa.sa2_name_2021.iloc[i], sub=sa["sub"].iloc[i], lga=sa.lga.iloc[i], basin=sa["basin"].iloc[i],
        **({"drain": sa["drain"].iloc[i]} if sa["drain"].iloc[i] else {}), km2=round(sa.area.iloc[i] / 1e6, 4),
        M=M[i].tolist(), F=F[i].tolist(), pop=int(g1.loc[c, "Tot_P_P"]),
        nfa=int(g18.loc[c, "P_Tot_Need_for_assistance"]), nfa_d=int(g18.loc[c, "P_Tot_Tot"] - g18.loc[c, "P_Tot_Need_for_assistance_ns"]),
        ltc=int(g20.loc[c, "P_1m_cond_Tot_Tot"]), ltc_d=int(g20.loc[c, "P_Tot_Tot"] - g20.loc[c, "P_cond_NS_Tot"]),
        emp=int(g46.loc[c, "P_Tot_Emp_Tot"]), unemp=int(g46.loc[c, "P_Tot_Unemp_Tot"]), lf=int(g46.loc[c, "P_Tot_LF_Tot"]),
        eng=int(g13.loc[c, "P_Tot_UOLSE_NWorNAA"]), eng_d=int(g13.loc[c, "P_Tot_Tot"] - g13.loc[c, "P_Tot_NS"]),
        car0=int(g34.loc[c, "Num_MVs_per_dweling_0_MVs"]), car_d=int(g34.loc[c, "Num_MVs_per_dweling_Tot"]),
        d_house=int(g36.loc[c, "OPDs_Separate_house_Dwellings"]), d_semi=int(g36.loc[c, "OPDs_SD_r_t_h_th_Tot_Dwgs"]),
        d_flatlow=int(g36.loc[c, "OPDs_F_ap_I_1or2_sty_blk_Ds"] + g36.loc[c, "OPDs_F_ap_I_3_sty_blk_Dwgs"] + g36.loc[c, "OPDs_Flt_apt_Att_house_Ds"]),
        d_flathigh=int(g36.loc[c, "OPDs_F_ap_I_4to8_sty_blk_Ds"] + g36.loc[c, "OPDs_F_ap_I_9_m_sty_blk_Ds"]),
        d_other=int(g36.loc[c, "OPDs_Other_dwelling_Tot_Dwgs"]), inc=int(g2.loc[c, "Median_tot_hhd_inc_weekly"]),
        riv=round(float(rivA[i]), 4), sbo=round(float(sboA[i]), 4),
        fl=round(float(anyA[i]), 4), fa=round(float(areaA[i]), 4),
        can=None if canopy is None or not np.isfinite(canopy.iloc[i]) else round(float(canopy.iloc[i]), 1),
        road=None if road is None or not np.isfinite(road.iloc[i]) else round(float(road.iloc[i]), 4),
        bcov=None if bcov is None else round(float(bcov.iloc[i]), 4), bn=None if bcount is None else int(bcount.iloc[i]),
        seifa=None if seifa is None else [None if k not in seifa or pd.isna(seifa[k].get(c)) else int(seifa[k].get(c))
                                          for k, _ in SEIFA_NAMES],
        ls=[r4(dim["exposure"][i]), r4(dim["sensitivity"][i]), r4(dim["adaptive"][i]), r4(FRI[i]), r4(DMG[i]), r4(IFRI[i])],
        **({"lsp": [r4(v) for v in paper_ls[i]]} if i in paper_ls else {})))

# ---------------- geometry for the browser
tol = ST["simplify_m"]
def gj(geom, t=tol):
    """Simplify, reproject and orient exterior rings clockwise. D3's spherical geometry
    (used for bounds, centroids and the analysis maps) reads an anticlockwise ring as
    'the whole globe except this shape'."""
    from shapely.geometry import MultiPolygon, Polygon
    from shapely.geometry.polygon import orient
    g = gpd.GeoSeries([geom], crs=CRS).simplify(t).to_crs(4326).iloc[0]
    if isinstance(g, Polygon):
        g = orient(g, sign=-1.0)
    elif isinstance(g, MultiPolygon):
        g = MultiPolygon([orient(p, sign=-1.0) for p in g.geoms])
    rnd = lambda o: [rnd(x) for x in o] if isinstance(o, (list, tuple)) else round(o, 5)
    m = g.__geo_interface__
    return {"type": m["type"], "coordinates": rnd(m["coordinates"])}
for m in stats:
    for u, g in zip(m.get("units", []), m.pop("_geoms", [])):
        u["g"] = gj(g, tol * 3)
p4 = mb.representative_point().to_crs(4326)
mbo = mb.assign(x=p4.x.round(5), y=p4.y.round(5))
mbo = mbo[(mbo["w"] > 0) | (mbo["riv"] + mbo["sbo"] > 0)]
out = dict(
    meta=dict(study=STUDY, title=ST["title"], label=ST["label"], n=len(sa), lat0=round(float(p4.y.mean()), 3),
              addr=bool(mb["naddr"].any()),
              notes=NOTES, presets=([{"key": "__paper", "label": ST["paper"]["label"], "group": "Study areas",
                                      "lgas": [l for l in lga["name"] if norm_lga(l) in {norm_lga(x) for x in ST["paper"]["lgas"]}]}]
                                    if ST.get("paper") else [])
              + [{"key": "basin:" + b, "label": f"{b} river basin", "group": "River basins (Melbourne Water)", "basin": b}
                 for b, n in sa["basin"].value_counts().items() if b and n >= 20]),
    sa1=recs, shapes=[gj(g) for g in sa.geometry], stats=stats,
    mb=[[r.x, r.y, int(r.i), round(float(r.w), 4), round(float(r.riv), 2), round(float(r.sbo), 2)] for r in mbo.itertuples()],
    riv=gj(riv, tol * 1.5), sbo=gj(sbo, tol * 1.5),
    lga=[{"name": r.name, "g": gj(r.geometry, tol * 3)} for r in lga.itertuples()],
    basins=[] if basins is None else [{"name": r.name, "g": gj(r.geometry.intersection(study_poly.buffer(2000)), tol * 4)}
                                      for r in basins.itertuples()],
    sal=[{"name": r.name, "g": gj(r.geometry, tol * 2)} for r in sal.itertuples()])
s = json.dumps(out, separators=(",", ":"), allow_nan=False)
open(f"data/processed/{STUDY}.json", "w").write(s)
print(f"data/processed/{STUDY}.json: {len(s) / 1e6:.1f} MB, {len(out['mb'])} mesh blocks, {len(out['sal'])} suburbs")
for n in NOTES:
    print("  note:", n)
