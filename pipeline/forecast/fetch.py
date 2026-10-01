"""Inputs for the population forecast (scenarios page, in development).

Kept apart from 01_fetch.py so the live site's build is unaffected. Everything is cached in
data/raw/forecast/; delete a file there to refetch it. Run from the repository root:

    python pipeline/forecast/fetch.py

  mb_counts_2016.csv     2016 Census Mesh Block Counts (ABS)            -> back-test baseline
  cg_mb2016_mb2021.csv   ABS correspondence, 2016 -> 2021 mesh blocks   -> back-test baseline
  erp_sa2.csv            ABS Estimated Resident Population by SA2       -> actual 2021-2025 totals
  addresses_new.npy      Vicmap addresses created since Census 2016,     -> observed new homes
                         as lon, lat, days since 1970-01-01
"""
import importlib.util, io, json, os, re, sys, urllib.parse
from concurrent.futures import ThreadPoolExecutor
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("f01", os.path.join(HERE, "..", "01_fetch.py"))
f01 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(f01)   # reuse get/get_json/optional
OUT = "data/raw/forecast"
BBOX = (144.33, -38.50, 145.88, -37.40)            # Greater Melbourne, lon/lat (as the address fetch)
CENSUS_2016 = "2016-08-09"
STRICT = os.environ.get("STRICT_FETCH") == "1"

MB2016_URL = ("https://www.abs.gov.au/AUSSTATS/subscriber.nsf/log?openagent&2016%20census%20mesh%20block%20counts.csv"
              "&2074.0&Data%20Cubes&1DED88080198D6C6CA2581520083D113&0&2016&04.07.2017&Latest")
CG_URL = ("https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/"
          "edition-3-july-2021-june-2026/access-and-downloads/correspondences/CG_MB_2016_MB_2021.csv")
ERP_URL = "https://data.api.abs.gov.au/rest/data/ABS_ANNUAL_ERP_ASGS2021/all?startPeriod=2016&format=csvfilewithlabels"


def save(url, dst, check=None):
    """Download url to dst unless cached; check(bytes) can reject an HTML error page."""
    if os.path.exists(dst):
        print(f"  {os.path.basename(dst)}: cached"); return
    b = f01.get(url, binary=True)
    if check and not check(b):
        raise RuntimeError(f"{os.path.basename(dst)}: unexpected content from {url[:90]}: {b[:120]!r}")
    open(dst, "wb").write(b)
    print(f"  {os.path.basename(dst)}: {len(b) / 1e6:.1f} MB")


def addresses_new(dst):
    """Every current Vicmap address in Greater Melbourne created on or after Census night 2016.
    Retired addresses are not in the layer, so the 2016-2021 count is a slight undercount."""
    if os.path.exists(dst):
        print("  addresses_new.npy: cached"); return
    cql = (f"BBOX(geom,{BBOX[1]},{BBOX[0]},{BBOX[3]},{BBOX[2]},'urn:ogc:def:crs:EPSG::4326') "
           f"AND pfi_created >= '{CENSUS_2016}T00:00:00Z'")
    base = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": "open-data-platform:address",
            "CQL_FILTER": cql}
    hits = f01.get(f01.WFS + "?" + urllib.parse.urlencode({**base, "resultType": "hits"}))
    total = int(re.search(r'numberMatched="(\d+)"', hits).group(1))

    def page(start):
        q = {**base, "outputFormat": "application/json", "srsName": "EPSG:4326", "propertyName": "geom,pfi_created",
             "sortBy": "ufi", "count": 5000, "startIndex": start}
        rows = []
        for f in f01.get_json(f01.WFS, q).get("features", []):
            c = (f.get("geometry") or {}).get("coordinates"); d = (f.get("properties") or {}).get("pfi_created")
            if not c or not d:
                continue
            while isinstance(c[0], list):
                c = c[0]
            rows.append((c[0], c[1], np.datetime64(d[:10], "D").astype(int)))
        return rows

    first = page(0); step = len(first) or 5000
    rows = list(first)
    with ThreadPoolExecutor(max_workers=8) as ex:
        for k, got in enumerate(ex.map(page, range(step, total, step)), 1):
            rows += got
            if k % 40 == 0:
                print(f"  new addresses: {len(rows):,} of {total:,}")
    if len(rows) < 0.98 * total:
        raise RuntimeError(f"new addresses: got {len(rows):,} of {total:,}")
    a = np.array(rows, dtype="float64")
    np.save(dst, a)
    days = a[:, 2].astype("int64").astype("datetime64[D]")
    yrs = {str(y): int(n) for y, n in zip(*np.unique(days.astype("datetime64[Y]").astype(str), return_counts=True))}
    print(f"  addresses_new.npy: {len(a):,} addresses created since {CENSUS_2016}; by year {yrs}")


def main():
    os.makedirs(OUT, exist_ok=True)
    csv_like = lambda b: not b.lstrip()[:15].lower().startswith((b"<!doctype", b"<html"))
    steps = [("2016 mesh-block counts", lambda: save(MB2016_URL, f"{OUT}/mb_counts_2016.csv", csv_like)),
             ("2016 -> 2021 mesh-block correspondence", lambda: save(CG_URL, f"{OUT}/cg_mb2016_mb2021.csv", csv_like)),
             ("ERP by SA2", lambda: save(ERP_URL, f"{OUT}/erp_sa2.csv", csv_like)),
             ("addresses created since 2016", lambda: addresses_new(f"{OUT}/addresses_new.npy"))]
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
