"""Can river-gauge flows for the October 2022 Melbourne floods be downloaded automatically?
Manual probe (gauges.yml); changes nothing. Tries the Bureau of Meteorology's Water Data Online
(KiWIS web service) and Victoria's Water Measurement Information System, and reports what comes back:
which stations measure discharge around Melbourne, and whether daily values exist for October 2022.
"""
import json, urllib.parse, urllib.request

BBOX = (144.33, -38.50, 146.20, -37.40)       # Greater Melbourne, lon/lat
UA = {"User-Agent": "Mozilla/5.0 (Melbourne_Flood research probe)"}


def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read()


def show(label, url, data=None):
    try:
        st, b = get(url, data)
        print(f"{label}: HTTP {st}, {len(b):,} bytes: {b[:300]!r}")
        return b
    except Exception as e:
        print(f"{label}: FAILED {e}")
        return None


def kiwis(base, **q):
    q = {"service": "kisters", "type": "queryServices", "datasource": "0", "format": "json", **q}
    return base + "?" + urllib.parse.urlencode(q)


print("== Bureau of Meteorology, Water Data Online (KiWIS)")
found = None
for base in ("http://www.bom.gov.au/waterdata/services", "https://www.bom.gov.au/waterdata/services"):
    b = show(base, kiwis(base, request="getStationList", parametertype_name="Water Course Discharge",
                         returnfields="station_name,station_no,station_latitude,station_longitude",
                         bbox=",".join(map(str, BBOX))))
    if b and b.lstrip()[:1] == b"[":
        found = base
        rows = json.loads(b)
        print(f"  {len(rows) - 1} discharge stations in the Melbourne box; first: {rows[1:6]}")
        break
if found:
    rows = json.loads(get(kiwis(found, request="getStationList", parametertype_name="Water Course Discharge",
                                returnfields="station_name,station_no", bbox=",".join(map(str, BBOX))))[1])[1:]
    want = [r for r in rows if "maribyrnong" in r[0].lower()][:3] + rows[:3]
    for name, no in want:
        b = show(f"  series for {name} ({no})", kiwis(found, request="getTimeseriesList", station_no=no,
                 parametertype_name="Water Course Discharge", returnfields="ts_id,ts_name"))
        if not b or b.lstrip()[:1] != b"[":
            continue
        ts = json.loads(b)[1:]
        print(f"    {len(ts)} series: {[t[1] for t in ts][:12]}")
        daily = next((t for t in ts if "DailyMean" in t[1]), None)
        hourly = next((t for t in ts if "Hourly" in t[1] or "AsStored" in t[1]), None)
        for t in [x for x in (daily, hourly) if x]:
            show(f"    values {t[1]} Oct 2022", kiwis(found, request="getTimeseriesValues", ts_id=t[0],
                 **{"from": "2022-10-10", "to": "2022-10-20"}))

print("\n== Victoria, Water Measurement Information System")
for url in ("https://data.water.vic.gov.au/", "https://data.water.vic.gov.au/WMIS/",
            "https://data.water.vic.gov.au/cgi/webservice.exe?" + urllib.parse.quote(json.dumps(
                {"function": "get_db_info", "version": "3", "params": {"table_name": "site", "return_type": "array",
                 "filter_values": {"station": "230106A"}}}))):
    show(url[:80], url)
