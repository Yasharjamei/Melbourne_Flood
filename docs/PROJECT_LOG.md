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

**Caught before merging: a truncated address download.** The first CI run fetched only 5,000 address points per study area. The Vicmap server caps every response at 5,000 features whatever `count` requests, and the paging loop took a short page as the end. Only 269 of 2,661 mesh blocks (west) had addresses, so most kept their area share. The exposure numbers from that run were a silent mix of two methods and were not published. Fixes:
- `wfs_points` pages until an empty response, sorts on the layer key, and fails if it receives fewer points than the server's `numberMatched`.
- `02_build.py` refuses the address method when under 80% of populated mesh blocks have a point.

Both were tested against a simulated capped server and a truncated file.

**Result (CI, head 575e759).**
- **Address download:** 184,780 points (west) and 3,123,830 (metro, 19 minutes with 8 parallel requests). Every populated mesh block has at least one.
- **Residents in overlays**, by area share → by address: 10,721 → 7,170 (west) and 239,650 → 185,538 (metro). The area measure overstated exposure by 50% and 29%.
- **Largest single correction:** a Footscray SA1 with 48% of its area but about 1% of its residents in an overlay.
- **Regression:** MGWR R² 0.444 vs GWR 0.218. Elevation is significant everywhere. Sand was not dropped this time, because GWR chose a wider bandwidth.

## 14. v0.6: SEIFA, canopy, buildings, 10 m DEM, metro MGWR (2026-09-27)

**Inputs offered by the owner, and what they turned out to be:**

| Offered | What it is | Used as |
|---|---|---|
| SEIFA 2021 (attached files) | The attachments didn't reach the session, so the ABS workbook is downloaded directly instead | IRSD/IRSAD/IER/IEO deciles |
| Vicmap 10 m DEM (WMTS link) | **Shaded relief: a picture, not elevation values** | A terrain toggle on the map. Values come from the separate `Vicmap_10m_DEM/ImageServer` |
| Tree canopy (S3 zip) | 2 GB of 20 cm canopy/no-canopy GeoTIFFs in VicGrid 2020, one per 1:100k half-sheet | Remote-zip reads of only the overlapping tiles, averaged to 10 m (tested locally: 2 tiles for the two councils in 2.5 minutes) |
| Microsoft building footprints | Per-quadkey line-delimited GeoJSON; the 2026-08 release | Count and roof coverage per SA1 |

**Metro MGWR.** At SA1 level it isn't feasible: 474 SA1s take ~7 minutes, and cost grows with n², so 11,293 would take days. It is fitted on SA2s instead. Two library defaults broke on smaller unit sets and are now set explicitly:
- the bandwidth search floor, 40 + 2k = 62
- MGWR's own initial search

**Statewide.** Possible, but not built. The tree-extent index covers all of Victoria (17 archives). An all-Victoria SA1 page would be about twice the metro page, around 30 MB, so it needs vector tiles first. The regression would run on SA2s (~520) or per region.

**Single map (owner's request).** The two-council page was dropped in favour of one Greater Melbourne map. The paper comparison was kept, because it is the only place the reproduction can be checked:
- a council-menu preset for the papers' 474 SA1s
- the Lama & Sun indices re-scaled within those SA1s (`lsp`), because min–max scaling is area-relative
- a second GWR/MGWR model on those SA1s

**Bug found while doing this:** the index variables read the filter state before it was declared, a JavaScript temporal dead zone. The page never became ready. It was caught by the local browser test and would also have failed the CI screenshot step.

**Road casement.** The owner supplied a DataVic *order* link: an 84 MB shapefile for the Melbourne Water region, in MGA 2020 zone 55. Order links are temporary, so `roads()` falls back to the same layer on the Vicmap WFS. The fixture test gave 5,138 polygons and a mean road-reserve share of 23.5% in the two paper councils.

**River basins and subcatchments.**
- The owner attached Melbourne Water's major river basins: 8 polygons, 3 MB. They are committed as static data, since there is no stable download link and they change rarely.
- The owner also sent an ArcGIS export link for *Catchments of all Waterways and Drains*. It was signed to expire within 65 minutes, so the pipeline finds the same Melbourne Water layer through the ArcGIS Online catalogue search instead.
- Fixture check: the two paper councils split into Maribyrnong (303 SA1s), Yarra (88) and Werribee (83). Werribee is plausible, since Melbourne Water's Werribee basin takes in the Kororoit and Laverton creek catchments.

**Supplied "DEM Hydro Conditioning Guide v3": reviewed, not adopted as written.** Despite its title, it is an evacuation-routing spec. Its routing needs modelled depth and velocity, which aren't public, and its hazard thresholds understate ADR guideline 7-3: it removes roads only at H5 and routes civilians through H4. A reduced, honest version (static isolation analysis on the road network with flood overlays) is on the roadmap as item 7b.

**Waterways and drains catchments, supplied as a file.** The owner then attached the full layer: a 3.2 MB zipped file geodatabase, 3,409 subcatchments, in EPSG:28355. It is committed to `data/static/` and read straight from the zip (`/vsizip/`), so the ArcGIS Online lookup is only a fallback now. Each record carries its drainage chain: subcatchment → major (creek) catchment → primary catchment → basin. In the paper councils the creek catchments are Kororoit Creek, Maribyrnong River, Moonee Ponds Creek, Stony Creek and Yarra River Main Stream. That explains the 83 SA1s in the Werribee basin: Kororoit Creek belongs to it.

## 15. v0.6 on real data; one branch from here on (2026-09-27)

**CI result for pull request #6** (8231d4a, full refetch, 70 min fetch + 17 min build):

| Input | Result |
|---|---|
| Tree canopy | 76 tiles from four packages; all 58,563 mesh blocks covered; mean 10.9% |
| SEIFA | parsed (header row 5); 10,948 SA1s matched |
| Road casement | 119,123 polygons; mean road-reserve share 22.3% |
| Buildings | 1.76 M footprints read, 1.62 M in study SA1s; mean roof coverage 20.3% |
| Basins / catchments | Yarra 4,824, Dandenong 3,305, Werribee 1,673, Western Port 873, Maribyrnong 601 SA1s; 84 creek catchments |
| Paper-area model (474 SA1s) | GWR R² 0.232, MGWR 0.451; paper-scaled FRI −0.168 to 0.272 (unchanged) |
| Metro model (353 SA2s) | GWR R² 0.338, MGWR 0.408 |
| Vicmap 10 m DEM | failed: LERC tiles are 257 × 257; fixed on `main` |

**Pull request #6 was the last.** At the owner's request, the workflow no longer runs on pull requests and no longer pushes a `ci-preview` branch.

**The committer was "Claude" on cherry-picks.** The checkout's git config named Claude, so a cherry-pick recorded Claude as committer. Earlier commits had set both identities explicitly. The repository's local config now names the owner.

**First main-only run (6f47eee):** green and deployed.
- **Vicmap 10 m DEM:** all 5,265 LERC tiles, elevation −13 to 1,475 m. The page now credits the Vicmap DEM, as the paper used.
- **1% AEP extent:** no WFS layer matched, so the build took Victorian Flood Database layer 14, "Flood extent – 1 in 100 year recurrence <250K". It is the only 1-in-100 extent in that service; layer 12 is just its group. That gave 308 polygons, 191.5 km² in the study area.
- **Paper model:** MGWR R² 0.452 (GWR 0.232). **Metro model:** MGWR 0.409 (GWR 0.339).
- **A race was avoided:** the v0.6 merge run (#28, old workflow) was still building when the newer run deployed, and it would have overwritten the site with the older build. It was cancelled. With a single `concurrency: pages` group and `cancel-in-progress`, this can't recur.

**Residents in the 1% AEP extent (e539ef8, cached rebuild in 19 minutes).** 14,563 residents live inside the VFD 1-in-100 extent, against 185,536 inside the planning overlays; at most 6,419 are in both. The likely reasons:
- the VFD layer covers mainly the major rivers and is generalised
- the overlays include the Special Building Overlay (overland flow), where most exposed residents live

It is documented as riverine 1% AEP. The newer DEECA statewide layer, which is vector tiles only, may close the gap.

## 16. Light-mode layer order; roof coverage explained (2026-09-28)

**Light and dark mode looked different.** Two causes, one a bug:
- **Bug (fixed in 8e8c95c):** data layers were inserted before the basemap's first symbol layer. In Dark Matter that is layer 66 of 93, after every road and building. In Positron it is layer 13 (`waterway_label`), before the roads and buildings, so in light mode they were drawn over the choropleth. Layers now go before the first label that follows the last non-label layer: `watername_ocean` in Positron, `waterway_label` in Dark Matter. The rule was checked against both style files from CartoDB/basemap-styles; the basemap host is not reachable from the development sandbox, so the rendered result is checked by CI screenshots and on the live site.
- **Not a bug:** the two screenshots compared had different toggles (Flood overlays on in one, off in the other).

**Roof coverage vs building footprints.** Roof coverage is derived from the Microsoft footprints (Σ footprint area ÷ SA1 area, by centroid) but the footprints are not drawn. The grey buildings on the basemap are OpenStreetMap. Drawing the footprints was considered and not done: ~1.62 M polygons would roughly double the 18.9 MB page, so it would need vector tiles (PMTiles) rather than a bundled page. The definition and its limits are now in the README (Method step 7, limits section).

**Repository hygiene left to the owner.** Deleting the remote branches (`claude/ecstatic-albattani-003dlt`, `v0.5-address-exposure`, `v0.6-more-open-data`, `ci-preview`) and rewriting history with `clean_history.py` were both blocked for the assistant in this environment. The owner chose to leave them for now, so those branches and the early commit trailers still exist. Pull requests #1–#6 cannot be deleted on GitHub in any case.

## 17. Work in git worktrees from here on (2026-09-28)

**Decision:** every change is made in its own git worktree, following CONTRIBUTING §5.

**Why local-only branches.** Git refuses to check out one branch in two worktrees, so each worktree needs its own branch. Those `wt/<topic>` branches stay local: the work is pushed with `git push origin HEAD:main`, and the branch is deleted afterwards. GitHub keeps one branch, as decided in §15.

**Snag found while setting it up.** A worktree shares the ~1 GB download cache through a link to the main checkout's `data/raw`. `.gitignore` had `data/raw/`, and the trailing slash matches only real folders, so the link showed as an untracked file and could have been committed. The pattern is now `data/raw`, which matches both.

**Making the rule last.** `CLAUDE.md` states the rule, plus the owner-only commit authorship, so it survives new sessions. Chat instructions alone do not. This change was itself made in a worktree (`../mf-worktree-docs`) as the first use of the workflow.

## 18. Keep only the latest Pages deployment (2026-09-28)

**Request:** keep only the latest GitHub Pages site and delete the old ones.

**What "old ones" are.** Pages serves exactly one version: each deploy replaces the whole site, so old versions are never reachable. What piles up is history: a `github-pages` deployment record per deploy, one workflow run per push (33 by then, each with logs), a Pages artifact per run, and a screenshots artifact kept 90 days.

**Decision:** a `cleanup` job in `pages.yml`, after `deploy`, using `actions/github-script`.
- Deployment records: all but the newest are marked inactive, then deleted.
- Workflow runs: completed runs beyond the newest `KEEP_RUNS` are deleted, which takes their logs and artifacts with them.
- It needs `actions: write` and `deployments: write`, granted to that job only.

**Why 5 runs, not 1.** A failed run's log is the only record of why it failed. With 1, the next green run would delete the evidence. Set `KEEP_RUNS: 1` for strictly latest-only.

**Safety.**
- The job runs only after a successful deploy, so a broken build never removes the last good deployment record.
- The current run is still in progress, so it is never in the list it deletes from.
- Every deletion is wrapped so a failure warns and never fails the run.
- The selection logic was tested against mock data: 4 deployments → 3 deleted, newest kept; 7 completed runs → 3 deleted, 4 kept plus the current run.
- The GitHub API side can't be tested from the sandbox; the first real run's log shows the counts.

**Not touched:**
- The `/metro/` redirect pages, which keep old links working.
- `snapshots/2026-09-25-prototype.html`, which is a file in the repository, not a deployed page.

## 19. Validating the A/B circles (2026-09-28)

**Question:** do moving the circles and the resident figures work correctly, and how would we know?

**Reading the code first** (`agg`, `sumW` in `web/template.html`):
- **The logic was sound.** A mesh block is counted when its point lies within R. It adds its resident share of its SA1, and its overlay shares scale the flood rows. The council filter skips SA1s outside the selection.
- **One inaccuracy:** longitude was converted to metres at a single study-wide latitude (`META.lat0`), while the ring is drawn at the circle's own latitude. **Fixed:** the page now uses the circle's latitude.

**Independent check** (`.github/scripts/check_circles.py`, in CI after the screenshots):
- **Independent by design.** Python and haversine, not the page's formula. The only allowance is the 0.25 m band that covers the two formulas' ≤0.2 m difference at 2 km.
- **A test hook.** The page code sits inside an IIFE (a self-contained function), so it exposes `window.__test` with its own `agg`, filter, pin positions and projection. The page never uses it.

**Getting the UI test honest:**
- The first drag test passed while proving nothing: the pin landed on 0 residents. It now drags onto the most populous point 300–1,500 m away.
- The pins then appeared to land 500–1,000 m off. The cause was the test, not the page: its on-screen check ignored the toolbar, so the mouse grabbed the toolbar instead of the pin. Replayed on its own, the drag lands within 1 px.

**Mutation testing** (deliberately broken copies of the page, test fixture):
- **Caught:** a circle 1% too wide; shares 10% low; the old single-latitude formula (one circle moved 4%); the riverine row replaced by all residents; the overland-flow row 20% low.
- **Missed at first:** a wrong flood-row value, because only "overlay ≤ residents" was checked. The flood rows are now recounted.
- **A fixture limit:** a "shares 10% high, capped at 1" mutation passed only because every fixture weight is exactly 1. The real data has fractional weights.

**Not yet run on real data from the sandbox.** Neither the live site nor its build artifact is reachable from the development sandbox. The first CI run after this commit is the first check on the 58,563 real mesh blocks; its log line "count: 300 random circles match …" is the evidence.

## 20. New data reaches the site on its own (2026-09-28)

**Request:** when new data comes in or a new factor is added, the project should reflect it automatically.

**What was actually happening.** The raw-data cache key was a hash of `01_fetch.py` and `config.py` only. So live sources were re-downloaded only when that code changed, and the README's "automatic on every build" for overlays and addresses was wrong. The page didn't show its data date either.

**Changes:**
- A monthly `schedule:` trigger, at 03:17 UTC on the 2nd.
- The month in the cache key: one full refetch per month, and later pushes reuse it.
- `fetched.txt` → `meta.fetched`, plus `meta.built`, shown in the footer.
- `STRICT_FETCH=1` on scheduled runs.

**Why strict on the schedule only.** Without a human watching, a source that is down that day would make the build fall back (for example, to area shares if addresses fail) and deploy a weaker map. Failing instead keeps last month's good site, and GitHub emails the owner. Pushes keep fall-back-and-say-so, because someone is watching those runs.

**Cost:** a full refetch is ~70–90 min of Actions time a month, well inside the 180-minute job timeout.

**Known limit:** GitHub disables scheduled workflows in public repositories after 60 days without activity.

**New factors are not automatic, and can't fully be.** A factor needs a source, a way to summarise it per SA1 (a mean, a share of area, a count) and a way to show it. The current route is ARCHITECTURE §4:
1. a fetch function
2. a build step
3. a `METRICS` entry
4. a panel row
5. the analysis variables if it enters the models

A config-driven factor registry (one entry in `config.py` → map variable, panel row, correlations) was proposed to the owner and not built yet.

## 21. Demo recording for sharing (2026-09-28)

**Request:** a GIF showing how the project works, for a LinkedIn post.

**Why it runs in CI.** The development sandbox can't reach the live site or the basemap, so a recording made there shows a bare map on test data. `demo_gif.py` runs in the build job instead, on the real page with the basemap. It adds the files to the *screenshots* artifact and is `continue-on-error`.

**Choices:**
- Frames are screenshots between scripted steps, not screen video, so timing doesn't depend on runner speed.
- The browser window is 1600×900, scaled down to 1280×720 (16:9, uncropped in feeds).
- The GIF is 960 px wide with 128 colours, to stay small. The MP4 is H.264 at full size. LinkedIn plays MP4 as video; GIF support in posts is less reliable.
- Hover tooltips and the first-visit hint are hidden in the recording.

**Checked on the test fixture:**
- The first attempt dragged circle A out of the study area (the final frame showed 0 residents), and a tooltip covered the map. The drag now heads for the middle of the view.
- 15 frames, about 20 s, 1.2 MB GIF on the fixture.

**First real run** (ae5b3ea, full refetch):
- **Circle check passed on real data:** 11,293 SA1s and 53,134 mesh blocks, with every SA1's shares summing to 1. All 300 random circles matched the independent recount; 19 had a mesh block within 0.25 m of the ring. The council filter checked out in 4 councils. The drag and click tests matched exactly (3,248 and 2,718 residents).
- **The demo GIF was made** (15 frames, 19.6 s, 2.1 MB), **but no MP4.** GitHub's ubuntu runners no longer ship `ffmpeg`, and Playwright's bundled ffmpeg has no H.264 encoder. Fixed by using the static build from the `imageio-ffmpeg` pip package.

## 22. A truncated download degraded the live site (2026-09-28)

**What happened.** The first build with a fresh monthly cache (ae5b3ea) was push-triggered, so it was not strict.
- The Vicmap WFS returned a truncated JSON page at 2,755,000 of 3,123,830 address points (cut at char 983,040, exactly 960 KiB).
- `get_json` treated a decode error as final. The address input was marked unavailable, and the build used area shares.
- It deployed with "residents in planning overlays: 242,856" (the area measure) instead of ~185,500.
- The footer said so, but nobody reads footers.
- Everything else was fine: the circle check passed (11,293 SA1s, 53,134 mesh blocks, 300 circles, exact drag/click), the 1% AEP extent held 22,918 residents, and MGWR R² was 0.460 (paper) and 0.397 (metro).

**Fixes:**
1. `get_json` now re-fetches truncated JSON (4 tries, with backoff), as `get` already did for network errors.
2. `STRICT_FETCH=1` on **every** CI run, not only the schedule. §20 kept pushes lenient on the grounds that "someone is watching"; this run disproved that.

**Side effect, deliberate.** Editing `01_fetch.py` changes the cache key, so the next run refetches everything and saves a complete cache. The September cache from ae5b3ea has no address file.

**AEP figures on the area method.** 22,918 in the 1% AEP extent and 12,915 in both. These will change once addresses are back.

## 23. Phones: iOS and Android (2026-09-29)

**Request:** use the project on a phone, on iOS and Android.

**No native app.** One responsive web page serves both. A web manifest with icons (`web/manifest.webmanifest`, `web/icons/`, drawn by `make_icons.py`; `03_bundle.py` copies them into `dist/`) makes *Add to Home Screen* open it full-screen with its own icon.

**Found in emulation** (Playwright, iPhone 13 390×664 and Pixel 7 412×839, touch on):
1. The legend and layer cards covered almost the whole map.
2. The map was only **307 px** tall on the iPhone. `.mapcol` was 74svh and contained the menu bar, so the map got what the bar left over.
3. The menus used 13.5 px text, so iOS Safari zooms in on focus.
4. The A/B counts were below the map, out of sight while dragging.
5. The scatter matrix scrolled sideways, with no cue that it could.

**Fixes (≤700 px wide):**
- The menus sit in a 2-column grid.
- `#map` has its own height, 68svh (min 340 px).
- The legend and layer list collapse (tap to toggle; the layer list scrolls inside the map when open).
- A pointer-transparent A/B readout sits on the map.
- Text inputs use 16 px.
- On touch screens, pins are 34 px and checkboxes 18 px.
- The layout respects the notch and home-bar insets.
- The analysis page gets tighter margins, a two-column map grid and a "swipe sideways" cue.

**Checks:**
- **Taps in emulation:** Layers and legend open and close. A map tap moves the nearer pin (B), and both readouts update (8,821 → 4,137). No page errors.
- **Desktop unchanged:** `check_circles.py` passes on the fixture.
- **One bug caught while testing:** the readout card intercepted taps meant for the legend. It is now `pointer-events:none`.

**Not verified:**
- **Real WebKit:** iOS Safari uses WebKit, which isn't available here or in CI.
- **Low-end phones:** the 19 MB inline page is the performance risk there.

## 24. Demo tours data-chosen councils; recorded without a rebuild (2026-09-30)

**Request:** a better demo that shows councils other than the papers' two. The owner asked for no site rebuild.

**Council choice.** The councils are chosen from the page's own data, not by hand. For each council, Σ SA1 residents × `fl` (the address-based share in any overlay) gives its residents in overlays. The top three outside the `__paper` preset are shown with three lenses: flood overlay, aged 75+, IFRI. In the first council, circle A is dragged to the mesh-block point with the most residents in an overlay. The captions quote each council's figure, rounded to the nearest 100.

**No rebuild.** `demo.yml` (manual `workflow_dispatch`) runs `demo_gif.py` against the live site (`DEMO_URL`). It only checks out the scripts; it doesn't fetch, build or deploy. The code change went up with `[skip ci]`, so the push didn't start `pages.yml`. `pages.yml`'s cleanup deletes only its own runs, so demo runs are kept until their artifacts expire (14 days).

**Tested** on the fixture. It has only the papers' two councils, so the tour fell back to those: 14 frames, 18 s, 1.1 MB GIF, 0.6 MB MP4. The real council choice is visible in the demo run's log ("tour: …").

**Ranking changed from total to share (same day).**
- The first live recording ranked by total and picked Melbourne (34,173), Glen Eira (16,876) and Port Phillip (15,167). All three are dense inner-city councils.
- Much of those counts is likely apartment residents above ground level: an address point per unit, inside an SBO or LSIO overlay.
- A caption like "34,000 residents live in flood overlays" invites an obvious challenge.
- The councils are now ranked by share of residents, the caption states the share and the count, and the owner's post notes that inner-city counts include apartment residents above ground level.

## 25. Population forecast: what the data allows, and the back-test (2026-10-01)

**Goal:** a scenarios page showing residents in today's flood areas in 2036, plus sea-level rise, with forecasts reaching SA1 and mesh-block level. The owner asked for multiple data sources and remote sensing.

**Three probe rounds** (`probe.yml`, manual, no site change) established:
- **ABS**
  - ERP by SA2: `ABS_ANNUAL_ERP_ASGS2021`, 2001 onwards, plus the 2024–25 regional population cubes.
  - ERP by council, age and sex, to 2025. Building approvals by council.
  - 2016 Mesh Block Counts (CSV) and the `CG_MB_2016_MB_2021` correspondence.
- **Vicmap Address** has `pfi_created`. Addresses created per year in Greater Melbourne, 2012–2026: 57,680; 43,206; 67,807; 76,880; 90,930; 82,763; 75,909; 71,852; 78,714; 76,456; 73,463; 57,442; 54,957; 59,570; 53,434 (2026 to October). No database-event spikes, and the trend follows the building cycle.
- **GHSL R2023A**: built-up surface, building volume and population at 100 m, 1975–2030 (2025 and 2030 modelled). **Sentinel-2 L2A**: 38 scenes over central Melbourne in Jan–Mar 2025, many cloud-free.
- **Not usable:** WorldPop (Australia stops at 2020), ESA WorldCover (2020–21 only), Microsoft footprints (no dates or heights).
- **Need the owner:**
  - VIF2023 files: planning.vic.gov.au answers automated requests with HTTP 403, and only council and region files are catalogued.
  - DataShare orders: Urban Development Program sites, 2016–2025, and the sea-level-rise scenarios. The WFS has only the 2009 baselines.

**Why addresses rather than satellite change.** A dated address is a new dwelling where it sits, towers and infill included. 10 m imagery sees new roofs, not new homes, and misses vertical growth. GHSL stays as an independent cross-check, and the bespoke Sentinel-2 analysis is dropped.

**Back-test design** (`pipeline/forecast/backtest.py`).
- **What it predicts:** each 2021 mesh block's residents, from the 2016 counts (moved onto 2021 mesh blocks with the correspondence) plus addresses created between the Census nights.
- **SA2 totals are set to the true 2021 values**, so the error measured is placement alone.
- **Methods compared:**
  - A: uniform growth within each SA2.
  - B: existing homes grow at a common SA2 rate, and new addresses add the SA2's persons per dwelling.
  - C: existing stock fixed, with the SA2 remainder going to new addresses.
- **Metrics:** WAPE, the share of units within 10 people or 20%, and the median error, for all mesh blocks, for growth mesh blocks (10+ new addresses) and for SA1s.
- **Decision rule:** the measured error decides whether the page shows mesh blocks, SA1s or suburbs.

**A bug caught on synthetic data.** pandas inferred one column from ABS title rows and, with `on_bad_lines="skip"`, silently dropped every data row. The file is now read as ragged rows.

**Known biases.**
- Retired addresses are absent, so 2016–21 new addresses are slightly undercounted.
- Addresses can predate occupation (created at subdivision).
- Non-residential addresses are included.

**First real run.** Inputs downloaded: 2016 counts (14.0 MB), correspondence (14.5 MB), ERP by SA2 (6.6 MB), and 717,776 addresses created since Census 2016. Two faults:
- **The back-test stopped on the 2021 counts workbook.** Its data-dictionary sheet names `MB_CODE_2021` too. The reader now skips any sheet lacking the required columns.
- **The run reported success anyway**, because `| tee` hid the exit code. The step now sets `pipefail`.

**Back-test result, run 2 (c0c3669).** 62,017 mesh blocks (the fetch box reaches past the 31 councils), 5,048,248 residents in 2021 and 4,594,879 in 2016 on the same blocks. 373,443 new addresses fell inside, against about 453,000 new residents.

| Model | Mesh block WAPE / within | Growth mesh blocks (10+ new addresses) | SA1 WAPE / within |
|---|---|---|---|
| A uniform | 22.5% / 72.9% | 46.4% / 46.8% | 16.7% / 82.3% |
| B address | 21.7% / 74.4% | **56.1%** / 41.4% | 15.4% / 83.9% |
| C address, stock fixed | 20.3% / 76.3% | 51.5% / 43.6% | 14.1% / 85.6% |

**The finding.**
- **Addresses barely help overall, and hurt where growth is.** Even with the true SA2 totals, placement error is ~20% at mesh block and ~14% at SA1.
- **The likely cause:** a new address is not a new household. At ~2.6 persons per dwelling, 373k addresses would mean ~970k people, twice the real growth. Many addresses are lots or units not yet occupied by Census night.
- **Next test:** D (one metro-wide residents-per-new-address, fitted) and E (D counting only addresses created 12+ months before Census night).
- **Publishing:** mesh-block forecasts are not publishable on this evidence. SA1 is borderline, so suburb or SA2 it is unless D/E change the picture.

**Run 3 (7c945d8): calibration fixes the failure.** Fitted residents per new address: k = 1.21 using all addresses, 1.51 using those created 12+ months before Census night.

| Model | Mesh block WAPE / within | Growth mesh blocks | SA1 WAPE / within |
|---|---|---|---|
| A uniform | 22.5% / 72.9% | 46.4% / 46.8% | 16.7% / 82.3% |
| D calibrated | 17.8% / 78.5% | 38.2% / 51.4% | 11.9% / 87.0% |
| **E calibrated + 12-month lag** | **17.1% / 78.9%** | **33.3% / 55.3%** | **11.4% / 87.3%** |

**What it means.**
- **E is the method.** It cuts error in growth mesh blocks by about 28% relative to uniform (46.4% → 33.3%) and at SA1 from 16.7% to 11.4%. The 12-month lag supports the "addresses come before residents" explanation.
- **The k values are in-sample** (fitted and scored on 2016–21), so these errors are a little optimistic. Out-of-sample checking will use ERP by SA2 2021–25, which only tests SA2 totals.
- **These are placement errors only.** Real forecasts add the error of the SA2 projections themselves.

**Publishing decision.**
- **Mesh block:** not published (17% error even with true totals). Used internally for the overlay intersection only.
- **SA1:** shown only with a range.
- **Suburb and SA2:** headline figures, also with ranges.

## 26. Scenarios page built ahead of its data (2026-10-01)

**Why now.** The inputs for a real 2036 forecast are still missing (VIF2023 by council or SA2; the DataShare sea-level-rise and UDP orders). The owner agreed to build the page on invented numbers so the design can be reviewed while those arrive.

**Safeguards against invented numbers escaping.**
- The sample (`web/scenarios_sample.json`) carries `meta.sample = true`, and the page then shows a banner: invented, do not quote.
- Area names are "Sample area 1–12", never real councils or suburbs, so a screenshot cannot pin a made-up figure on a real place.
- The page is not bundled into the site unless the real `data/processed/scenarios.json` exists and `PUBLISH_SCENARIOS=1` is set. The monthly scheduled rebuild cannot publish it.
- The back-test table is the only real content, labelled as such.

**Design decisions.**
- Headline unit is the suburb, with ranges, per the §25 publishing decision. SA1 and mesh blocks are not shown.
- Sea level: today, +0.2 m, +0.5 m, +0.8 m. The year labels (about 2040, about 2070, 2100 benchmark) follow the Victorian planning benchmark of 0.8 m by 2100; they will be checked against the DataShare layer metadata when it arrives.
- The total gets its own range rather than the sum of area ranges, which would overstate the uncertainty.
- No map yet: the flood-area geometry for the sea-level scenarios doesn't exist here. A map view is a later step.
- Plain SVG, no D3 or MapLibre, so it loads quickly on phones. Checked at 1280 px (light and dark) and 390 px: no sideways page scroll, no script errors.

## 27. First DataShare delivery checked (2026-10-19)

The owner shared six DataShare order links. Four (FJU93V, SQYREY, YJA1AQ, PB7TWE) return S3 *AccessDenied*: the delivery links had expired or were withdrawn, so their contents are unknown. Two downloaded:

- **LBRN1F: Victorian Coastal Inundation, SLR20CM_2040** (3.6 MB; 1,424 polygons, 101 km², MGA2020 zone 55, clipped to a polygon around Port Phillip and Western Port; CC BY 4.0). The metadata settles the scenario set: **+20 cm by 2040, +47 cm by 2070, +82 cm by 2100**, each also as a 1-in-100-year storm tide version (surge +6%, +13%, +19%), all against 2009 sea level. The page's sample labels said +0.5 and +0.8 m; corrected to 0.47 and 0.82 m.
  - **Limits that shape the method:** a "bathtub" model (no flow or drainage connectivity), generalised for use at 1:75,000 or coarser, and "NOT suitable for assessments of potential risks at property level". So residents counted by address inside these polygons are reported for suburbs and SA2s only, never for SA1s or mesh blocks, and the page will say it is a bathtub model.
- **FM70LT: Vicmap Vegetation Tree Urban** (543 MB zip, 2.9 GB unzipped; tree points from 2018–20 aerial imagery by machine learning, F1 0.79). Not an input to the population forecast or the sea-level scenarios; set aside.

**Storage.** DataShare links expire, so CI cannot fetch from them. Once the full set arrives, the sea-level layers (a few MB each) go in `data/static/` like the Melbourne Water catchments.

**Boundary for DataShare orders (2026-10-19).** The owner asked for the Greater Melbourne shapefile to clip orders with. The manual workflow *Export study-area boundary* (`boundary.yml`, `.github/scripts/export_boundary.py`) dissolves the 31 councils in `config.py` (ABS ASGS 2021 LGAs, the site's own study area) and uploads zipped shapefiles in MGA2020 zone 55 (EPSG:7855, the CRS DataShare delivers in), a 20 m simplified copy for upload forms, the councils separately, and a WGS84 copy. Holes and slivers under 1 ha are removed so a clip never leaves gaps.

## 28. VIF2023 council projections in hand (2026-10-20)

The owner supplied the four VIF2023 workbooks (committed to `data/static/vif2023/`; the publisher's site refuses CI).

**What they give.**
- **LGA files (to 2036):** population, households, dwellings, persons per household and occupancy for all 79 councils, 2021/26/31/36, plus five-year age by sex. All 31 study councils match by name and code.
- **Region files (to 2051):** the same measures for the metropolitan regions only (five in Melbourne), five-yearly to 2051.
- **No SA2s.** VIF models SA2s internally but publishes councils. The control totals are therefore council totals, not SA2 totals.

**First numbers (31 councils).** Population 4,890,910 (2021) → 6,378,550 (2036), +30.4%; dwellings 2,028,360 → 2,667,440, +31.5%. Growth concentrates in the growth areas: Wyndham +175,930, Melton +168,170 (+93%), Casey +158,030, Hume +109,150, Whittlesea +103,570, Melbourne +88,420. Nillumbik grows least (+3,970, +6%).

**What it changes in the method.**
- The §25 back-test held SA2 totals at their true values. With council totals only, a council → SA2 step is added, which adds error. Next: re-run the back-test with only council totals known (2016 → 2021) to measure it.
- An honest out-of-sample check is now possible: VIF2023's 2026 figures against ABS ERP by council for 2024–25, as those years were future when VIF was made (base ERP 2022).
- Dwellings are projected too, which suits the address-based placement: projected new dwellings per council, placed where addresses are being created, converted to residents with VIF's own household size and occupancy.
- Population years (2026–2036) don't reach the sea-level years (2040, 2070, 2100). The region files reach 2051 at region level only; the page should pair 2036 population with the 2040 sea level and say so, rather than extrapolate councils past 2036.

**Licence.** The workbooks state no licence; the publisher's open data is generally CC BY 4.0. To confirm before the page is published.

## 29. Ensemble back-test: council totals to SA2s (2026-10-20)

**Question from the owner:** is there modelling from the literature that projects population with high confidence and less error? **Answer given:** no method gives high confidence at small-area level; error grows as areas shrink and horizons lengthen, and complex models (land-use, agent-based, cellular automata, cohort-component at SA2) have not shown lower error than simple ones. What the literature supports is combining simple models (Wilson 2015; Wilson et al. 2022), optionally with a machine-learning combiner (Grossman, Bandara, Wilson & Kirley 2022), and ranges from measured past errors. Neither source paper projects population; Lama & Sun list future development and climate change as a limitation and future work. The owner approved building and testing this.

**Design** (`pipeline/forecast/ensemble.py`, run by `forecast.yml`):
- Units are SA2 x council pieces, because SA2s do not nest exactly in councils. Each SA2's ERP is split across councils by its 2021 Census residents.
- Council totals are held at their true values, so the tests measure the council -> SA2 split alone, the step VIF2023's council-only totals add.
- Models: constant share, share of growth, linear, exponential, housing unit (addresses created in the previous five years), their mean (ENS), a gradient-boosting model trained only on earlier windows (ML), and ENS+ML. HUK uses addresses created after the base year: a near-term best case, not usable for 2036.
- Tests: 2011->2016, 2016->2021, 2021->2025 (h = 4-5) and 2011->2021, 2011->2025 (h = 10, 14; 2036 is 15 years from 2021). SA2 error is reported as WAPE, median, 80th and 90th percentile, and by SA2 size and growth class, for the page's ranges.
- VIF2023 is checked against actual 2025 council ERP (VIF interpolated between 2021 and 2026), and end to end: VIF council totals plus the split, against actual SA2 ERP 2025.
- Inputs extended: ERP by SA2 from 2001 (was 2016) and addresses created since 2006 (was 2016). Pre-2012 address dates are unverified; the run prints addresses per creation year to check for bulk-load spikes before HU on the 2011 base is trusted.
- Tested here on synthetic inputs in the real file formats (SDMX csv with labels, ABS xlsx with title rows, both with and without council ERP rows); the real numbers come from the CI run.
- **Downloads clipped to the study area** (owner's request). The address download used a fixed rectangle (~16,600 km², taking in Geelong's edge and West Gippsland, and cutting off the eastern edge of Yarra Ranges and Cardinia past 145.88°E). It now builds the 31 councils dissolved and buffered 1 km in MGA2020 zone 55 (EPSG:7855), requests only the 0.1° cells touching that, removes duplicates on cell edges by `ufi`, and keeps only points inside. The main site's downloads (`01_fetch.py`) still use the councils' bounding box; changing them needs a site rebuild to validate, so that waits for the owner's approval.

**Run 1 results (forecast.yml run 39351825006, commit a391c2e).**
- Inputs: 1,336,712 addresses created since 2006 inside the study area (1,363,671 matched in 136 cells; edge duplicates and points outside removed). Per year 39,682-85,712, no bulk-load spike, so pre-2016 dates are usable. ERP by SA2 2001-2025 (no council rows in this dataflow, so council actuals are SA2s split by 2021 residents). 371 SA2 x council pieces, 349 SA2s scored.
- Study-area ERP: 4,108,837 (2011), 4,642,177 (2016), 4,890,099 (2021), 5,338,153 (2025).

| SA2 WAPE, council totals true | 2011->16 | 2016->21 | 2021->25 | 2011->21 (h=10) | 2011->25 (h=14) |
|---|---|---|---|---|---|
| CS constant share | 8.5% | 9.8% | 6.6% | 16.9% | 22.7% |
| SG / LIN / EXP | 5.9-7.2% | 8.2-9.9% | 4.7-6.8% | 15.2-16.8% | 21.1-23.8% |
| **HU housing unit** | **4.3%** | **6.0%** | **2.7%** | **11.7%** | **17.0%** |
| ENS (mean of five) | 5.3% | 7.3% | 3.9% | 14.2% | 19.5% |
| ML / ENS+ML | - | 7.3% / 7.2% | 2.9% / 3.6% | - | - |
| HUK (future addresses known) | 4.0% | 4.8% | 3.2% | 7.0% | 7.8% |

**Findings.**
- **The housing-unit model beats the ensemble in every test.** The literature's "combine simple models" result does not hold here: averaging dilutes the one model with real information about where homes are being built. ML trained on one or two windows adds nothing yet.
- **Error is concentrated.** At h = 14 (ENS): SA2s under 5,000 residents median 53% error; SA2s that grew 60%+ median 34%; established SA2s of 15,000+ median 4%.
- **Knowing where homes will be built halves the long-horizon error** (HUK 7.8% vs HU 17.0% at h = 14). Land-supply data (UDP greenfield and redevelopment sites) is the lever for the growth areas.
- **VIF2023 is close so far.** Interpolated to 2025: 5,303,910 vs actual 5,338,153 (-0.6%); council WAPE 1.3%; it under-projected growth (413,000 vs 448,054 since 2021). Largest misses: Melbourne -5.5%, Monash and Glen Eira -3.4%, Maribyrnong +3.4%.
- **End to end 2021->2025** (VIF council totals + split, against actual SA2 ERP): CS 6.7%, ENS 3.9%, ENS+ML 3.6%, HUK 3.3% WAPE.

**Decisions.**
- Primary method: housing unit, with VIF council totals rebased to ERP 2025 (VIF is short on growth so far). Others stay as checks; ML is dropped until more training windows exist.
- Ranges on the page come from the measured error by SA2 size and growth class at h = 10-14, not one figure for all SA2s. Small and fast-growing SA2s get wide ranges and a flag; headline totals stay at council and study-area level.
- UDP land-supply data is now the highest-value missing input.

**Owner decisions (2026-10-20).** The main site's downloads stay on the councils' bounding box for now (clip them together with the scenarios launch, one rebuild instead of two). The monthly scheduled rebuild on 2 November stays on.

## 30. Sea-level layers 2040, 2070, 2100 in hand (2026-10-20)

Three DataShare orders, all clipped to the 31-council boundary (8,831 km², matching `boundary.yml`), committed to `data/static/coastal_inundation/`:
- ICA0IN: SLR20CM_2040, 631 polygons, 29.2 km² inside the study councils.
- QBY4LJ: SLR47CM_2070, 657 polygons, 37.7 km².
- K0XLIZ: SLR82CM_2100, 840 polygons, 62.6 km².

All geometries valid; extent grows with each scenario as it should. ICA0IN supersedes LBRN1F (§27), whose clip polygon reached beyond the councils (101 km²). Earlier order 84AZJS (SLR00CM_2009) came back empty because it was clipped to Banyule only.

**Still missing:** the 2009 baseline (needed to count residents *added* by sea-level rise, not those already in today's coastal extent) and the four storm-tide layers.
- **2009 baseline arrived** (order 21WL2D, SLR00CM_2009): 492 polygons, 20.8 km², clipped to the 31 councils; committed as `SLR00CM_2009.zip`. Area beyond the baseline: 8.5 km² (2040), 18.0 km² (2070), 41.8 km² (2100). The layers don't nest perfectly (1.13 km² of 2009 outside the 2070 layer, 0.08 and 0.03 km² for 2040 and 2100), so each future extent is taken as its union with 2009. A link `Order_QBY4LJ.zip?orderid=ELE0Q1` returned the 2070 file already held (S3 ignores the query); `Order_ELE0Q1.zip` is AccessDenied. Storm-tide layers still missing.

## 31. Planned: Urban Development Program pipeline in the housing-unit model (2026-10-20)

The owner pointed to the UDP 2025 methods page (planning.vic.gov.au; blocked to this environment and to CI, so read through search summaries; to verify against the page itself).

**What UDP provides (as summarised):**
- **Major redevelopment:** projects of 10+ dwellings in the established urban area, from aerial imagery, planning permits, real-estate and developer sites. Each has a status: Completed, Under Construction, Firm (approved and/or taking sales), Likely, Possible (early indicator, or inactive for years). UDP itself warns that some proposed projects are abandoned or delayed.
- **Greenfield:** proposed lots, zoned englobo land and unzoned englobo land (growth corridor plans, usually Urban Growth Zone). As at January 2025: 39,812 proposed lots, 165,671 lots from zoned englobo, 128,536 from unzoned englobo.
- **Not covered:** minor infill (under 10 dwellings).

**How it fits the forecast.** §29 showed that knowing where homes will be built halves the 14-year SA2 error (HUK 7.8% vs HU 17.0%). UDP is the best available forward-looking stand-in for that. Planned model:
1. Expected new dwellings per piece by year = Σ over sites of (dwellings × probability the site is built by then), with the probability set by status. Greenfield lots are staged in order: proposed, then zoned englobo, then unzoned.
2. Minor infill (not in UDP) continues at the recent address-creation rate (the current HU model).
3. Rescaled to VIF2023 council dwellings, converted to residents with VIF's household size and occupancy, and rescaled to VIF council population.

**The probabilities must be measured, not assumed.** An older UDP edition (2016, or the earliest available) lets each status's realisation rate be measured against addresses created at those sites since. Without an old edition, the rates would be guesses, and the page would have to say so. This is why the order asks for both 2025 and the oldest year.

**UDP delivery and its licence (2026-10-20).** Five orders: EQKZCF (GF2025, greenfield), KR7TGF and XDUSKJ (MRS2025, the same data twice), 7U99LV (IND2025, industrial land, not needed) and VQEO9G (RGF2024, regional greenfield: Moorabool only, outside the study area).
- **GF2025, MRS2025 and IND2025 come under a DEECA *Data Access Licence Agreement*, not CC BY.** Its terms: the material and "any product or service derived from" it must be kept confidential and not disclosed to any third party; "Permitted Information Products: None"; one computer; no copies except backup. Use is limited to the licensee's own project work.
- **Consequences:** these files are **not committed** to this public repository, and nothing derived from them may be published on the site while that licence applies. The copies downloaded for inspection were deleted after this summary. RGF2024 came with a Creative Commons licence, but it isn't needed.
- **What the data would offer** (aggregate counts only): MRS2025 has 2,173 projects and 184,827 dwellings by status (Completed, Under Construction, Firm, Likely, Possible). Completion years cover 2023-2024 only, so it gives no long history for measuring how often each status gets built. GF2025 has 298,115 lots (proposed, titled in 2024, zoned and unzoned englobo).
- **Open question for the owner:** the DataVic catalogue lists UDP datasets publicly, possibly under CC BY. If the catalogue licence is CC BY, the agreement attached to the order may be a generic default. Confirm with DEECA (gis.helpdesk@deeca.vic.gov.au) before any use that reaches the site.

**UDP route decided (2026-10-20).** The owner chose to use UDP in the model and to note the DEECA licence. This environment's automated safety check declined twice, first to create a repository secret for encrypted UDP files and then to bring the raw files into the repository folder. The owner chose the laptop route:
- `pipeline/forecast/udp_aggregate.py` (committed, no data) reads the DataShare zips from `data/private/udp/` (git-ignored) on the owner's computer. It writes `data/static/udp2025/udp2025_pieces.csv`: per SA2 x council piece, major-redevelopment dwellings by status and greenfield lots by status. No site detail is kept. Committing that file is the owner's decision; `data/static/udp2025/README.md` states the licence.
- The pieces (`data/static/sa2_council_pieces_7855.geojson`, 370 pieces, 355 SA2s, 8,832 km²) are ABS SA2s cut by the 31 councils, exported by `boundary.yml`. The workflow also prints them to its log, because this environment cannot download artifacts.
- Tested on synthetic data in the DataShare zip layout: dwellings and lots are conserved exactly (9,869 and 1,040), including a greenfield polygon split across pieces.
- **Council check (for the owner, not published):** VIF2023 needs 471,864 new dwellings in the 31 councils from mid-2025 to 2036. UDP identifies 158,080 in the redevelopment pipeline, 55,617 titled or proposed greenfield lots, 153,946 on zoned englobo land and 88,552 on unzoned land. Growth-area and inner councils are fully covered; middle-ring councils are not (Monash ~24%, Boroondara ~30%, Merri-bek ~38%, Mornington Peninsula ~11%), where small infill under 10 dwellings dominates.

## 32. The 2036 forecast (2026-10-20)

`pipeline/forecast/forecast.py`, run by `forecast.yml` after the back-tests; writes `data/processed/scenarios.json` for the page.
- **Base:** ABS ERP 2025 by SA2, split into SA2 x council pieces by 2021 Census residents.
- **Council totals:** VIF2023 growth from mid-2025 (interpolated) added to actual ERP 2025, keeping VIF's growth and removing its level error. Council dwelling need from VIF dwellings the same way.
- **Placement:** UDP 2025 supply per piece weighted by assumed build-out shares (under construction 95% in 2 years; firm 80% in 5; likely 50% in 8; possible 25% in 11; greenfield titled 95% in 2, proposed 85% in 5, zoned 60% in 11, unzoned 15% in 11), capped at each council's projected new dwellings; the remainder (small infill) by addresses created in the last 5 years. **The build-out shares are assumptions**: UDP 2025 has no history to measure them. The cap means they mainly decide where inside a council growth goes, not how much. An open-data-only run (no UDP) is computed alongside for comparison.
- **Flood areas:** "today" = planning overlays (LSIO, FO, SBO) plus the 2009 coastal extent; sea-level scenarios add the 2040/2070/2100 extents (each unioned with 2009). Existing residents by mesh-block address shares (as the live map); new residents by the share of 2016-2025 addresses in the same piece that fall inside.
- **Ranges:** SA2s from the housing-unit model's back-tested 80th-percentile error, interpolated by horizon and scaled by size and growth class; councils and total from VIF's 2021-25 council error grown linearly (about ±3.6% at 2036).
- **Page:** base year 2025, SA2 (top 25) / council toggle, proportional time axis, DEECA licence note when UDP is used, method text rewritten. Tested on synthetic inputs in this environment (desktop and phone, no script errors); real numbers come from the CI run.

**Storm-tide layers arrived (2026-10-20).** Orders N5IED9, HT9DOF, ZKWZ5D, JQ9CQI (CC BY 4.0), clipped to the 31 councils, committed to `data/static/coastal_inundation/`. A 1-in-100-year storm tide floods about five times the calm-water area: 101.1 km² (2009), 137.0 (2040), 163.8 (2070), 243.3 (2100), against 20.8 / 29.2 / 37.7 / 62.6 km². All geometries valid. **Nesting flaw:** 12.8 km² of the 2040 storm-tide extent lies outside the 2070 one (and 1.1 km² of calm 2009 outside storm 2009), presumably from modelling or generalisation differences; each storm-tide extent is therefore used cumulatively (itself + every earlier one + the calm layer of the same year). To add to the forecast as a second set of scenarios after the first real forecast run is checked.

**First real forecast run failed (run 39395650424).** Everything before the forecast step passed. `forecast.py` stopped with a GEOS TopologyException when merging the planning overlays: some Vicmap overlay polygons self-intersect, and `02_build.py` repairs them first while `forecast.py` didn't. Fixed: every polygon layer (councils, overlays, coastal extents) now goes through `make_valid` and keeps only polygonal parts; tested with a deliberately self-intersecting overlay.
- **Also fixed: every forecast run re-downloaded the main build's inputs (~70 min)**, because the workflow only restored the site's cache, never saved one. It now fetches just the five inputs it reads (`fetch.py --main`: councils, mesh blocks, mesh-block counts, overlays, addresses) and keeps them in its own monthly cache.
- **Storm tide added:** four more scenarios (today and +0.20/+0.47/+0.82 m, each with a 1-in-100-year storm tide, cumulative extents). The page gets a "Calm high tide / 1-in-100-year storm tide" switch, hidden when the data has no storm-tide scenarios (the sample).

**First real forecast (run 39406154294, commit b4658b7).** Downloads now 15 min (was 70); the forecast step took 23 min, mostly the area-share fallback for mesh blocks without addresses (one large intersection per scenario). Replaced with a spatially indexed overlay; identical results on synthetic data.
- **Population, 31 councils:** 5,338,153 (2025) → 5,441,403 (2026) → 5,928,573 (2031) → **6,412,793 (2036)**. VIF2023's own 2036 figure is 6,378,550; the difference is the rebasing to actual ERP 2025.
- **Residents in today's flood areas** (planning overlays + 2009 coastal extent): **209,713 (2025) → 279,282 (2036), range 269,528-289,036**, +33% against +20% population. The live map's 185,536 is 2021 residents in overlays only; scaled to 2025 population it would be about 202,000, so the 2025 base is consistent.
- **Why exposure outgrows population:** new housing concentrates where overlays are. Largest increases: Clyde North - South (519 → 7,965), Cranbourne South (843 → 8,155), Port Melbourne Industrial / Fishermans Bend (373 → 6,650, range 2,556-10,744), Southbank - East (16,087 → 21,887), Docklands (7,598 → 12,888), Southbank (West) - South Wharf (7,779 → 12,407). These come from where homes built 2016-2025 actually sit relative to the overlays, not from an assumption.
- **Calm sea-level rise adds almost no residents:** +0.82 m adds about 250 in 2025 and 280 in 2036. The calm extents fall mostly inside existing overlays or on unpopulated land (largest: Carrum - Patterson Lakes +100, Altona +65).
- **Storm tide matters:** with a 1-in-100-year storm tide, +0.47 m adds about 12,100 residents (2025 population) and +0.82 m about **50,000 (2025) / 64,300 (2036)**: 343,594 in 2036 (range 331,594-355,594). Today's storm tide adds only about 90, consistent with coastal LSIO already being drawn around storm-tide levels.
- **UDP changes where growth goes a lot:** it moves 153,744 of the 2036 residents between SA2s compared with the open-data method (council totals unchanged).
- **Caveat to carry onto the page:** "in an overlay" is not "flooded inside the home". Overlays require floor levels above the flood level for new buildings, and most new residents in Southbank, Docklands and Fishermans Bend live above ground level. The figure measures exposure of where people live, not damage.

## 33. Animations for sharing (2026-10-20)

The owner shared a column-map animation of stream gauges during Hurricane Helene (3D columns, colour = % of average flow, dark relief basemap) and asked for something similar. **The existing map and analysis pages are not to change** (owner's instruction); everything below is in new files and none of it is added to the site.
- **Forecast columns** (`web/columns.html`, `.github/scripts/record_columns.py`, run by `forecast.yml`): one column per SA2, height = residents in flood areas, colour = change since 2025 (cyan → blue → orange → red → pink, like the reference). Story: 2025 → 2036 in today's flood areas, then at 2036 population the 1-in-100-year storm tide at today's sea level, +0.20, +0.47 and +0.82 m. Dark CARTO basemap without labels plus a hillshade from AWS terrain tiles. 418 frames at 20 fps (~21 s), MP4 1280x720 and an 800-px GIF. The page waits for the style rather than every tile, so a slow tile server can't stall the recording. Tested here on synthetic data with the basemap blocked.
- **River gauges, October 2022** (`gauges.yml`, `probe_gauges.py`): the Bureau of Meteorology's Water Data Online KiWIS service works from CI. 444 discharge stations in the Melbourne box; Maribyrnong River at Keilor daily mean flow 7.7 m³/s on 12 October 2022 and 502.6 m³/s on 14 October; 15-minute and hourly series exist. Victoria's WMIS web service answered too, but the request needs a different format. A gauge animation of the October 2022 flood is feasible from BoM alone.
- **Dropped:** the earlier idea of a "Scenarios" button on the main map, because the main map must not change.
- **First real column video (run 39426274204, commit 4041086):** MP4 20.9 s, 418 frames, 6.6 MB, recorded in 7.5 min (about 1.1 s a frame with the real basemap in software rendering). Forecast numbers identical to the previous run. Two earlier attempts produced nothing: waiting for map 'idle' on every frame took 10+ s a frame, and buffered output hid the progress. Fixed with one rendered frame per step, `python -u`, a 12-minute frame budget and a 25-minute step cap. The GIF was 48.7 MB; now 640 px and every 3rd frame. Not yet reviewed by eye here (this environment cannot download artifacts); the owner reviews it before any sharing.
- **The first video showed an "API key" message instead of a map** (owner's review). The raster tile address used for the basemap (`basemaps.cartocdn.com/dark_nolabels/...`) evidently returns an API-key notice; the main site's CARTO vector style works. Switched to that style (`dark-matter-gl-style`) with its labels hidden, plus our hillshade and columns; if the style can't load within 20 s, a plain dark background is used instead. **It was missed because nobody had seen a real frame**: this environment can't download artifacts. The recorder now prints five sample frames into the run log as small JPEGs, and they are checked before a video is reported as ready.
- **The video didn't explain itself** (owner: "what does the map even explain?"). Added an opening "How to read this" card (column = one neighbourhood/SA2; height = residents in flood-prone areas; colour = change since 2025), a caption for each stage with the totals, and names on the places the story is about (largest 2025-2036 increases and storm-tide additions; Port Melbourne Industrial shown as Fishermans Bend; names within 2 km of one already shown are skipped). The video is now about 26 s.
- **Map on the scenarios page** (owner agreed; the main map is untouched). Same CARTO vector basemap as the main map (dark or light with the theme), data drawn under its labels. Neighbourhoods (the SA2 x council pieces) coloured by residents in flood areas for the chosen year and sea level (fixed classes 1-99 up to 10,000+, so years and scenarios compare), planning overlays in blue, the chosen scenario's coastal extent in teal, tap for name, value, range and 2025 figure. Geometry comes from `forecast.py` into `scenarios.json` (`geo`): pieces simplified 30 m (~450 kB), overlays 15 m with parts under 0.2 ha dropped, coastal extents 40 m / 10 m coordinates / parts under 0.5 ha dropped (the dataset is 1:75,000), ~2.3 MB for all eight. Hidden when the data has no geometry (the sample).
- **Second video checked from its own frames (run 39518644814):** the CARTO basemap now renders (bay, coastline, no API-key notice); card, captions and counter readable. Still wrong: Docklands, Southbank and Fishermans Bend labels overlapped, and the camera was too far out. Fixed: names at least 4 km apart, camera zoom 8.9 → 9.6 centred on the bay, tallest column 9 km (was 14).
- **The scenarios map explains itself** (owner: make it "more comprehensive so it can explain itself"). Added: a "What you're seeing" panel on the map (colours, blue overlays, teal coast, exposure not damage; folded on phones), the current year and scenario as a label on the map, three colour measures (residents in flood areas, share of residents, change since 2025; fixed classes each), names on the top five places for the current view (at least 3 km apart), a fuller tap popup (value, range, share of the neighbourhood's residents, 2025 figure, change), and a bridge sentence to the main map: 185,536 residents in overlays at the 2021 Census (main map) → the 2025 figure counted the same way plus coastal flooding → 2036. The map shifts right on desktop so the help panel doesn't cover the west.
- **How the video and this page relate to the original map:** the same address-point counting of residents in the same planning overlays, moved forward in time (2021 Census → ERP 2025 → 2036) and widened to coastal flooding and sea-level rise; the original shows who lives there (age, needs) by SA1 inside A/B circles, this shows how many, where and when by SA2.
- Robustness: map shapes are exported as polygons only (a repaired piece had come out as a geometry collection and broke the label points); the page also tolerates collections.
- **Phone view of the scenarios map** (owner: "make sure to consider phone view too"). Checked in iPhone 13 and Pixel 7 emulation. Fixed: the open help panel covered the whole map and place names showed through it, so on phones the help now sits under the map (folded by default); the state label collided with the zoom buttons, so the label is smaller and the zoom buttons are dropped on phones (pinch instead); names ran off the right edge, so phones show three names, smaller, anchored away from the nearer edge; and one-finger drags would have trapped the page scroll on the map, so phones use two-finger map movement (MapLibre cooperative gestures). No sideways scroll at 390 or 412 px.
- **Scenarios map with the main map's kind of controls** (owner: select variables, zoom to suburbs or SA1/SA2, other filters that fit). Added: an *Area level* switch (neighbourhood/SA2, suburb, SA1), a *Show on map* menu (residents in flood areas, share of residents, change since 2025, added by the chosen sea level or storm tide, all residents, population growth since 2025, width of the likely range), a council → suburb slicer that zooms to the selection and greys out the rest, a *Find a suburb* box, colour classes recomputed within the selection (five equal-count classes, as on the main map), hover popups on desktop and tap popups on phones. Year, sea level and calm/storm tide still drive everything.
  - **Suburbs and SA1s come from the forecast** (`finer()` in `forecast.py`): each piece's population and residents-in-flood-areas are spread over its mesh blocks (existing residents by 2021 Census share, growth where addresses were created in the last 5 years; flood shares from each mesh block's address points, new homes by the shares of addresses created since 2016), rescaled so mesh blocks add back exactly to the piece totals, and summed to SA1s; suburbs are sums of their SA1s (SA1 to suburb by representative point, as the main map). Ranges: suburbs use the SA2 back-test error; **SA1s use 1.9 times it** (SA1 placement error 11.6% vs SA2 split error 6.0% in the back-tests), and the page says SA1s are the least certain level. Mesh blocks are still never shown.
  - **SA1s load only when chosen** (`scenarios_sa1.js`, loaded as a script so it also works when the preview is opened from disk), keeping the first load light on phones. `fetch.py --main` now also fetches SA1 and suburb boundaries (cache key bumped, restoring the previous one so only the new files download).
  - Tested on synthetic inputs (desktop and iPhone emulation): council filter, suburb level, variable switch, SA1 loading and Find all work, no script errors, no sideways scroll.
- **First real run of the finer levels (run 39744327671):** 518 suburbs, 11,293 SA1s (5.9 MB, loaded on demand), suburb shapes 663 kB; forecast totals unchanged. **The consistency check failed**: SA1s did not add up to the piece totals. Cause: a piece can have residents in a flood area while none of its mesh blocks does on its own (new homes counted at piece level from mesh blocks with too few new addresses to judge), and those were dropped. Fixed by spreading such a piece's figure over its mesh blocks by population; the check now prints the difference per scenario (zero on synthetic data).

- **Scenarios map, closer to the main map** (owner: storm tide not visible, names overlapping when zoomed, "only see notes when I roam", layer switches, A and B as on the main map).
  - **Storm tide was already modelled** (1-in-100-year storm tide at today's sea level and +0.20/+0.47/+0.82 m), but it could only be chosen above the chart. A *Coast* menu (calm high tide / with storm tide) now sits with the map controls and stays in step with the one above.
  - **No permanent place names.** The top-five labels are gone; information appears only on hover (desktop) or tap (phones), as on the main map.
  - **Layers card** (folds behind a *Layers* button on phones): areas coloured by the measure, area outlines, river flood overlays, overland-flow overlays, coastal flood extent, basemap. The overlays are now split as on the main map: river (LSIO/FO, stronger blue, solid edge) and overland flow (SBO, light blue, dashed); `forecast.py` tags each overlay part `t: r|s`.
  - **Compare A and B**: a switch in the Layers card, then click (tap) the map to place A, again for B, then to move the nearer one; radius 300–2,000 m (default 800 m). Each circle sums the SA1s whose centre falls inside it (coarser than the main map's circles, which split SA1s by mesh block) and the table under the map compares A and B on the measures in *Show on map* for the chosen year and scenario, with ranges as for suburbs. The SA1 file loads when A/B is first switched on.
  - Phones: the area-level switch fills the row instead of wrapping into an oval; the A/B table wraps its labels so both columns fit at 390 px without sideways scrolling.
  - Tested on synthetic data in desktop and iPhone 13 emulation: hover and tap popups, storm-tide switch, layers off/on, two pins placed and the table filled, no script errors, no sideways scroll. **Not yet seen on the real data in a real browser.**
- **A and B made the same as the main map** (owner: "point A and B is not as same the original page"; "SA1 (finest) is not showing anything").
  - A/B is always on, as on the main map: the main map's two example areas are placed when the page opens; click to place or move the nearer pin, drag either pin, radius and *Clear areas* under *Layers*. The comparison sits beside the map on desktop (below it on phones) with the main map's layout: two headline boxes (residents in flood areas in A and B, and the suburbs they are mostly in), then a table with A, B and the whole selection (all 31 councils, or the chosen council/suburb).
  - **Counting as on the main map**: a circle counts the mesh blocks whose centre falls inside it, each adding its share of its SA1's residents (per year) and of its SA1's residents in each flood area; with a council or suburb chosen, only its residents count. The SA1s a circle touches are shaded in its colour, darker for a larger share counted. The earlier version counted whole SA1s by their centre, so small circles often came out as 0. `forecast.py` now writes the mesh-block points into `scenarios_sa1.js` (`mb`: position, SA1, residents share per year, flood share per scenario in thousandths). Flood shares within an SA1 use the final year for every year, and a circle's flood count is capped at the residents it counts.
  - The SA1 file now loads when the page opens (A/B needs it). **If it cannot load**, the page now says so plainly and gives the likely cause: opening `index.html` from inside a zip file, which leaves `sa1.js` behind. SA1 outlines show from zoom 9 (was 10).
  - Not reproduced here: why SA1 showed nothing for the owner. Likely causes are the zip (no `sa1.js` beside the page) or zoom (most SA1s have no one in a flood area and are left uncoloured; the rest are small at city scale). To see the real page, `forecast.yml` now opens the preview in desktop and phone browsers and prints, for the example areas and for the SA1 level in Maribyrnong, what was drawn, the panel figures, script errors and small screenshots (`.github/scripts/check_scenarios.py`). The video is optional (`video` input) so a check run takes ~25 minutes instead of ~45.
  - This environment's container was reset mid-task and the uncommitted work was redone from the session record.
- **First browser check on the real data (run 40188594770):** no script errors on desktop or phone, no sideways scroll (1280 / 390 px). The SA1 file loads (50,713 mesh-block points) and the two example areas show A 12 and B 1,118 residents in flood areas in 2036 (Avondale Heights/Keilor East; Footscray), shading 19 and 24 SA1s. At SA1 level in Maribyrnong, 196 SA1s are drawn and coloured (seen in the screenshots), so the SA1 level works when `sa1.js` sits next to the page; the owner's empty SA1 map was most likely the page opened from inside the zip. With Maribyrnong chosen, A (outside it) reads "0, outside Maribyrnong", as the main map does. The check's "coloured" count read 0 because it counted the wrong entries of the colour expression; fixed. On phones the A/B readout overlapped the map credits; moved above them.
- **Owner review of the scenarios page (2026-10-25)**: SA1 empty, A/B clicks not working and the suburb highlight not working (the page reported "SA1 data could not be loaded"); B wanted under A; the radius value ran out of its card; overlays all blue; the council chart unclear; the "not yet included" list stale.
  - **SA1 data is now built into the preview page** (`preview.py`), so the download is one self-contained `index.html`. On the owner's computer the separate `sa1.js` did not load even though the CI browser loaded it from the same folder; the likely cause is opening the page without it beside it (from inside the zip, or the page copied on its own). The site build still keeps it as a separate file loaded on demand.
  - Pins are placed and moved by clicks even before (or without) the SA1 data; the figures fill in when it arrives. The main map's example areas are placed at once.
  - The chosen suburb is outlined (dark line with a light halo), as on the main map.
  - Area B sits under area A; the radius slider shrinks so its value stays inside the Layers card.
  - Overlay colours: river overlays blue, overland-flow overlays cyan with a dashed edge, coastal flood extent green (was teal), so the three no longer read as one blue.
  - Council/SA2 chart: was a dot (estimate), a faint bar (range) and a tick (2025), hard to read. Now a bar: grey to the 2025 figure in today's flood areas, coloured for what is added by the chosen year (growth plus any sea level or storm tide), an outline where the figure falls, and a thin line with end caps for the likely range; a key above the table and the scale in the column header.
  - "Not yet included": storm tide removed (it has been in since the storm-tide extents arrived; the method list now says so); flood depth stays, with the reason (no depth data covering Greater Melbourne in this project).
  - The browser check in `forecast.yml` now also clicks the map twice after *Clear areas* (pins must follow), selects a suburb (its outline must be drawn), checks the radius value stays inside its card, and screenshots the council chart.
- **Browser check of those fixes on the real data (run 40196181237), desktop and phone:** SA1 level coloured (67 of 196 SA1s in Maribyrnong have residents in flood areas; the rest have none and stay clear), chosen suburb outlined (Braybrook), two clicks after *Clear areas* place A and B with figures (e.g. A 299 Port Melbourne, B 3,355 Melbourne/South Melbourne), radius value inside its card, B under A, council bar chart readable, no script errors, no sideways scroll. Then, from the phone screenshot: the A/B readout still sat on the map credits (moved under the state label, which now stays on one line), the A/B table's labels were squeezed to one word a line (numbers may now wrap), and blue river overlays over the red colours read as purple, close to circle A (river fill lighter, .42 → .28, with a firmer edge).

## 34. Checks on the flood count itself (2026-10-26)

The population back-tests (§25, §29) measure where people will live, not how many of them will be in flood areas, and the owner asked why the City of Melbourne leads (43,226 in 2025 → 62,862 in 2036: Southbank, Docklands and Fishermans Bend, where large new apartment projects sit on low-lying land under overlays) and how else accuracy can be tested. Two checks added in `pipeline/forecast/floodtest.py`, run by `forecast.yml` after the forecast (report-only step; output `floodtest.txt`, `data/processed/forecast_floodtest.json`):
- **Flood-count back-test, 2016 → 2021.** Each SA2's 2021 residents in today's flood areas predicted the forecast's way from 2016 (residents already there at their address share inside the flood areas, growth at the share of addresses created 2016-2021 inside them), with SA2 totals known. Compared with (a) 2021 counted from the Census mesh-block counts and the address shares of addresses that existed by Census night 2021, and (b) an exact subset: mesh blocks wholly inside the flood areas (all addresses inside and 95%+ of the area), where every Census resident is in a flood area whatever the counting method. Two simple rivals as yardsticks: growth at the existing share, and the 2016 count unchanged. Also: the 2021 count by area share instead of address share, by council, to show how much the count depends on the counting method.
- **Ground-level residents.** The count includes everyone whose address is inside a flood area, so a 40-storey tower counts in full. From Census 2021 table G36 (dwelling structure, persons) for each SA1, an assumed share of each type's residents at ground level (houses, townhouses 1; flats in 1-2 storey blocks 0.5, 3 storeys 0.33, 4-8 storeys 0.15, 9+ storeys 0.03; low and high variants), applied to the forecast's SA1 figures for 2025 and 2036 by council. SA1s with under 30 residents take their SA2's mix. Growth gets the SA1's 2021 mix, which overstates the ground-level share where towers replace houses or industry. Tested here on made-up inputs only.
- **Results (run 40282079347):**
  - *Back-test 2016 → 2021, SA2 totals known.* 2021 residents in today's flood areas, counted from the Census the forecast's way: 186,238 (the main map's 185,536 is overlays only). Predicted from 2016: 193,943 (+4.1%). **The growth was overstated**: +20,519 predicted against +12,815 observed (1.6 times). Part of this is probably COVID: Census night 2021 fell in a lockdown with international students away, emptying many Southbank and Docklands apartments, which are in flood areas; how much is not known. SA2 WAPE 9.4% (median 4.3%, 78% within 10%) against 10.9% for growth at the existing share and 14.1% for the 2016 count unchanged; council WAPE 6.0% (rivals 6.1%, 11.0%). So the new-address step helps at SA2 level and barely at council level.
  - *Exact subset:* 596 mesh blocks wholly inside flood areas, 49,452 residents in 2021, predicted 50,328 (+1.8%); WAPE 23.7% by mesh block, 7.6% by SA2 (55 SA2s).
  - *Counting method:* measuring each mesh block's share by area instead of by address points gives 242,865 (+30%), with large swings by council (Merri-bek +70%, Casey +48%, Stonnington +43%, Port Phillip +35%, Melbourne +12%). The counting method matters more than the forecast error; address points are the better choice (people live at addresses, and flood overlays cover roads, parks and creek corridors), but the figure is not method-free.
  - *Ground level (G36 persons columns found for all eight types):* 2025: 150,330 of 209,708 residents in flood areas at ground level (146,517-154,480); 2036: 192,130 of 279,279 (186,960-197,870), 69%. **City of Melbourne: 6,956 of 62,866 (11%, 4,801-9,932)**, so at ground level it falls from first to about tenth. Casey leads at ground level (30,963, 100%: houses), then Glen Eira 17,990, Cardinia 15,568, Merri-bek 15,214, Kingston 14,999, Port Phillip 12,007 (49%), Stonnington 5,606 (47%). Melbourne's lead in the headline count is mostly towers.

## 35. Ground-level measure, COVID check, and sources for two more checks (2026-10-26)

- **Ground level on the scenarios page.** `forecast.py` now computes, for every SA1, the share of residents living at ground level (Census 2021 G36 dwelling types, the §34 assumptions; helpers `g36_table`, `ground_share`, used by `floodtest.py` too) and stores a ground share for SA1s, suburbs, SA2s and councils (weighted by 2036 residents in today's flood areas). The page gets a *Residents in flood areas at ground level (estimate)* measure, a ground-level line in the hover popups, and a row in the A/B table; hidden when the shares are absent. G36 is cached with the forecast's main inputs (cache key v3).
- **COVID check.** `floodtest.py` now splits the 2016 → 2021 growth in flood areas (observed vs predicted) between the four inner councils where Census night 2021 emptied apartments (Melbourne, Port Phillip, Yarra, Stonnington) and the rest, and lists the councils with the largest overstatements. If the overstatement sits in the inner four, COVID is the likely cause; if it is spread out, the new-address flood share needs scaling down.
- **Sources for the next checks** (owner asked about the UDP back-test and comparison with council forecasts such as .id): the 2017 and 2018 UDP editions (Major Residential Redevelopment Sites, Broadhectare Residential Land) are on DataVic under CC BY, unlike UDP 2025, so a UDP back-test can run from 2017 in CI without the licence problem. The City of Melbourne publishes its own small-area forecasts (CLUE areas, 2023-2043, prepared by SGS) under CC BY. .id's council forecasts are copyright .id; downloading them for a private comparison may be fine but their numbers should not go into this repository or the page without checking .id's terms. `probe_sources.py` (manual workflow *Probe data sources*) lists and reads these sources so the checks can be written against their real layouts.
- **Probe results (run 40308096082):** UDP 2017 and 2018 (MRS and Broadhectare) are CC BY 4.0 on DataVic, but their resources point to DataShare search pages: the files come only through a DataShare order (free), so they cannot be fetched in CI; the owner orders them and they can be committed under `data/static/` (the licence allows it). The City of Melbourne forecasts download directly (opendatasoft API; columns geography, year, gender, age, value; single years 2023-2043), as do the CLUE small-area boundaries (GeoJSON). DataVic shows their licence as "other-open"; the City of Melbourne's open data is CC BY 4.0 and is credited as such.
- **City of Melbourne comparison** (`com_compare.py`, report-only step in `forecast.yml`, output `com_compare.txt`, `data/processed/forecast_com.json`): our SA1 populations summed to the 13 CLUE areas (SA1 representative points), beside the council's own forecast for 2025 and 2036, with our 2036 residents in today's flood areas per area. A comparison, not a test.
- **Results (runs 40308100220, 40316329665).** *COVID is not the cause* of the overstated 2016 → 2021 growth in flood areas: the four inner councils were slightly *under*-predicted (observed +7,567, predicted +6,211); the others were over-predicted 2.7 times (observed +5,239, predicted +14,308), mostly Casey (+4,333) and Bayside (+3,640). *Cause:* the flood share of new addresses is higher than the flood share of new residents: 6.9% vs 4.6% overall, 22.2% vs 20.8% in the inner four, 3.8% vs 2.6% elsewhere; addresses created 12+ months before Census night give 7.1%, so it is not a timing lag. Clearest case: Casey SA2 212031556 (340 → 14,806 residents; 1,339 of 6,731 new addresses in flood overlays; residents in flood areas +227). Likely: overlays on creek and drainage corridors in new estates collect addresses (lots, reserves, later amendments) but few residents. Bayside SA2 208011169 is a measurement effect, not a forecast error: population flat (22,715 → 22,755) while the counted figure moved 3,665 between the 2016 and 2021 address stocks. *Ground level:* 192,122 of 279,270 in 2036; the A/B table row and the map measure work (browser check, no errors). *City of Melbourne comparison:* failed on the boundary name column; also their file has a "City of Melbourne" row that was being added to the small areas (sum 392,449 for 2025 instead of about 196,000). Fixed: name column picked by matching their area names, municipality row kept apart.
- **City of Melbourne comparison (run 40329587131).** Their 13 small areas: 196,229 (2025), 261,896 (2036); ours on the same areas 194,730 (−1%) and 252,826 (−3%). By area, 2036 (ours vs theirs): Docklands 32,057 vs 26,918 (+19%), Port Melbourne (the council's part of Fishermans Bend) 5,595 vs 522, Southbank 39,039 vs 40,311 (−3%), CBD 76,817 vs 75,685 (+1%); lower than theirs in North Melbourne (23,045 vs 28,504, −19%), Kensington (−19%), Parkville (−24%), East Melbourne and South Yarra (−26%), West Melbourne residential (−13%). Reading: totals agree; *where* differs. Ours concentrates growth on UDP 2025 redevelopment sites (Docklands, Fishermans Bend), theirs spreads it more widely, including the Arden precinct (North Melbourne, Kensington) and established areas. Both Docklands and Arden are flood-prone, so the effect on the flood count partly cancels: using their area totals with our flood shares per area gives roughly 2,000-2,500 fewer residents in flood areas in the City of Melbourne in 2036 (about 60,500 instead of 62,866), mostly Docklands and Fishermans Bend. Our SA1s are assigned to CLUE areas by representative point, so boundary slivers (West Melbourne Industrial) are noise. A comparison, not a test: either can be wrong.

## 36. UDP back-test with the 2017 and 2018 editions (2026-10-27)

The owner ordered the 2017 and 2018 UDP editions from DataShare (CC BY 4.0, unlike UDP 2025): Major Residential Redevelopments Sites (3,918 and 3,440 projects; with dwellings by type and maximum storeys) and Broadhectare Residential Land (2017: 1,876 parcels with expected timing bands 1-2, 3-5, 6-10, 11+ years, UGZ, no timing; 2018: 66,474 lots and englobo parcels by development status). Stored as delivered in `data/static/udp_history/` with a README crediting the Department of Transport and Planning.

`pipeline/forecast/udp_backtest.py` (report-only step in `forecast.yml`, before the forecast):
- **Placement test.** Base 2017 (and 2018) to 2021 and the latest ERP year, council totals known, SA2 x council pieces: the forecast's method (UDP supply weighted by status and timing, capped at council growth, 2.6 residents per dwelling, remainder by addresses of the previous 5 years) against addresses only (HU) and constant share, scored on SA2 ERP, overall and for SA2s that grew 30%+.
- **Build-out test.** For each 2017 status and timing band, the share of the dwellings or lots actually built by mid-2021 and mid-2025, measured by addresses created on the site since mid-2017 (capped at the site's supply), to check the share-built weights assumed for 2025. Apartment buildings sometimes share one address, so the redevelopment shares are lower bounds.
- Tested here on the real UDP files: 2017 supply 560,764 dwellings/lots in 329 SA2s, 2018 592,370 in 322; the scoring needs the CI inputs (ERP, addresses).
- **Results (run 40453124896).** *Placement* (SA2 WAPE; fast-growing SA2s = grew 30%+, median / 80th-percentile error):

  | Test | Constant share | Addresses only (HU) | UDP + addresses | Fast-growing: HU | Fast-growing: UDP |
  |---|---|---|---|---|---|
  | 2017 → 2021 (4 y) | 8.1% | 4.6% | **3.9%** | 12.6% / 33.9% | **9.9% / 21.5%** (27 SA2s) |
  | 2017 → 2025 (8 y) | 13.7% | 6.9% | **4.8%** | 19.6% / 35.2% | **7.2% / 19.5%** (42) |
  | 2018 → 2021 (3 y) | 6.3% | 3.6% | 3.5% | 11.5% / 26.9% | 15.7% / 22.4% (19) |
  | 2018 → 2025 (7 y) | 11.8% | 5.5% | **4.8%** | 12.0% / 30.2% | **10.8% / 20.0%** (34) |

  The UDP step helps, most over longer horizons and in fast-growing areas, where it cuts the 80th-percentile error by a third to a half; at 3 years it is a draw. This supports keeping it in the 2036 forecast. *Build-out of 2017 supply* (addresses created on the site since mid-2017 / supply): redevelopment under construction 53% by 2021, 56% by 2025; firm 29% / 41%; likely 14% / 25%; possible 7% / 17%; completed (control) 5% / 6%. Greenfield: 1-2 years 48% / 55%, 3-5 years 45% / 68%, 6-10 years 26% / 53%, 11+ years 13% / 39%, UGZ 13% / 31%, no timing 18% / 36%. Both are lower bounds: apartment blocks can share an address, and lots in the near-term greenfield bands often had addresses before 2017 (the 1-2 years band shows less than 3-5 years by 2025). A cleaner measure (house and townhouse projects only, one address per dwelling) is added for the next run. If under construction (assumed .95 in 2 years) really reached about 95%, the address undercount is about 1.7 times, and firm, likely and possible come to about 70%, 42% and 29% by 8 years, against the assumed 80% (5 y), 50% (8 y) and about 18% (8 of 11 y): firm and likely slightly optimistic, possible slightly pessimistic. Bug fixed: the printed council growth summed each council once per piece.

## 37. Calibration and evidence (2026-10-27)

The owner approved three corrections and a "Method and evidence" section.
- **Build-out weights** (`forecast.STATUS`), from what UDP 2017 delivered by 2025 (§36, corrected for apartment blocks sharing addresses): firm (0.80, 5 y) → (0.75, 8 y); likely (0.50, 8 y) → (0.50, 10 y); possible (0.25, 11 y) → (0.35, 11 y). Under construction and the greenfield categories unchanged. Supported in direction by Lichfields, *Start to Finish* (3rd ed., 2024): large brownfield apartment schemes over 3 times longer from approval to first completion; brownfield 34% slower than greenfield.
- **Flood share of new residents**: the share of new addresses inside flood areas is scaled by the 2016 → 2021 ratio of new residents to new addresses in flood areas (§35): 0.94 in Melbourne, Port Phillip, Yarra and Stonnington, 0.68 elsewhere (`FLOOD_CAL`).
- **Ground level of growth**: new addresses since mid-2016 in apartment buildings (5+ new addresses at one point, or 100+ new addresses per hectare of mesh block) get the 4+ storey ground share (0.08); growth in each SA1 takes the mix of homes built there since 2016 instead of the 2021 dwelling mix (Footscray and other new-tower areas).
- `forecast.py` prints the before/after effect by council (population and residents in today's flood areas, 2036) and the ground-level total with the 2021 mix only versus with the new homes' mix.
- **Method and evidence** section on the scenarios page: each step with its evidence (journal articles, reports, our back-tests, or assumption) and a confidence level; references to Smith & Cody (2013), Wilson et al. (2022), Rayer, Smith & Tayman (2009), Le, Melser & Ruthbah (2025), Smith et al. (2019), Zandbergen (2011), AHURI Final Report 420 (2024), Lichfields (2024), the UDP editions. Le et al. (2025) read in full: postcode level, WRI Aqueduct flood depth > 0.5 m, flood risk not significantly related to housing growth (coefficient -1.10, s.e. 2.74), so it is cited as national context, not as confirmation of the Melbourne finding.

## 38. Better flood data: the modelled 1% AEP extent and the October 2022 flood (2026-10-27)

The owner asked for better flood data. Found: the *Victorian Flood History October 2022 Event* extent (DEECA, CC BY 4.0) is served on the Vicmap WFS (`open-data-platform:vic_flood_history_public`), so no DataShare order is needed; the modelled 1% AEP extent was already fetched for the main map (`01_fetch.aep1`, Victorian Flood Database). No flood-depth grid covering Greater Melbourne was found (the database holds extents, contours and spot heights from flood studies).
- `fetch.py --main` now also fetches both (`data/raw/shared/aep1.geojson`, `data/raw/metro/flood_oct2022.geojson`; forecast cache key v4).
- `forecast.py`: the 1% AEP extent is a second definition of "flood area" (zone `aep`): residents in it in 2025 and 2036, by council, printed and stored in `scenarios.json` (`aep`); not yet shown on the page.
- `floodval.py` (report-only step): residents (Census 2021, placed by address) inside the observed October 2022 flood, and the share of them that were inside the planning overlays, the 1% AEP extent, or either. A test of whether our flood areas catch the people a real flood reaches; residents in flood areas the 2022 water missed are not errors.
- **Results of the calibration (run 40505054817).** Residents in today's flood areas, 2036: **279,270 → 265,087** (−14,184; range 255,828-274,345). Casey 30,984 → 25,154 (−5,830), Melbourne 62,861 → 61,489, Cardinia 15,730 → 14,563, Moreland/Merri-bek 17,633 → 16,704; every council down a little. Council populations unchanged (VIF totals); the build-out weights only move growth *within* councils. **Fishermans Bend did not slow**: the City of Melbourne part (CLUE "Port Melbourne") went 5,595 → 5,777, because at an 11-year horizon all redevelopment ramps finish and the new weights (firm .75, likely .50, possible .35) keep roughly the same proportions (possible even rose). Slowing large brownfield apartment precincts (Lichfields 2024) needs project size at piece level, which the UDP 2025 aggregate does not carry. *Apartment signal*: 168,996 of 574,190 addresses created mid-2016 to mid-2025 are in apartment buildings (168,400 at shared points, 83,440 in dense mesh blocks); ground level 2036 with the 2021 dwelling mix 180,193, with the new homes' mix for growth 177,449 (of 265,087). Browser check: no errors (desktop 1280 px, phone 390 px). City of Melbourne comparison unchanged in substance (2036: ours 252,833, theirs 261,896).
- **First results (run 40508665207).** *1% AEP extent*: the fetch took Victorian Flood Database layer 14 "Flood extent - 1 in 100 year recurrence <250K", a statewide 1:250,000 compilation (308 polygons, 191.5 km² in the study area against 860.8 km² of planning overlays). Residents in it: 17,747 (2025) → 25,157 (2036), against 265,114 in overlays + present coast. Too coarse for urban Melbourne (Wyndham 11,511 in it vs 607 in overlays in 2036; Melbourne 1,185 vs 61,498): it maps the main rivers' floodplains broadly and misses urban overland flow. Next: layer 12 "Flood - 1 in 100 years" (detailed, from flood studies), fetched for the forecast only (the main map's `aep1.geojson` is left as it is). *October 2022 extent*: the public layer has one polygon covering 1.3 km² of the study area (the Maribyrnong River reach). Inside it, 1,103 residents (Census 2021, by address): Maribyrnong 710, Moonee Valley 392. Inside the planning overlays beforehand: 86% (Maribyrnong 100%, Moonee Valley 60%); inside the 1% AEP extent: 99%. So the overlays missed about 40% of the people the 2022 flood reached in Moonee Valley (about 157), and the modelled extent caught them. One reach, one event: indicative only.
- **Detailed layer: none exists (run 40520399197, probe 40535684491).** Layer 12 "Flood - 1 in 100 years" is a *group* layer (parent 11 "Statistical Flood Data") holding only 13 (height contours, polyline) and 14 (the <250K extent). The Victorian Flood Database's public service has no finer 1-in-100-year extent polygon; the forecast falls back to the coarse extent, with a WARNING. `fetch.aep_detailed` now reads `/layers` and picks any 1-in-100-year polygon layer other than the 1:250,000 one, so it will use a detailed layer if one is published. The other return periods (1 in 5/10/20/50/200/500) are marked "limited coverage" (0-279 polygons in the metro box). No 1% AEP dataset was found on DataVic either (searches: "flood extent 1% AEP", "Melbourne Water flood", "flood study extent"; only coastal inundation sets). Melbourne Water's flood mapping is public only through the planning overlays, so the overlays stay the main definition. Not yet used: layer 9 "Flood extents - history" (136 polygons in the metro box, earlier recorded floods), which could extend the October 2022 test to more events. October 2022 results unchanged (1,103 residents; 86% in overlays, 99% in the 1% AEP extent).
