"""Feasibility probe for the population-forecast and remote-sensing work (scenarios page).

Checks, from a machine with open internet, what each candidate source actually offers:
format, years, coverage and useful fields. Prints a report and writes probe_report.md.
Changes nothing; run it from Actions -> "Probe data sources" -> Run workflow.
"""
import json, os, re, ssl, sys, urllib.parse, urllib.request

BBOX = (144.33, -38.50, 145.88, -37.40)          # Greater Melbourne, lon/lat
UA = {"User-Agent": "Mozilla/5.0 (Melbourne_Flood feasibility probe)"}
out = []


def say(s=""):
    print(s); out.append(s)


def get(url, n=None, timeout=60, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(n) if n else r.read()


def jget(url, **kw):
    return json.loads(get(url, **kw))


def section(title, fn):
    say(f"\n## {title}")
    try:
        fn()
    except Exception as e:
        say(f"- **FAILED:** {type(e).__name__}: {str(e)[:300]}")


def ckan(query, rows=8):
    """DataVic's catalogue (CKAN API): datasets matching query, with each resource's format and URL."""
    q = urllib.parse.urlencode({"q": query, "rows": rows})
    js = jget(f"https://discover.data.vic.gov.au/api/3/action/package_search?{q}")
    say(f"- {js['result']['count']} datasets match `{query}`")
    for p in js["result"]["results"]:
        say(f"  - **{p['title']}** (licence: {p.get('license_title')}, modified {str(p.get('metadata_modified'))[:10]})")
        for r in p.get("resources", [])[:8]:
            say(f"    - {r.get('format') or '?'}: {r.get('name') or ''} <{r.get('url')}>")


def vif():
    ckan("VIF2023 SA2")
    ckan("VIF2023 small area")


def udp():
    ckan("urban development program")


def coastal():
    ckan("Victorian Coastal Inundation")
    caps = get("https://opendata.maps.vic.gov.au/geoserver/wfs?service=WFS&version=2.0.0&request=GetCapabilities", timeout=120).decode("utf-8", "ignore")
    names = sorted(set(re.findall(r"<Name>([^<]*(?:inund|slr|sea_?level|storm|coast)[^<]*)</Name>", caps, re.I)))
    say(f"- Vicmap WFS layers matching inundation/SLR/coast: {len(names)}")
    for n in names[:40]:
        say(f"  - `{n}`")


def abs_api():
    xml = get("https://api.data.abs.gov.au/dataflow/ABS", timeout=120, headers={"Accept": "application/xml"}).decode("utf-8", "ignore")
    flows = re.findall(r'<structure:Dataflow[^>]*id="([^"]+)"[^>]*>.*?<common:Name[^>]*>([^<]+)</common:Name>', xml, re.S)
    hits = [(i, n) for i, n in flows if re.search(r"ERP|resident population|building approv|BA_", i + " " + n, re.I)]
    say(f"- ABS Data API dataflows: {len(flows)} total; {len(hits)} about ERP or building approvals:")
    for i, n in hits[:30]:
        say(f"  - `{i}`: {n}")


def abs_mb2016():
    """2016 Mesh Block counts are needed for the 2016 -> 2021 back-test."""
    for url in ["https://www.abs.gov.au/AUSSTATS/subscriber.nsf/log?openagent&2016%20census%20mesh%20block%20counts.xlsx&2074.0&Data%20Cubes&1DED88080198D6C6CA2581520083D113&0&2016&04.07.2017&Latest",
                "https://www.abs.gov.au/ausstats/abs@.nsf/mf/2074.0"]:
        try:
            b = get(url, n=400, timeout=60); say(f"- reachable: <{url[:110]}> ({b[:60]!r})")
        except Exception as e:
            say(f"- not reachable: <{url[:110]}>: {e}")


def sentinel2():
    """Free Sentinel-2 L2A (10 m) scenes over Melbourne, via the Earth Search STAC API on AWS."""
    for yr in (2016, 2019, 2021, 2025):
        body = json.dumps({"collections": ["sentinel-2-l2a"], "bbox": list(BBOX),
                           "datetime": f"{yr}-01-01T00:00:00Z/{yr}-03-31T23:59:59Z",
                           "query": {"eo:cloud_cover": {"lt": 10}}, "limit": 100}).encode()
        req = urllib.request.Request("https://earth-search.aws.element84.com/v1/search", data=body,
                                     headers={**UA, "Content-Type": "application/geo+json"})
        js = json.loads(urllib.request.urlopen(req, timeout=120).read())
        tiles = sorted({f["properties"].get("s2:mgrs_tile") or f["id"].split("_")[1] for f in js["features"]})
        say(f"- Jan–Mar {yr}: {len(js['features'])} scenes under 10% cloud; MGRS tiles {tiles}")


def ghsl():
    """JRC Global Human Settlement Layer: built-up surface/volume and population, 1975-2030 (incl. projections)."""
    base = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
    html = get(base, timeout=60).decode("utf-8", "ignore")
    dirs = sorted(set(re.findall(r'href="(GHS_[A-Z_]+_GLOBE_R20\d\d[AB]?)/?"', html)))
    say(f"- GHSL product folders: {dirs}")
    for d in [x for x in dirs if re.search(r"BUILT_S|BUILT_V|POP", x)][:4]:
        sub = get(base + d + "/", timeout=60).decode("utf-8", "ignore")
        subs = sorted(set(re.findall(r'href="([^"/]+)/"', sub)))[:12]
        say(f"  - {d}: {subs}")


def worldpop():
    js = jget("https://hub.worldpop.org/rest/data/pop/wpgp?iso3=AUS", timeout=60)
    yrs = sorted({d.get("popyear") for d in js.get("data", [])})
    say(f"- WorldPop 100 m population, Australia: years {yrs}")


def worldcover():
    for y, v in (("2020", "v100"), ("2021", "v200")):
        url = f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/{v}/{y}/map/ESA_WorldCover_10m_{y}_{v}_S39E144_Map.tif"
        req = urllib.request.Request(url, method="HEAD", headers=UA)
        r = urllib.request.urlopen(req, timeout=60)
        say(f"- ESA WorldCover {y} tile S39E144: HTTP {r.status}, {int(r.headers.get('Content-Length', 0)) / 1e6:.0f} MB")


def ms_buildings():
    """Do Microsoft footprints carry capture dates or heights? (needed to date new buildings)."""
    import csv, gzip, io
    rows = list(csv.DictReader(io.StringIO(get("https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv", timeout=120).decode())))
    au = [r for r in rows if r["Location"] == "Australia"]
    url = au[len(au) // 2]["Url"]
    feat = json.loads(gzip.decompress(get(url, timeout=120)).splitlines()[0])
    say(f"- {len(au)} Australian tiles; sample properties: `{json.dumps(feat.get('properties'))[:300]}`")


def vicmap_address():
    """Does Vicmap Address record when an address was created? (observed new dwellings since 2021)."""
    d = get("https://opendata.maps.vic.gov.au/geoserver/wfs?service=WFS&version=2.0.0&request=DescribeFeatureType&typeNames=open-data-platform:address", timeout=120).decode("utf-8", "ignore")
    fields = re.findall(r'name="([^"]+)"\s+[^>]*type="([^"]+)"', d)
    dated = [f for f in fields if re.search(r"date|time|creat|modif|retire", f[0], re.I)]
    say(f"- {len(fields)} fields; date-like: {dated}")


# ---- round 2: fixes for round 1's probe errors, plus the questions round 1 raised

def ckan_titles(query, rows=25, must=None):
    q = urllib.parse.urlencode({"q": query, "rows": rows})
    js = jget(f"https://discover.data.vic.gov.au/api/3/action/package_search?{q}")
    hits = [p for p in js["result"]["results"] if not must or re.search(must, p["title"], re.I)]
    say(f"- `{query}`: {len(hits)} relevant of {js['result']['count']}")
    for p in hits[:15]:
        res = "; ".join(f"{r.get('format')} <{r.get('url')}>" for r in p.get("resources", [])[:3])
        say(f"  - **{p['title']}** ({p.get('license_title')}): {res}")


def vif2():
    ckan_titles("Victoria in Future 2023", must=r"VIF|Victoria in Future")
    ckan_titles("VIF2023", must=r"SA2|SA3|small|statistical", rows=60)


def udp2():
    for q in ("Urban Development Program major redevelopment", "Urban Development Program broadhectare",
              "Urban Development Program residential"):
        ckan_titles(q, must=r"redevelop|broadhectare|residential|minor infill")


def abs2():
    xml = get("https://data.api.abs.gov.au/rest/dataflow/ABS?detail=allstubs", timeout=120,
              headers={"Accept": "application/xml"}).decode("utf-8", "ignore")
    flows = re.findall(r'id="([^"]+)"[^>]*>\s*<common:Name[^>]*>([^<]+)<', xml)
    hits = [(i, n) for i, n in flows if re.search(r"ERP|resident population|building approv", i + " " + n, re.I)]
    say(f"- {len(flows)} dataflows; {len(hits)} on ERP / building approvals:")
    for i, n in hits[:30]:
        say(f"  - `{i}`: {n}")


def mb2016():
    for page in ("https://www.abs.gov.au/AUSSTATS/abs@.nsf/DetailsPage/2074.02016?OpenDocument",
                 "https://www.abs.gov.au/ausstats/abs@.nsf/mf/2074.0"):
        try:
            html = get(page, timeout=60).decode("utf-8", "ignore")
            links = sorted(set(re.findall(r'href="([^"]*(?:mesh%20block|Mesh%20Block|mesh_block|MB)[^"]*\.(?:csv|xlsx|xls|zip)[^"]*)"', html, re.I)))
            say(f"- {page}: {len(links)} file links")
            for l in links[:10]:
                say(f"  - <{l.replace('&amp;', '&')}>")
        except Exception as e:
            say(f"- {page}: {e}")


def s2():
    for yr in (2016, 2019, 2021, 2025):
        q = urllib.parse.urlencode({"collections": "sentinel-2-l2a", "bbox": ",".join(map(str, BBOX)),
                                    "datetime": f"{yr}-01-01T00:00:00Z/{yr}-03-31T23:59:59Z", "limit": 200})
        js = jget(f"https://earth-search.aws.element84.com/v1/search?{q}", timeout=120)
        f = js["features"]
        clear = [x for x in f if (x["properties"].get("eo:cloud_cover") or 100) < 10]
        tiles = sorted({x["properties"].get("grid:code") or x["properties"].get("s2:mgrs_tile") or x["id"] for x in clear})
        say(f"- Jan–Mar {yr}: {len(f)} scenes over Melbourne, {len(clear)} under 10% cloud; tiles {tiles[:12]}")


def ghsl2():
    base = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
    for d in ("GHS_BUILT_S_GLOBE_R2023A", "GHS_BUILT_V_GLOBE_R2023A", "GHS_POP_GLOBE_R2023A"):
        sub = get(base + d + "/", timeout=60).decode("utf-8", "ignore")
        ep = sorted(set(re.findall(r"_E(\d{4})_GLOBE_R2023A_54009_100", sub)))
        say(f"- {d}: epochs at 100 m: {ep}")


def address_dates():
    """How many Melbourne addresses were created each year? Spikes = database events, not homes."""
    wfs = "https://opendata.maps.vic.gov.au/geoserver/wfs"
    for yr in range(2012, 2027):
        cql = (f"BBOX(geom,{BBOX[1]},{BBOX[0]},{BBOX[3]},{BBOX[2]},'urn:ogc:def:crs:EPSG::4326') AND "
               f"pfi_created >= '{yr}-01-01T00:00:00Z' AND pfi_created < '{yr + 1}-01-01T00:00:00Z'")
        q = urllib.parse.urlencode({"service": "WFS", "version": "2.0.0", "request": "GetFeature",
                                    "typeNames": "open-data-platform:address", "resultType": "hits", "CQL_FILTER": cql})
        try:
            m = re.search(r'numberMatched="(\d+)"', get(f"{wfs}?{q}", timeout=180).decode("utf-8", "ignore"))
            say(f"- addresses with pfi_created in {yr}: {int(m.group(1)):,}" if m else f"- {yr}: no count")
        except Exception as e:
            say(f"- {yr}: {str(e)[:150]}")


say("# Feasibility probe, round 2")
for title, fn in [("VIF2023 small-area files", vif2), ("UDP residential (redevelopment, broadhectare)", udp2),
                  ("ABS Data API (correct host)", abs2), ("ABS 2016 Mesh Block counts: file links", mb2016),
                  ("Sentinel-2 over Melbourne (GET search)", s2), ("GHSL epochs incl. projections", ghsl2),
                  ("Vicmap Address: addresses created per year, Greater Melbourne", address_dates)]:
    section(title, fn)
open("probe_report.md", "w").write("\n".join(out) + "\n")
if os.environ.get("GITHUB_STEP_SUMMARY"):
    open(os.environ["GITHUB_STEP_SUMMARY"], "a").write("\n".join(out) + "\n")
