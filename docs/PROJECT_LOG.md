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

