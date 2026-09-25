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

## 6. How a circle shows what it counts (design chat, 2026-09-25)

**What the Mashhad video does and the prototype didn't.** The polygons under each circle change colour. The prototype only drew a flat translucent disc, so SA1s looked the same whether they were counted or not.

From a full-resolution frame at 0:13 (moderate confidence):
- **Circle B:** the parcels inside are recoloured orange and keep their shapes. The tint stops at the circle's edge, so parcels crossing the boundary are only partly highlighted.
- **Circle A:** the parcels inside are muted towards grey under a yellow dashed ring. The two circles use different treatments.
- **How it's built:** most likely a clipping mask on the layer, not a selection of whole parcels. So the visual cut-off doesn't tell you how they count partial parcels in the totals.

**Why the choice matters more here.** Mashhad's parcels are tiny compared with the circle, so clipping reads as precise. Our SA1s are large, and an 800 m circle often clips just a corner of several of them.

| Option | Looks | Problem |
|---|---|---|
| 1. Clipped tint (like Mashhad) | Clean | Implies precision we don't have. The residents in a clipped corner are an even-spread estimate. |
| 2. Tint every SA1 the circle touches, opacity = share of its residents counted | Busier | None. It shows exactly what each estimate is built from. |

**Decision: option 2**, with a thin outline ring on top so the circle still reads as a circle. It puts the apportionment weakness on the map instead of in a footnote. It was cheap to add, because the grid already computes each SA1's share inside the circle.

**Implemented** in `web/template.html`:
- the circle becomes an outline only
- a tint layer draws each touched SA1 in the circle's colour, with `fill-opacity = 0.08 + 0.62 × share`
- the SA1 tooltip gains "Counted in A: xx% of residents"

It was checked in Chromium against the snapshot data: the default circles touch 54 SA1s, and the A/B figures are unchanged. Once mesh-block weighting lands, "share" automatically becomes share of *residents* rather than share of *area*, because opacity is read from the same weights the totals use.

## 7. Scope request: all Melbourne LGAs (2026-09-25)

**Request:** extend from Maribyrnong + Moonee Valley to all Melbourne councils.

What that implies:
- **About 10,000 SA1s** across the 31 Greater Melbourne LGAs instead of 474. That includes large peri-urban councils (Yarra Ranges, Cardinia, Mornington Peninsula).
- **The 50 m grid doesn't scale.** Greater Melbourne is roughly 10,000 km², which is about 4 million cells. As an inline page that means well over 100 MB.
- **So scaling up and the accuracy fix are the same piece of work.** Replace the grid with **mesh blocks** (population-weighted, about 60k points for the metro area). That is roadmap item 2.
- **The papers only cover two LGAs.** The metro build is a separate page. The two-council page stays as the one that reproduces and critiques the papers.
- **Planning-overlay extents exist state-wide,** so flood context scales. HEC-RAS depth, if obtained, would still cover only the Maribyrnong catchment.

## 8. v0.3: all of Melbourne, Lama & Sun maps, suburbs (2026-09-25)

**Request:** add all Melbourne councils, reproduce the maps in Lama & Sun's methodology, add suburbs, and keep the README and changelog current.

**What was built**, detailed in `CHANGELOG.md`:
- **Two pages from one pipeline:** `west` (the papers' 474 SA1s) and `metro` (31 councils).
- **Mesh-block weighting** replaces the 50 m grid. This was needed for metro scale anyway: about 4 million grid points would have been too many.
- **The six maps from the paper's Figures 5 and 6,** with circle-level means in the panel.
- **Suburbs:** outlines, labels, search, and names in tooltips.

**Decisions:**
- **Paper formulas reproduced as written:** z-score then min–max, Table 2 weights, `FRI = AC − (S + E)`, `D_x = (A1/A)·X`, `IFRI = 0.5·FRI − 0.5·DI`. Counts are kept as counts, to match the paper, even though rates would be the better choice (see the README critique).
- **"Mean income generating population"** turned out to be exactly the ABS personal income band $1,750–$1,999 a week, which is $91,000–$103,999 a year. That resolves the open question in section 5.
- **Elevation and sand are inverted,** so low ground and low sand count as more exposed. The paper's highest exposure (0.043 of a possible 0.047) is in low-lying Flemington, which only makes sense if low elevation scores high.
- **Quintile classes**, not natural breaks: the paper doesn't name its method.
- **Optional inputs fall back instead of failing,** and each fallback is written to the page footer. So a page never silently claims data it doesn't have.

**Checked before pushing:**
- The full build ran offline on a stand-in dataset derived from the snapshot's real SA1s, overlays and counts.
- FRI came out in −0.15 to 0.31, the same order as the paper's −0.148 to 0.228.
- The page rendered in Chromium with no errors, and all six index layers, the suburb search and the cross-link worked.
- Real-data runs happen in CI on the pull request.

**Verified on live data** ([run 36142233452](https://github.com/Yasharjamei/Melbourne_Flood/actions/runs/36142233452)), after four fixes that only real data could reveal: overlay filter, G43 column names, invalid council geometry, and the counts workbook layout.
- **Two councils:** 474 SA1s. Mesh-block counts place 207,015 of 207,058 residents. FRI −0.169 to 0.272 (paper −0.148 to 0.228). Max Exposure 0.047 (paper 0.043).
- **Greater Melbourne:** 31 councils, 11,293 SA1s, 58,563 mesh blocks, 543 suburbs, 2,302 overlay polygons. 4,833,357 of 4,833,389 residents placed. The page is 14.2 MB, about 3 MB compressed.

## 9. v0.3.1: the metro page had holes (2026-09-25)

**Report:** the live Greater Melbourne page didn't cover the whole metro area.

**Cause:**
- The fetch asked the ABS server for pre-simplified council boundaries (`maxAllowableOffset`), and that made some boundaries cross themselves.
- The first metro build crashed on those boundaries. The fix at the time was `buffer(0)`, which "repairs" a self-crossing ring by keeping only one piece. On a simple test shape it kept half the area; `make_valid` kept all of it.
- SA1s are assigned to a council by testing whether their representative point is inside it. So every SA1 in a discarded piece dropped out of the study area.

**Why the verified-build numbers didn't catch it:** the check compared mesh-block residents with the Census totals *of the SA1s that had been selected*. That confirms the apportionment is internally consistent. It can't reveal SA1s that were never selected.

**Fix:**
- Council boundaries are fetched at full detail.
- All geometry is repaired with `make_valid`.
- A per-council coverage check fails the build if the SA1s don't tile a council.
- PR builds publish screenshots to `ci-preview`, so the map itself is checked before merging, not just the build log.

