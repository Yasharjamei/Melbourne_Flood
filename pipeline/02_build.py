"""Build one study area's dataset from data/raw/<study>/ -> data/processed/<study>.json

    python pipeline/02_build.py --study west

Per SA1: Census 2021 counts, flood-overlay shares, suburb, and the Lama & Sun (2026)
Exposure / Sensitivity / Adaptive capacity / FRI / Damage / IFRI indices.
Per mesh block: a population weight used to apportion SA1 counts to circles.
"""
import argparse, glob, json, os, re, sys
import numpy as np, pandas as pd, geopandas as gpd
from shapely.ops import unary_union
sys.path.insert(0, os.path.dirname(__file__))
from config import STUDIES, LAMA_SUN, DAMAGE_INDICATORS, norm_lga

ap = argparse.ArgumentParser(); ap.add_argument("--study", default="west", choices=STUDIES)
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


# ---------------- geography
wanted = {norm_lga(n) for n in ST["lgas"]}
lga = gpd.read_file(f"{RAW}/lga.geojson")
lga = lga[lga["lga_name_2021"].map(norm_lga).isin(wanted)].to_crs(CRS).reset_index(drop=True)
lga["name"] = lga["lga_name_2021"].str.replace(" (Vic.)", "", regex=False)
sa = gpd.read_file(f"{RAW}/sa1.geojson").to_crs(CRS)
pt = sa.copy(); pt["geometry"] = sa.representative_point()
j = gpd.sjoin(pt, lga[["name", "geometry"]], predicate="within")
j = j[~j.index.duplicated()]
sa = sa.loc[j.index].copy(); sa["lga"] = j["name"].values
sa = sa.drop_duplicates("sa1_code_2021").reset_index(drop=True)
sa["area"] = sa.area
codes = sa["sa1_code_2021"].astype(str).tolist(); idx = {c: i for i, c in enumerate(codes)}
print(f"{STUDY}: {len(lga)} LGAs, {len(sa)} SA1s")

# suburbs (ABS Suburbs and Localities): SA1 -> suburb by representative point
sal = gpd.read_file(f"{RAW}/sal.geojson").to_crs(CRS)
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

# ---------------- flood overlays
fl = gpd.read_file(f"{RAW}/flood.geojson").to_crs(CRS)
fl = fl[fl.geometry.notna()].copy(); fl["geometry"] = fl.buffer(0)
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
mb = gpd.read_file(f"{RAW}/mb.geojson").to_crs(CRS)
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
        rows = []
        for df in pd.read_excel("data/raw/shared/mb_counts_2021.xlsx", sheet_name=None, header=None, dtype=str).values():
            h = df.index[df.apply(lambda r: r.astype(str).str.strip().eq("MB_CODE_2021").any(), axis=1)]
            if len(h):
                d = df.iloc[h[0] + 1:].copy(); d.columns = df.iloc[h[0]].astype(str).str.strip(); rows.append(d)
        pop = pd.to_numeric(pd.concat(rows).set_index("MB_CODE_2021")["Person"], errors="coerce")
        mb["pop"] = mb["code"].map(pop).fillna(0).values
        NOTES.append("Mesh blocks weighted by 2021 Census resident counts (ABS Mesh Block Counts).")
    except Exception as e:
        print("WARNING could not read mesh-block counts:", e); pop = None
if pop is None:
    mb["pop"] = np.where(mb["cat"].str.lower().str.startswith("residential"), mb["area"], 0.0)
    NOTES.append("Mesh-block counts unavailable: residents placed on Residential mesh blocks in proportion to area.")
tot = mb.groupby("i")["pop"].transform("sum")
atot = mb.groupby("i")["area"].transform("sum")
mb["w"] = np.where(tot > 0, mb["pop"] / tot.where(tot > 0, 1), mb["area"] / atot)
mb["riv"] = share_in(mb, riv); mb["sbo"] = share_in(mb, sbo)
area_i = mb.groupby("i")["area"].sum()
nonurban = mb["cat"].str.lower().str.contains("parkland|water|primary production")
urban = ((mb["area"] * ~nonurban).groupby(mb["i"]).sum() / area_i).reindex(range(len(sa))).fillna(0)
rivA = ((mb["area"] * mb["riv"]).groupby(mb["i"]).sum() / area_i).reindex(range(len(sa))).fillna(0)
sboA = ((mb["area"] * mb["sbo"]).groupby(mb["i"]).sum() / area_i).reindex(range(len(sa))).fillna(0)
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
elev = sample(sorted(glob.glob("data/raw/shared/dem_*.tif")))
sand = sample(glob.glob(f"{RAW}/sand.tif"), 0.1)  # SoilGrids g/kg -> %
NOTES.append("Elevation: Copernicus GLO-30 surface model, 30 m (the paper used the Vicmap 10 m DEM)." if elev is not None
             else "Elevation unavailable for this build, so the elevation term is left out of Exposure.")
NOTES.append("Sand: SoilGrids 250 m, 0-5 cm (the paper used the 30 m Victorian soil grid)." if sand is not None
             else "Soil sand % unavailable for this build, so the sand term is left out of Exposure.")
NOTES.append("Flood depth: share of each SA1 inside LSIO/FO/SBO planning overlays (the paper used HEC-RAS depth).")

# ---------------- Lama & Sun (2026) indices
dwell = g36[dwell_cols].sum(axis=1).values
dep = M[:, :4].sum(axis=1) + F[:, :4].sum(axis=1) + M[:, 12:].sum(axis=1) + F[:, 12:].sum(axis=1)   # under 20 and 60+
flood = np.minimum(1, rivA.values + sboA.values)
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

dim = {}
for d, items in LAMA_SUN.items():
    s = np.zeros(len(sa))
    for k, w, sgn in items:
        if ind[k].isna().all():
            continue
        n = mm(ind[k]).values
        s += w * (1 - n if sgn < 0 else n)
    dim[d] = s
FRI = dim["adaptive"] - (dim["sensitivity"] + dim["exposure"])
DMG = mm(sum(mm(flood * ind[k].values) for k in DAMAGE_INDICATORS)).values
IFRI = 0.5 * FRI - 0.5 * DMG
print(f"Exposure max {dim['exposure'].max():.3f} | FRI {FRI.min():.3f} to {FRI.max():.3f} | IFRI {IFRI.min():.3f} to {IFRI.max():.3f}")

r4 = lambda v: None if not np.isfinite(v) else round(float(v), 4)
recs = []
for i, c in enumerate(codes):
    recs.append(dict(
        id=c, sa2=sa.sa2_name_2021.iloc[i], sub=sa["sub"].iloc[i], lga=sa.lga.iloc[i], km2=round(sa.area.iloc[i] / 1e6, 4),
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
        ls=[r4(dim["exposure"][i]), r4(dim["sensitivity"][i]), r4(dim["adaptive"][i]), r4(FRI[i]), r4(DMG[i]), r4(IFRI[i])]))

# ---------------- geometry for the browser
tol = ST["simplify_m"]
def gj(geom, t=tol):
    g = gpd.GeoSeries([geom], crs=CRS).simplify(t).to_crs(4326).iloc[0]
    rnd = lambda o: [rnd(x) for x in o] if isinstance(o, (list, tuple)) else round(o, 5)
    m = g.__geo_interface__
    return {"type": m["type"], "coordinates": rnd(m["coordinates"])}
p4 = mb.representative_point().to_crs(4326)
mbo = mb.assign(x=p4.x.round(5), y=p4.y.round(5))
mbo = mbo[(mbo["w"] > 0) | (mbo["riv"] + mbo["sbo"] > 0)]
out = dict(
    meta=dict(study=STUDY, title=ST["title"], label=ST["label"], n=len(sa), lat0=round(float(p4.y.mean()), 3),
              notes=NOTES, other={"west": ["All of Melbourne", "metro/"], "metro": ["Maribyrnong & Moonee Valley", "../"]}[STUDY]),
    sa1=recs, shapes=[gj(g) for g in sa.geometry],
    mb=[[r.x, r.y, int(r.i), round(float(r.w), 4), round(float(r.riv), 2), round(float(r.sbo), 2)] for r in mbo.itertuples()],
    riv=gj(riv, tol * 1.5), sbo=gj(sbo, tol * 1.5),
    lga=[{"name": r.name, "g": gj(r.geometry, tol * 3)} for r in lga.itertuples()],
    sal=[{"name": r.name, "g": gj(r.geometry, tol * 2)} for r in sal.itertuples()])
s = json.dumps(out, separators=(",", ":"), allow_nan=False)
open(f"data/processed/{STUDY}.json", "w").write(s)
print(f"data/processed/{STUDY}.json: {len(s) / 1e6:.1f} MB, {len(out['mb'])} mesh blocks, {len(out['sal'])} suburbs")
for n in NOTES:
    print("  note:", n)
