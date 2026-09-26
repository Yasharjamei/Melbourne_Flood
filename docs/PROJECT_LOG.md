# Project log

A record of how this project got here and why each decision was made, so none of it lives only in chat history.

## 1. Idea (before this repo)

**Inspiration: a "Demographic Explorer" web map** (screen recording, not stored here). Described from notes:
- Dark Mapbox basemap. Urban blocks are shaded by a population measure.
- **Compare mode:** drop two circles, A and B, and drag them around. A side panel updates live for each circle: total population, a male/female donut and an age–sex pyramid.
- Other tabs cover literacy, employment by sex, housing, area, building structure and building materials.
- A bottom bar switches between **Circle / Compare / Density / Parcels** modes.
- The point it makes: pyramid shapes change sharply between neighbourhoods, and a city-wide average hides that.

**Why it transfers to the flood papers:** both papers reduce vulnerable people to one percentage per SA1. Lama & Sun's "dependent population" puts under-20s and over-59s together. A pyramid under a flood layer separates them. A suburb of toddlers and a suburb of 80-year-olds need different evacuation plans even when their "dependent %" is identical.

**What doesn't transfer:**
- *Coarser data.* Australian age–sex data stops at SA1 level (about 400 people). Mesh blocks carry totals only. The reference map's data appears to be block or parcel level.
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

**What the reference video does and the prototype didn't.** The polygons under each circle change colour. The prototype only drew a flat translucent disc, so SA1s looked the same whether they were counted or not.

From a full-resolution frame at 0:13 (moderate confidence):
- **Circle B:** the parcels inside are recoloured orange and keep their shapes. The tint stops at the circle's edge, so parcels crossing the boundary are only partly highlighted.
- **Circle A:** the parcels inside are muted towards grey under a yellow dashed ring. The two circles use different treatments.
- **How it's built:** most likely a clipping mask on the layer, not a selection of whole parcels. So the visual cut-off doesn't tell you how they count partial parcels in the totals.

**Why the choice matters more here.** The reference map's parcels are tiny compared with the circle, so clipping reads as precise. Our SA1s are large, and an 800 m circle often clips just a corner of several of them.

| Option | Looks | Problem |
|---|---|---|
| 1. Clipped tint (like the reference map) | Clean | Implies precision we don't have. The residents in a clipped corner are an even-spread estimate. |
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

## 9. v0.3.1: "the metro page doesn't cover all of Greater Melbourne" (2026-09-25)

**Report:** the live Greater Melbourne page didn't cover the whole metro area.

**First hypothesis, which turned out wrong:**
- The fetch asked for pre-simplified council boundaries, and `buffer(0)` repairs a self-crossing ring by keeping only one piece. On a simple test shape it kept half the area.
- SA1s are assigned by representative point, so a lost piece would drop every SA1 in it.
- This was demonstrated on a test shape, not on the real data, and it was reported to the user as the cause before being confirmed. It shouldn't have been.

**What the data showed:** the new per-council coverage check came back at 99.6–103.8% for all 31 councils. The SA1 count was 11,293 both before and after the change, so 0.3.0 wasn't missing SA1s.

**Still open:** what the user saw. The leading candidates are visual: near-white lowest classes (the default "Aged 75+" map puts the young growth suburbs there) and blank SA1s with fewer than 10 residents. The user has been asked which areas looked missing.

**Kept anyway:** `make_valid`, the coverage check, object-ID paging, retry on truncated JSON, and CI screenshots. Each guards against a real failure mode, and two of them (the 504 and the truncated JSON) fixed real CI failures.

**Lesson:** the v0.3.0 "verified build" figures checked internal consistency (mesh blocks against selected SA1s), not coverage. A coverage check is now part of every build, and a claimed root cause should be checked against the data before it's reported.

## 10. v0.4: basemap, council filter, symbology (2026-09-25)

**Request:** filter by council, give different variables different symbology, make it look more professional, and add a basemap "using GeoLibre or any other Python library".

**Interpretation and push-back:**
- **"GeoLibre"** was read as **MapLibre**; I don't know of a library by that name.
- **Python map libraries** (folium, leafmap, pydeck) only write out a JavaScript map. Switching to one would have meant rebuilding the draggable circles, the share-based tint and the live panel. MapLibre GL JS used directly in the page adds the basemap while keeping all of those.

**Symbology decisions,** following the dataviz method:
- One hue per variable family, light to dark.
- A diverging scale with its midpoint at zero for the two resilience indices, where the sign means something ("damage exceeds resilience").
- Circle colours were checked with the palette validator. The old green/amber pair failed the chroma floor. Violet/orange passed in both modes, so those two hues are reserved for the circles.

**Filter semantics:** a filter is analytical, not just visual. With a council selected, colour classes, the comparison column and circle counts are all computed within that council, so the map and the panel never disagree.

## 11. Following the paper's full methodology (2026-09-25)

**Request:** make sure the Lama & Sun methodology is followed, including the correlation figure and the (M)GWR maps and results. Also add light and dark mode.

**Gap found:** v0.3 reproduced the index pipeline (indicators, AHP weights, E/S/AC, FRI, Damage, IFRI) but not the statistical analysis: Table 5, Figure 4 and Figure 7.

**Added:**
- `pipeline/lamasun_stats.py`: GWR and MGWR on standardised variables with an adaptive bisquare kernel, bandwidths by AICc, and multiple-testing-corrected significance.
- A per-study `analysis/` page with Table 5 next to the paper's values, Figure 4 as small-multiple maps, and Figure 7 as a scatter matrix.

**Paper inconsistency:** section 2.2.3 makes flood depth the response, but section 3.2 says the model explains IFRI. I followed 2.2.3. Figure 4 has ten coefficient maps, and IFRI regressed on its own inputs would give an R² near 1.

**New finding to verify on real data:** the first test run gave huge coefficients of opposite sign for the employed, educated and income-earner counts. That's the signature of multicollinearity from using counts rather than rates, so VIF is now reported. If the real data confirms it, it's a substantive critique of the paper's MGWR specification.

**Scope decision:** MGWR runs on the 474-SA1 study area only, because its cost grows with n². The correlation matrix runs on both pages.

**Theme:** a toggle stores the choice in `localStorage` and reloads. The variable, council, circles and view are carried across in `sessionStorage`, since MapLibre would otherwise have to rebuild every custom layer on a style swap.

## 12. Pre-merge check of the CI screenshots (2026-09-25)

Before merging to `main`, I read the final CI screenshots, which turned up two defects:

- **Analysis page:** the GWR table showed Intercept and Sand coefficients around 10¹¹ and 10¹⁵. The MGWR validity check didn't cover GWR. The likely cause is sand from a 250 m raster that barely varies inside each neighbourhood, so it is collinear with the local intercept. Fix: GWR drops the covariate behind the blow-up and refits. A synthetic test with a piecewise-constant sand column reproduced the blow-up (about 10⁸) and the fix (maximum |coefficient| 0.91 after dropping sand).
- **Casey view:** the example pins sit in the west, so after filtering to Casey both circles counted 0. Fix: pins move inside the filtered area when a council or suburb is chosen.

**Result (CI, head 1c418d1):**
- The guard dropped sand on the real data.
- MGWR converged: R² 0.647, adjusted R² 0.588, AICc 1013.8, bandwidths [52, 51, 95, 473, 473, 473, 98, 473, 473, 473].
- GWR: R² 0.526, adjusted R² 0.458, AICc 1130.4, bandwidth 175.

My earlier explanation, that collinear counts made MGWR diverge, was wrong or at least incomplete. The singular sand column was enough to break it.

Collinearity still shows in the fitted model: population (+0.63) and employed population (−0.63) are both 100% significant, with global bandwidths and mirror-image coefficients. That's a suppression pair and shouldn't be read as two effects.

The Casey screenshot now shows A = 4,503 (Cranbourne East) and B = 3,958 (Narre Warren).

## 13. v0.5: resident-based exposure and documentation (2026-09-26)

**Request:** better spatial accuracy, comprehensive documentation for returning to the code or taking contributions, no trace of the development branch name, and no place-specific references to the reference map.

**Which dataset, and why.** The biggest accuracy gap was not polygon detail but *what* was measured. Flood exposure was an **area** share, so a flooded reserve inside a residential block counted the same as flooded houses. Options considered:

| Option | Gain | Cost | Decision |
|---|---|---|---|
| Vicmap Address points (property/unit locations) | places dwellings inside each mesh block | ~2 M points for metro, cached | **adopted** |
| Less polygon simplification | sharper edges on screen | metro page already 14 MB | not now; needs vector tiles |
| Victorian Flood Database 1% AEP extents | modelled extent instead of planning control | overlays are largely derived from the same mapping | roadmap |
| Vicmap Elevation 10 m DEM | matches the paper | large download, small index weight (0.014) | roadmap |

**What was built:**
- `01_fetch.py` discovers the address layer from WFS GetCapabilities and downloads geometry only.
- `02_build.py` uses the address points to compute address-share per mesh block, then resident-weighted SA1 shares.
- The pages and indices use the new measure.
- Docs: `ARCHITECTURE.md`, `CONTRIBUTING.md` and code comments.

**History rewrite (not done in-session).** The request to re-author earlier commits and remove the branch name and trailers from history needs a force-push to `main`. The session's permission policy blocked it, so it is left for the repository owner to run or approve.

