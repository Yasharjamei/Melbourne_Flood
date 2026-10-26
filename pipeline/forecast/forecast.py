"""Population forecast to 2036 and residents in flood areas, for the scenarios page.

Method (docs/PROJECT_LOG.md §29-31):
  1. Base: ABS ERP 2025 by SA2, split into SA2 x council pieces by 2021 Census residents (mesh blocks).
  2. Council totals: VIF2023 growth from mid-2025 (VIF interpolated) added to the actual 2025 ERP, so
     VIF's level error to date is removed and its growth kept. Dwellings likewise.
  3. Where each council's growth goes (housing-unit model):
       - Urban Development Program 2025 supply, if data/static/udp2025/udp2025_pieces.csv exists:
         major-redevelopment dwellings and greenfield lots, each weighted by an ASSUMED probability
         of being built by the year (STATUS below). Capped at the council's projected new dwellings.
       - the rest (minor infill, not in UDP) by where addresses were created in the last 5 years.
     Without the UDP file only the second part runs (the open-data method).
  4. Residents in flood areas: existing residents by each mesh block's share of address points inside
     the area (as the live map); new residents by the share of addresses created since 2016 in that
     piece that fall inside it (new housing has largely avoided the overlays).
     Areas: "today" = planning overlays (LSIO, FO, SBO) + present-day (2009) coastal extent;
     each sea-level scenario adds its coastal extent (taken as its union with 2009).
  5. Ranges: SA2 from the back-test (housing-unit model's 80th-percentile SA2 error, interpolated by
     horizon, widened or narrowed by SA2 size and growth class); councils and the total from VIF's
     2021-25 council error, grown linearly with the horizon.

Run after fetch.py, ensemble.py and the main 01_fetch.py:
    python pipeline/forecast/forecast.py  ->  data/processed/scenarios.json (the page's data), prints a report
"""
import glob, json, os, re, sys, zipfile
import numpy as np, pandas as pd, geopandas as gpd
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, HERE)
from config import STUDIES, norm_lga
from backtest import table, codes
from ensemble import read_erp

RAW, FC, ST = "data/raw/metro", "data/raw/forecast", "data/static"
CRS = 7855
BASE, YEARS = 2025, [2025, 2026, 2031, 2036]
# (id, label, short label, layers added to the planning overlays; storm-tide extents are cumulative because
# the published layers don't nest: 12.8 km2 of the 2040 storm tide lies outside the 2070 one)
SLR = [("none", "Today's flood areas", "Today", ["SLR00CM_2009"]),
       ("0.2", "+0.20 m sea level (2040)", "+0.20 m", ["SLR00CM_2009", "SLR20CM_2040"]),
       ("0.47", "+0.47 m sea level (2070)", "+0.47 m", ["SLR00CM_2009", "SLR47CM_2070"]),
       ("0.82", "+0.82 m sea level (2100)", "+0.82 m", ["SLR00CM_2009", "SLR82CM_2100"]),
       ("st", "Today, with a 1-in-100-year storm tide", "Today", ["SLR00CM_2009", "SLR00CM_ST_2009"]),
       ("st0.2", "+0.20 m sea level (2040) with a storm tide", "+0.20 m", ["SLR00CM_2009", "SLR20CM_2040", "SLR00CM_ST_2009", "SLR20CM_ST_2040"]),
       ("st0.47", "+0.47 m sea level (2070) with a storm tide", "+0.47 m", ["SLR00CM_2009", "SLR47CM_2070", "SLR00CM_ST_2009", "SLR20CM_ST_2040", "SLR47CM_ST_2070"]),
       ("st0.82", "+0.82 m sea level (2100) with a storm tide", "+0.82 m", ["SLR00CM_2009", "SLR82CM_2100", "SLR00CM_ST_2009", "SLR20CM_ST_2040", "SLR47CM_ST_2070", "SLR82CM_ST_2100"])]
# ASSUMED share of each UDP category built by the end of the ramp, and the ramp length in years from
# mid-2025. Not measured: UDP 2025 has no history (completions 2023-24 only). Council caps limit how
# much these matter; they mainly decide WHERE inside a council the growth goes.
STATUS = {"mrs_under_construction": (0.95, 2), "mrs_firm": (0.80, 5), "mrs_likely": (0.50, 8),
          "mrs_possible": (0.25, 11), "gf_titled": (0.95, 2), "gf_proposed": (0.85, 5),
          "gf_zoned": (0.60, 11), "gf_unzoned": (0.15, 11)}


def ramp(y, p, T, start=0):
    return p * float(np.clip((y - BASE - start) / T, 0, 1))


def vif(sheet):
    t = pd.read_excel(f"{ST}/vif2023/VIF2023_LGA_Pop_Hhold_Dwelling_Projections_to_2036.xlsx", sheet_name=sheet, header=None)
    h = t.index[t.iloc[:, 0].astype(str).str.contains("LGA", case=False) & t.iloc[:, 2].astype(str).str.startswith("2021")][0]
    d = t.loc[h + 1:, :5].dropna(subset=[0]); d.columns = ["code", "name", 2021, 2026, 2031, 2036]
    d["code"] = codes(d["code"]); d = d[d["code"].str.fullmatch(r"\d{5}")]
    d["name"] = d["name"].astype(str).str.replace(r"\s*\(.*\)$", "", regex=True)
    for y in (2021, 2026, 2031, 2036):
        d[y] = d[y].astype(float)
    d[BASE] = d[2021] + (BASE - 2021) / 5 * (d[2026] - d[2021])
    return d.set_index("code")


def polys(g):
    """Repair, then keep only the polygonal parts (Vicmap overlays include self-intersecting rings,
    which made a plain union fail with a GEOS TopologyException in the first CI run)."""
    from shapely.geometry import MultiPolygon, Polygon
    g = gpd.GeoSeries(g if isinstance(g, (list, gpd.GeoSeries)) else [g], crs=CRS).make_valid()
    parts = [q for x in g for q in getattr(x, "geoms", [x]) if isinstance(q, (Polygon, MultiPolygon)) and not q.is_empty]
    return unary_union(parts) if parts else MultiPolygon()


_layers = {}
def slr_layer(name):
    if name not in _layers:
        z = f"{ST}/coastal_inundation/{name}.zip"
        inner = next(n for n in zipfile.ZipFile(z).namelist() if n.endswith(f"/{name}.shp"))
        _layers[name] = polys(gpd.read_file(f"zip://{z}!{inner}").to_crs(CRS).geometry)
    return _layers[name]


def to_geojson(geoms, props=None, tol=20, min_m2=0, grid=1e-5):
    """Simplified lon/lat GeoJSON for the page's map. Parts under min_m2 are dropped (when no properties)."""
    import shapely
    g = gpd.GeoSeries([polys(x) for x in geoms], crs=CRS)                   # polygonal parts only, no collections
    if min_m2:
        keep = (g.area >= min_m2).values
        g = g[keep].reset_index(drop=True)
        props = [q for q, k in zip(props, keep) if k] if props else None
    g = g.simplify(tol).to_crs(4326)
    g = gpd.GeoSeries(shapely.set_precision(g.values, grid), crs=4326)
    feats = []
    for i, x in enumerate(g):
        if x is None or x.is_empty:
            continue
        feats.append({"type": "Feature", "properties": (props[i] if props else {}), "geometry": shapely.geometry.mapping(x)})
    return {"type": "FeatureCollection", "features": feats}


def ov_layers(fl, study):
    """Planning overlays for the map, riverine (LSIO, FO: t='r') and overland flow (SBO: t='s') kept apart
    so each can be switched on and off, as on the main map."""
    parts, props = [], []
    for t, codes_ in (("r", ["LSIO", "FO"]), ("s", ["SBO"])):
        z = polys(polys(fl[fl.scheme_code.isin(codes_)].geometry).intersection(study))
        g = list(getattr(z, "geoms", [z]))
        parts += g; props += [{"t": t}] * len(g)
    return to_geojson(parts, props, tol=15, min_m2=2000)


def inside(pts, zone):
    parts = gpd.GeoDataFrame(geometry=list(getattr(zone, "geoms", [zone])), crs=CRS)
    parts = parts[~parts.is_empty]
    if parts.empty:
        return np.zeros(len(pts), bool)
    return pts.index.isin(gpd.sjoin(pts, parts, predicate="within", how="inner").index.unique())


# Ground level. Everyone whose address is inside a flood area is counted, including people on the 30th floor.
# From the 2021 Census dwelling structure of each SA1 (table G36, persons), with an assumed share of each
# type's residents living at ground level: central (low, high). Roughly one floor in n for a block of n
# storeys, less where the ground floor is lobby, shops or parking.
G36 = "data/raw/gcp/2021Census_G36_VIC_SA1.csv"
GCP_URL = "https://www.abs.gov.au/census/find-census-data/datapacks/download/2021_GCP_SA1_for_VIC_short-header.zip"
GROUND = {"house": (1, 1, 1), "semi": (1, 1, 1), "attached": (1, 1, 1), "other": (1, 1, 1),
          "flat12": (.5, .4, .6), "flat3": (.33, .25, .4), "flat48": (.15, .05, .2), "flat9": (.03, 0, .08)}
G36_TYPES = {"house": r"OPDs_Separate_house", "semi": r"OPDs_SD_r_t_h_th_Tot", "attached": r"OPDs_Flt_apt_Att_house",
             "other": r"OPDs_Other_dwelling_Tot", "flat12": r"OPDs_F_ap_I_1or2_sty_blk", "flat3": r"OPDs_F_ap_I_3_sty_blk",
             "flat48": r"OPDs_F_ap_I_4to8_sty_blk", "flat9": r"OPDs_F_ap_I_9_m_sty_blk"}


def g36_table():
    """Census 2021 G36 residents by dwelling type for every Victorian SA1 (downloads the DataPack if not cached)."""
    import io, urllib.request
    if not os.path.exists(G36):
        print("  Census table G36 not cached; downloading the DataPack (~100 MB)")
        req = urllib.request.Request(GCP_URL, headers={"User-Agent": "Mozilla/5.0 (melbourne-flood pipeline)"})
        z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(req, timeout=600).read()))
        m = [n for n in z.namelist() if n.endswith("2021Census_G36_VIC_SA1.csv")]
        os.makedirs(os.path.dirname(G36), exist_ok=True); open(G36, "wb").write(z.read(m[0]))
    t = pd.read_csv(G36, dtype={"SA1_CODE_2021": str}).set_index("SA1_CODE_2021")
    dwg, per = re.compile(r"(Dwellings|Dwgs|Dwlgs|_Ds)$", re.I), re.compile(r"(Persons|Psns|Prsns|_Ps|_P)$", re.I)
    cols = {}
    for k, pre in G36_TYPES.items():
        cand = [c for c in t.columns if c.startswith(pre)]
        pc = [c for c in cand if per.search(c) and not dwg.search(c)] or [c for c in cand if dwg.search(c)]
        cols[k] = pc[0] if pc else None
    return pd.DataFrame({k: (pd.to_numeric(t[c], errors="coerce").fillna(0) if c else 0) for k, c in cols.items()}, index=t.index)


def ground_share(sa1_codes, which=0):
    """Share of each SA1's residents living at ground level (index = SA1 code); SA1s with under 30
    residents take their SA2's mix. which: 0 central, 1 low, 2 high."""
    idx = pd.Index(sa1_codes)
    T = g36_table().reindex(idx).fillna(0)
    f = pd.Series({k: v[which] for k, v in GROUND.items()})
    tot, grd = T.sum(axis=1), (T * f).sum(axis=1)
    sa2 = pd.Series(idx.str[:9], index=idx)
    g2 = grd.groupby(sa2).transform("sum") / tot.groupby(sa2).transform("sum").replace(0, np.nan)
    return (grd / tot.replace(0, np.nan)).where(tot >= 30, g2).fillna(g2).fillna(1.0)


SA1_ERR = 1.9     # SA1 placement error / SA2 split error in the 2016->2021 back-tests (11.6% vs 6.0%, §25 and §29)


def mb_points(m2, sa1_of, rows, mb_pop, mb_ex):
    """Mesh-block points for the A/B circles, as on the main map: a circle counts the mesh blocks whose
    centre falls inside it, each adding its share of its SA1's residents (w, per year) and of its SA1's
    residents in each flood area (f, per scenario, final-year shares used for every year). Shares are
    in thousandths; mesh blocks with no residents in any year are left out."""
    ri = pd.Series(np.arange(len(rows)), index=rows)
    s = pd.Series(sa1_of).map(ri).values
    live = ~np.isnan(s) & (np.max(np.vstack(list(mb_pop.values())), axis=0) > 0)
    pt = gpd.GeoSeries(m2.geometry.values, crs=CRS)[live].representative_point().to_crs(4326)
    si = s[live].astype(int)
    def share(v):
        v = v[live]
        t = np.bincount(si, weights=v, minlength=len(rows))
        return np.round(1000 * v / np.where(t[si] > 0, t[si], 1)).astype(int).tolist()
    return {"x": np.round(pt.x.values * 1e4).astype(int).tolist(), "y": np.round(pt.y.values * 1e4).astype(int).tolist(),
            "s": si.tolist(), "w": [share(mb_pop[y]) for y in YEARS], "f": {k: share(e) for k, e in mb_ex.items()}}


def finer(out, p, mb, pop, exposure, zones, sa2_rel):
    """Suburbs and SA1s for the map's area-level switch. Each piece's forecast is spread over its mesh blocks
    (existing residents by 2021 Census share, growth where addresses were created in the last 5 years), the
    residents in each flood area follow the mesh blocks' address shares, and everything is rescaled so mesh
    blocks add back to the piece totals. Suburbs go into scenarios.json; SA1s into a separate file loaded only
    when chosen (scenarios_sa1.js), to keep the page light."""
    ids = list(zones)
    sa1g = gpd.read_file(f"{RAW}/sa1.geojson").to_crs(CRS)
    sa1g["c"] = codes(sa1g[next(c for c in sa1g.columns if re.fullmatch(r"sa1_code_2021|sa1_code.*", c, re.I))])
    sal = gpd.read_file(f"{RAW}/sal.geojson").to_crs(CRS)
    sal["c"] = codes(sal[next(c for c in sal.columns if re.fullmatch(r"sal_code_2021|sal_code.*", c, re.I))])
    sal["name"] = sal[next(c for c in sal.columns if re.fullmatch(r"sal_name_2021|sal_name.*", c, re.I))].str.replace(r" \(Vic\.\)", "", regex=True)
    rp = sa1g.set_geometry(sa1g.geometry.representative_point())[["c", "geometry"]]
    js = gpd.sjoin(rp, sal[["c", "geometry"]].rename(columns={"c": "sal"}), predicate="within", how="left")
    sa1_sal = js[~js.index.duplicated()].set_index("c")["sal"]

    kidx = pd.Series(np.arange(len(p)), index=p["key"].values)
    mi = mb["key"].map(kidx)
    keep = mi.notna().values
    m2, mi = mb[keep], mi[keep].astype(int).values
    n_mb = np.bincount(mi, minlength=len(p))
    p21p, rcp = p["p21"].values[mi], p["recent"].values[mi].astype(float)
    w_old = np.where(p21p > 0, m2["p21"].values / np.where(p21p > 0, p21p, 1), 1 / n_mb[mi])
    w_new = np.where(rcp > 0, m2["recent"].values / np.where(rcp > 0, rcp, 1), w_old)
    sa1_of, P0 = m2["sa1"].values, p["P"].values
    sa1_pop, sa1_ex, mb_pop, mb_ex = {}, {k: {} for k in ids}, {}, {}
    for y in YEARS:
        d = (pop[y] - P0)[mi]
        grow = np.where(d > 0, d * w_new, d * w_old)
        mb_pop[y] = np.maximum(P0[mi] * w_old + grow, 0)
        sa1_pop[y] = pd.Series(P0[mi] * w_old + grow).groupby(sa1_of).sum()
        for k in ids:
            s_old = m2[f"s_{k}"].values
            s_new = np.where(m2["new"].values >= 5, m2[f"n_{k}"].values / np.maximum(m2["new"].values, 1), s_old)
            e = P0[mi] * w_old * s_old + np.where(d > 0, d * w_new * s_new, d * w_old * s_old)
            tot = np.bincount(mi, weights=e, minlength=len(p))
            E = exposure(pop[y], k)
            # A piece can have residents in a flood area while none of its mesh blocks does on its own
            # (new homes counted at piece level from mesh blocks with too few new addresses to judge).
            # There, spread the piece's figure over its mesh blocks by population, so SA1s add up exactly.
            mbpop = np.maximum(P0[mi] * w_old + grow, 0)
            ptot = np.bincount(mi, weights=mbpop, minlength=len(p))
            e = np.where((tot > 0)[mi], e * np.where(tot > 0, E / np.where(tot > 0, tot, 1), 0)[mi],
                         np.where((ptot > 0)[mi], E[mi] * mbpop / np.where(ptot > 0, ptot, 1)[mi], E[mi] / n_mb[mi]))
            sa1_ex[k][y] = pd.Series(e).groupby(sa1_of).sum()
            mb_ex[k] = e                                        # last year's, for the A/B circle weights
    s1 = pd.Index(sorted(sa1_pop[YEARS[0]].index))
    lga_of = m2.groupby("sa1")["lga"].agg(lambda x: x.value_counts().index[0]).reindex(s1)
    out["rel"] = {"suburb": [round(sa2_rel(y - BASE), 4) for y in YEARS],
                  "sa1": [round(min(0.9, SA1_ERR * sa2_rel(y - BASE)), 4) for y in YEARS]}

    # suburbs: sums of their SA1s
    sl = sa1_sal.reindex(s1)
    subs = []
    for c, idx in pd.Series(s1, index=s1).groupby(sl.values):
        names = sal.loc[sal["c"] == c, "name"]
        subs.append({"code": c, "name": names.iloc[0] if len(names) else c,
                     "lga": lga_of.reindex(idx).value_counts().index[0],
                     "pop": [round(sa1_pop[y].reindex(idx).sum()) for y in YEARS],
                     "v": {k: [round(sa1_ex[k][y].reindex(idx).sum()) for y in YEARS] for k in ids}})
    out["suburbs"] = subs
    try:
        gsh = ground_share(list(s1))
        w36 = sa1_ex["none"][YEARS[-1]].reindex(s1).fillna(0)
        def gmean(idx):
            w = w36.reindex(idx).fillna(0); g = gsh.reindex(idx).fillna(1.0)
            return round(float((w * g).sum() / w.sum()) if w.sum() > 0 else float(g.mean()), 3)
        for x in subs:
            x["g"] = gmean(s1[sl.values == x["code"]])
        for a in out["areas"]:
            a["g"] = gmean(s1[s1.str[:9] == a["code"]])
        for c in out["councils"]:
            c["g"] = gmean(lga_of.index[lga_of.values == c["code"]])
        print(f"ground level: {float((w36 * gsh).sum()):,.0f} of {float(w36.sum()):,.0f} residents in today's flood areas in {YEARS[-1]} (central)")
    except Exception as e:                                                     # optional: the page hides the measure
        print(f"ground level: skipped ({e})"); gsh = None
    keep_sal = sal[sal["c"].isin([x["code"] for x in subs])]
    out["geo"]["sal"] = to_geojson(list(keep_sal.geometry), [{"c": c} for c in keep_sal["c"]], tol=25)
    # SA2 -> council (majority of 2021 residents), for the council filter
    sa2_lga = m2.groupby("sa2").apply(lambda g: g.groupby("lga")["p21"].sum().idxmax())
    for a in out["areas"]:
        a["lga"] = sa2_lga.get(a["code"], "")

    # SA1s: separate lazily loaded file
    g1 = sa1g.set_index("c").reindex(s1)
    has = g1.geometry.notna().values
    rows = s1[has]
    d1 = {"years": YEARS, "codes": list(rows), "sa2": [c[:9] for c in rows], "lga": list(lga_of.reindex(rows).fillna("")),
          "sal": list(sa1_sal.reindex(rows).fillna("")),
          **({"g": [round(float(x), 2) for x in gsh.reindex(rows).fillna(1.0)]} if gsh is not None else {}),
          "pop": [[round(sa1_pop[y].get(c, 0)) for y in YEARS] for c in rows],
          "v": {k: [[round(sa1_ex[k][y].get(c, 0)) for y in YEARS] for c in rows] for k in ids},
          "geo": to_geojson(list(g1.geometry[has]), [{"i": i} for i in range(len(rows))], tol=12),
          "mb": mb_points(m2, sa1_of, rows, mb_pop, mb_ex)}
    txt = json.dumps(d1, separators=(",", ":"))
    open("data/processed/scenarios_sa1.js", "w").write("window.SA1DATA=" + txt + ";")
    print(f"finer levels: {len(subs)} suburbs; {len(rows):,} SA1s ({len(txt) / 1e6:.1f} MB, loaded on demand); "
          "SA1 sums vs pieces: " + ", ".join(f"{k} {sa1_ex[k][YEARS[-1]].sum() - exposure(pop[YEARS[-1]], k).sum():+.1f}" for k in ids))


def main():
    lgas = {norm_lga(n) for n in STUDIES["metro"]["lgas"]}
    # ---------------- mesh blocks, councils, pieces
    mb = gpd.read_file(f"{RAW}/mb.geojson").to_crs(CRS)
    code = next(c for c in mb.columns if re.fullmatch(r"mb_code_2021|mb_code.*", c, re.I))
    sa1c = next(c for c in mb.columns if re.fullmatch(r"sa1_code_2021|sa1_code.*", c, re.I))
    mb["mb21"], mb["sa1"] = codes(mb[code]), codes(mb[sa1c])
    mb = mb[mb["sa1"].str.fullmatch(r"\d{11}")].reset_index(drop=True)
    mb["sa2"] = mb["sa1"].str[:9]
    c21 = table("data/raw/shared/mb_counts_2021.xlsx", "MB_CODE_2021", ["MB_CODE_2021", "PERSON"])
    c21["mb21"] = codes(c21["MB_CODE_2021"])
    c21 = c21[c21["mb21"].str.fullmatch(r"\d{11}")].drop_duplicates("mb21").set_index("mb21")
    mb["p21"] = pd.to_numeric(mb["mb21"].map(c21["PERSON"]), errors="coerce").fillna(0)
    lga = gpd.read_file(f"{RAW}/lga.geojson").to_crs(CRS)
    lga = lga[lga["lga_name_2021"].map(norm_lga).isin(lgas)]
    pt = mb.set_geometry(mb.geometry.representative_point())[["geometry"]]
    j = gpd.sjoin(pt, lga[["lga_code_2021", "geometry"]], predicate="within", how="inner")
    mb["lga"] = j[~j.index.duplicated()]["lga_code_2021"].astype(str).reindex(mb.index)
    sa2_p21 = mb.groupby("sa2")["p21"].sum()
    mb = mb.dropna(subset=["lga"]).reset_index(drop=True)
    mb["key"] = mb["sa2"] + "|" + mb["lga"]
    study = polys(lga.geometry)

    # ---------------- flood areas
    fl = gpd.read_file(f"{RAW}/flood.geojson").to_crs(CRS)
    ov = polys(polys(fl[fl.scheme_code.isin(["LSIO", "FO", "SBO"])].geometry).intersection(study))
    zones = {k: polys([ov] + [slr_layer(n) for n in names]) for k, _, _, names in SLR}
    print(f"flood areas (km2): " + ", ".join(f"{k} {z.area / 1e6:,.1f}" for k, z in zones.items()))

    # ---------------- address shares per mesh block: all addresses, and those created 2016-2025
    a = np.load(f"{RAW}/addr.npy")
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(a[:, 0], a[:, 1]), crs=4326).to_crs(CRS)
    pts = gpd.sjoin(pts, mb[["geometry"]], predicate="within", how="inner")
    pts = pts[~pts.index.duplicated()].rename(columns={"index_right": "m"})[["m", "geometry"]]
    n_all = pts.groupby("m").size().reindex(mb.index).fillna(0)
    an = np.load(f"{FC}/addresses_new.npy")
    day = an[:, 2].astype("int64").astype("datetime64[D]")
    sel = (day >= np.datetime64("2016-07-01")) & (day < np.datetime64(f"{BASE}-07-01"))
    npts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(an[sel, 0], an[sel, 1]), crs=4326).to_crs(CRS)
    npts = gpd.sjoin(npts, mb[["geometry"]], predicate="within", how="inner")
    npts = npts[~npts.index.duplicated()].rename(columns={"index_right": "m"})[["m", "geometry"]]
    recent = (day[sel] >= np.datetime64(f"{BASE - 5}-07-01"))[npts.index.values]
    mb["new"] = npts.groupby("m").size().reindex(mb.index).fillna(0).values
    mb["recent"] = npts[recent].groupby("m").size().reindex(mb.index).fillna(0).values
    for k, z in zones.items():
        pin = inside(pts, z)
        share = pd.Series(pin, index=pts.index).groupby(pts["m"]).mean().reindex(mb.index)
        no = share.index[share.isna()]                                       # no address: area share instead
        if len(no):                                                          # (spatial-indexed overlay, not one big intersection each)
            parts = gpd.GeoDataFrame(geometry=list(getattr(z, "geoms", [z])), crs=CRS)
            cut = gpd.overlay(mb.loc[no, ["geometry"]].reset_index(names="m"), parts, how="intersection", keep_geom_type=True)
            share.loc[no] = (cut.area.groupby(cut["m"]).sum().reindex(no).fillna(0) / mb.loc[no].area.where(mb.loc[no].area > 0, 1)).values
        mb[f"s_{k}"] = share.values
        mb[f"n_{k}"] = pd.Series(inside(npts, z), index=npts.index).groupby(npts["m"]).sum().reindex(mb.index).fillna(0).values
    print(f"addresses: {len(pts):,} in study mesh blocks; {int(mb['new'].sum()):,} created mid-2016 to mid-{BASE}, "
          f"{int(mb['recent'].sum()):,} in the last 5 years")

    # ---------------- pieces: ERP 2025, exposure shares, recent addresses
    g = mb.groupby("key")
    p = g.agg(sa2=("sa2", "first"), lga=("lga", "first"), p21=("p21", "sum"), new=("new", "sum"), recent=("recent", "sum")).reset_index()
    for k in zones:
        se = (mb["p21"] * mb[f"s_{k}"]).groupby(mb["key"]).sum() / g["p21"].sum().where(g["p21"].sum() > 0, np.nan)
        se = se.fillna(g[f"s_{k}"].mean())
        p[f"se_{k}"] = p["key"].map(se).values
        sn = g[f"n_{k}"].sum() / g["new"].sum().where(g["new"].sum() >= 20, np.nan)
        p[f"sn_{k}"] = p["key"].map(sn).fillna(p[f"se_{k}"]).values
    erp = read_erp(f"{FC}/erp_sa2.csv")
    e = erp[next(k for k in erp if re.fullmatch(r"SA2.*", k, re.I))]
    e = e[e["year"] == BASE].drop_duplicates("code").set_index("code")["erp"]
    p["w"] = p["p21"] / p["sa2"].map(sa2_p21).clip(lower=1)
    p["P"] = p["sa2"].map(e).fillna(0).values * p["w"].values
    miss = p["sa2"].map(e).isna()
    print(f"pieces: {len(p)} in {p['lga'].nunique()} councils; ERP {BASE} {p['P'].sum():,.0f}; "
          f"{int(miss.sum())} pieces without ERP ({p.loc[miss, 'p21'].sum():,.0f} 2021 residents)")

    # ---------------- council targets from VIF2023, rebased to ERP 2025
    vp, vd = vif("Total_Population"), vif("Total_Dwellings")
    act = p.groupby("lga")["P"].sum()
    tgt = {y: act + (vp.reindex(act.index)[y] - vp.reindex(act.index)[BASE]) for y in YEARS if y != BASE}
    need = {y: (vd.reindex(act.index)[y] - vd.reindex(act.index)[BASE]).clip(lower=0) for y in YEARS if y != BASE}

    # ---------------- UDP supply (optional)
    udp_path = f"{ST}/udp2025/udp2025_pieces.csv"
    use_udp = os.path.exists(udp_path)
    p["key2"] = p["sa2"] + "|" + p["lga"]
    if use_udp:
        u = pd.read_csv(udp_path, dtype={"sa2_code_2021": str, "lga_code": str})
        u["key2"] = u["sa2_code_2021"] + "|" + u["lga_code"]
        cols = [c for c in STATUS if c in u.columns]
        u = u.groupby("key2")[cols].sum()
        unmatched = u[~u.index.isin(p["key2"])][cols].sum().sum()
        p = p.join(u, on="key2").fillna({c: 0 for c in cols})
        print(f"UDP 2025: {u[cols].sum().sum():,.0f} dwellings/lots in {len(u)} pieces; {unmatched:,.0f} in pieces "
              f"not found here (dropped)")
    else:
        cols = []
        print("UDP 2025: not present, open-data method only")

    def allocate(y, udp=True):
        """Population of each piece in year y."""
        lg = p["lga"].values
        E = np.zeros(len(p))
        if udp and cols:
            for c in cols:
                pr, T = STATUS[c]
                E += p[c].values * ramp(y, pr, T)
        E_l = pd.Series(E).groupby(lg).transform("sum").values
        N_l = pd.Series(lg).map(need[y]).fillna(0).values
        scale = np.where(E_l > N_l, N_l / np.where(E_l > 0, E_l, 1), 1.0)
        E = E * scale
        R_l = np.clip(N_l - E_l, 0, None)                                    # infill not covered by UDP
        rc = p["recent"].values.astype(float)
        rc_l = pd.Series(rc).groupby(lg).transform("sum").values
        P = p["P"].values
        P_l = pd.Series(P).groupby(lg).transform("sum").values
        infill = np.where(rc_l > 0, R_l * rc / np.where(rc_l > 0, rc_l, 1), R_l * P / np.where(P_l > 0, P_l, 1))
        D = E + infill
        D_l = pd.Series(D).groupby(lg).transform("sum").values
        dL = pd.Series(lg).map(tgt[y] - act).fillna(0).values
        return P + np.where(D_l > 0, dL * D / np.where(D_l > 0, D_l, 1), dL * P / np.where(P_l > 0, P_l, 1))

    pop = {BASE: p["P"].values}
    pop_open = {BASE: p["P"].values}
    for y in YEARS[1:]:
        pop[y] = allocate(y, True); pop_open[y] = allocate(y, False)

    def exposure(P, k):
        P0 = p["P"].values; d = P - P0
        return P0 * p[f"se_{k}"].values + np.where(d > 0, d * p[f"sn_{k}"].values, d * p[f"se_{k}"].values)

    # ---------------- ranges
    ens = json.load(open("data/processed/forecast_ensemble.json")) if os.path.exists("data/processed/forecast_ensemble.json") else {}
    hu = {}
    for name, models in ens.get("tests", {}).items():
        h = int(re.search(r"h=(\d+)", name).group(1)); hu.setdefault(h, []).append(models["HU"]["p80_ape"])
    hs = sorted(hu); hv = [float(np.mean(hu[h])) for h in hs]
    sa2_rel = (lambda h: float(np.interp(h, [0] + hs, [0] + hv))) if hs else (lambda h: 0.03 * h)
    cls = ens.get("ens_error_by_class", {})
    ens14 = next((m["ENS"]["p80_ape"] for n, m in ens.get("tests", {}).items() if "h=14" in n), None)
    def class_factor(size, growth):
        if not cls or not ens14:
            return 1.0
        s = cls["size"].get("<5k" if size < 5000 else "5-10k" if size < 10000 else "10-15k" if size < 15000 else "15k+", {}).get("p80_ape", ens14)
        gr = cls["growth"].get("<10%" if growth < 1.1 else "10-30%" if growth < 1.3 else "30-60%" if growth < 1.6 else "60%+", {}).get("p80_ape", ens14)
        return float(np.sqrt(s * gr) / ens14)
    vif_err = ens.get("vif_check", {}).get("wape", 0.013)
    council_rel = lambda h: vif_err * h / 4

    # ---------------- outputs: SA2s, councils, total
    names = gpd.read_file(f"{ST}/sa2_council_pieces_7855.geojson")[["sa2_code_2021", "sa2_name_2021"]].drop_duplicates("sa2_code_2021")
    sa2_name = names.set_index("sa2_code_2021")["sa2_name_2021"]
    sid = p["sa2"].values
    def by(groups, P_dict):
        return {y: pd.Series(P_dict[y]).groupby(groups).sum() for y in YEARS}
    pop_sa2 = by(sid, pop)
    growth11 = (pop_sa2[2036] / pop_sa2[BASE].clip(lower=1))
    out = {"meta": {"sample": False, "years": YEARS, "base": BASE, "unit": "SA2",
                    "method": "udp" if use_udp else "open", "restricted": bool(use_udp),
                    "note": ("Housing-unit model with Urban Development Program 2025 supply (DEECA licence) and "
                             "VIF2023 council totals rebased to ERP 2025." if use_udp else
                             "Housing-unit model (recent address creation) with VIF2023 council totals rebased to ERP 2025."),
                    "status_assumptions": {k: {"share_built": v[0], "years": v[1]} for k, v in STATUS.items()} if use_udp else None},
           "slr": [{"id": k, "label": lab, "short": sh, "storm": k.startswith("st")} for k, lab, sh, _ in SLR], "total": {}, "areas": [], "councils": [], "population": {}}
    lo_hi = lambda v, r: [round(v), round(v * (1 - r)), round(v * (1 + r))]
    for k, _, _, _ in SLR:
        ex = {y: exposure(pop[y], k) for y in YEARS}
        tot = [lo_hi(ex[y].sum(), council_rel(y - BASE)) for y in YEARS]
        out["total"][k] = tot
        ex_sa2 = {y: pd.Series(ex[y]).groupby(sid).sum() for y in YEARS}
        ex_lga = {y: pd.Series(ex[y]).groupby(p["lga"].values).sum() for y in YEARS}
        for s in pop_sa2[BASE].index:
            rel = class_factor(pop_sa2[BASE][s], growth11[s])
            row = next((r for r in out["areas"] if r["code"] == s), None)
            if row is None:
                row = {"code": s, "name": sa2_name.get(s, s), "v": {}, "pop": [lo_hi(pop_sa2[y][s], sa2_rel(y - BASE) * class_factor(pop_sa2[BASE][s], growth11[s])) for y in YEARS]}
                out["areas"].append(row)
            row["v"][k] = [lo_hi(ex_sa2[y][s], sa2_rel(y - BASE) * rel) for y in YEARS]
        for c in ex_lga[BASE].index:
            row = next((r for r in out["councils"] if r["code"] == c), None)
            if row is None:
                row = {"code": c, "name": vp["name"].get(c, c), "v": {},
                       "pop": [lo_hi(pd.Series(pop[y]).groupby(p["lga"].values).sum()[c], council_rel(y - BASE)) for y in YEARS]}
                out["councils"].append(row)
            row["v"][k] = [lo_hi(ex_lga[y][c], council_rel(y - BASE)) for y in YEARS]
    for a_ in out["areas"]:
        a_["coastal"] = bool(a_["v"]["0.82"][-1][0] > a_["v"]["none"][-1][0] + 5)
    out["population"] = {"total": [lo_hi(pop[y].sum(), council_rel(y - BASE)) for y in YEARS],
                         "open_method_total": [round(pop_open[y].sum()) for y in YEARS]}
    out["backtest"] = json.load(open("web/scenarios_sample.json"))["backtest"]     # the real §25 table
    out["split_test"] = {str(h): round(v, 4) for h, v in zip(hs, hv)}              # HU p80 SA2 error by horizon
    os.makedirs("data/processed", exist_ok=True)
    # ---------------- map layers for the page: SA2 x council pieces, overlays, each scenario's coastal extent
    pcs = gpd.read_file(f"{ST}/sa2_council_pieces_7855.geojson")
    coast = {k: polys([slr_layer(n) for n in names]) for k, _, _, names in SLR}
    out["geo"] = {"sa2": to_geojson(list(pcs.geometry), [{"c": c, "l": str(l)} for c, l in zip(pcs["sa2_code_2021"], pcs["lga_code"])], tol=30),
                  "overlay": ov_layers(fl, study),
                  "coast": {k: to_geojson(list(getattr(z, "geoms", [z])), tol=40, min_m2=5000, grid=1e-4) for k, z in coast.items()}}   # the dataset is 1:75,000 (~75 m)
    finer(out, p, mb, pop, exposure, zones, sa2_rel)
    sz = {k: len(json.dumps(v, separators=(",", ":"))) // 1000 for k, v in out["geo"].items()}
    print(f"map layers (kB): {sz}")
    json.dump(out, open("data/processed/scenarios.json", "w"), separators=(",", ":"))

    # ---------------- report
    print(f"\nPopulation, 31 councils ({out['meta']['method']} method): " +
          ", ".join(f"{y} {pop[y].sum():,.0f}" for y in YEARS) + f"; open-data method 2036 {pop_open[2036].sum():,.0f}")
    print("Residents in flood areas (central, low-high):")
    for k, lab, _, _ in SLR:
        print(f"  {lab:44} " + "  ".join(f"{y}: {t[0]:,} ({t[1]:,}-{t[2]:,})" for y, t in zip(YEARS, out['total'][k])))
    d36 = sorted(out["areas"], key=lambda r: -(r["v"]["none"][-1][0] - r["v"]["none"][0][0]))[:10]
    print("SA2s adding the most residents in today's flood areas by 2036:")
    for r in d36:
        print(f"  {r['name']:32} {r['v']['none'][0][0]:>7,} -> {r['v']['none'][-1][0]:>7,} (range {r['v']['none'][-1][1]:,}-{r['v']['none'][-1][2]:,})")
    s82 = sorted(out["areas"], key=lambda r: -(r["v"]["0.82"][-1][0] - r["v"]["none"][-1][0]))[:8]
    print("SA2s where +0.82 m sea level adds the most residents (2036 population):")
    for r in s82:
        print(f"  {r['name']:32} +{r['v']['0.82'][-1][0] - r['v']['none'][-1][0]:,}")
    if use_udp:
        dd = pd.Series(pop[2036] - pop_open[2036]).groupby(sid).sum().abs().sum() / 2
        print(f"UDP moves {dd:,.0f} of 2036 residents between SA2s compared with the open-data method")


if __name__ == "__main__":
    main()
