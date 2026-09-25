# Changelog

Notable changes to the explorer and its pipeline. Dates are when a change landed on `main`.

## [0.3.0] - 2026-09-25

### Added
- **Greater Melbourne page** (`/metro/`): all 31 metropolitan councils (about 10,000 SA1s), built from the same pipeline. The two-council page stays at `/` and links across.
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

### Changed
- **Mesh-block weighting replaces the 50 m even-spread grid.** Residents are placed using ABS Mesh Block Counts, or Residential mesh-block area if the counts can't be downloaded. Circle figures for the default A/B comparison move slightly as a result.
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
