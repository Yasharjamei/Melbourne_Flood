# Who lives in the flood path

An interactive web map for Maribyrnong and Moonee Valley (Melbourne). You drag two circles, **A** and **B**, anywhere across the two councils. A side panel compares who lives inside each one: an age–sex pyramid, flood-relevant needs (aged 75+, aged 0–4, need for assistance, no car, limited English and so on), and how many residents fall inside the planning-scheme flood overlays.

The project applies two flood-resilience papers to the same 474 SA1 "urban units" they studied. The interaction comes from a Mashhad "Demographic Explorer" web map. The goal is not to redo the papers' single index. It is to show what that index hides.

> **Status:** working prototype (Census 2021, area-weighted apportionment, no basemap). See [Roadmap](#roadmap) for what is being built next and why.

---

## Contents

1. [Why this exists](#why-this-exists)
2. [Source material](#source-material)
3. [What the prototype does](#what-the-prototype-does)
4. [Repository layout](#repository-layout)
5. [Running it](#running-it)
6. [Method](#method)
7. [How this maps onto the papers](#how-this-maps-onto-the-papers)
8. [Known limitations](#known-limitations)
9. [Roadmap](#roadmap)
10. [Tools and Claude Code skills needed](#tools-and-claude-code-skills-needed)
11. [Data sources and licences](#data-sources-and-licences)

---

## Why this exists

Both papers reduce vulnerable people to one number per SA1. Lama & Sun's **"dependent population"** counts everyone **under 20 and everyone over 59** together. Two neighbourhoods with the same "dependent %" can need completely different flood responses. A street of toddlers and a street of 85-year-olds have different evacuation plans, transport needs and medical risks.

The default comparison already shows this, using Census 2021 and 800 m circles on two riverside suburbs:

| Measure | Avondale Heights (A) | Footscray (B) |
|---|---|---|
| Lama & Sun "dependent" (under 20 + 60+) | 55% | 30% |
| Aged 75+ | 17.4% | 6.5% |
| Aged 0–4 | 4.3% | 4.1% |

Avondale Heights' higher dependency comes almost entirely from older residents. The single indicator hides that, and a pyramid shows it immediately.

## Source material

| Source | Role in this project | Status in repo |
|---|---|---|
| Lama, P. & Sun, Q. C. (2026). *Assessing urban flood resilience: a comprehensive framework with evidence from Melbourne.* **Urban Informatics** 5:25. [doi:10.1007/s44212-026-00115-0](https://doi.org/10.1007/s44212-026-00115-0) (CC BY 4.0) | Study area, 474 SA1 units, indicator set, AHP weights, FRI / Damage Index / IFRI formulas | Read and summarised below |
| Lee, Sun & Wachowicz (2026). Research Square preprint | Second methodology to apply | **Not yet reviewed in this repo**, details to be added |
| Mashhad "Demographic Explorer" (screen recording) | Interaction model: two draggable circles, live side-by-side pyramids, Circle / Compare / Density / Parcels modes | Described from notes, video not stored here |

Lama & Sun's data is "available from the corresponding author upon reasonable request" and is not public. This project therefore rebuilds everything it can from public ABS and DataVic sources, and names every substitution.

## What the prototype does

- **Two draggable circles** (A and B) with one shared radius, 300–2,000 m.
- **Overlaid age–sex pyramid** in **percentages**, not counts, so a denser circle doesn't just look bigger. A is filled, B is outlined, and the two-council average sits in grey behind.
- **Indicator table** comparing A and B: aged 75+, aged 0–4, need for assistance, long-term health condition, no car, limited English, unemployment, dwellings in 4+ storey blocks, median household income, and estimated residents inside riverine (LSIO + Floodway) and overland-flow (SBO) overlays.
- **Choropleth** of all 474 SA1s, which can be shaded by any indicator.
- **Self-contained output:** one `dist/index.html` with the data inlined. It opens offline and has no basemap (see roadmap).

## Repository layout

```
.
├── pipeline/
│   ├── 01_fetch.sh      # downloads every public input into data/raw/
│   ├── 02_build.py      # SA1 attributes, overlay shares, 50 m grid -> data/processed/data.json
│   └── 03_bundle.py     # inlines data.json into web/template.html -> dist/index.html
├── web/
│   └── template.html    # the explorer (D3 v7, inline SVG map, no build step)
├── requirements.txt
└── README.md
```

`data/` and `dist/` are git-ignored because the pipeline regenerates them. Never commit the raw Census DataPack, which is about 100 MB zipped.

## Running it

Requires Python 3.10+, `bash`, `curl`, `unzip`. On Windows, use Git Bash or WSL for `01_fetch.sh`.

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
bash pipeline/01_fetch.sh      # public data -> data/raw/        (needs internet, ~100 MB)
python pipeline/02_build.py    # -> data/processed/data.json
python pipeline/03_bundle.py   # -> dist/index.html  (open in a browser)
```

Run every command from the repository root.

**Network hosts the pipeline needs:** `geo.abs.gov.au`, `www.abs.gov.au`, `opendata.maps.vic.gov.au`. Add these to the environment's allowed domains in Claude Code on the web, or on a restricted network. The page itself loads D3 from `cdnjs.cloudflare.com` and fonts from Google Fonts.

**Reproducibility caveat:** `01_fetch.sh` pulls live endpoints. The ABS 2021 DataPack is frozen, but DataVic republishes planning overlays whenever an amendment is gazetted. A later run can therefore differ from the published build. The roadmap adds SHA-256 checksums for each input.

## Method

1. **Study area.** SA1s (ASGS 2021) are fetched for a bounding box. An SA1 is kept if its representative point falls inside the Maribyrnong or Moonee Valley LGA. That leaves 474 SA1s, the same count as Lama & Sun.
2. **Census attributes.** The 2021 General Community Profile (SA1, VIC) supplies the figures.

   | Indicator | Table |
   |---|---|
   | Age by sex, 18 five-year bands (85+ merged) | G04A/B |
   | Median household income | G02 |
   | Need for assistance | G18 |
   | Long-term health condition | G20A/B |
   | Limited English | G13E |
   | Dwellings with no car | G34 |
   | Dwelling structure, incl. 4+ storey flats | G36 |
   | Unemployment | G46B |

   Denominators exclude "not stated".
3. **Flood overlays.** The Vicmap Planning `plan_overlay` layer is filtered to LSIO and FO (riverine) and SBO (overland flow), then dissolved. Each SA1 gets the share of its area inside each overlay.
4. **Apportionment grid.** A 50 m point grid (EPSG:7855) covers the study area. Each point takes the SA1 it falls in and flags for riverine and overland overlays. An SA1 too small to hold a point gets one at its representative point.
5. **Circle aggregation (in the browser).** Each SA1's counts are spread evenly across its grid points. A circle sums the share of each SA1's points inside it. "Residents in overlay" does the same for points that are both inside the circle and flagged.

## How this maps onto the papers

Lama & Sun (2026) build their index in five steps.

1. Eleven indicators in three dimensions are z-scored, then min–max normalised to 0–1.
2. AHP weights are applied (n = 11, CR = 0.042).
3. `Dimension = Σ wₙ · normₙ`
4. `FRI = Adaptive Capacity − (Sensitivity + Exposure)`
5. `D_x = (A_flooded / A_SA1) · X` for each indicator, which is summed, standardised and normalised into a Damage Index. Then `IFRI = 0.5·FRI − 0.5·Damage Index`.

| Dimension | Indicator | AHP weight | Public substitute here | Status |
|---|---|---|---|---|
| Exposure | Flood depth (HEC-RAS, Oct 2022 event) | 0.019 | LSIO/FO/SBO overlay share (extent only, no depth) | Proxy |
| Exposure | Elevation (Vicmap DEM 10 m) | 0.014 | Vicmap Elevation DEM 10 m, SA1 mean | Planned |
| Exposure | Sand % in soil (30 m) | 0.014 | Soil and Landscape Grid of Australia, sand % | Planned |
| Sensitivity | Land use (Esri 10 m) | 0.050 | Esri Land Cover 10 m / ABS mesh-block category | Planned |
| Sensitivity | Number of dwellings | 0.050 | G36 total dwellings | Available |
| Sensitivity | Population | 0.074 | G01 | Available |
| Sensitivity | Dependent population (< 20 and > 59) | 0.074 | G04, **and split into age bands** | Available and extended |
| Sensitivity | Long-term health condition | 0.110 | G20 | Available |
| Adaptive capacity | Employed population | 0.168 | G46 | Available |
| Adaptive capacity | Educated population | 0.168 | G49 (non-school qualification) | Planned |
| Adaptive capacity | "Mean income generating population" (income bracket $91k–$103,999) | 0.259 | G17 personal income bands | Planned, definition to confirm |

What this project adds on top:

- **Age–sex pyramids instead of one "dependent" figure.** This is the central point.
- **Indicators the papers didn't use** but emergency planners need: aged 75+, 0–4, need for assistance, no car, limited English, 4+ storey dwellings. These address the ground-level-structure assumption the paper names as a limitation.
- **Circles as a second view, alongside SA1s.** A circle is also an arbitrary unit (the modifiable areal unit problem). Showing both makes the choice of unit visible instead of hidden.

### Critical reading of the index (to test, not assume)

- **Adaptive capacity carries 0.595 of the weight and flood depth 0.019** (weights from Table 2). An FRI map may therefore mostly show income, education and employment. The plan is to recompute FRI with and without the flood-depth term and report how many SA1s change resilience class.
- **The indicators appear to be counts, not rates.** Population, dwellings, employed and educated all scale with SA1 size, so larger SA1s can score higher on sensitivity and on adaptive capacity at once. The build will compute both count and rate variants.
- **Damage uses the same uniform-density assumption** as this prototype. Replacing both with dasymetric weights (roadmap item 2) fixes the prototype and the reproduced Damage Index together.

## Known limitations

- **Area-weighted apportionment. This is the largest error source.** Residents are spread over parks, rail yards and industrial land. The Avondale Heights circle shows **0 residents in the riverine overlay** despite touching the Maribyrnong River. The most likely reason is that its riverside SA1s put the overlay on open space while the people live upslope.
- **Overlays are planning controls, not flood modelling.** They show extent only, with no depth, and they don't match the October 2022 event the papers simulated.
- **Coarse age data.** Age–sex data stops at SA1 level, about 400 people. Below roughly 500 m radius, a circle's pyramid is mostly apportionment artefact.
- **No basemap** in the self-contained build.
- **No SEIFA yet.** Income is a population-weighted mean of SA1 medians, which isn't a true median.
- **ABS perturbation.** Small random adjustments mean totals differ slightly between tables.

## Roadmap

Ordered by how much each step changes the numbers, not the look.

1. **Repository hygiene.** *(this commit)* Layout matches the commands, and this README. Next: SHA-256 manifest of raw inputs, and `01_fetch.sh` fails loudly on an empty or HTML download.
2. **Dasymetric weighting.** Replace the uniform 50 m grid with weights from **G-NAF residential address points** (preferred, because it leaves out garages and warehouses) or **Vicmap building footprints**. Check SA1 totals are preserved exactly, then report how the A/B figures and in-overlay counts change.
3. **Reproduce the Lama & Sun indicators.** Add elevation, sand %, land use, education and the income bracket. Compute FRI, Damage Index and IFRI with their AHP weights. Map them next to the pyramids, and run the sensitivity checks above.
4. **MapLibre GL JS plus a real basemap.** Replace the inline SVG map. SA1s become a vector source. Circles become draggable GeoJSON using Turf.js `circle` and `booleanPointInPolygon`. Basemap: OpenFreeMap or CARTO Positron/Dark Matter (no key), or MapTiler/Mapbox with a key kept out of git. Add the video's **Circle / Compare / Density** modes. Parcels mode depends on step 2.
5. **SEIFA 2021 (IRSD / IRSAD)** at SA1, added to the table and choropleth.
6. **Modelled depth.** If Chayn Sun shares the HEC-RAS October 2022 depth raster, replace the overlay proxy with depth bands (for example > 0.3 m, > 0.5 m, > 1.2 m, matching common vehicle and pedestrian stability thresholds). Otherwise use Melbourne Water's 1% AEP flood extent where licensing allows.
7. **Second paper (Lee, Sun & Wachowicz).** Add its method once it is reviewed.
8. **Publish** with GitHub Pages from `dist/`, with a link from the portfolio site.

## Tools and Claude Code skills needed

### Software

| Tool | Why | Install |
|---|---|---|
| Python 3.10+ with `geopandas`, `shapely`, `pandas`, `numpy` | Pipeline | `pip install -r requirements.txt` |
| `rasterio`, `rasterstats` | Elevation, sand % and depth rasters per SA1 (roadmap 3, 6) | to be added to `requirements.txt` |
| `bash`, `curl`, `unzip` | `01_fetch.sh` | Git Bash or WSL on Windows |
| MapLibre GL JS, Turf.js | Basemap map and circle geometry (roadmap 4) | CDN (`cdn.jsdelivr.net/npm/maplibre-gl`, `@turf/turf`) or npm |
| Optional: `tippecanoe` / PMTiles | Only if the SA1 layer outgrows inline GeoJSON | not needed yet |

### Claude Code skills

None have to be installed separately. The ones below are built in or come with the Claude Code environment. Invoke them with `/name` in a session.

| Skill | Use in this project |
|---|---|
| `dataviz` | Pyramid, choropleth ramps and indicator table: accessible, colour-blind-safe palettes that work in light and dark |
| `run` | Open `dist/index.html` in the pre-installed Chromium and take screenshots to check a change actually works |
| `session-start-hook` | Adds a hook so every Claude Code on the web session installs `requirements.txt` before work starts |
| `code-review` / `simplify` | Review pipeline changes before merging, especially the apportionment maths |
| `anthropic-skills:pdf` | Pull text, tables and equations out of the papers (used for the summary above) |
| `anthropic-skills:xlsx` | Only if TableBuilder exports (Excel) replace the DataPack CSVs |

### Environment settings (Claude Code on the web)

The cloud environment's network policy blocks the data hosts by default. To run the pipeline there, allow `geo.abs.gov.au`, `www.abs.gov.au` and `opendata.maps.vic.gov.au`, plus your chosen basemap tile host, under **environment → Edit → Network access**. Running Claude Code locally avoids this.

## Data sources and licences

- **ABS** Census 2021 GCP DataPack (SA1, VIC) and ASGS 2021 boundaries: CC BY 4.0, © Commonwealth of Australia.
- **Vicmap Planning** overlays via DataVic: CC BY 4.0, © State of Victoria.
- **Lama & Sun (2026):** CC BY 4.0. The methodology and weights are cited and credited. None of the authors' data is redistributed here.
