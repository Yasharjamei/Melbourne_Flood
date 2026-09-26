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
 Vicmap Address (WFS) ────────┤        ▼
 Copernicus DEM, SoilGrids ───┘   02_build.py ──► data/processed/<study>.json
                                       │   └─ lamasun_stats.py (GWR / MGWR, two-council study only)
                                       ▼
                                  03_bundle.py ──► dist/index.html, dist/metro/index.html      ◄── web/template.html
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

There are two **study areas**, defined in `pipeline/config.py`:

| key | councils | output | notes |
|---|---|---|---|
| `west` | Maribyrnong, Moonee Valley (474 SA1s) | `dist/index.html` | the papers' own study area; runs GWR/MGWR |
| `metro` | all 31 Greater Melbourne councils (11,293 SA1s) | `dist/metro/index.html` | GWR/MGWR skipped: cost grows with n² |

Every pipeline step takes `--study <key>`.

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
.github/
  workflows/pages.yml   CI: fetch -> build -> bundle -> (PR) screenshots / (main) deploy
  scripts/screenshot.py headless-Chromium screenshots of the built pages, for PR review
docs/
  ARCHITECTURE.md    this file
  PROJECT_LOG.md     decisions and history
papers/              the two source papers (PDF)
snapshots/           the first prototype, frozen
```

### 2.1 `pipeline/config.py`

- `STUDIES[key]` sets:
  - `title`, `label`: the name used for the whole area in the side panel ("Both councils", "All 31 councils")
  - `lgas`: ASGS 2021 council names
  - `out`: output path under `dist/`
  - `simplify_m`: polygon simplification tolerance in metres; this trades page size against edge accuracy
  - `mgwr`: whether to run the regressions
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
| `optional` | runs an optional download and only warns on failure | 02_build falls back and records the fallback in `NOTES` |

**Required inputs:** councils, SA1, mesh blocks, suburbs (SAL), overlays and the Census DataPack. A failure here stops the run.

**Optional inputs:** mesh-block counts, address points, DEM and sand.

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
9. **Rasters:** DEM and sand are sampled at mesh-block points and area-weighted to each SA1.
10. **Lama & Sun indices:**
    - Each indicator is z-scored, then min–max scaled, and flipped where the direction is −1.
    - The scaled indicators are AHP-weighted into Exposure, Sensitivity and Adaptive capacity.
    - FRI = AC − (S + E)
    - DMG = mm(Σ mm(flood × X))
    - IFRI = ½FRI − ½DMG
11. **GWR/MGWR:** only when `ST["mgwr"]`; see 2.4.
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
| map | `map`, sources `sa1`, `lga`, `sal`, `riv`, `sbo` | MapLibre layers are placed under the basemap's labels |
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

### 2.8 CI: `.github/workflows/pages.yml`

The workflow runs on pull requests, on pushes to `main` and on manual dispatch.

1. It restores the `data/raw` cache. The key is a hash of `01_fetch.py` and `config.py`, so changing either refetches everything.
2. It fetches and builds `west`, then `metro`, then bundles both.
3. **On a pull request:** it takes screenshots with `screenshot.py` and force-pushes them to the `ci-preview` branch for review. Nothing is deployed.
4. **On `main`:** it uploads `dist/` and deploys it to Pages.

---

## 3. Data contract: `data/processed/<study>.json`

```jsonc
{
  "meta": {
    "study": "west", "title": "...", "label": "Both councils", "n": 474,
    "lat0": -37.77,            // for the equirectangular distance used by circles
    "addr": true,              // address points were used for flood shares
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
    "ls": [E, S, AC, FRI, DMG, IFRI]   // Lama & Sun indices, null where undefined
  }],
  "shapes": [GeoJSON geometry per SA1, same order as sa1],
  "mb": [[lon, lat, i, w, riv, sbo]],  // mesh-block point, SA1 index, resident share, in-overlay shares
  "riv": GeoJSON, "sbo": GeoJSON,     // overlay polygons for display
  "lga": [{"name": "...", "g": GeoJSON}], "sal": [{"name": "...", "g": GeoJSON}],
  "stats": null | { see lamasun_stats.run() }
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
