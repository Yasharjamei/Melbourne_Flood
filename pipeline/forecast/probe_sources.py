"""Probe open sources for two more accuracy checks, and print what they hold (nothing is kept):
  - Urban Development Program 2017 and 2018 (Major Residential Redevelopment Sites, Broadhectare
    Residential Land; DataVic, CC BY): for a back-test of the UDP step from 2017 to 2021 and 2025;
  - City of Melbourne population forecasts by small area (CLUE areas; DataVic, CC BY) and the CLUE
    small-area boundaries: to compare the forecast with the council's own.
    python pipeline/forecast/probe_sources.py
"""
import glob, io, json, os, tempfile, urllib.parse, urllib.request, zipfile

CKAN = "https://discover.data.vic.gov.au/api/3/action/"
UA = {"User-Agent": "Mozilla/5.0 (melbourne-flood pipeline)"}
IDS = ["victorian-flood-history-october-2022-event-public", "victoria-1-in-100-year-flood-extent",
       "major-residential-redevelopments-sites-2017", "major-residential-redevelopments-sites-2018",
       "broadhectare-residential-land-2017", "broadhectare-residential-land-2018",
       "city-of-melbourne-population-forecasts-by-small-area-2021-2041"]
SEARCH = ["flood history October 2022", "Victorian Flood Database", "flood extent 1% AEP", "flood depth"]


def get(url, timeout=300):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def api(action, **q):
    return json.loads(get(CKAN + action + "?" + urllib.parse.urlencode(q)))["result"]


def peek(url, fmt):
    import geopandas as gpd, pandas as pd
    b = get(url, timeout=600)
    print(f"      downloaded {len(b) / 1e6:.1f} MB")
    tmp = tempfile.mkdtemp()
    if b[:2] == b"PK":
        zipfile.ZipFile(io.BytesIO(b)).extractall(tmp)
        files = glob.glob(f"{tmp}/**/*", recursive=True)
        print("      zip: " + ", ".join(sorted({os.path.relpath(f, tmp) for f in files})[:12]))
        cands = [f for f in files if f.lower().endswith((".shp", ".gdb", ".geojson", ".csv", ".tab"))]
    else:
        p = os.path.join(tmp, "f." + (fmt or "csv").lower()); open(p, "wb").write(b); cands = [p]
    for c in cands[:3]:
        try:
            if c.lower().endswith(".csv"):
                d = pd.read_csv(c, nrows=2000)
            else:
                import pyogrio
                layers = pyogrio.list_layers(c) if c.lower().endswith(".gdb") else [[None]]
                for L in layers[:4]:
                    d = gpd.read_file(c, layer=L[0]) if L[0] else gpd.read_file(c)
                    print(f"      {os.path.basename(c)} {L[0] or ''}: {len(d):,} rows; crs {getattr(d, 'crs', None)}; columns {list(d.columns)[:30]}")
                    print("      " + d.drop(columns="geometry", errors="ignore").head(3).to_string(max_colwidth=30).replace("\n", "\n      "))
                    for col in d.columns:
                        if d[col].dtype == object and 1 < d[col].nunique() <= 12:
                            print(f"      values of {col}: {d[col].value_counts().to_dict()}")
                continue
            print(f"      {os.path.basename(c)}: {len(d):,} rows; columns {list(d.columns)[:30]}")
            print("      " + d.head(5).to_string(max_colwidth=30).replace("\n", "\n      "))
            for col in d.columns:
                if d[col].dtype == object and 1 < d[col].nunique() <= 15:
                    print(f"      values of {col}: {d[col].value_counts().to_dict()}")
        except Exception as e:
            print(f"      could not read {os.path.basename(c)}: {e}")


def main():
    for i in IDS:
        print(f"\n== {i}")
        try:
            pk = api("package_show", id=i)
        except Exception as e:
            print(f"   not found: {e}"); continue
        print(f"   {pk.get('title')} | licence {pk.get('license_title')} | modified {pk.get('metadata_modified', '')[:10]}")
        res = pk.get("resources", [])
        for r in res:
            print(f"   - {r.get('name')} [{r.get('format')}] {r.get('url')}")
        pref = ["CSV", "SHP", "ZIP", "GEOJSON", "FGDB", "GDB", "MIF", "TAB"]
        res = sorted(res, key=lambda r: pref.index(r.get("format", "").upper()) if r.get("format", "").upper() in pref else 99)
        for r in res[:1]:
            print(f"   reading {r.get('name')} [{r.get('format')}]")
            try:
                peek(r["url"], r.get("format"))
            except Exception as e:
                print(f"      failed: {e}")
    for q in SEARCH:
        print(f"\n== search: {q}")
        try:
            for pk in api("package_search", q=q, rows=8)["results"]:
                print(f"   {pk['name']} | {pk.get('title')} | {pk.get('license_title')} | " + ", ".join(f"{r.get('format')}" for r in pk.get("resources", [])))
        except Exception as e:
            print(f"   failed: {e}")


if __name__ == "__main__":
    main()
