# Architecture and code guide

This is the reference for anyone changing the code, including future-you. It explains:

- how the pieces fit together
- what every file does
- the exact shape of the data passed between them
- the non-obvious decisions that will bite if they are undone

For *why* the project exists and how it maps onto the papers, see the [README](../README.md). The story of how it was built is in [PROJECT_LOG.md](PROJECT_LOG.md).

---

## 1. The big picture

```
 public data services                 pipeline (Python)                          browser (static HTML)
 ───────────────────                  ─────────────────                          ─────────────────────
 ABS ASGS 2021 (ArcGIS REST) ─┐
 ABS Census GCP DataPack ─────┤
 ABS Mesh Block Counts ───────┤   01_fetch.py ──► data/raw/<study>/   (cached, git-ignored)
 Vicmap Planning (WFS) ───────┤        │
 Vicmap Address (WFS) ────────┤        │
 Vicmap 10 m DEM, canopy ─────┤        │
 SEIFA, MS buildings ─────────┤        ▼
 Copernicus DEM, SoilGrids ───┘   02_build.py ──► data/processed/<study>.json
                                       │   └─ lamasun_stats.py (GWR / MGWR: SA1s west, SA2s metro)
                                       ▼
                                  03_bundle.py ──► dist/index.html (+ /metro/ redirect)          ◄── web/template.html
                                                   dist/**/analysis/index.html                 ◄── web/analysis.html
                                       │
                                       ▼
                         .github/workflows/pages.yml ──► GitHub Pages
```

There is **no server and no database**. Each page is one self-contained HTML file with its data inlined as JSON. The only network requests a page makes are for:

- D3 (cdnjs)
- MapLibre GL JS (jsdelivr)
- the CARTO basemap

If the basemap is unreachable, the page falls back to a plain background.

There is one **study area**, `metro`, defined in `pipeline/config.py`. The papers' own area is a *preset* inside it:

| key | councils | output | notes |
|---|---|---|---|
| `metro` | all 31 Greater Melbourne councils (11,293 SA1s) | `dist/index.html` | GWR/MGWR on ~300 SA2s (cost grows with n²) |
| `metro.paper` (preset) | Maribyrnong, Moonee Valley (474 SA1s) | same page, council menu | GWR/MGWR on its SA1s (the paper's Table 5); Lama & Sun indices also scaled within it (`lsp`) |

Every pipeline step takes `--study <key>` (default `metro`). Adding a small study to `STUDIES` is the quickest way to iterate. `03_bundle.py` also writes redirects from the retired `/metro/` addresses.

---

## 2. Files

```
pipeline/
  config.py          study areas, council list, Lama & Sun AHP weights
  01_fetch.py        download every input into data/raw/ (cached; delete a file to refetch)
  02_build.py        join, weight and index everything -> data/processed/<study>.json
  lamasun_stats.py   VIF, GWR, MGWR (Lama & Sun Table 5 / Fig. 4)
  03_bundle.py       inline each JSON into the two HTML templates -> dist/
web/
  template.html      the map page (MapLibre + D3): circles, pyramids, filters, legend
  analysis.html      the analysis page: Table 5, Fig. 4 small multiples, Fig. 7 scatter matrix
  scenarios.html     the scenarios page (2036 and sea-level rise); not published until approved
  scenarios_sample.json  invented numbers in the real shape, for designing the page (pipeline/forecast/sample.py)
.github/
  workflows/pages.yml   CI: fetch -> build -> bundle -> screenshot check -> deploy -> clean-up
  scripts/screenshot.py headless-Chromium check and screenshots of the built pages (a page error fails the run)
  scripts/check_circles.py independent recount of the A/B circles against the page's maths
  scripts/screenshot.py also captures mobile_iphone.png and mobile_android.png (device emulation)
  workflows/forecast.yml manual only: forecast inputs + 2016->2021 placement back-test (never deploys)
  workflows/probe.yml   manual only: checks what candidate data sources offer
  workflows/demo.yml    manual only: records the demo from the live site (no build, no deploy)
  scripts/demo_gif.py     captioned ~20 s demo of the built map (GIF + MP4) for sharing; never blocks a deploy
docs/
  ARCHITECTURE.md    this file
  PROJECT_LOG.md     decisions and history
papers/              the two source papers (PDF)
data/static/         inputs with no stable download link, committed: Melbourne Water river basins and
                     waterways/drains catchments (zipped geodatabase, read in place)
snapshots/           the first prototype, frozen
```

### 2.1 `pipeline/config.py`

- `STUDIES[key]` sets:
  - `title`, `label`: the name used for the whole area in the side panel ("Both councils", "All 31 councils")
  - `lgas`: ASGS 2021 council names
  - `out`: output path under `dist/`
  - `simplify_m`: polygon simplification tolerance in metres; this trades page size against edge accuracy
  - `mgwr`: `"SA2"` fits the study-wide model on SA2s
  - `paper`: `{label, lgas}`, the papers' study area, which becomes the map preset `__paper`, a second GWR/MGWR model on its SA1s, and the paper-scaled indices `lsp`
- `norm_lga()` lowercases a name, strips " (Vic.)" and maps Merri-bek to its ASGS 2021 name, Moreland.
- `LAMA_SUN` holds Table 2 of the paper: for each dimension, a list of `(indicator, AHP weight, direction)`. Direction −1 flips the normalised value, so for example lower elevation means higher exposure.
- `DAMAGE_INDICATORS` lists the X terms of the damage index D = Σ flood × X.

### 2.2 `pipeline/01_fetch.py`

| function | what it does | gotcha |
|---|---|---|
| `get`, `get_json` | HTTP with retries and exponential back-off | turns truncated JSON into a clear error |
| `service_url` | finds the ABS ArcGIS service for a layer (names vary: `SA1`, `ASGS2021_SA1`, …) | |
| `arcgis` | pages through an ArcGIS layer with **keyset paging** (`objectid > last`) | offset paging hit 504s at 62,000; the page size halves on failure |
| `wfs_overlays` | LSIO/FO/SBO planning overlays from Vicmap, filtered **by council name** | a BBOX filter returned 0 features; bbox is only the fallback |
| `wfs_layer` | finds a Vicmap layer by regex in GetCapabilities | layer names change between GeoServer releases |
| `wfs_points` | Vicmap Address points, geometry only, saved as a float32 `addr.npy` | tries both axis orders; about 2 M points for metro |
| `HttpRange` | a seekable file over HTTP range requests | lets `zipfile` list and extract single members of a remote zip |
| `canopy` | Vicmap tree extent (20 cm, 0/1/2 = no tree, tree, no data), reduced to 10 m canopy-% grids in `data/raw/shared/canopy10/` | reads only the tiles that overlap the study area, straight from the four statewide zips (Melbourne, Warburton, Port Phillip, Warragul) (`/vsizip//vsicurl/`); ~30 s per tile |
| `buildings` | Microsoft ML building footprints (quadkey tiles from `dataset-links.csv`), saved as `lon, lat, area m², height` | area from degrees² × cos(latitude), which is accurate to well under 1% at building scale |
| `dem10` | Vicmap 10 m DEM from the image service: `exportImage` if allowed, else its LERC elevation tiles at the level nearest 10 m, mosaicked to `dem10.tif` (Web Mercator) | the *shaded relief* service is only a picture and is used as a map layer, not as data |
| `optional` | runs an optional download and only warns on failure | 02_build falls back and records the fallback in `NOTES` |

**Required inputs:** councils, SA1, mesh blocks, suburbs (SAL), overlays and the Census DataPack. A failure here stops the run.

**Optional inputs:** mesh-block counts, address points, the Vicmap 10 m DEM (falls back to Copernicus 30 m), Copernicus DEM, sand, SEIFA, tree canopy and building footprints.

### 2.3 `pipeline/02_build.py`

The script runs top to bottom, one section per `# ----` banner:

1. **Councils and study polygon.**
2. **SA1s:** each is assigned to a council by representative point. A coverage check compares SA1 area with council area for every council. It warns outside 97–103% and **fails outside 90–110%**, which stops a silently incomplete map.
3. **Census tables:** G01, G02, G04, G13, G17, G18, G20, G34, G36, G43 and G46 are joined on `SA1_CODE_2021`. `col()` finds columns by regex, because the short-header names are cryptic.
4. **Suburbs (SAL):** assigned to each SA1 by representative point.
5. **Flood overlays:** `riv` is LSIO ∪ FO, `sbo` is SBO, both clipped to the study polygon. `share_in()` gives each geometry's area share inside a zone.
6. **Mesh blocks:**
   - Residents come from the ABS Mesh Block Counts workbook. The fallback is area-weighted residential mesh blocks, or address counts.
   - `w` is each mesh block's share of its SA1's residents. The circles use it to split SA1 counts.
7. **Address points:**
   - Each Vicmap Address point is joined to its mesh block and flagged if it falls inside `riv` or `sbo`.
   - A mesh block's `riv`, `sbo` and `any` then become the **share of its addresses** inside the overlay, not the share of its area. A mesh block with no addresses keeps its area share.
8. **Resident-weighted SA1 shares:** `rivA`, `sboA` and `anyA` = Σ w × share. This means "share of residents", so a flooded park no longer counts as exposure. `areaA`, the old area share, is kept for comparison.
9. **Rasters:** DEM (Vicmap 10 m if present, else Copernicus 30 m) and sand are sampled at mesh-block points and area-weighted to each SA1.
   - **Tree canopy:** mesh blocks are rasterised onto each 10 m canopy grid, giving a zonal mean per mesh block, then an area-weighted mean per SA1.
   - **Buildings:** footprint centroids are joined to SA1s, giving a count and roof coverage (Σ footprint area ÷ SA1 area).
   - **SEIFA:** `Table 1` of the ABS workbook is parsed by header text, not position, taking the decile column of each of the four indexes.
10. **Lama & Sun indices:**
    - Each indicator is z-scored, then min–max scaled, and flipped where the direction is −1.
    - The scaled indicators are AHP-weighted into Exposure, Sensitivity and Adaptive capacity.
    - FRI = AC − (S + E)
    - DMG = mm(Σ mm(flood × X))
    - IFRI = ½FRI − ½DMG
11. **GWR/MGWR** runs two models, `paper_model()` on the paper area's SA1s and `sa2_model()` on all SA2s. For the SA2 model, counts are summed, the flood share is resident-weighted and physical indicators are area-weighted. It needs at least 60 SA2s. Each model's failure is caught, so the maps still build and the analysis page says so. `stats` is a list of models. See 2.4.
   - **Road casement:** road-reserve share per SA1, by rasterising roads and SA1s at 5 m in 10 km tiles (`polygon_share`).
12. **Output JSON** (schema in section 3). Every polygon goes through `gj()`, which simplifies, reprojects to WGS84, rounds to 5 decimals (about 1 m) and **orients exterior rings clockwise** (see section 5).

Working CRS: **EPSG:7855** (GDA2020 / MGA zone 55), so areas and distances are in metres.

### 2.4 `pipeline/lamasun_stats.py`

`run(ind, coords)` standardises the flood response and ten explanatory variables, then:

1. **Local-singularity guard.** It fits GWR. If any coefficient exceeds 1,000 (impossible on standardised data), it drops the worst covariate and refits. It found SoilGrids sand, which is almost constant inside each neighbourhood.
2. **VIF** for each remaining variable. The count variables are strongly collinear.
3. **MGWR**, with bandwidths floored at 50 SA1s, then **validated**. A diverged fit falls back to GWR, and the page says so.
4. It returns a dict:
   - model fit for both models, next to the paper's Table 5
   - coefficient and significance matrices, corrected for multiple testing
   - local R²
   - VIF
   - the lists of dropped variables (`dropped` for missing data, `unstable` for singular ones)

### 2.5 `pipeline/03_bundle.py`

This script replaces the `__DATA__` placeholder in each template with the JSON. It writes the map page to `dist/<out>` and the analysis page next to it, in `analysis/index.html`.

### 2.6 `web/template.html` (map page)

This is one file, with CSS at the top, then markup, then a script. The script's sections are marked `// ----`:

| section | key names | role |
|---|---|---|
| data | `D`, `S` (SA1 records), `C` (mesh-block tuples), `META` | parsed from the inlined JSON |
| state | `SAVED` | restores the variable, filter, circles and view across a theme switch (sessionStorage) |
| symbology | `METRICS` | one entry per map variable: key, label, value function, formatter, ColorBrewer ramp `r`, `div` for diverging |
| filters | `activeLga`, `activeSub`, `visible(i)`, `fillSuburbs()`, `applyFilter()`, `movePinsInside()` | council → suburb slicer |
| map | `map`, sources `sa1`, `lga`, `sal`, `riv`, `sbo` | MapLibre layers are inserted before the first label that follows the basemap's last non-label layer: above its roads and buildings, below its labels. (Inserting before the *first* label broke light mode, because Positron has a waterway label ahead of its roads.) |
| classes | `recolour()`, `drawLegend()` | quintile breaks (or ±3 classes for diverging) over the **visible** SA1s |
| aggregation | `agg(area)`, `sumW()`, `allAgg()` | what a circle counts |
| tint | `paintTint()` | feature-state opacity = share of each SA1's residents inside a circle |
| panel | `ROWS`, `update()` | the comparison table |
| pyramid | `drawPyr()` | age–sex bars as percentages |

**How a circle counts people.** For every mesh block whose point lies within radius `R` of the pin, the mesh block's resident share `w` is added to its SA1. Each SA1 count is then multiplied by that share. Flood tallies multiply in the mesh block's in-overlay share, which comes from address points where available. This is **apportionment, not observation**: Census age data does not exist below SA1.

### 2.7 `web/analysis.html`

This page reads `D.stats`, which is `null` for metro, and `D.sa1[].ls`. It draws:

- Table 5 and the bandwidth/VIF table
- the Fig. 4 small multiples: one SVG map per coefficient; grey means not significant
- the Fig. 7 scatter matrix: canvas points plus SVG labels

### 2.7.1 `web/scenarios.html` (built, not published)

The page shows residents in flood areas by year (2021, 2026, 2031, 2036) and sea-level scenario (today, +0.2, +0.5, +0.8 m), plus the real placement back-test. It has no map library and no D3: plain SVG, so it loads fast on a phone.

**Data shape** (`data/processed/scenarios.json`, or `web/scenarios_sample.json` until the forecast exists):
- `meta`: `sample` (true shows the "invented numbers" banner), `years`, `base`, `unit` (the area level in the table).
- `slr`: `[{id, label}]`; `id` `"none"` is today's flood areas.
- `total[slr_id][year_index]` and `areas[].v[slr_id][year_index]`: `[central, low, high]`. The total carries its own range because area ranges are not independent and cannot be summed.
- `backtest`: the method table from PROJECT_LOG §25.

**Publishing gate.** `03_bundle.py` writes `dist/scenarios/index.html` only when `data/processed/scenarios.json` exists **and** `PUBLISH_SCENARIOS=1`. A routine or scheduled rebuild therefore never publishes it early. `pipeline/forecast/preview.py` renders it into `preview/` (git-ignored) for review, from the sample when the real file is absent.

### 2.8 CI: `.github/workflows/pages.yml`

The workflow runs on every push to `main`, on manual dispatch, and on a monthly schedule (03:17 UTC on the 2nd). The repository has one branch on GitHub and no pull requests; changes are made in local git worktrees and pushed to `main` (CONTRIBUTING §5).

1. It restores the `data/raw` cache. The key is a hash of `01_fetch.py` and `config.py` plus the current month (`YYYY-MM`), so changing either file, or the month turning, refetches everything. `01_fetch.py` writes `data/raw/<study>/fetched.txt` when it starts a fresh download set; `02_build.py` copies it to `meta.fetched`. In CI `STRICT_FETCH=1` (every run) makes any failed optional download fatal, so nothing is deployed from a partial fetch; `get_json` retries cut-off responses first. The first full fetch takes about 70 minutes.
2. It fetches and builds `metro`, then bundles the map, the analysis page and the `/metro/` redirects.
3. It opens both pages in headless Chromium with `screenshot.py`. A page error fails the run. The screenshots are uploaded as the run's `screenshots` artifact, kept 14 days.
4. It records `demo_gif.py` (a captioned demo, GIF and MP4, into the `screenshots` artifact; a failure here is ignored). It runs `check_circles.py`, which recounts the A/B circles independently and drives a real pin drag and click; any mismatch fails the run. The page exposes `window.__test` (its own `agg`, filter, pin positions and screen projection) for this script only.
5. **Only if every step passed**, it uploads `dist/` and deploys it to Pages. A failed run leaves the live site on its last good version.
6. **Clean-up (after a successful deploy only).** It deletes every `github-pages` deployment record except the one just made, and every completed run of this workflow except the newest `KEEP_RUNS` (5, counting the current run). Deleting a run deletes its logs and artifacts too. Each deletion that fails is logged as a warning and never fails the run.

---

## 3. Data contract: `data/processed/<study>.json`

```jsonc
{
  "meta": {
    "presets": [{"key": "__paper", "label": "...", "lgas": [...]}],   // extra entries in the council menu
    "study": "west", "title": "...", "label": "Both councils", "n": 474,
    "lat0": -37.77,            // for the equirectangular distance used by circles
    "addr": true,              // address points were used for flood shares
    "fetched": "2026-10-02",   // when the live inputs were downloaded (null if unknown)
    "built": "2026-10-02",     // when 02_build.py ran
    "notes": ["..."],          // every substitution and fallback, shown in the page footer
    "other": ["All of Melbourne", "metro/"]
  },
  "sa1": [{                    // one per SA1; the index i is the id used everywhere else
    "id": "21301...", "sa2": "...", "sub": "Footscray", "lga": "Maribyrnong", "km2": 0.21,
    "M": [18 ints], "F": [18 ints],        // males/females by 5-year band, 0-4 ... 85+
    "pop": 412,
    "nfa": 0, "nfa_d": 0,      // need for assistance / its denominator (valid answers)
    "ltc": 0, "ltc_d": 0,      // long-term health condition
    "emp": 0, "unemp": 0, "lf": 0, "eng": 0, "eng_d": 0, "car0": 0, "car_d": 0,
    "d_house": 0, "d_semi": 0, "d_flatlow": 0, "d_flathigh": 0, "d_other": 0, "inc": 1500,
    "riv": 0.12, "sbo": 0.03,  // share of residents in riverine / overland-flow overlays
    "fl": 0.14,                // share of residents in any overlay (not riv + sbo: they overlap)
    "fa": 0.20,                // share of AREA in any overlay (the pre-v0.5 measure)
    "can": 12.3,               // % tree canopy (null if unavailable)
    "bcov": 0.31, "bn": 145,   // roof coverage share, building count (null if unavailable)
    "seifa": [3, 4, 2, 5],     // IRSD, IRSAD, IER, IEO deciles (1 = most disadvantaged); null if unavailable
    "road": 0.23,              // share of area in road casement (null if unavailable)
    "basin": "Maribyrnong",    // Melbourne Water river basin ("" outside all)
    "drain": "Ascot Vale M.D. → Maribyrnong River",   // drainage chain (absent if unknown)
    "lsp": [...],              // paper-area SA1s only: the six indices scaled within the paper's 474 SA1s
    "ls": [E, S, AC, FRI, DMG, IFRI]   // Lama & Sun indices, null where undefined
  }],
  "shapes": [GeoJSON geometry per SA1, same order as sa1],
  "mb": [[lon, lat, i, w, riv, sbo]],  // mesh-block point, SA1 index, resident share, in-overlay shares
  "riv": GeoJSON, "sbo": GeoJSON,     // overlay polygons for display
  "lga": [{"name": "...", "g": GeoJSON}], "basins": [...], "catchments": [...],   // same shape "sal": [{"name": "...", "g": GeoJSON}],
  "stats": [ { see lamasun_stats.run(), plus "title", "unit": "SA1" | "SA2", and "idx" (SA1 indices) or "units": [{"name", "g"}] } ]
}
```

Records are positional, so the order of `sa1` and `shapes` must stay aligned. `mb[][2]` refers to that index.

---

## 4. Common changes

**Add a map variable**
1. If it's a new Census field, add it to `recs` in `02_build.py`, and to the `keys` list in `sumW()` if circles should sum it.
2. Add an entry to `METRICS` in `template.html`, with its own ColorBrewer ramp. Violet and orange are reserved for the circles.

**Add a study area**
1. Add a `STUDIES` entry with ASGS 2021 council names.
2. Add fetch/build steps for it in `pages.yml`.
3. Add a link in `meta.other`.

**Change an index weight:** edit `LAMA_SUN` in `config.py`. Nothing else hard-codes the weights.

**Swap the flood input**, for example for modelled 1% AEP extents: produce `riv`/`sbo` polygons in section 5 of `02_build.py`. Everything downstream (addresses, shares, indices, circles) follows automatically.

**Run just the front end on existing data:** `python pipeline/03_bundle.py` after editing `web/*.html`. There's no need to refetch or rebuild.

---

## 5. Things that look wrong but are deliberate

- **Clockwise rings** (`gj()`): D3's spherical maths reads an anticlockwise ring as "the whole globe minus this shape". Undoing this zooms the council filter out to the whole world and blanks the analysis maps.
- **Filtering overlays by council name, not bbox:** the Vicmap WFS returned nothing for BBOX queries on `plan_overlay`.
- **Keyset paging and `page_max=10` for councils:** offset paging timed out, and full-detail council polygons in larger pages arrived truncated.
- **`make_valid` in `read()`:** metro SA1s contain self-intersections that crash GEOS overlays.
- **The MGWR bandwidth floor of 50 and the validity check:** without them, the first real run diverged to R² ≈ −10²⁰.
- **Sand can vanish from the regressions:** see `unstable` in the analysis page note. That is the guard working.
- **Circles tint every SA1 they touch** instead of clipping at the circle's edge. Clipping would imply sub-SA1 precision that Census age data doesn't have (see PROJECT_LOG §6).
- **Pyramids use percentages:** otherwise a denser circle just looks bigger.
