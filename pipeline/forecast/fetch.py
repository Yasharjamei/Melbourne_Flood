"""Inputs for the population forecast (scenarios page, in development).

Kept apart from 01_fetch.py so the live site's build is unaffected. Everything is cached in
data/raw/forecast/; delete a file there to refetch it. Run from the repository root:

    python pipeline/forecast/fetch.py

  mb_counts_2016.csv     2016 Census Mesh Block Counts (ABS)            -> back-test baseline
  cg_mb2016_mb2021.csv   ABS correspondence, 2016 -> 2021 mesh blocks   -> back-test baseline
  erp_sa2.csv            ABS Estimated Resident Population by SA2,      -> history 2001-2025 for the
                         2001 onwards (2021 boundaries)                     ensemble back-test (ensemble.py)
  addresses_new.npy      Vicmap addresses created since 2006,            -> observed new homes
                         as lon, lat, days since 1970-01-01
"""
import importlib.util, io, json, os, re, sys, urllib.parse
from concurrent.futures import ThreadPoolExecutor
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("f01", os.path.join(HERE, "..", "01_fetch.py"))
f01 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(f01)   # reuse get/get_json/optional
OUT = "data/raw/forecast"
BUFFER_M = 1000                                     # around the 31 councils, so edge mesh blocks keep their addresses
CELL = 0.1                                          # degrees; only grid cells touching the study area are requested
CENSUS_2016 = "2016-08-09"
ADDR_FROM = "2006-01-01"                           # history for the ensemble back-test
STRICT = os.environ.get("STRICT_FETCH") == "1"

MB2016_URL = ("https://www.abs.gov.au/AUSSTATS/subscriber.nsf/log?openagent&2016%20census%20mesh%20block%20counts.csv"
              "&2074.0&Data%20Cubes&1DED88080198D6C6CA2581520083D113&0&2016&04.07.2017&Latest")
CG_URL = ("https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/"
          "edition-3-july-2021-june-2026/access-and-downloads/correspondences/CG_MB_2016_MB_2021.csv")
ERP_URL = "https://data.api.abs.gov.au/rest/data/ABS_ANNUAL_ERP_ASGS2021/all?startPeriod=2001&format=csvfilewithlabels"


def save(url, dst, check=None):
    """Download url to dst unless cached; check(bytes) can reject an HTML error page."""
    if os.path.exists(dst):
        print(f"  {os.path.basename(dst)}: cached"); return
    b = f01.get(url, binary=True)
    if check and not check(b):
        raise RuntimeError(f"{os.path.basename(dst)}: unexpected content from {url[:90]}: {b[:120]!r}")
    open(dst, "wb").write(b)
    print(f"  {os.path.basename(dst)}: {len(b) / 1e6:.1f} MB")


def study_area():
    """The 31 study councils dissolved and buffered in MGA2020 zone 55 (EPSG:7855), returned in
    lon/lat with the request cells that touch it. Uses the main build's council file, else fetches it."""
    import tempfile
    import geopandas as gpd
    from shapely.geometry import box
    from shapely.prepared import prep
    sys.path.insert(0, os.path.join(HERE, ".."))
    from config import STUDIES, norm_lga
    src = "data/raw/metro/lga.geojson"
    if not os.path.exists(src):
        src = os.path.join(tempfile.mkdtemp(), "lga.geojson")
        f01.arcgis("LGA", "state_code_2021='2'", None, 0.00001, src, page_max=10)
    lga = gpd.read_file(src)
    want = {norm_lga(n) for n in STUDIES["metro"]["lgas"]}
    lga = lga[lga["lga_name_2021"].map(norm_lga).isin(want)]
    if lga["lga_name_2021"].map(norm_lga).nunique() != len(want):
        raise RuntimeError(f"study area: found {lga['lga_name_2021'].nunique()} of {len(want)} councils")
    area = gpd.GeoSeries([lga.to_crs(7855).union_all().buffer(BUFFER_M)], crs=7855).to_crs(4326).iloc[0]
    x0, y0, x1, y1 = area.bounds
    pa = prep(area)
    cells = []
    for i in range(int((x1 - x0) / CELL) + 1):
        for j in range(int((y1 - y0) / CELL) + 1):
            c = (x0 + i * CELL, y0 + j * CELL, min(x0 + (i + 1) * CELL, x1), min(y0 + (j + 1) * CELL, y1))
            if pa.intersects(box(*c)):
                cells.append(c)
    print(f"  study area: 31 councils + {BUFFER_M} m in EPSG:7855, {gpd.GeoSeries([area], crs=4326).to_crs(7855).area.iloc[0] / 1e6:,.0f} km2; "
          f"{len(cells)} cells of {CELL} deg")
    return area, cells


def addresses_new(dst):
    """Every current Vicmap address in Greater Melbourne created on or after ADDR_FROM.
    Retired addresses are not in the layer, so past counts are slight undercounts."""
    if os.path.exists(dst):
        print("  addresses_new.npy: cached"); return
    from shapely import contains_xy
    area, cells = study_area()

    def cql(c):
        return (f"BBOX(geom,{c[1]},{c[0]},{c[3]},{c[2]},'urn:ogc:def:crs:EPSG::4326') "
                f"AND pfi_created >= '{ADDR_FROM}T00:00:00Z'")

    def cell(c):
        """Every page of one cell: (ufi, lon, lat, day) rows, and the server's own count."""
        base = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": "open-data-platform:address",
                "CQL_FILTER": cql(c)}
        hits = f01.get(f01.WFS + "?" + urllib.parse.urlencode({**base, "resultType": "hits"}))
        total = int(re.search(r'numberMatched="(\d+)"', hits).group(1))
        rows, start = [], 0
        while start < total:
            q = {**base, "outputFormat": "application/json", "srsName": "EPSG:4326",
                 "propertyName": "geom,pfi_created,ufi", "sortBy": "ufi", "count": 5000, "startIndex": start}
            feats = f01.get_json(f01.WFS, q).get("features", [])
            if not feats:
                break
            for f in feats:
                g, pr = (f.get("geometry") or {}).get("coordinates"), f.get("properties") or {}
                if not g or not pr.get("pfi_created"):
                    continue
                while isinstance(g[0], list):
                    g = g[0]
                rows.append((pr.get("ufi") or 0, g[0], g[1], np.datetime64(pr["pfi_created"][:10], "D").astype(int)))
            start += len(feats)
        if len(rows) < 0.98 * total:
            raise RuntimeError(f"cell {c}: got {len(rows):,} of {total:,}")
        return rows, total

    rows, matched = [], 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for k, (got, n) in enumerate(ex.map(cell, cells), 1):
            rows += got; matched += n
            if k % 20 == 0:
                print(f"  new addresses: {k} of {len(cells)} cells, {len(rows):,} so far")
    r = np.array(rows, dtype="float64")
    _, first = np.unique(r[:, 0], return_index=True)            # a point on a cell edge comes back twice
    r = r[np.sort(first)] if (r[:, 0] > 0).all() else r
    keep = contains_xy(area, r[:, 1], r[:, 2])
    print(f"  new addresses: {matched:,} matched in the cells, {len(r):,} unique, {int(keep.sum()):,} inside the study area kept")
    a = r[keep][:, 1:]
    np.save(dst, a)
    days = a[:, 2].astype("int64").astype("datetime64[D]")
    yrs = {str(y): int(n) for y, n in zip(*np.unique(days.astype("datetime64[Y]").astype(str), return_counts=True))}
    print(f"  addresses_new.npy: {len(a):,} addresses created since {ADDR_FROM}; by year {yrs}")


def aep_detailed(bbox, out):
    """The detailed 1% AEP flood layer of the Victorian Flood Database (from flood studies), not the
    statewide 1:250,000 compilation the main map uses. Layer found by name, as ids can change."""
    import re
    if os.path.exists(out):
        print("  cached"); return
    os.makedirs(os.path.dirname(out), exist_ok=True)
    # /layers gives geometry type and parent; "Flood - 1 in 100 years" can be a group layer
    info = f01.get_json(f01.VFD + "/layers", {"f": "json"})
    allL = info.get("layers", [])
    for l in allL:
        print(f"    VFD {l.get('id')}: {l.get('name')!r} {l.get('type')} {l.get('geometryType', '')} parent={(l.get('parentLayer') or {}).get('id')}")
    poly = [l for l in allL if l.get("geometryType") == "esriGeometryPolygon"]
    grp = [l for l in allL if re.fullmatch(r"flood\s*-\s*1 in 100 years?", l["name"].strip(), re.I)]
    kids = {k["id"] for g in grp for k in (g.get("subLayers") or [])}
    lay = [l for l in poly if (l["id"] in kids or l in grp or re.search(r"1 in 100|1%|100 ?y", l["name"], re.I))
           and not re.search(r"250 ?k", l["name"], re.I)]
    if not lay:
        raise RuntimeError("no detailed 1-in-100-year polygon layer besides the 1:250,000 one (layer list above)")
    url = f"{f01.VFD}/{lay[0]['id']}"
    feats, off = [], 0
    while True:
        js = f01.get_json(url + "/query", {"where": "1=1", "outFields": "", "returnGeometry": "true", "f": "geojson", "outSR": 4326,
                                           "geometry": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}", "geometryType": "esriGeometryEnvelope",
                                           "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "resultOffset": off, "resultRecordCount": 1000})
        got = js.get("features", [])
        feats += got; off += len(got)
        if len(got) < 1000:
            break
    json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": f["geometry"]}
                                                          for f in feats if f.get("geometry")]}, open(out, "w"))
    print(f"  layer {lay[0]['id']} '{lay[0]['name']}': {len(feats):,} polygons -> {out}")


def main_inputs():
    """Only the main build's inputs the forecast reads (councils, mesh blocks, mesh-block counts, flood
    overlays, address points, SA1s and suburbs for the scenarios map), each skipped if present. A full 01_fetch.py takes ~70 min; these are a part."""
    sys.path.insert(0, os.path.join(HERE, ".."))
    from config import STUDIES, norm_lga
    st, raw = STUDIES["metro"], "data/raw/metro"
    os.makedirs(raw, exist_ok=True); os.makedirs("data/raw/shared", exist_ok=True)
    wanted = {norm_lga(n) for n in st["lgas"]}
    print("Councils"); f01.arcgis("LGA", "state_code_2021='2'", None, 0.00001, f"{raw}/lga.geojson", page_max=10)
    bbox = f01.lga_bbox(f"{raw}/lga.geojson", wanted)
    print("Mesh blocks"); f01.arcgis("MB", "state_code_2021='2'", bbox, 0.00006, f"{raw}/mb.geojson")
    print("SA1s"); f01.arcgis("SA1", "state_code_2021='2'", bbox, 0.00006, f"{raw}/sa1.geojson")
    print("Suburbs"); f01.arcgis("SAL", "state_code_2021='2'", bbox, 0.00012, f"{raw}/sal.geojson")
    print("Flood overlays"); f01.wfs_overlays(bbox, st["lgas"], f"{raw}/flood.geojson")
    print("Address points"); f01.wfs_points(bbox, f"{raw}/addr.npy")
    # better flood data: the modelled 1% AEP extent (Victorian Flood Database) and the observed October 2022 extent
    print("1% AEP flood extent (modelled)")
    try:
        f01.aep1(bbox)
    except Exception as e:
        print(f"  WARNING 1% AEP extent unavailable: {str(e)[:200]}")
    print("1% AEP flood extent, detailed (Victorian Flood Database layer 'Flood - 1 in 100 years'; forecast only)")
    try:
        aep_detailed(bbox, "data/raw/forecast/aep100.geojson")
    except Exception as e:
        print(f"  WARNING detailed 1% AEP extent unavailable: {str(e)[:200]}")
    print("October 2022 flood extent (observed; Victorian Flood History, CC BY 4.0)")
    if os.path.exists(f"{raw}/flood_oct2022.geojson"):
        print("  cached")
    else:
        try:
            f01.wfs_polygons("open-data-platform:vic_flood_history_public", bbox, f"{raw}/flood_oct2022.geojson", "October 2022 flood extent")
        except Exception as e:
            print(f"  WARNING October 2022 extent unavailable: {str(e)[:200]}")
    dst = "data/raw/shared/mb_counts_2021.xlsx"
    print("Mesh-block counts")
    if os.path.exists(dst):
        print("  cached"); return
    for u in f01.MB_COUNT_URLS:
        try:
            b = f01.get(u, binary=True, tries=2)
            if b[:2] == b"PK":
                open(dst, "wb").write(b); print(f"  -> {dst}"); return
        except Exception as e:
            print(f"  {u[:60]}...: {e}")
    raise SystemExit("mesh-block counts unavailable")


def main():
    if "--main" in sys.argv:
        return main_inputs()
    os.makedirs(OUT, exist_ok=True)
    csv_like = lambda b: not b.lstrip()[:15].lower().startswith((b"<!doctype", b"<html"))
    steps = [("2016 mesh-block counts", lambda: save(MB2016_URL, f"{OUT}/mb_counts_2016.csv", csv_like)),
             ("2016 -> 2021 mesh-block correspondence", lambda: save(CG_URL, f"{OUT}/cg_mb2016_mb2021.csv", csv_like)),
             ("ERP by SA2", lambda: save(ERP_URL, f"{OUT}/erp_sa2.csv", csv_like)),
             ("addresses created since 2006", lambda: addresses_new(f"{OUT}/addresses_new.npy"))]
    failed = []
    for label, fn in steps:
        print(label)
        try:
            fn()
        except Exception as e:
            print(f"  WARNING {label} unavailable: {e}"); failed.append(label)
    if failed and STRICT:
        sys.exit(f"forecast inputs missing: {failed}")


if __name__ == "__main__":
    main()
