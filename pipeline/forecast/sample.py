"""Write web/scenarios_sample.json: made-up numbers in the exact shape the real forecast will produce,
so the scenarios page can be designed and reviewed before the VIF2023 and sea-level-rise inputs arrive.

Every value here is invented. The file carries meta.sample = true and the page shows a warning banner
while it does. Area names are placeholders on purpose: invented figures must never sit beside a real
council's name. The back-test block is the one real part (docs/PROJECT_LOG.md §25, run 3).
"""
import json, random

YEARS = [2021, 2026, 2031, 2036]
SLR = [
    {"id": "none", "label": "Today's flood areas"},
    {"id": "0.2", "label": "+0.2 m sea level (about 2040)"},
    {"id": "0.5", "label": "+0.5 m sea level (about 2070)"},
    {"id": "0.8", "label": "+0.8 m sea level (2100 planning benchmark)"},
]
SLR_GAIN = {"none": 0, "0.2": .04, "0.5": .11, "0.8": .22}   # share added in coastal areas, invented

rnd = random.Random(2036)
areas = []
for i in range(1, 13):
    base = rnd.randint(30, 260) * 100
    growth = rnd.uniform(-.002, .03)                    # yearly, invented
    coastal = i % 3 == 0
    v = {}
    for s in SLR:
        rows = []
        for y in YEARS:
            t = y - 2021
            mid = base * (1 + growth) ** t * (1 + (SLR_GAIN[s["id"]] if coastal else 0))
            half = mid * (.04 + .025 * t / 5)            # range widens with the horizon
            rows.append([round(mid), round(mid - half), round(mid + half)])
        v[s["id"]] = rows
    areas.append({"name": f"Sample area {i}", "coastal": coastal, "v": v})

# Area ranges are not independent, so the total gets its own (narrower than summed) range.
total = {}
for s in SLR:
    rows = []
    for k, y in enumerate(YEARS):
        mid = sum(a["v"][s["id"]][k][0] for a in areas)
        half = mid * (.02 + .015 * (y - 2021) / 5)
        rows.append([mid, round(mid - half), round(mid + half)])
    total[s["id"]] = rows

out = {
    "meta": {"sample": True, "years": YEARS, "base": 2021, "unit": "Suburb (placeholder)",
             "note": "Invented numbers for layout review only."},
    "slr": SLR,
    "total": total,
    "areas": areas,
    "backtest": {
        "source": "2016→2021 back-test, docs/PROJECT_LOG.md §25 run 3",
        "rows": [
            {"model": "A · spread evenly within each SA2", "mb": [22.5, 72.9], "growth": [46.4, 46.8], "sa1": [16.7, 82.3]},
            {"model": "D · new addresses, calibrated (k = 1.21)", "mb": [17.8, 78.5], "growth": [38.2, 51.4], "sa1": [11.9, 87.0]},
            {"model": "E · as D, addresses 12+ months old (k = 1.51)", "mb": [17.1, 78.9], "growth": [33.3, 55.3], "sa1": [11.4, 87.3], "chosen": True},
        ],
    },
}
json.dump(out, open("web/scenarios_sample.json", "w"), indent=1)
print("web/scenarios_sample.json: written (sample data)")
