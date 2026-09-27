"""Download every public input for one study area into data/raw/.

    python pipeline/01_fetch.py                  # all 31 Greater Melbourne councils (the only study)

Required inputs stop the run on failure. Optional ones (mesh-block counts, address
points, DEMs, soil sand, SEIFA, tree canopy, building footprints) log a warning and 02_build.py falls back, saying so in its output.

Every download is cached under data/raw/: delete a file to fetch it again.
"""
import argparse, io, json, math, os, re, sys, time, urllib.parse, urllib.request, zipfile
sys.path.insert(0, os.path.dirname(__file__))
from config import STUDIES, norm_lga
import numpy as np

UA = {"User-Agent": "Mozilla/5.0 (melbourne-flood pipeline)"}
ABS_GEO = "https://geo.abs.gov.au/arcgis/rest/services/ASGS2021"
GCP_URL = "https://www.abs.gov.au/census/find-census-data/datapacks/download/2021_GCP_SA1_for_VIC_short-header.zip"
GCP_TABLES = ["G01", "G02", "G04A", "G04B", "G13E", "G17A", "G17B", "G17C", "G18",
              "G20A", "G20B", "G34", "G36", "G43", "G46B"]
MB_COUNT_URLS = [
    "https://www.abs.gov.au/census/guide-census-data/mesh-block-counts/2021/Mesh%20Block%20Counts%2C%202021.xlsx",
    "https://www.abs.gov.au/census/guide-census-data/mesh-block-counts/latest-release/Mesh%20Block%20Counts%2C%202021.xlsx",
]
WFS = "https://opendata.maps.vic.gov.au/geoserver/wfs"
WFS_LAYER = "open-data-platform:plan_overlay"
DEM_TILE = ("https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/"
            "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif")
SAND_WCS = "https://maps.isric.org/mapserv?map=/map/sand.map"
SEIFA_URLS = [
    "https://www.abs.gov.au/statistics/people/people-and-communities/socio-economic-indexes-areas-seifa-australia/2021/"
    "Statistical%20Area%20Level%201%2C%20Indexes%2C%20SEIFA%202021.xlsx",
]
# Vicmap Elevation 10 m DEM as an image service (real elevation values, unlike the shaded-relief tiles).
DEM10 = "https://tiles-ap1.arcgis.com/P744lA0wf4LlBZ84/arcgis/rest/services/Vicmap_10m_DEM/ImageServer"
# Vicmap Vegetation tree extent, 20 cm canopy / no-canopy rasters (2020), one zip for Greater Melbourne.
# Greater Melbourne spans four of the statewide 1:250k packages; tiles outside the study bbox are skipped.
CANOPY_ZIPS = [f"https://cl-isd-prd-datashare-s3-delivery.s3.amazonaws.com/PrePackages/VMVEG_TREE_EXTENT/"
               f"VMVEG_TREE_EXTENT_{n}.zip" for n in ("MELBOURNE", "WARBURTON", "PORT_PHILLIP", "WARRAGUL")]
# Vicmap Property road casement (road reserves), a DataVic order for the Melbourne Water region.
# Order links are temporary; when this one is gone the WFS layer is used instead.
ROAD_ORDER_URLS = ["https://s3.ap-southeast-2.amazonaws.com/cl-isd-prd-datashare-s3-delivery/Order_5YFHYM.zip"]
# Microsoft Global ML Building Footprints: manifest of per-country, per-quadkey files.
MS_BUILDINGS = "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv"


def get(url, params=None, tries=4, binary=False, headers=None):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout=300) as r:
                data = r.read()
            return data if binary else data.decode("utf-8")
        except Exception as e:
            if i == tries - 1:
                raise RuntimeError(f"GET failed after {tries} tries: {url[:200]}\n  {e}")
            time.sleep(2 ** (i + 1))


def get_json(url, params=None):
    try:
        js = json.loads(get(url, params))
    except json.JSONDecodeError as e:    # truncated response from an overloaded server
        raise RuntimeError(f"Invalid JSON from {url[:120]}: {e}")
    if isinstance(js, dict) and "error" in js:
        raise RuntimeError(f"Server error from {url}: {js['error']}")
    return js


def service_url(name):
    """ABS names some services e.g. 'SA1' or 'ASGS2021_SA1'; find the one that exists."""
    svc = get_json(ABS_GEO, {"f": "json"}).get("services", [])
    names = [s["name"].split("/")[-1] for s in svc]
    for cand in (name, f"ASGS2021_{name}", f"{name}_2021"):
        if cand in names:
            return f"{ABS_GEO}/{cand}/MapServer/0"
    raise RuntimeError(f"No ABS service for {name}. Available: {sorted(names)}")


def arcgis(name, where, bbox, offset_deg, out, page_max=2000):
    """Page through an ArcGIS layer, writing a GeoJSON FeatureCollection."""
    if os.path.exists(out):
        feats = json.load(open(out))["features"]; print(f"  {name}: cached ({len(feats)})"); return feats
    layer = service_url(name)
    info = get_json(layer, {"f": "json"})
    oid = info.get("objectIdField") or "objectid"
    page = min(int(info.get("maxRecordCount") or 1000), page_max)
    print(f"  {name}: {layer.split('services/')[-1]} fields="
          f"{[f['name'] for f in info.get('fields', [])][:25]} page={page}")
    # Keyset paging (objectid > last) rather than resultOffset: deep offsets make the ABS
    # server time out (a 504 at offset 62,000 on Greater Melbourne mesh blocks).
    feats, last, size = [], -1, page
    while True:
        p = {"where": f"({where}) AND {oid} > {last}", "outFields": "*", "outSR": 4326, "f": "geojson",
             "orderByFields": f"{oid} ASC", "resultRecordCount": size,
             "geometryPrecision": 6, "returnGeometry": "true"}
        if offset_deg:
            p["maxAllowableOffset"] = offset_deg
        if bbox:
            p.update(geometry=",".join(map(str, bbox)), geometryType="esriGeometryEnvelope",
                     inSR=4326, spatialRel="esriSpatialRelIntersects")
        try:
            js = get_json(layer + "/query", p)
        except RuntimeError:
            if size <= min(250, page_max // 4 or 1):
                raise
            size //= 2
            print(f"  {name}: request failed, retrying with pages of {size}")
            continue
        got = js.get("features", [])
        if not got:
            break
        feats += got
        ids = [f.get("properties", {}).get(oid, f.get("id")) for f in got]
        last = max(i for i in ids if i is not None)
        if len(got) < size and not js.get("exceededTransferLimit"):
            break
    if not feats:
        raise RuntimeError(f"{name}: query returned no features")
    json.dump({"type": "FeatureCollection", "features": feats}, open(out, "w"))
    print(f"  {name}: {len(feats)} features -> {out}")
    return feats


def lga_bbox(lgas_path, wanted):
    fc = json.load(open(lgas_path))
    xs, ys = [], []
    for f in fc["features"]:
        if norm_lga(f["properties"].get("lga_name_2021", "")) in wanted:
            def walk(c):
                if isinstance(c[0], (int, float)):
                    xs.append(c[0]); ys.append(c[1])
                else:
                    for k in c: walk(k)
            walk(f["geometry"]["coordinates"])
    return [min(xs), min(ys), max(xs), max(ys)]


def wfs_overlays(bbox, lgas, out):
    """LSIO/FO/SBO polygons. Filter by council name (what the v0.1 script used);
    fall back to a bounding box in both axis orders if that returns nothing."""
    if os.path.exists(out):
        print("  overlays: cached"); return
    names = sorted({("MERRI-BEK" if n.lower() in ("moreland", "merri-bek") else n.upper()) for n in lgas}
                   | ({"MORELAND"} if any(n.lower() == "moreland" for n in lgas) else set()))
    scheme = "scheme_code IN ('LSIO','FO','SBO')"
    filters = [f"{scheme} AND lga IN ({','.join(repr(n) for n in names)})"]
    desc = get(WFS, {"service": "WFS", "version": "2.0.0", "request": "DescribeFeatureType", "typeNames": WFS_LAYER})
    geom = next((t.split('name="')[1].split('"')[0] for t in desc.split("<")
                 if 'type="gml:' in t and 'name="' in t), "geom")
    filters += [f"{scheme} AND BBOX({geom},{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},'EPSG:4326')",
                f"{scheme} AND BBOX({geom},{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]},'EPSG:4326')"]
    for cql in filters:
        feats, start, n = [], 0, 5000
        while True:
            js = get_json(WFS, {"service": "WFS", "version": "2.0.0", "request": "GetFeature",
                                "typeNames": WFS_LAYER, "outputFormat": "application/json",
                                "srsName": "EPSG:4326", "CQL_FILTER": cql, "count": n, "startIndex": start})
            got = js.get("features", [])
            feats += got; start += len(got)
            if len(got) < n:
                break
        print(f"  overlays: {len(feats)} features for filter {cql[:90]}...")
        if feats:
            by = {}
            for f in feats:
                k = f["properties"].get("lga", "?"); by[k] = by.get(k, 0) + 1
            print(f"  overlays per council: {dict(sorted(by.items()))}")
            json.dump({"type": "FeatureCollection", "features": feats}, open(out, "w"))
            return
    raise RuntimeError("Flood overlay queries returned no features")


def wfs_layer(pattern, prefer):
    """Find a layer on the Vicmap GeoServer by name. Layer names change between
    GeoServer releases, so search GetCapabilities instead of hard-coding one."""
    caps = get(WFS, {"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"})
    names = re.findall(r"<(?:wfs:)?Name>([^<]+)</(?:wfs:)?Name>", caps)
    hits = [n for n in names if re.search(pattern, n, re.I)]
    print(f"  layers matching /{pattern}/: {hits[:12]}")
    for p in prefer:
        for n in hits:
            if re.search(p, n, re.I):
                return n
    if not hits:
        raise RuntimeError(f"no WFS layer matches {pattern}")
    return hits[0]


def wfs_points(bbox, out, pattern=r"address", prefer=(r"address_point$", r"addr.*point", r"address")):
    """Vicmap Address points (one per property or unit) inside the study bbox, saved as a
    compact float32 lon/lat array. Only the geometry is requested, which keeps the metro
    download (about 2 million points) to a few hundred MB, cached after the first run."""
    if os.path.exists(out):
        print("  address points: cached"); return
    import numpy as np
    layer = wfs_layer(pattern, prefer)
    desc = get(WFS, {"service": "WFS", "version": "2.0.0", "request": "DescribeFeatureType", "typeNames": layer})
    geom = next((t.split('name="')[1].split('"')[0] for t in desc.split("<")
                 if 'type="gml:' in t and 'name="' in t), "geom")
    # The WFS 2.0 URN form of EPSG:4326 is lat/lon; the short form is lon/lat on GeoServer.
    boxes = [f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]},urn:ogc:def:crs:EPSG::4326",
             f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:4326"]
    # The server caps every response (5,000 features at the time of writing) whatever `count`
    # asks for, so fetch every page (in parallel once the total is known), sort on a key for
    # stable paging, and check the number received against the server's own numberMatched.
    fields = re.findall(r'name="([^"]+)"', desc)
    key = next((f for f in ("ufi", "pfi", "objectid", "id") if f in fields), None)
    def page(start):
        q = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": layer,
             "outputFormat": "application/json", "srsName": "EPSG:4326", "propertyName": geom,
             "bbox": boxes[0], "count": 50000, "startIndex": start}
        if key:
            q["sortBy"] = key
        return get_json(WFS, q)

    def coords(feats):
        out = []
        for f in feats:
            c = (f.get("geometry") or {}).get("coordinates")
            if c:
                while isinstance(c[0], list):   # MultiPoint -> first point
                    c = c[0]
                out.append(c[:2])
        return out

    js = page(0)
    if not js.get("features") and len(boxes) > 1:
        print("  address points: none with lat/lon bbox, retrying lon/lat"); boxes.pop(0); js = page(0)
    first = js.get("features", [])
    total = js.get("numberMatched", js.get("totalFeatures"))
    total = total if isinstance(total, int) else None
    step = len(first)
    print(f"  address points: {total if total is not None else 'unknown'} matched; "
          f"{step} per page, sorted by {key or '(server order)'}")
    pts = coords(first)
    if total is not None and step:
        # Each page takes ~10 s on the server, and metro needs ~500 of them: fetch 8 at a time.
        from concurrent.futures import ThreadPoolExecutor
        starts = list(range(step, total, step))
        with ThreadPoolExecutor(max_workers=8) as ex:
            for k, got in enumerate(ex.map(lambda s: page(s).get("features", []), starts), 1):
                pts += coords(got)
                if k % 50 == 0:
                    print(f"  address points: {len(pts):,} of {total:,}")
    else:                                     # no total reported: page one at a time until empty
        start = step
        while step:
            got = page(start).get("features", [])
            if not got:
                break
            pts += coords(got); start += len(got)
    if total is not None and len(pts) < 0.99 * total:
        raise RuntimeError(f"incomplete download: {len(pts):,} of {total:,} address points")
    if not pts:
        raise RuntimeError(f"{layer} returned no points in {bbox}")
    a = np.asarray(pts, dtype=np.float32)
    lon_ok = (a[:, 0] >= bbox[0] - 1) & (a[:, 0] <= bbox[2] + 1)
    if lon_ok.mean() < 0.5:                      # server answered in lat/lon order
        a = a[:, ::-1].copy()
    np.save(out, a)
    print(f"  address points: {len(a):,} from {layer} -> {out}")


class HttpRange(io.RawIOBase):
    """A seekable file over HTTP range requests, so zipfile can list and extract single members
    of a remote archive without downloading all of it (the canopy zip is 2 GB)."""
    def __init__(self, url):
        r = urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers=UA), timeout=60)
        self.url, self.n, self.p = url, int(r.headers["Content-Length"]), 0
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.p
    def seek(self, o, w=0):
        self.p = o if w == 0 else self.p + o if w == 1 else self.n + o
        return self.p
    def readinto(self, b):
        if self.p >= self.n:
            return 0
        end = min(self.n, self.p + len(b)) - 1
        d = get(self.url, binary=True, tries=4, headers={"Range": f"bytes={self.p}-{end}"})
        b[:len(d)] = d; self.p += len(d)
        return len(d)


def canopy(bbox, outdir="data/raw/shared/canopy10"):
    """Tree canopy share on a 10 m grid, from the 20 cm Vicmap tree-extent tiles that overlap bbox
    (listing every package is cheap: only zip directories are read until a tile is needed).
    Each 20 cm tile (about 110,000 x 70,000 pixels, 0 = no tree, 1 = tree, 2 = no data) is read
    straight out of the remote zip and averaged 50 x 50 into a 10 m percentage grid."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import transform_bounds
    os.makedirs(outdir, exist_ok=True)
    tifs = []
    for url in CANOPY_ZIPS:
        z = zipfile.ZipFile(io.BufferedReader(HttpRange(url), 1 << 20))
        tifs += [(url, m) for m in z.namelist() if m.lower().endswith(".tif")]
    env = rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".zip,.tif",
                       GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="2")
    used = 0
    with env:
        for url, m in tifs:
            dst = os.path.join(outdir, os.path.basename(m).replace("_20cm_", "_10m_"))
            src = f"/vsizip//vsicurl/{url}/{m}"
            with rasterio.open(src) as r:
                w, s_, e, n = transform_bounds(r.crs, 4326, *r.bounds)
                if e < bbox[0] or w > bbox[2] or n < bbox[1] or s_ > bbox[3]:
                    continue
                used += 1
                if os.path.exists(dst):
                    continue
                f = 50
                a = r.read(1, out_shape=(r.height // f, r.width // f), resampling=Resampling.average, masked=True)
                pct = np.where(np.ma.getmaskarray(a), 255, np.round(a.filled(0) * 100)).astype("uint8")
                t = r.transform * r.transform.scale(r.width / pct.shape[1], r.height / pct.shape[0])
                prof = dict(driver="GTiff", width=pct.shape[1], height=pct.shape[0], count=1, dtype="uint8",
                            crs=r.crs, transform=t, nodata=255, compress="deflate")
                with rasterio.open(dst, "w", **prof) as o:
                    o.write(pct, 1)
                print(f"  canopy: {os.path.basename(m)} -> {dst} ({pct.shape[1]}x{pct.shape[0]})")
    if not used:
        raise RuntimeError("no canopy tile overlaps the study area")
    print(f"  canopy: {used} tiles cover the study area")


def buildings(bbox, out):
    """Microsoft Global ML Building Footprints inside bbox, reduced to one row per building:
    lon, lat (centroid), footprint area in m2, height in m (-1 if unknown)."""
    if os.path.exists(out):
        print("  buildings: cached"); return
    import csv, gzip, shapely
    def quadkey(lon, lat, z=9):
        x = int((lon + 180) / 360 * 2 ** z)
        s = math.sin(math.radians(lat)); y = int((0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * 2 ** z)
        return "".join(str(((x >> i) & 1) + 2 * ((y >> i) & 1)) for i in range(z - 1, -1, -1))
    step = 0.05
    keys = {quadkey(bbox[0] + i * step, bbox[1] + j * step)
            for i in range(int((bbox[2] - bbox[0]) / step) + 2) for j in range(int((bbox[3] - bbox[1]) / step) + 2)}
    rows = [r for r in csv.DictReader(io.StringIO(get(MS_BUILDINGS)))
            if r["Location"] == "Australia" and r["QuadKey"].zfill(9) in keys]
    if not rows:
        raise RuntimeError(f"no Australia building tiles for quadkeys {sorted(keys)[:5]}...")
    print(f"  buildings: {len(rows)} tiles, uploaded {sorted({r.get('UploadDate', '?') for r in rows})}")
    parts = []
    for r in rows:
        lines = gzip.decompress(get(r["Url"], binary=True)).decode("utf-8").splitlines()
        feats = [json.loads(l) for l in lines if l.strip()]
        g = shapely.from_geojson([json.dumps(f["geometry"]) for f in feats])
        c = shapely.centroid(g); x, y = shapely.get_x(c), shapely.get_y(c)
        k = (x >= bbox[0]) & (x <= bbox[2]) & (y >= bbox[1]) & (y <= bbox[3])
        area = shapely.area(g) * (111320.0 ** 2) * np.cos(np.radians(y))     # degrees^2 -> m^2
        h = np.array([float((f.get("properties") or {}).get("height") or -1) for f in feats])
        parts.append(np.column_stack([x, y, area, h])[k])
        print(f"  buildings: tile {r['QuadKey']}: {len(feats):,} footprints, {int(k.sum()):,} in the study bbox")
    a = np.vstack(parts).astype(np.float32)
    np.save(out, a); print(f"  buildings: {len(a):,} -> {out}")


def roads(bbox, outdir="data/raw/shared/roads"):
    """Vicmap Property road casement polygons (the whole road reserve, kerb to kerb and verge).
    First the DataVic order zip (a shapefile in MGA 2020 zone 55); if that link has expired,
    the same layer from the Vicmap WFS, paged in parallel, saved as GeoJSON."""
    if glob_any(outdir, (".shp", ".geojson")):
        print("  road casement: cached"); return
    os.makedirs(outdir, exist_ok=True)
    for u in ROAD_ORDER_URLS:
        try:
            z = zipfile.ZipFile(io.BufferedReader(HttpRange(u), 1 << 20))
            parts = [m for m in z.namelist() if "ROAD_CASEMENT_POLYGON." in m.upper()]
            if not any(m.lower().endswith(".shp") for m in parts):
                raise RuntimeError("no ROAD_CASEMENT_POLYGON.shp in the order")
            for m in parts:
                open(os.path.join(outdir, os.path.basename(m)), "wb").write(z.read(m))
            print(f"  road casement: {len(parts)} shapefile parts from the DataVic order"); return
        except Exception as e:
            print(f"  road casement: order link unusable ({str(e)[:120]}); trying WFS")
    layer = wfs_layer(r"casement", (r"road_casement_polygon$", r"road_casement", r"casement"))
    desc = get(WFS, {"service": "WFS", "version": "2.0.0", "request": "DescribeFeatureType", "typeNames": layer})
    geom = next((t.split('name="')[1].split('"')[0] for t in desc.split("<")
                 if 'type="gml:' in t and 'name="' in t), "geom")
    q = lambda start: {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": layer,
                       "outputFormat": "application/json", "srsName": "EPSG:4326", "propertyName": geom,
                       "bbox": f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]},urn:ogc:def:crs:EPSG::4326",
                       "count": 50000, "startIndex": start}
    js = get_json(WFS, q(0)); first = js.get("features", [])
    total = js.get("numberMatched"); step = len(first)
    feats = list(first)
    if isinstance(total, int) and step:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as ex:
            for got in ex.map(lambda st: get_json(WFS, q(st)).get("features", []), range(step, total, step)):
                feats += got
    if not feats:
        raise RuntimeError(f"{layer} returned no features")
    json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": f["geometry"]}
                                                          for f in feats if f.get("geometry")]},
              open(os.path.join(outdir, "road_casement.geojson"), "w"))
    print(f"  road casement: {len(feats):,} polygons from {layer}")


def subcatchments(bbox, out="data/raw/shared/subcatchments.geojson"):
    """Melbourne Water 'Catchments - Waterways and Drains Subcatchments': the catchment of every
    Melbourne Water drain and waterway. Found through the ArcGIS Online catalogue (the hub's own
    export links are signed and expire within the hour), then paged from its FeatureServer."""
    if os.path.exists(out) or os.path.exists("data/static/waterways_drains_catchments.gdb.zip"):
        print("  subcatchments: cached or stored in data/static"); return
    hits = get_json("https://www.arcgis.com/sharing/rest/search",
                    {"q": 'title:"Waterways and Drains Subcatchments" AND type:"Feature Service"', "num": 20, "f": "json"})
    items = [r for r in hits.get("results", []) if r.get("url") and "subcatchment" in r.get("title", "").lower()]
    items.sort(key=lambda r: (("melbourne" not in (r.get("owner", "") + r.get("title", "")).lower()), -r.get("numViews", 0)))
    if not items:
        raise RuntimeError("no 'Waterways and Drains Subcatchments' feature service found")
    svc = items[0]["url"].rstrip("/")
    meta = get_json(svc, {"f": "json"})
    lyr = svc if "/FeatureServer/" in svc else f"{svc}/{(meta.get('layers') or [{'id': 0}])[0]['id']}"
    print(f"  subcatchments: {items[0].get('title')} (owner {items[0].get('owner')}) -> {lyr}")
    feats, off = [], 0
    while True:
        js = get_json(lyr + "/query", {"where": "1=1", "outFields": "*", "returnGeometry": "true", "f": "geojson",
                                        "outSR": 4326, "geometry": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
                                        "geometryType": "esriGeometryEnvelope", "inSR": 4326,
                                        "spatialRel": "esriSpatialRelIntersects", "resultOffset": off, "resultRecordCount": 1000})
        got = js.get("features", [])
        feats += got; off += len(got)
        if not got or not (js.get("exceededTransferLimit") or (js.get("properties") or {}).get("exceededTransferLimit")):
            if len(got) < 1000:
                break
    json.dump({"type": "FeatureCollection", "features": feats}, open(out, "w"))
    print(f"  subcatchments: {len(feats):,} polygons -> {out}")


def glob_any(d, exts):
    return os.path.isdir(d) and any(f.lower().endswith(exts) for f in os.listdir(d))


def dem10(bbox, raw):
    """Vicmap Elevation 10 m DEM from its image service. exportImage is tried first; hosted tiled
    image services often refuse it, so the fallback reads the service's own LERC elevation tiles
    (float values, not a picture) at the level closest to 10 m and mosaics them into one GeoTIFF."""
    if glob_any(raw, ("dem10.tif",)) or os.path.exists(f"{raw}/dem10_000.tif"):
        print("  Vicmap 10 m DEM: cached"); return
    info = get_json(DEM10, {"f": "json"})
    print(f"  DEM service: capabilities={info.get('capabilities')}, format={(info.get('tileInfo') or {}).get('format')}, "
          f"pixelType={info.get('pixelType')}, allowExport={info.get('exportTilesAllowed')}")
    try:
        b = get(DEM10 + "/exportImage", {"bbox": f"{bbox[0]},{bbox[1]},{min(bbox[2], bbox[0] + 0.05)},{min(bbox[3], bbox[1] + 0.05)}",
                                         "bboxSR": 4326, "imageSR": 4326, "size": "500,500", "format": "tiff",
                                         "pixelType": "F32", "f": "image"}, binary=True, tries=1)
        if b[:2] not in (b"II", b"MM"):
            raise RuntimeError(b[:200].decode("latin1"))
        dem10_export(bbox, raw, info)
    except Exception as e:
        print(f"  DEM exportImage refused ({str(e)[:160]}); trying LERC tiles")
        dem10_tiles(bbox, raw, info)


def dem10_export(bbox, raw, info):
    mw, mh = int(info.get("maxImageWidth", 4000)), int(info.get("maxImageHeight", 4000))
    res = 0.0001                                # ~9-11 m at Melbourne's latitude
    cw, ch = min(mw, 4000) * res, min(mh, 4000) * res
    k, x = 0, bbox[0]
    while x < bbox[2]:
        y = bbox[1]
        while y < bbox[3]:
            dst = f"{raw}/dem10_{k:03d}.tif"; k += 1
            x2, y2 = min(x + cw, bbox[2] + res), min(y + ch, bbox[3] + res)
            b = get(DEM10 + "/exportImage", {"bbox": f"{x},{y},{x2},{y2}", "bboxSR": 4326, "imageSR": 4326,
                                             "size": f"{round((x2 - x) / res)},{round((y2 - y) / res)}",
                                             "format": "tiff", "pixelType": "F32", "f": "image"}, binary=True, tries=3)
            open(dst, "wb").write(b)
            y = y2
        x = x2
    print(f"  Vicmap 10 m DEM: {k} exported chunks in {raw}/dem10_*.tif")


def dem10_tiles(bbox, raw, info):
    import lerc, rasterio
    from rasterio.transform import from_origin
    from concurrent.futures import ThreadPoolExecutor
    ti = info.get("tileInfo") or {}
    if str(ti.get("format", "")).upper() != "LERC":
        raise RuntimeError(f"tiles are {ti.get('format')}, not LERC elevation")
    wkid = (ti.get("spatialReference") or {}).get("latestWkid") or (ti.get("spatialReference") or {}).get("wkid")
    if wkid not in (3857, 102100):
        raise RuntimeError(f"tile grid in wkid {wkid}, expected Web Mercator")
    ox, oy, tw, th = ti["origin"]["x"], ti["origin"]["y"], ti["cols"], ti["rows"]
    lat = (bbox[1] + bbox[3]) / 2
    want = 10 / math.cos(math.radians(lat))    # Web Mercator units per 10 ground metres here
    lod = min(ti["lods"], key=lambda l: abs(l["resolution"] - want))
    r = lod["resolution"]
    X = lambda lon: lon * 20037508.342789244 / 180
    Y = lambda la: math.log(math.tan((90 + la) * math.pi / 360)) * 6378137.0
    c0, c1 = int((X(bbox[0]) - ox) / (r * tw)), int((X(bbox[2]) - ox) / (r * tw))
    r0, r1 = int((oy - Y(bbox[3])) / (r * th)), int((oy - Y(bbox[1])) / (r * th))
    print(f"  DEM tiles: level {lod['level']} ({r:.1f} m Web Mercator, ~{r * math.cos(math.radians(lat)):.1f} m ground), "
          f"{(c1 - c0 + 1) * (r1 - r0 + 1)} tiles")
    out = np.full(((r1 - r0 + 1) * th, (c1 - c0 + 1) * tw), np.nan, dtype="float32")
    def one(rc):
        row, col = rc
        try:
            b = get(f"{DEM10}/tile/{lod['level']}/{row}/{col}", binary=True, tries=3)
        except Exception:
            return rc, None                   # tiles over the sea may not exist
        res = lerc.decode(b)
        data, mask = res[1], res[2] if len(res) > 2 else None
        a = np.asarray(data, dtype="float32").reshape(th, tw)
        if mask is not None:
            a = np.where(np.asarray(mask).reshape(th, tw) > 0, a, np.nan)
        return rc, a
    cells = [(row, col) for row in range(r0, r1 + 1) for col in range(c0, c1 + 1)]
    got = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for (row, col), a in ex.map(one, cells):
            if a is not None:
                out[(row - r0) * th:(row - r0 + 1) * th, (col - c0) * tw:(col - c0 + 1) * tw] = a; got += 1
    if not got:
        raise RuntimeError("no DEM tile could be read")
    tr = from_origin(ox + c0 * tw * r, oy - r0 * th * r, r, r)
    with rasterio.open(f"{raw}/dem10.tif", "w", driver="GTiff", width=out.shape[1], height=out.shape[0], count=1,
                       dtype="float32", crs="EPSG:3857", transform=tr, nodata=np.nan, compress="deflate",
                       predictor=3, tiled=True) as o:
        o.write(out, 1)
    print(f"  Vicmap 10 m DEM: {got} of {len(cells)} LERC tiles -> {raw}/dem10.tif "
          f"(elevation {np.nanmin(out):.0f} to {np.nanmax(out):.0f} m)")


def optional(label, fn):
    try:
        fn()
    except Exception as e:
        print(f"  WARNING optional input '{label}' unavailable: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", default="metro", choices=STUDIES)
    a = ap.parse_args()
    st = STUDIES[a.study]
    wanted = {norm_lga(n) for n in st["lgas"]}
    raw = f"data/raw/{a.study}"
    os.makedirs(raw, exist_ok=True)
    os.makedirs("data/raw/gcp", exist_ok=True)
    os.makedirs("data/raw/shared", exist_ok=True)
    fine = 0.00002 if len(st["lgas"]) <= 3 else 0.00006   # ~2 m for a few councils, ~6 m for the metro

    print("LGAs")
    # Council boundaries decide which SA1s are in the study area: near-full detail (1 m),
    # a few at a time (one 82-council response at full detail came back truncated).
    lgas = arcgis("LGA", "state_code_2021='2'", None, 0.00001, f"{raw}/lga.geojson", page_max=10)
    found = {norm_lga(f["properties"].get("lga_name_2021", "")) for f in lgas}
    missing = wanted - found
    if missing:
        raise RuntimeError(f"LGAs not found: {sorted(missing)}. Available: {sorted(found)}")
    bbox = lga_bbox(f"{raw}/lga.geojson", wanted)
    print(f"  study bbox {bbox}")

    where = "state_code_2021='2'"
    print("SA1s");        arcgis("SA1", where, bbox, fine, f"{raw}/sa1.geojson")
    print("Mesh blocks"); arcgis("MB", where, bbox, fine, f"{raw}/mb.geojson")
    print("Suburbs");     arcgis("SAL", where, bbox, fine * 2, f"{raw}/sal.geojson")
    print("Flood overlays"); wfs_overlays(bbox, st["lgas"], f"{raw}/flood.geojson")

    print("Address points, Vicmap Address (optional)")
    optional("address points", lambda: wfs_points(bbox, f"{raw}/addr.npy"))

    if not all(os.path.exists(f"data/raw/gcp/2021Census_{t}_VIC_SA1.csv") for t in GCP_TABLES):
        print("Census DataPack (~100 MB)")
        z = zipfile.ZipFile(io.BytesIO(get(GCP_URL, binary=True)))
        for t in GCP_TABLES:
            m = [n for n in z.namelist() if n.endswith(f"2021Census_{t}_VIC_SA1.csv")]
            if not m:
                raise RuntimeError(f"Table {t} not in DataPack")
            open(f"data/raw/gcp/2021Census_{t}_VIC_SA1.csv", "wb").write(z.read(m[0]))
        print(f"  {len(GCP_TABLES)} tables -> data/raw/gcp/")

    def mb_counts():
        dst = "data/raw/shared/mb_counts_2021.xlsx"
        if os.path.exists(dst):
            return
        err = None
        for u in MB_COUNT_URLS:
            try:
                b = get(u, binary=True, tries=2)
                if b[:2] != b"PK":
                    raise RuntimeError("not an xlsx")
                open(dst, "wb").write(b); print(f"  mesh-block counts -> {dst}"); return
            except Exception as e:
                err = e
        raise RuntimeError(err)
    print("Mesh-block counts (optional)"); optional("mesh-block counts", mb_counts)

    def dem():
        for lat in range(math.floor(bbox[1]), math.floor(bbox[3]) + 1):
            for lon in range(math.floor(bbox[0]), math.floor(bbox[2]) + 1):
                ns, la = ("S", -lat) if lat < 0 else ("N", lat)
                u = DEM_TILE.format(ns=ns, lat=la, ew="E", lon=lon)
                dst = f"data/raw/shared/dem_{ns}{la}_E{lon}.tif"
                if not os.path.exists(dst):
                    open(dst, "wb").write(get(u, binary=True, tries=3)); print(f"  DEM tile -> {dst}")
    print("Elevation, Copernicus GLO-30 (optional)"); optional("DEM", dem)

    def sand():
        dst = f"{raw}/sand.tif"
        if os.path.exists(dst):
            return
        q = (f"&SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage&COVERAGEID=sand_0-5cm_mean&FORMAT=image/tiff"
             f"&SUBSET=long({bbox[0] - .01},{bbox[2] + .01})&SUBSET=lat({bbox[1] - .01},{bbox[3] + .01})"
             f"&SUBSETTINGCRS=http://www.opengis.net/def/crs/EPSG/0/4326"
             f"&OUTPUTCRS=http://www.opengis.net/def/crs/EPSG/0/4326")
        b = get(SAND_WCS + q, binary=True, tries=3)
        if b[:2] not in (b"II", b"MM"):
            raise RuntimeError("response is not a GeoTIFF: " + b[:200].decode("latin1"))
        open(dst, "wb").write(b); print(f"  sand -> {dst}")
    print("Soil sand %, SoilGrids (optional)"); optional("sand", sand)

    def seifa():
        dst = "data/raw/shared/seifa_sa1_2021.xlsx"
        if os.path.exists(dst):
            return
        for u in SEIFA_URLS:
            b = get(u, binary=True, tries=3)
            if b[:2] == b"PK":
                open(dst, "wb").write(b); print(f"  SEIFA -> {dst}"); return
        raise RuntimeError("SEIFA download is not an xlsx")
    print("SEIFA 2021 by SA1 (optional)"); optional("SEIFA", seifa)
    print("Vicmap Elevation 10 m DEM (optional; Copernicus 30 m is the fallback)"); optional("DEM 10 m", lambda: dem10(bbox, raw))
    print("Tree canopy, Vicmap tree extent 2020 (optional)"); optional("canopy", lambda: canopy(bbox))
    print("Road casement, Vicmap Property (optional)"); optional("road casement", lambda: roads(bbox))
    print("Waterway and drain subcatchments, Melbourne Water (optional)"); optional("subcatchments", lambda: subcatchments(bbox))
    print("Building footprints, Microsoft (optional)"); optional("buildings", lambda: buildings(bbox, f"{raw}/buildings.npy"))
    print("done")


if __name__ == "__main__":
    main()
