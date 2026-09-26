"""Download every public input for one study area into data/raw/.

    python pipeline/01_fetch.py --study west     # Maribyrnong + Moonee Valley
    python pipeline/01_fetch.py --study metro    # all 31 Greater Melbourne councils

Required inputs stop the run on failure. Optional ones (mesh-block counts, address
points, DEM, soil sand) log a warning and 02_build.py falls back, saying so in its output.

Every download is cached under data/raw/: delete a file to fetch it again.
"""
import argparse, io, json, math, os, re, sys, time, urllib.parse, urllib.request, zipfile
sys.path.insert(0, os.path.dirname(__file__))
from config import STUDIES, norm_lga

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


def get(url, params=None, tries=4, binary=False):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
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
    # asks for, so page until an empty response, sort on a key for stable paging, and check the
    # total against the server's own numberMatched.
    fields = re.findall(r'name="([^"]+)"', desc)
    key = next((f for f in ("ufi", "pfi", "objectid", "id") if f in fields), None)
    pts, start, total = [], 0, None
    while True:
        q = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": layer,
             "outputFormat": "application/json", "srsName": "EPSG:4326", "propertyName": geom,
             "bbox": boxes[0], "count": 50000, "startIndex": start}
        if key:
            q["sortBy"] = key
        js = get_json(WFS, q)
        got = js.get("features", [])
        if not got and start == 0 and len(boxes) > 1:
            print("  address points: none with lat/lon bbox, retrying lon/lat"); boxes.pop(0); continue
        if total is None:
            total = js.get("numberMatched", js.get("totalFeatures"))
            total = total if isinstance(total, int) else None
            print(f"  address points: {total if total is not None else 'unknown'} matched; "
                  f"{len(got)} per page, sorted by {key or '(server order)'}")
        if not got:
            break
        for f in got:
            c = (f.get("geometry") or {}).get("coordinates")
            if c:
                while isinstance(c[0], list):   # MultiPoint -> first point
                    c = c[0]
                pts.append(c[:2])
        start += len(got)
        if total is not None and start >= total:
            break
        if start % 250000 < len(got):
            print(f"  address points: {start:,} so far")
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


def optional(label, fn):
    try:
        fn()
    except Exception as e:
        print(f"  WARNING optional input '{label}' unavailable: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", default="west", choices=STUDIES)
    a = ap.parse_args()
    st = STUDIES[a.study]
    wanted = {norm_lga(n) for n in st["lgas"]}
    raw = f"data/raw/{a.study}"
    os.makedirs(raw, exist_ok=True)
    os.makedirs("data/raw/gcp", exist_ok=True)
    os.makedirs("data/raw/shared", exist_ok=True)
    fine = 0.00002 if a.study == "west" else 0.00006

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
    print("done")


if __name__ == "__main__":
    main()
