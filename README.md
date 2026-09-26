# Who lives in the flood path

An interactive web map of Melbourne, built as two pages from one pipeline:

- **Maribyrnong & Moonee Valley** (`/`): the 474 SA1s studied by both papers. This page reproduces, and critiques, Lama & Sun (2026).
- **Greater Melbourne** (`/metro/`): all 31 metropolitan councils, 11,293 SA1s and 543 suburbs, with the same tools.

On either page you drag two circles, **A** and **B**, anywhere on the map. A side panel compares who lives inside each one: an age–sex pyramid, flood-relevant needs (aged 75+, aged 0–4, need for assistance, no car, limited English and so on), and how many residents fall inside the planning-scheme flood overlays.

The project applies two flood-resilience papers to the same 474 SA1 "urban units" they studied. The interaction comes from an existing "Demographic Explorer" web map. The goal is not to redo the papers' single index. It is to show what that index hides.

> **Status (v0.5):**
> - Live at **https://yasharjamei.github.io/Melbourne_Flood/** (and `/metro/`, `/analysis/`).
> - Flood exposure is measured on **residents**: each dwelling is placed at its Vicmap Address point, so a flooded park no longer counts as exposure (see [Method](#method), step 3).
> - **Working on the code?** Start with [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (how it fits together, data contract, gotchas) and [`CONTRIBUTING.md`](CONTRIBUTING.md) (setup, checks, pull requests).
> - The first prototype, which used even spreading, is kept at [`snapshots/2026-09-25-prototype.html`](snapshots/2026-09-25-prototype.html).
> - Changes are listed in [`CHANGELOG.md`](CHANGELOG.md), and the history and decisions in [`docs/PROJECT_LOG.md`](docs/PROJECT_LOG.md).

### Verified build (GitHub Actions, live ABS and DataVic data)

| | Maribyrnong & Moonee Valley | Greater Melbourne |
|---|---|---|
| Councils / SA1s / suburbs | 2 / 474 / 24 | 31 / 11,293 / 543 |
| Mesh blocks (with residents) | 2,661 (2,228) | 58,563 (48,770) |
| Residents placed by mesh-block counts / Census SA1 total | 207,015 / 207,058 | 4,833,357 / 4,833,389 |
| Flood-overlay polygons (LSIO, FO, SBO) | 72 | 2,302 |
| FRI range (paper, two councils: −0.148 to 0.228) | −0.168 to 0.272 | −0.225 to 0.211 |
| Vicmap Address points fetched / inside study mesh blocks | 184,780 / 135,885 | 3,123,830 / 2,967,784 |
| Populated mesh blocks with at least one address | 100% | 100% |
| **Residents in a flood overlay: by area share → by address** | **10,721 → 7,170** (area overstated by 50%) | **239,650 → 185,538** (by 29%) |
| Max Exposure (paper: 0.043 of a possible 0.047) | 0.047 | 0.047 |
| Page size (compressed on the wire) | 0.6 MB | 14.3 MB (about 3 MB) |

The residents placed by mesh-block counts match the Census SA1 totals to within 0.02%; the small gap is ABS perturbation between the two releases. The FRI range lands close to the paper's, even with the substituted depth, elevation and sand inputs.

---

## Contents

1. [Why this exists](#why-this-exists)
2. [Source material](#source-material)
3. [What the explorer does](#what-the-explorer-does)
4. [Repository layout](#repository-layout)
5. [Running it](#running-it)
6. [Method](#method)
7. [How accurate is the data, and how it was tested](#how-accurate-is-the-data-and-how-it-was-tested)
8. [How this maps onto the papers](#how-this-maps-onto-the-papers)
9. [Known limitations](#known-limitations)
10. [Roadmap](#roadmap)
11. [Tools and Claude Code skills needed](#tools-and-claude-code-skills-needed)
12. [Data sources and licences](#data-sources-and-licences)

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
| A "Demographic Explorer" web map (screen recording) | Interaction model: two draggable circles, live side-by-side pyramids, Circle / Compare / Density / Parcels modes | Described from notes, video not stored here |

Both PDFs are in [`papers/`](papers/). They are CC BY 4.0, so redistributing them here is allowed.

Neither paper publishes its HEC-RAS flood output. Lama & Sun's data is "available from the corresponding author upon reasonable request". Lee et al. say their Census, SEIFA, terrain, land-cover and building-footprint inputs are public, but the Melbourne Water/Jacobs flood extent and the council 3D building data are licensed. This project therefore rebuilds everything it can from public sources and names every substitution.

## What the explorer does

- **Two draggable circles** (A and B) with one shared radius, 300–2,000 m.
- **Every SA1 a circle touches is shaded** in that circle's colour, darker where more of its residents are counted. The estimate's make-up is visible on the map, and the tooltip gives the exact share.
- **Overlaid age–sex pyramid** in **percentages**, not counts, so a denser circle doesn't just look bigger. A is filled, B is outlined, and the two-council average sits in grey behind.
- **Indicator table** comparing A and B: aged 75+, aged 0–4, need for assistance, long-term health condition, no car, limited English, unemployment, dwellings in 4+ storey blocks, median household income, and estimated residents inside riverine (LSIO + Floodway) and overland-flow (SBO) overlays.
- **Basemap and map engine:** MapLibre GL JS (WebGL) over a CARTO basemap (Positron in light mode, Dark Matter in dark mode, © OpenStreetMap contributors). Data layers draw beneath the basemap's street and place labels. If the basemap can't load, the page falls back to a plain background, and a toggle hides the basemap.
- **Choropleth** of every SA1, chosen from one grouped "Show on map" menu. Each variable family has its own symbology:

  | Variable | ColorBrewer scheme | Classes |
  |---|---|---|
  | Residents per hectare / Aged 75+ / Aged 0–4 | YlGnBu / PuBuGn / GnBu | quintiles |
  | Need help / Long-term health / No car / Limited English | Reds / RdPu / Greys / PuRd | quintiles |
  | 4+ storey dwellings / Unemployment / Income | BuPu / YlOrBr / Greens | quintiles |
  | Area in flood overlay | Blues | quintiles of SA1s with any overlay; "not in an overlay" left clear |
  | Exposure / Sensitivity / Adaptive capacity / Damage | OrRd / PuBu / YlGn / YlOrRd | quintiles |
  | FRI / IFRI | RdBu / RdYlBu (diverging, split at 0) | three quantile classes each side of 0 |

  Violet and orange mark circles A and B. That pair passed the colour-blindness validator in light and dark mode. A legend card on the map shows each class's value range.
- **Light / dark mode** toggle, remembered between visits.
- **Analysis page** (`analysis/`): the paper's Table 5 (GWR vs MGWR), Figure 4 (local R² and MGWR coefficient maps) and Figure 7 (index correlation matrix). See [Lama & Sun's statistical analysis](#lama--suns-statistical-analysis-table-5-figures-4-and-7).
- **Council → suburb slicer:** the suburb list follows the chosen council. Choosing a suburb filters the map, legend classes, comparison column and circles to that suburb.
- **Council filter:** pick any council to zoom to it and hide the rest. Colour classes are recomputed within that council, the panel's comparison column switches to it, and circles count only its residents.
- **Lama & Sun (2026) maps:** Exposure, Sensitivity, Adaptive capacity, Flood Resilience Index (FRI), Damage index and Integrated FRI (IFRI). These are the six maps in the paper's Figures 5 and 6, shown in five classes (quintiles). The panel also gives each circle's resident-weighted FRI, Damage and IFRI.
- **Suburbs** (ABS Suburbs and Localities 2021):
  - dashed outlines, with labels that appear as you zoom in
  - a "Find a suburb" box that zooms the map to a suburb
  - suburb names in tooltips and under each circle's resident count
- **Self-contained output:** one HTML file per page with the data inlined. It works offline apart from the basemap tiles and the MapLibre/D3 libraries, which load from CDNs.

## Repository layout

```
.
├── .github/
│   ├── workflows/pages.yml   # CI: fetch -> build -> bundle -> (PR) screenshots / (main) deploy
│   └── scripts/screenshot.py # headless-Chromium previews of the built pages
├── pipeline/
│   ├── config.py        # study areas (west, metro) and Lama & Sun weights
│   ├── 01_fetch.py      # downloads public inputs -> data/raw/<study>/, data/raw/gcp/, data/raw/shared/
│   ├── 02_build.py      # SA1 + mesh-block + suburb data and indices -> data/processed/<study>.json
│   ├── lamasun_stats.py # VIF, GWR and MGWR (Lama & Sun Table 5, Fig. 4)
│   └── 03_bundle.py     # inlines each dataset into web/template.html -> dist/index.html, dist/metro/index.html
├── web/
│   ├── template.html    # the explorer (MapLibre GL JS map + D3 panel, no build step)
│   └── analysis.html    # Table 5, Fig. 4 coefficient maps, Fig. 7 correlation matrix
├── papers/              # the two source papers (CC BY 4.0)
├── snapshots/           # frozen builds, e.g. the first published prototype (open in a browser)
├── docs/
│   ├── ARCHITECTURE.md  # code guide: data flow, every file, JSON contract, deliberate oddities
│   └── PROJECT_LOG.md   # history, decisions and open questions
├── CHANGELOG.md
├── CONTRIBUTING.md      # setup, local build, checks, pull-request flow
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

Some inputs are **optional**: mesh-block resident counts, Vicmap Address points, the elevation model and soil sand. If a download fails, the build carries on and records the substitution in the page footer. For example, "Mesh-block counts unavailable: residents placed on Residential mesh blocks in proportion to area".

Run every command from the repository root.

**Network hosts the pipeline needs:** `geo.abs.gov.au`, `www.abs.gov.au`, `opendata.maps.vic.gov.au`, `copernicus-dem-30m.s3.amazonaws.com` and `maps.isric.org`. Add these to the environment's allowed domains in Claude Code on the web, or on a restricted network. The page itself loads MapLibre GL JS from `cdn.jsdelivr.net`, D3 from `cdnjs.cloudflare.com`, basemap tiles from `basemaps.cartocdn.com` and fonts from Google Fonts.

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
   - `metro` is the 31 Greater Melbourne councils: Merri-bek appears under its ASGS 2021 name, Moreland. Its planning overlays are fetched under the current name, Merri-bek.
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
3. **Flood overlays and who is inside them.** The Vicmap Planning `plan_overlay` layer is filtered to LSIO and FO (riverine) and SBO (overland flow), then dissolved.
   - **Since v0.5, exposure is measured on residents, not land.** Every Vicmap Address point (one per property or unit) is joined to its mesh block and flagged if it lies inside an overlay.
   - A mesh block's in-overlay share is the share of its **addresses** inside the overlay. A mesh block without addresses falls back to its area share.
   - Each SA1's share is the resident-weighted mean over its mesh blocks. The old area share is kept in the data as `fa` for comparison.
   - **Why it matters:** a mesh block or SA1 beside a creek often contains a reserve that is the only part in the overlay. By area it looks exposed; by where people live, it often isn't.
   - **Measured on the published build:** the area measure overstated residents in overlays by **50%** in Maribyrnong + Moonee Valley (10,721 → 7,170) and by **29%** across Greater Melbourne (239,650 → 185,538).
   - 824 metro SA1s dropped by more than 5 percentage points, and 191 rose. Some SA1s have housing in a narrow overlay strip, which the area share understated.
   - Example: SA1 21303134845 in Footscray has 48% of its area in an overlay but about 1% of its residents.
   - If the address layer can't be fetched, the build falls back to mesh-block area shares, still resident-weighted, and says so in the page footer.
4. **Mesh-block weighting.** This replaced the v0.1 50 m grid, which spread people evenly.
   - Each ABS 2021 mesh block gets a weight: its share of its SA1's residents, from the ABS Mesh Block Counts.
   - If that file can't be downloaded, residents go onto Residential mesh blocks in proportion to their area.
   - Each mesh block also records its category and the share of its area inside riverine and overland-flow overlays.
5. **Circle aggregation (in the browser).** A circle counts the mesh blocks whose representative point is inside it.
   - Each SA1 contributes its counts multiplied by the summed weight of those mesh blocks.
   - "Residents in overlay" uses the same weights, multiplied by each mesh block's overlay share.
   - Age–sex shares are assumed constant within an SA1, because mesh blocks carry no age data.
6. **Suburbs.** Each SA1 is assigned to an ABS Suburb and Locality (SAL 2021) by its representative point.

## How accurate is the data, and how it was tested

Accuracy here has three parts:

- **Where** things are: boundaries and flood extents.
- **How many** people are counted.
- **Whether the method reproduces the paper.**

Each check below runs on every build unless marked otherwise. Anything not tested is listed at the end, because that's where the real limits are.

### Checks that run on every build (the build fails or warns)

| Check | What it guards against | Result on the published build |
|---|---|---|
| **Council coverage:** for every council, the area of its SA1s is compared with the council's own boundary. Outside 97–103% it warns; outside 90–110% the build **fails**. | Missing or duplicated SA1s, e.g. a truncated download | Passes for all 31 councils; 11,293 SA1s. Knox is at 103.8%, just over the warning line, because a few SA1s straddle its boundary. |
| **Population reconciliation:** residents placed by mesh-block counts are compared with the Census SA1 total. | Mesh blocks lost in the join, or counts from the wrong release | 207,015 vs 207,058 (two councils) and 4,833,357 vs 4,833,389 (metro): within 0.02%. The gap is ABS perturbation, the small random noise ABS adds for privacy. |
| **Address download completeness:** points received are compared with the server's own `numberMatched`; the build then requires address points in at least 80% of populated mesh blocks, or it falls back to area shares and says so. | A silently truncated download mixing two methods | Added after the first CI run fetched only 5,000 points, because the server caps each page. Caught before publishing. |
| **Geometry repair:** every polygon goes through `make_valid`, and rings are oriented clockwise on export. | Self-intersections that crash overlays; maps that render as "the whole world" | Found and fixed real defects in the metro SA1s (see CHANGELOG 0.3.1 and 0.4.0) |
| **Regression guards:** coefficients are checked for blow-ups, MGWR for divergence, and VIF is reported. | Publishing numerically meaningless coefficients | Caught a locally constant soil layer (sand coefficient about 10¹⁵) and dropped it; MGWR then converged |
| **Fallback notes:** every optional input that fails is named in the page footer. | Silent substitution | Visible on each page |

### Checks against the paper (same 474 SA1s)

| Quantity | Lama & Sun (2026) | This build |
|---|---|---|
| Number of SA1s in Maribyrnong + Moonee Valley | 474 | 474 |
| FRI range | −0.148 to 0.228 | −0.168 to 0.272 |
| Maximum Exposure (of a possible 0.047) | 0.043 | 0.047 |
| MGWR better than GWR? | yes (R² 0.767 vs 0.755) | yes (R² 0.444 vs 0.218; lower because the response is now residents, not land) |

The ranges agree closely, even though three inputs are public substitutes:

- flood depth → planning overlays
- 10 m DEM → Copernicus 30 m
- 30 m soil grid → SoilGrids 250 m

Lower R² is expected: the response variable is a stand-in for their flood depths.

### Checks run during development (not automated)

- **Screenshots of every page on every pull request** (CI → `ci-preview` branch). They were reviewed before merging and caught:
  - the council filter zooming out to the world map
  - blank coefficient maps
  - circles left outside a filtered council
  - exploding GWR coefficients
- **Synthetic tests** of the regression guard (a piecewise-constant covariate reproduces the blow-up and the guard removes it) and of the address-point step (random points in mesh blocks, compared with the area-share result).
- **Interaction tests in headless Chromium:** every variable in the menu gets its own legend; the council → suburb slicer narrows the list and filters the map; pins move inside the filtered area.

### Spatial precision, stage by stage

| Stage | Precision |
|---|---|
| Boundaries downloaded from ABS | generalised to about 2 m (two councils) or 6 m (metro) |
| Boundaries drawn on screen | simplified to 4 m (two councils) or 12 m (metro), to keep the metro page loadable; coordinates rounded to about 1 m |
| Flood overlays | Vicmap Planning polygons as gazetted; the planning-scheme maps are their source of truth |
| Who is inside an overlay | Vicmap Address point per property or unit (v0.5); before v0.5, mesh-block area |
| Age and sex | SA1 only (about 400 people). **Nothing finer exists publicly.** |

### What is *not* tested, and the limits that follow

- **No ground truth for flooding.** Overlays are planning controls, not observed or modelled water. No one has validated them here against the October 2022 flood extent, and no depth is available.
- **No unit-test suite.** The checks above are integration checks on live data.
- **Circles apportion; they don't observe.** A circle's age mix is its SA1s' mix weighted by residents. Below roughly 500 m radius, treat pyramids as indicative.
- **Address points count every property equally,** so a house, a flat and a shop each count as one. Commercial addresses in overlays can slightly inflate exposure in mixed-use blocks.
- **Live sources change.** DataVic republishes overlays when planning amendments are gazetted, so a rebuild can differ slightly from the published version.

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

### Lama & Sun's statistical analysis (Table 5, Figures 4 and 7)

Implemented in `pipeline/lamasun_stats.py` and shown on the `analysis/` page.

| Paper element | What it is | Reproduced here |
|---|---|---|
| Section 2.2.3, Table 5 | GWR and MGWR, flood depth ~ 10 indicators; R², adjusted R², AICc, bandwidth | Yes, with PySAL `mgwr` (adaptive bisquare kernel, AICc golden-section search, standardised variables), shown beside the paper's values |
| Figure 4a | Local R² map | Yes. It comes from the MGWR model where the library provides it, and from GWR otherwise; the page says which |
| Figures 4b–k | MGWR local coefficient maps | Yes: ten small-multiple maps, with SA1s that aren't significant (multiple-testing corrected) greyed out |
| Figure 7 | Scatter matrix of Exposure, Sensitivity, Adaptive capacity, FRI, Damage and IFRI with Pearson's r and adjusted R² | Yes, on both pages |

**Response variable.** The paper contradicts itself here:
- Section 2.2.3 says flood depth is the dependent variable.
- Section 3.2 says the model explains IFRI, with flood depth as one of the inputs.

This build follows 2.2.3, for two reasons:
- Figure 4 has ten coefficient maps (b–k), which matches ten explanatory variables.
- IFRI is a deterministic function of those same inputs, so regressing it on them would give an R² near 1, not the reported 0.72.

**The results aren't comparable with the paper's,** because the response is the overlay-share proxy, which is zero for most SA1s, instead of HEC-RAS depth. The page says so beside the table.

**Result on real data (two councils, 474 SA1s, v0.5: response = share of residents in an overlay):**
- **GWR:** R² 0.218, adjusted R² 0.152, AICc 1310.7, bandwidth 291 SA1s. The paper reports 0.755, 0.684, 916.1 and 62.
- **MGWR:** R² 0.444, adjusted R² 0.364, AICc 1206.3. The paper reports 0.767, 0.724 and 831.6.
  - Only the intercept and land use vary locally (bandwidth 51 SA1s).
  - Elevation is regional (327).
  - The other eight are global (473 SA1s).
- **As in the paper, MGWR beats GWR** on every fit statistic.
- **Elevation is the one clear, stable effect.** It is negative and significant in every SA1: lower ground has more residents inside overlays, as it should.
- **Why the fit dropped from v0.4** (then GWR 0.526, MGWR 0.647, on the *area* share): much of the old area share was parks and creek reserves. Land cover explains those well, and they had nothing to do with where people live. The resident-based response is the harder and more honest target.
- **The sand history.** In v0.4, SoilGrids sand (a 250 m raster) was almost constant inside each GWR neighbourhood, and its coefficient blew up to about 10¹⁵. A guard now detects this, drops the variable and refits, and the page names it. With the v0.5 response, GWR chose a wider bandwidth (291) and sand stayed stable, so nothing was dropped. The guard remains in place.

**Collinearity.** The page reports a variance inflation factor for each variable: population 39.4, dwellings 15.1, employed 53.5, educated 44.9. Population, dwellings, employed, educated and income earners are all counts that grow with SA1 size. Their coefficients can't be interpreted separately wherever VIF is above 10, and that applies to the paper's specification too. The fitted model shows the symptom: population is +0.67 and significant everywhere, while employed (−0.43) and educated (−0.37) pull the other way. That is a suppression pattern, not three real effects.

**Scope.** GWR and MGWR run on the two-council study area (474 SA1s, about 12 minutes on 4 cores). They aren't run on the 11,293 metro SA1s, because MGWR's cost grows with the square of the number of units. The correlation matrix is computed for both pages.

**Assumptions the paper leaves open, and the choices made here:**
- **Direction for elevation and sand.** The paper doesn't say whether low elevation or high sand is inverted before weighting. Its text implies both should be (low ground and clay soils flood). Their highest Exposure score, 0.043 out of a possible 0.047, is in low-lying Flemington. That only makes sense if low elevation scores high. Both are inverted here.
- **Classes.** The paper maps five classes without naming the method, which is probably natural breaks. Quintiles are used here, so class boundaries won't match the published figures exactly.
- **Normalisation scope.** For `metro`, indicators are normalised across all 11,293 SA1s, so its index values aren't comparable with the two-council page.

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

- **Apportionment is still an estimate.** Mesh blocks (v0.3) put people where they actually live, down to about 30–60 residents per block, and address points (v0.5) place them inside each block for flood exposure. But a circle includes a whole mesh block or none of it, and age–sex shares are assumed constant within each SA1. Every address point counts equally, so a house, a unit and a shop are each weighted as one. The v0.1 even-spreading error, which showed 0 riverine-overlay residents at Avondale Heights, should shrink. That needs re-checking on the first live build.
- **Overlays are planning controls, not flood modelling.** They show extent only, with no depth, and they don't match the October 2022 event the papers simulated.
- **Coarse age data.** Age–sex data stops at SA1 level, about 400 people. Below roughly 500 m radius, a circle's pyramid is mostly apportionment artefact.
- **No SEIFA yet.** Income is a population-weighted mean of SA1 medians, which isn't a true median.
- **Metro page size.** 14 MB (about 3 MB compressed), because every SA1 outline is inlined. MapLibre draws them quickly once loaded, but the first load is slow on phones. Vector tiles (PMTiles) are the next fix.
- **ABS perturbation.** Small random adjustments mean totals differ slightly between tables.

## Roadmap

Ordered by how much each step changes the numbers, not the look.

1. **Repository hygiene.** *(done, v0.2)* Layout matches the commands, papers in `papers/`, and this README. Next: SHA-256 manifest of raw inputs, and `01_fetch.sh` fails loudly on an empty or HTML download.
2. **Dasymetric weighting from mesh blocks.** *(done, v0.3; address-point refinement done in v0.5 with Vicmap Address; the mesh-block view mode is still open)* ABS 2021 mesh blocks (about 30–60 residents each) publish real **population and dwelling counts** and a **land-use category** (Residential, Parkland, Industrial…). That makes them the best public weight layer: parks and industrial blocks get their true, usually near-zero, population, not an even share. Within each mesh block, split further by G-NAF residential address points or building footprints. Mesh blocks carry **no age–sex data**, so a circle's pyramid is still built from SA1 age shares, now weighted by where people actually live. Check that SA1 totals are preserved within ABS perturbation, then report how the A/B figures and in-overlay counts change.
   - **Mesh-block view mode.** A third geography next to SA1 and circle, answering "who lives *here*". The panel shows mesh-block population, dwellings and category, plus the age pyramid of the parent SA1, labelled as *inherited*, never as the mesh block's own.
3. **Reproduce the Lama & Sun indicators.** *(done, v0.3; the sensitivity checks below are still open)* Add elevation, sand %, land use, education and the income bracket. Compute FRI, Damage Index and IFRI with their AHP weights. Map them next to the pyramids, and run the sensitivity checks above.
4. **MapLibre GL JS plus a real basemap.** *(done, v0.4: CARTO basemap, council filter, per-variable symbology; the Circle/Compare/Density modes and PMTiles are still open)* Replace the inline SVG map. SA1s become a vector source. Circles become draggable GeoJSON using Turf.js `circle` and `booleanPointInPolygon`. Basemap: OpenFreeMap or CARTO Positron/Dark Matter (no key), or MapTiler/Mapbox with a key kept out of git. Add the video's **Circle / Compare / Density** modes. Parcels mode depends on step 2.
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
| `mgwr` (PySAL) | GWR and MGWR (Table 5, Figure 4) | in `requirements.txt` |
| `rasterio`, `openpyxl` | Elevation/sand sampling; reading the mesh-block counts workbook | in `requirements.txt` |
| MapLibre GL JS 4.7 | Map engine and basemap (v0.4) | CDN: `cdn.jsdelivr.net/npm/maplibre-gl@4.7.1` |
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
| Microsoft Global ML Building Footprints (Australia) | Building density; residential-only filtering of address points | Microsoft (ODbL) | Yes |
| Tree canopy extent | Vegetation density | DataVic (DELWP) | Yes |
| Vicmap road casement | Transport density | DataVic | Yes |
| Maribyrnong catchment boundary | The 412-SA1 study area of Lee et al. | Melbourne Water / DEM watershed | Probably |
| HEC-RAS October 2022 depth raster | Real hazard (depth, spread ≥ 0.15 m) instead of overlays | Chayn Sun (RMIT), on request | No |
| Melbourne Water 1% AEP flood extent | Better proxy than planning overlays | Melbourne Water / Jacobs | Licensed |

## Data sources and licences

- **ABS** Census 2021 GCP DataPack (SA1, VIC) and ASGS 2021 boundaries: CC BY 4.0, © Commonwealth of Australia.
- **Vicmap Planning** overlays and **Vicmap Address** points via DataVic: CC BY 4.0, © State of Victoria.
- **ABS** Mesh Block Counts 2021 and Suburbs and Localities 2021: CC BY 4.0.
- **Copernicus GLO-30 DEM:** © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018, provided under COPERNICUS by the European Union and ESA.
- **SoilGrids 2.0 (ISRIC):** CC BY 4.0.
- **Lama & Sun (2026):** CC BY 4.0. The methodology and weights are cited and credited. None of the authors' data is redistributed here.
