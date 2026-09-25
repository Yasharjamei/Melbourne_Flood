# Project log

A record of how this project got here and why each decision was made, so none of it lives only in chat history.

## 1. Idea (before this repo)

**Inspiration: a Mashhad "Demographic Explorer" web map** (screen recording, not stored here). Described from notes:
- Dark Mapbox basemap. Urban blocks are shaded by a population measure. Place labels include Mashhad, Imam Reza Town, Torghabeh and Kashaf.
- **Compare mode:** drop two circles, A and B, and drag them around. A side panel updates live for each circle: total population, a male/female donut and an age–sex pyramid.
- Other tabs cover literacy, employment by sex, housing, area, building structure and building materials.
- A bottom bar switches between **Circle / Compare / Density / Parcels** modes.
- The point it makes: pyramid shapes change sharply between neighbourhoods, and a city-wide average hides that.

**Why it transfers to the flood papers:** both papers reduce vulnerable people to one percentage per SA1. Lama & Sun's "dependent population" puts under-20s and over-59s together. A pyramid under a flood layer separates them. A suburb of toddlers and a suburb of 80-year-olds need different evacuation plans even when their "dependent %" is identical.

**What doesn't transfer:**
- *Coarser data.* Australian age–sex data stops at SA1 level (about 400 people). Mesh blocks carry totals only. The Mashhad data appears to be block or parcel level.
- *Circles are another arbitrary unit* (the modifiable areal unit problem). Pyramids must be shown as percentages, or denser circles simply look bigger.
- *No public flood model.* Planning overlays (LSIO, FO, SBO) stand in for the papers' HEC-RAS output.

## 2. Prototype (published on claude.ai)

Built as a self-contained page, **without a basemap**, because published claude.ai pages block external map tiles. A snapshot is kept at [`snapshots/2026-09-25-prototype.html`](../snapshots/2026-09-25-prototype.html):
- open it in any browser
- 474 SA1s, total population 207,058
- about 29,750 grid cells
- the page shell matches `web/template.html` exactly

Default comparison (800 m circles, Census 2021):

| Measure | Avondale Heights (A) | Footscray (B) |
|---|---|---|
| Lama & Sun "dependent" (under 20 + 60+) | 55% | 30% |
| Aged 75+ | 17.4% | 6.5% |
| Aged 0–4 | 4.3% | 4.1% |

Weak points found at this stage:
- **Area-weighted apportionment is the largest error.** People are spread over parks and industrial land.
- **"Residents in overlay" is unreliable locally.** Avondale Heights shows 0 riverine-overlay residents despite touching the river.
- **Overlays are planning controls, not flood depths.**

## 3. Repository (2026-09-25)

- **Pushed** from `D:\Yashar projects\Melbourne_Flood_WebGIS`. The files first landed at the repo root, but the README and `03_bundle.py` expected `pipeline/` and `web/`. The layout was fixed in [PR #1](https://github.com/Yasharjamei/Melbourne_Flood/pull/1).
- **Papers** were added under `papers/`. `Data/` was renamed because on Windows it's the same folder as the pipeline's git-ignored `data/`.
- **Workflows:** GitHub's template PyPI and SLSA workflows were replaced with a Pages workflow, `.github/workflows/pages.yml`.
- **First CI run** ([run 36134201360](https://github.com/Yasharjamei/Melbourne_Flood/actions/runs/36134201360)): the **build job passed**. Fetch, build and bundle all ran on a clean GitHub runner against live ABS and DataVic endpoints. The **deploy job failed** with a 404 because GitHub Pages wasn't enabled in the repository settings yet.

## 4. What the papers turned out to say

Full details are in the README's "How this maps onto the papers" section. The points that changed the plan:

- **Lama & Sun (2026):**
  - 474 SA1s, AHP weights, `FRI = AC − (S + E)`, `IFRI = 0.5·FRI − 0.5·Damage`.
  - Flood depth carries only 0.019 of the weight, and adaptive capacity 0.595. The index may mostly show income and education.
  - The indicators look like counts, not rates.
  - Their damage term makes the same uniform-density assumption as this prototype.
- **Lee, Sun & Wachowicz (2026, preprint):**
  - 412 SA1s inside the catchment, the IPCC hazard/exposure/vulnerability split, rates rather than counts, SEIFA IER and IEO.
  - MGWR local weights `|β| / Σ|β|`, with flood spread as the response.
  - The authors report that the population indicators weren't significant, and 84 SA1s had negative local R² in the exposure model. Treat the local weights as a comparison layer, not ground truth.
  - They single out Avondale Heights for its dependent and health-condition population. The pyramid shows that group is mostly people aged 75+.

## 5. Decisions and open questions

| Decision | Reason |
|---|---|
| Next priority is dasymetric weighting, before the basemap | It changes the numbers. The basemap only changes the look. |
| Mesh blocks are used as weights, not as a pyramid geography | Mesh blocks have no age–sex data. A mesh-block pyramid would just repeat the parent SA1's. |
| Show AHP, equal and MGWR weightings side by side | Both papers' weightings have documented weaknesses. Showing where they disagree is the finding. |
| Keep `data/` and `dist/` out of git | The pipeline rebuilds them. The raw DataPack is about 100 MB. |

Open:
- **Ask Chayn Sun (RMIT) for the October 2022 HEC-RAS depth raster.** It's the biggest gain in credibility available.
- **Add SHA-256 checksums for raw inputs.** DataVic overlays change whenever planning amendments are gazetted.
- **Confirm Lama & Sun's "mean income generating population".** It appears to count people in the $91k–$103,999 bracket.
