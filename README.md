# Who lives in the flood path

An interactive web map of Melbourne, built as two pages from one pipeline:

- **Maribyrnong & Moonee Valley** (`/`): the 474 SA1s studied by both papers. This page reproduces, and critiques, Lama & Sun (2026).
- **Greater Melbourne** (`/metro/`): all 31 metropolitan councils, about 10,000 SA1s, with the same tools.

On either page you drag two circles, **A** and **B**, anywhere on the map. A side panel compares who lives inside each one: an age–sex pyramid, flood-relevant needs (aged 75+, aged 0–4, need for assistance, no car, limited English and so on), and how many residents fall inside the planning-scheme flood overlays.

The project applies two flood-resilience papers to the same 474 SA1 "urban units" they studied. The interaction comes from a Mashhad "Demographic Explorer" web map. The goal is not to redo the papers' single index. It is to show what that index hides.

> **Status (v0.3):**
> - Mesh-block weighting and Lama & Sun's six index maps are built for both pages, with suburbs on both.
> - It goes live at **https://yasharjamei.github.io/Melbourne_Flood/** once GitHub Pages is enabled (see [Live site](#live-site-github-pages)).
> - The first prototype, which used even spreading, is kept at [`snapshots/2026-09-25-prototype.html`](snapshots/2026-09-25-prototype.html).
> - Changes are listed in [`CHANGELOG.md`](CHANGELOG.md), and the history and decisions in [`docs/PROJECT_LOG.md`](docs/PROJECT_LOG.md).

---

## Contents

1. [Why this exists](#why-this-exists)
2. [Source material](#source-material)
3. [What the explorer does](#what-the-explorer-does)
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

The default comparison already shows this, using Census 2021 and 800 m circles on two riverside suburbs. These figures come from the v0.1 prototype, which spread people evenly. Mesh-block weighting moves them slightly:

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
| Lee, N., Sun, Q. C. & Wachowicz, M. (2026). *Flood risk assessment at the neighbourhood level using Spatially Adaptive Weighting.* Research Square preprint. [doi:10.21203/rs.3.rs-10610207/v1](https://doi.org/10.21203/rs.3.rs-10610207/v1) (CC BY 4.0) | IPCC hazard / exposure / vulnerability split, 14 indicators as **rates**, SEIFA IER and IEO, MGWR-derived **local** weights | Read and summarised below |
| Mashhad "Demographic Explorer" (screen recording) | Interaction model: two draggable circles, live side-by-side pyramids, Circle / Compare / Density / Parcels modes | Described from notes, video not stored here |

Both PDFs are in [`papers/`](papers/). They are CC BY 4.0, so redistributing them here is allowed.

Neither paper publishes its HEC-RAS flood output. Lama & Sun's data is "available from the corresponding author upon reasonable request". Lee et al. say their Census, SEIFA, terrain, land-cover and building-footprint inputs are public, but the Melbourne Water/Jacobs flood extent and the council 3D building data are licensed. This project therefore rebuilds everything it can from public sources and names every substitution.

## What the explorer does

- **Two draggable circles** (A and B) with one shared radius, 300–2,000 m.
- **Every SA1 a circle touches is shaded** in that circle's colour, darker where more of its residents are counted. The estimate's make-up is visible on the map, and the tooltip gives the exact share.
- **Overlaid age–sex pyramid** in **percentages**, not counts, so a denser circle doesn't just look bigger. A is filled, B is outlined, and the two-council average sits in grey behind.
- **Indicator table** comparing A and B: aged 75+, aged 0–4, need for assistance, long-term health condition, no car, limited English, unemployment, dwellings in 4+ storey blocks, median household income, and estimated residents inside riverine (LSIO + Floodway) and overland-flow (SBO) overlays.
- **Choropleth** of every SA1, shaded by any of those indicators.
- **Lama & Sun (2026) maps:** Exposure, Sensitivity, Adaptive capacity, Flood Resilience Index (FRI), Damage index and Integrated FRI (IFRI). These are the six maps in the paper's Figures 5 and 6, shown in five classes (quintiles). The panel also gives each circle's resident-weighted FRI, Damage and IFRI.
- **Suburbs** (ABS Suburbs and Localities 2021):
  - dashed outlines, with labels that appear as you zoom in
  - a "Find a suburb" box that zooms the map to a suburb
  - suburb names in tooltips and under each circle's resident count
- **Self-contained output:** one HTML file per page with the data inlined. It opens offline and has no basemap yet (see roadmap).

## Repository layout

```
.
├── .github/workflows/
│   └── pages.yml        # CI: fetch -> build -> bundle -> deploy to GitHub Pages
├── pipeline/
│   ├── config.py        # study areas (west, metro) and Lama & Sun weights
│   ├── 01_fetch.py      # downloads public inputs -> data/raw/<study>/, data/raw/gcp/, data/raw/shared/
│   ├── 02_build.py      # SA1 + mesh-block + suburb data and indices -> data/processed/<study>.json
│   └── 03_bundle.py     # inlines each dataset into web/template.html -> dist/index.html, dist/metro/index.html
├── web/
│   └── template.html    # the explorer (D3 v7, inline SVG map, no build step)
├── papers/              # the two source papers (CC BY 4.0)
├── snapshots/           # frozen builds, e.g. the first published prototype (open in a browser)
├── docs/
│   └── PROJECT_LOG.md   # history, decisions and open questions
├── CHANGELOG.md
├── requirements.txt
└── README.md
```

`data/` and `dist/` are git-ignored because the pipeline regenerates them. Never commit the raw Census DataPack, which is about 100 MB zipped.

## Running it

Requires Python 3.10+. It's pure Python, so it works the same in Windows PowerShell.

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python pipeline/01_fetch.py --study west     # Maribyrnong + Moonee Valley (~150 MB incl. Census DataPack)
python pipeline/02_build.py --study west
python pipeline/01_fetch.py --study metro    # all 31 councils (adds several hundred MB of boundaries/overlays)
python pipeline/02_build.py --study metro
python pipeline/03_bundle.py                 # -> dist/index.html and dist/metro/index.html
```

Build `west` only if you don't need the metro page; `03_bundle.py` bundles whichever datasets exist.

Some inputs are **optional**: mesh-block resident counts, the elevation model and soil sand. If a download fails, the build carries on and records the substitution in the page footer. For example, "Mesh-block counts unavailable: residents placed on Residential mesh blocks in proportion to area".

Run every command from the repository root.

**Network hosts the pipeline needs:** `geo.abs.gov.au`, `www.abs.gov.au`, `opendata.maps.vic.gov.au`, `copernicus-dem-30m.s3.amazonaws.com` and `maps.isric.org`. Add these to the environment's allowed domains in Claude Code on the web, or on a restricted network. The page itself loads D3 from `cdnjs.cloudflare.com` and fonts from Google Fonts.

### Live site (GitHub Pages)

[`.github/workflows/pages.yml`](.github/workflows/pages.yml) fetches, builds and bundles both pages on a GitHub runner:
- **On every pull request** it builds only, to prove the pipeline works on live data.
- **On every push to `main`** it also publishes the pages:
  - **https://yasharjamei.github.io/Melbourne_Flood/**
  - **https://yasharjamei.github.io/Melbourne_Flood/metro/**

Raw inputs are cached, and downloaded again only when `pipeline/01_fetch.py` or `pipeline/config.py` changes.

One-time setup: **Settings → Pages → Build and deployment → Source: GitHub Actions**. Pages on a private repo needs a paid GitHub plan. Otherwise make the repo public.

**Reproducibility caveat:** `01_fetch.py` pulls live endpoints. The ABS 2021 DataPack is frozen, but DataVic republishes planning overlays whenever an amendment is gazetted. A later run can therefore differ from the published build. The roadmap adds SHA-256 checksums for each input.

## Method

1. **Study area.** Set in `pipeline/config.py`.
   - `west` is the papers' two councils.
   - `metro` is the 31 Greater Melbourne councils: Merri-bek appears under its ASGS 2021 name, Moreland.
   - An SA1 is kept if its representative point falls inside a study council. For `west`, that leaves 474 SA1s, the same count as Lama & Sun.
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
   | Unemployment, employed persons | G46B |
   | Non-school qualifications ("educated population") | G43 |
   | Personal income $1,750–$1,999/wk ("mean income generating population") | G17A–C |

   Denominators exclude "not stated".
3. **Flood overlays.** The Vicmap Planning `plan_overlay` layer is filtered to LSIO and FO (riverine) and SBO (overland flow), then dissolved. Each SA1 gets the share of its area inside each overlay.
4. **Mesh-block weighting.** This replaced the v0.1 50 m grid, which spread people evenly.
   - Each ABS 2021 mesh block gets a weight: its share of its SA1's residents, from the ABS Mesh Block Counts.
   - If that file can't be downloaded, residents go onto Residential mesh blocks in proportion to their area.
   - Each mesh block also records its category and the share of its area inside riverine and overland-flow overlays.
5. **Circle aggregation (in the browser).** A circle counts the mesh blocks whose representative point is inside it.
   - Each SA1 contributes its counts multiplied by the summed weight of those mesh blocks.
   - "Residents in overlay" uses the same weights, multiplied by each mesh block's overlay share.
   - Age–sex shares are assumed constant within an SA1, because mesh blocks carry no age data.
6. **Suburbs.** Each SA1 is assigned to an ABS Suburb and Locality (SAL 2021) by its representative point.

## How this maps onto the papers

Lama & Sun (2026) build their index in five steps. **All five are implemented in `02_build.py` (v0.3).**

1. Eleven indicators in three dimensions are z-scored, then min–max normalised to 0–1.
2. AHP weights are applied (n = 11, CR = 0.042).
3. `Dimension = Σ wₙ · normₙ`
4. `FRI = Adaptive Capacity − (Sensitivity + Exposure)`
5. `D_x = (A_flooded / A_SA1) · X` for each indicator, which is summed, standardised and normalised into a Damage Index. Then `IFRI = 0.5·FRI − 0.5·Damage Index`.

| Dimension | Indicator | AHP weight | Public substitute here | Status |
|---|---|---|---|---|
| Exposure | Flood depth (HEC-RAS, Oct 2022 event) | 0.019 | Share of SA1 inside LSIO/FO/SBO overlays (extent only, no depth) | Proxy |
| Exposure | Elevation (Vicmap DEM 10 m); low = more exposed | 0.014 | Copernicus GLO-30 (30 m surface model), mesh-block samples, area-weighted to SA1 | Substitute |
| Exposure | Sand % in soil (30 m); more sand = better drainage | 0.014 | SoilGrids 250 m, 0–5 cm | Substitute |
| Sensitivity | Land use (Esri 10 m) | 0.050 | Share of SA1 area in built-up mesh-block categories (not Parkland, Water or Primary Production) | Substitute |
| Sensitivity | Number of dwellings | 0.050 | G36 total dwellings | Available |
| Sensitivity | Population | 0.074 | G01 | Available |
| Sensitivity | Dependent population (< 20 and > 59) | 0.074 | G04, **and split into age bands** | Available and extended |
| Sensitivity | Long-term health condition | 0.110 | G20 | Available |
| Adaptive capacity | Employed population | 0.168 | G46 | Available |
| Adaptive capacity | Educated population | 0.168 | G43 non-school qualifications | Available |
| Adaptive capacity | "Mean income generating population" ($91,000–$103,999 a year) | 0.259 | G17 persons earning $1,750–$1,999 a week, which is exactly that bracket | Available |

**Assumptions the paper leaves open, and the choices made here:**
- **Direction for elevation and sand.** The paper doesn't say whether low elevation or high sand is inverted before weighting. Its text implies both should be (low ground and clay soils flood). Their highest Exposure score, 0.043 out of a possible 0.047, is in low-lying Flemington. That only makes sense if low elevation scores high. Both are inverted here.
- **Classes.** The paper maps five classes without naming the method, which is probably natural breaks. Quintiles are used here, so class boundaries won't match the published figures exactly.
- **Normalisation scope.** For `metro`, indicators are normalised across all ~10,000 SA1s, so its index values aren't comparable with the two-council page.

What this project adds on top:

- **Age–sex pyramids instead of one "dependent" figure.** This is the central point.
- **Indicators the papers didn't use** but emergency planners need: aged 75+, 0–4, need for assistance, no car, limited English, 4+ storey dwellings. These address the ground-level-structure assumption the paper names as a limitation.
- **Circles as a second view, alongside SA1s.** A circle is also an arbitrary unit (the modifiable areal unit problem). Showing both makes the choice of unit visible instead of hidden.

### Critical reading of the index (to test, not assume)

- **Adaptive capacity carries 0.595 of the weight and flood depth 0.019** (weights from Table 2). An FRI map may therefore mostly show income, education and employment. The plan is to recompute FRI with and without the flood-depth term and report how many SA1s change resilience class.
- **The indicators appear to be counts, not rates.** Population, dwellings, employed and educated all scale with SA1 size, so larger SA1s can score higher on sensitivity and on adaptive capacity at once. The build will compute both count and rate variants.
- **Damage assumes people are spread evenly within each SA1** (`A1/A × X`, as in the paper). The circles here use mesh-block weights instead. So the Damage index reproduces the paper's assumption, while the circle figures don't share it.

### Lee, Sun & Wachowicz (2026): spatially adaptive weighting

**Study area:** 412 SA1s (not 474). These are the Maribyrnong and Moonee Valley SA1s inside the Maribyrnong River catchment. The pipeline needs a catchment clip to reproduce it (Melbourne Water catchment boundary or a DEM-derived watershed).

**Framework (IPCC):** `Risk = f(Hazard, Exposure, Vulnerability)`. Every indicator is min–max normalised to [0, 1]. It is flipped (1 − x) wherever lower values mean higher risk.

| Component | Indicator | Unit | Direction | Public substitute here | Status |
|---|---|---|---|---|---|
| Hazard | Mean flood depth (HEC-RAS, Oct 2022, permanent water removed) | m | + | none public; overlay proxy only | Proxy |
| Hazard | Flood spread (share of SA1 at depth ≥ 0.15 m) | % | + | LSIO/FO/SBO overlay share | Proxy |
| Hazard | Drainage density | km⁻¹ | + | Vicmap Hydro / DEM-derived streams | Planned |
| Vulnerability | Mean elevation | m | − | Vicmap Elevation DEM 10 m | Planned |
| Vulnerability | Mean slope | ° | − | DEM derivative | Planned |
| Vulnerability | Mean curvature | m⁻¹ | − | DEM derivative | Planned |
| Vulnerability | SEIFA IER (economic resources) | score | − | ABS SEIFA 2021, SA1 | Planned |
| Vulnerability | Vegetation density | % | − | DELWP/Vicmap tree canopy | Planned |
| Vulnerability | Transport density | % | − | Vicmap road casement | Planned |
| Exposure | Population density | people/m² | + | G01 ÷ SA1 area (**dasymetric: residential area**) | Available |
| Exposure | Building density | % | + | Microsoft Global ML Building Footprints (public) | Planned |
| Exposure | Dependent population | % | + | G04, **and split into age bands** | Available and extended |
| Exposure | Population with health condition (ASSNP) | % | + | G18 need for assistance | Available |
| Exposure | SEIFA IEO (education–occupation) | score | − | ABS SEIFA 2021, SA1 | Planned |

**Weighting:**
- **Hazard** is the equal-weighted mean of its three indicators.
- **Vulnerability** and **exposure** each get a separate MGWR model, with *flood spread* as the response.
- In each SA1, an indicator's weight is `|βᵢ| / Σ|βⱼ|` within its component.
- Each component index is the mean of the weighted indicators, then min–max normalised.
- `FRI = (H + V + E) / 3`, unweighted.

**How it differs from Lama & Sun:**

| | Lama & Sun | Lee et al. |
|---|---|---|
| Units | 474 SA1s, both LGAs | 412 SA1s, catchment only |
| Components | exposure, sensitivity, adaptive capacity | hazard, exposure, vulnerability (IPCC) |
| Weights | AHP, one set for the whole area | MGWR, a different set per SA1 |
| Population indicators | counts, as read | rates / densities |
| Index | `AC − (S + E)`, then IFRI with damage | `(H + V + E) / 3` |
| "Higher is…" | more resilient | more at risk |

Both treat "dependent" as one number. Lama & Sun define it as under 20 plus over 59. Lee et al. build it from ABS AGE10P (10-year age bands) but don't state the age cut-offs. Lee et al. also single out **Avondale Heights** for its "high dependent population and population with health condition concentrations" in evacuation planning. The default A/B comparison shows that this dependency there is mostly people aged 75+, not children. **So the pyramid argument applies to both papers.**

**Weaknesses to check before copying the method** (most are stated in the paper itself):
- **The exposure weights may be mostly noise.** The authors report that population density, dependent % and health-condition % were *not statistically significant* against flooding. Moran's I on exposure indicators versus depth was consistent with chance. 84 SA1s had *negative* local R² in the exposure model. Taking `|β|` of an insignificant coefficient still produces a weight, so local exposure weights shouldn't be read as meaningful until tested. The plan is to report the local t-values and shrink insignificant coefficients to zero or to the global value, then compare.
- **The weights measure association with where water went, not with harm.** The response variable is flood spread. Using `|β|` also means an indicator *negatively* associated with flooding gets as much weight as one positively associated. The authors acknowledge the first point as their "most consequential limitation".
- **The hazard term enters twice.** Flood spread is a hazard indicator and also the variable that sets the vulnerability and exposure weights.
- **Validation is partial.** It is checked against the 1% AEP design extent, which only covers the lower catchment, and no depth error is reported.

**What to take from it:** rates instead of counts, SEIFA IER/IEO, building-footprint density, DEM derivatives, and the IPCC split. These are all public. Local MGWR weights are worth reproducing, but as a *comparison layer* next to equal and AHP weights, not as ground truth. The map can then show where the choice of weighting changes an SA1's risk class. The interactive circles make that easy to explore.

## Known limitations

- **Apportionment is still an estimate.** Mesh blocks (v0.3) put people where they actually live, down to about 30–60 residents per block. But a circle includes a whole mesh block or none of it, and age–sex shares are assumed constant within each SA1. The v0.1 even-spreading error, which showed 0 riverine-overlay residents at Avondale Heights, should shrink. That needs re-checking on the first live build.
- **Overlays are planning controls, not flood modelling.** They show extent only, with no depth, and they don't match the October 2022 event the papers simulated.
- **Coarse age data.** Age–sex data stops at SA1 level, about 400 people. Below roughly 500 m radius, a circle's pyramid is mostly apportionment artefact.
- **No basemap** in the self-contained build.
- **No SEIFA yet.** Income is a population-weighted mean of SA1 medians, which isn't a true median.
- **Metro page size.** About 10,000 SA1 outlines drawn as SVG, which is slower on phones. MapLibre with vector tiles is the fix (roadmap).
- **ABS perturbation.** Small random adjustments mean totals differ slightly between tables.

## Roadmap

Ordered by how much each step changes the numbers, not the look.

1. **Repository hygiene.** *(done, v0.2)* Layout matches the commands, papers in `papers/`, and this README. Next: SHA-256 manifest of raw inputs, and `01_fetch.sh` fails loudly on an empty or HTML download.
2. **Dasymetric weighting from mesh blocks.** *(done, v0.3; G-NAF refinement and the mesh-block view mode still open)* ABS 2021 mesh blocks (about 30–60 residents each) publish real **population and dwelling counts** and a **land-use category** (Residential, Parkland, Industrial…). That makes them the best public weight layer: parks and industrial blocks get their true, usually near-zero, population, not an even share. Within each mesh block, split further by G-NAF residential address points or building footprints. Mesh blocks carry **no age–sex data**, so a circle's pyramid is still built from SA1 age shares, now weighted by where people actually live. Check that SA1 totals are preserved within ABS perturbation, then report how the A/B figures and in-overlay counts change.
   - **Mesh-block view mode.** A third geography next to SA1 and circle, answering "who lives *here*". The panel shows mesh-block population, dwellings and category, plus the age pyramid of the parent SA1, labelled as *inherited*, never as the mesh block's own.
3. **Reproduce the Lama & Sun indicators.** *(done, v0.3; the sensitivity checks below are still open)* Add elevation, sand %, land use, education and the income bracket. Compute FRI, Damage Index and IFRI with their AHP weights. Map them next to the pyramids, and run the sensitivity checks above.
4. **MapLibre GL JS plus a real basemap.** Replace the inline SVG map. SA1s become a vector source. Circles become draggable GeoJSON using Turf.js `circle` and `booleanPointInPolygon`. Basemap: OpenFreeMap or CARTO Positron/Dark Matter (no key), or MapTiler/Mapbox with a key kept out of git. Add the video's **Circle / Compare / Density** modes. Parcels mode depends on step 2.
5. **SEIFA 2021 (IRSD / IRSAD)** at SA1, added to the table and choropleth.
5b. **All Greater Melbourne.** *(done, v0.3)* A second page for the 31 councils, sharing the pipeline.
6. **Modelled depth.** If Chayn Sun shares the HEC-RAS October 2022 depth raster, replace the overlay proxy with depth bands (for example > 0.3 m, > 0.5 m, > 1.2 m, matching common vehicle and pedestrian stability thresholds). Otherwise use Melbourne Water's 1% AEP flood extent where licensing allows.
7. **Second paper (Lee, Sun & Wachowicz).** Add its method once it is reviewed.
8. **Publish.** *(workflow added)* GitHub Pages deploys from `dist/` on every push to `main`. Still to do: link it from the portfolio site.

## Tools and Claude Code skills needed

### Software

| Tool | Why | Install |
|---|---|---|
| Python 3.10+ with `geopandas`, `shapely`, `pandas`, `numpy` | Pipeline | `pip install -r requirements.txt` |
| `rasterio`, `openpyxl` | Elevation/sand sampling; reading the mesh-block counts workbook | in `requirements.txt` |
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

### Data still to add (in priority order)

| Dataset | Unlocks | Source | Public? |
|---|---|---|---|
| SEIFA 2021 at SA1 (IRSD, IRSAD, IER, IEO) | Lee et al. vulnerability and exposure | ABS | Yes |
| Vicmap Elevation DEM 10 m (to replace Copernicus 30 m) | Finer elevation, slope, curvature, drainage density | DataVic / Vicmap | Yes |
| Microsoft Global ML Building Footprints (Australia) | Building density, dasymetric refinement | Microsoft (ODbL) | Yes |
| Tree canopy extent | Vegetation density | DataVic (DELWP) | Yes |
| Vicmap road casement | Transport density | DataVic | Yes |
| Maribyrnong catchment boundary | The 412-SA1 study area of Lee et al. | Melbourne Water / DEM watershed | Probably |
| HEC-RAS October 2022 depth raster | Real hazard (depth, spread ≥ 0.15 m) instead of overlays | Chayn Sun (RMIT), on request | No |
| Melbourne Water 1% AEP flood extent | Better proxy than planning overlays | Melbourne Water / Jacobs | Licensed |

## Data sources and licences

- **ABS** Census 2021 GCP DataPack (SA1, VIC) and ASGS 2021 boundaries: CC BY 4.0, © Commonwealth of Australia.
- **Vicmap Planning** overlays via DataVic: CC BY 4.0, © State of Victoria.
- **ABS** Mesh Block Counts 2021 and Suburbs and Localities 2021: CC BY 4.0.
- **Copernicus GLO-30 DEM:** © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018, provided under COPERNICUS by the European Union and ESA.
- **SoilGrids 2.0 (ISRIC):** CC BY 4.0.
- **Lama & Sun (2026):** CC BY 4.0. The methodology and weights are cited and credited. None of the authors' data is redistributed here.
