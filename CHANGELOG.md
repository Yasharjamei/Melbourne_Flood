# Changelog

Notable changes to the explorer and its pipeline. Dates are when a change landed on `main`.

## [0.4.0] - 2026-09-25

### Added
- **Basemap.** The map is now drawn with MapLibre GL JS (WebGL) over CARTO Positron, or Dark Matter in dark mode. Data layers sit under the basemap's labels, and there's a toggle to hide the basemap. If the basemap host can't be reached, the page falls back to a plain background.
- **Council filter.** Zooms to one council and hides the others. Colour classes, the comparison column and circle counts all switch to that council.
- **Per-variable symbology.** Each of the 17 variables has its own ColorBrewer scheme. The near-white step is dropped, so a low class never looks like "no data". FRI and IFRI use two different diverging red–blue schemes split at zero. A legend card shows each class's value range.
- **Council → suburb slicer.** Choosing a council narrows the suburb list. Choosing a suburb filters the map to that suburb's SA1s and outlines it, and the colour classes, comparison column and circle counts switch to the suburb.
- **Grouped "Show on map" menu**, replacing two rows of buttons.
- **Light and dark mode toggle.** It's remembered between visits, swaps the basemap too, and keeps the chosen variable, council, circles and view across the switch.
- **Analysis page** (`analysis/`, one per study area), reproducing the rest of Lama & Sun's statistical results:
  - **Table 5:** GWR vs MGWR fit (R², adjusted R², AICc, bandwidth), next to the paper's values.
  - **MGWR by variable:** bandwidth, share of SA1s significant (multiple-testing corrected), coefficient range, and **VIF**, since the paper's count indicators are strongly collinear.
  - **Figure 4:** local R² and ten coefficient maps as small multiples. SA1s that aren't significant are grey.
  - **Figure 7:** a 6×6 scatter matrix of the indices, with Pearson's r and adjusted R².
- **MGWR safeguards.** Bandwidths are floored at 50 SA1s, and the result is validated. The first real-data run chose bandwidths of 10–16 and diverged to R² = −3.7 × 10²⁰, with singular local matrices from collinear counts (VIF: employed 53.5, educated 44.9, population 39.4, dwellings 15.1). If MGWR still doesn't converge, the page says so and shows GWR coefficients instead.
- **Polygons oriented clockwise on export.** D3's spherical maths read anticlockwise rings as "the whole globe", which zoomed the council filter out to the world map and blanked the Figure 4 maps.
- **`pipeline/lamasun_stats.py`:** GWR and MGWR (PySAL `mgwr`, adaptive bisquare kernel, standardised variables). It runs on the two-council study area only, because MGWR's cost grows with the square of the number of SA1s.

### Fixed (found in the pre-merge screenshots)
- **GWR coefficients blew up for Intercept and Sand** (means of about 10¹¹ and 10¹⁵). SoilGrids sand is a 250 m raster, so it barely varies inside a 159-SA1 neighbourhood. That makes it collinear with the local intercept. GWR now checks its own coefficients (on standardised data none should come near 1,000), drops the worst covariate and refits. The analysis page names any variable dropped this way.
- **Filtering to a council left both circles outside it**, so A and B showed 0 residents. Pins outside the filtered area now move to the most populous visible SA1, and the other pin goes at least three radii away, or as far as the area allows.

### Changed
- **Circle colours** are now violet (A) and orange (B). The pair passed colour-blindness checks in light and dark mode, and no map palette uses those two hues.
- **Suburb labels** use the basemap's own fonts, and names appear from zoom 11.5.
- **CI screenshots** now wait for the map to finish loading, and include a Casey IFRI view of the metro page.

## [0.3.1] - 2026-09-25

### Investigated
- **Report: "the Greater Melbourne page doesn't cover all of Greater Melbourne."** The first suspect was geometry repair. `buffer(0)` can drop part of a self-crossing polygon, and the council boundaries were downloaded pre-simplified. The new coverage check disproved it: all 31 councils are 99.6–103.8% covered by their SA1s, and the build has 11,293 SA1s both before and after the change. **No SA1s were missing in 0.3.0.** The likely visual cause is under review: SA1s in the lightest class and SA1s with fewer than 10 residents looked like empty background.

### Changed (hardening kept from the investigation)
- Geometry is repaired with `make_valid`, which can't lose area, instead of `buffer(0)`.
- Council boundaries are downloaded at near-full detail (1 m), 10 at a time.
- **Coverage check in `02_build.py`:** reports SA1 count and area coverage per council; warns outside 97–103% and fails the build outside 90–110%.
- **Sturdier ABS downloads:** layers are paged by object ID (`objectid > last`) instead of by record offset, after a 504 at offset 62,000. Truncated or failed pages are retried at half size.
- **CI previews:** pull-request builds push screenshots and the built pages to the `ci-preview` branch.

## [0.3.0] - 2026-09-25

### Added
- **Greater Melbourne page** (`/metro/`): all 31 metropolitan councils (11,293 SA1s, 58,563 mesh blocks, 543 suburbs), built from the same pipeline. The two-council page stays at `/` and links across.
- **Lama & Sun (2026) index maps**, following the paper's Table 2 weights and Appendix formulas:
  - Exposure, Sensitivity, Adaptive capacity
  - FRI = Adaptive capacity − (Sensitivity + Exposure)
  - Damage index
  - IFRI = 0.5·FRI − 0.5·Damage index

  Shown in five quintile classes. Each circle also gets resident-weighted FRI, Damage and IFRI in the panel.
- **New indicators** for those indices:
  - educated population (G43)
  - "mean income generating population", meaning persons earning $1,750–$1,999 a week (G17), which is exactly the paper's $91,000–$103,999 bracket
  - elevation (Copernicus GLO-30)
  - soil sand (SoilGrids)
  - urban land share from mesh-block categories
- **Suburbs** (ABS Suburbs and Localities 2021):
  - outlines, with labels that appear as you zoom in
  - a "Find a suburb" box
  - suburb names in tooltips and circle captions
- **SA1 shading under each circle**, darker where more of its residents are counted, plus a tooltip line with the counted share.
- **`pipeline/config.py`**: study areas and index weights in one place.
- **CI** builds both pages on every pull request, so pipeline changes are tested on live data before they reach `main`.

### Fixed during CI verification
- Flood overlays: filter by council name; a CQL bounding-box filter returned nothing.
- Census G43: real column names are `non_sch_qual_*`. Certificates are counted once, through `CertTot`.
- Geometries repaired on load; server-side simplification had left invalid council boundaries.
- Mesh-block counts workbook parsed by its `MB_CODE_2021` and `Person` columns only, so title and footer rows are skipped.

### Changed
- **Mesh-block weighting replaces the 50 m even-spread grid.** Residents are placed using ABS Mesh Block Counts, or Residential mesh-block area if the counts can't be downloaded. In the verified build the counts cover 207,015 of 207,058 residents (two councils) and 4,833,357 of 4,833,389 (metro). Circle figures for the default A/B comparison move slightly as a result.
- **`pipeline/01_fetch.sh` is replaced by `pipeline/01_fetch.py`** (pure Python):
  - pages through ABS and DataVic services
  - caches downloads
  - treats mesh-block counts, DEM and sand as optional, with fallbacks recorded in the page footer
- **Circles are drawn as outline rings** instead of translucent discs.
- **Zoom range** extended to 40× for suburb-level views on the metro page.

## [0.2.0] - 2026-09-25

### Added
- GitHub Pages workflow (fetch → build → bundle → deploy).
- `papers/` with both source papers, and `docs/PROJECT_LOG.md`.
- `snapshots/2026-09-25-prototype.html`, the original published prototype.

### Changed
- Scripts moved into `pipeline/` and `web/` so the documented commands work.
- Downloads fail loudly on HTTP errors.

### Removed
- Template PyPI and SLSA workflows that didn't apply to this repo.

## [0.1.0] - 2026-09-25

### Added
- First prototype, for Maribyrnong and Moonee Valley (474 SA1s):
  - two draggable circles
  - an overlaid age–sex pyramid
  - an indicator table
  - flood-overlay context
