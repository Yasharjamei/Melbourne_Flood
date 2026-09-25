# Who lives in the flood path

Prototype explorer comparing the age–sex structure and flood-relevant needs of any two places in Maribyrnong and Moonee Valley (474 SA1s, Census 2021), overlaid on Victorian planning-scheme flood overlays.

Inspired by a Mashhad "Demographic Explorer" (city-wide pyramids hide neighbourhood differences) and applied to the study area of Lama & Sun (2026, *Urban Informatics* 5:25) and Lee, Sun & Wachowicz (2026, Research Square preprint).

## Run

```bash
pip install -r requirements.txt
bash pipeline/01_fetch.sh      # public data -> data/raw
python pipeline/02_build.py    # -> data/processed/data.json
python pipeline/03_bundle.py   # -> dist/index.html (open in a browser)
```

## Method, in one paragraph

Each SA1's census counts are spread evenly across a 50 m grid of points inside it. A circle sums the share of points it contains. Flood overlays (LSIO and Floodway = riverine; SBO = overland flow) are flagged per grid point, so "residents in overlay" is also area-weighted.

## Known limitations (the backlog)

- Uniform-density apportionment: residents are placed on parks and industrial land. Next step: dasymetric weights from building footprints or G-NAF address points.
- Flood extents are planning controls, not modelled depths from the October 2022 event.
- No basemap in the self-contained build.
- No SEIFA yet; income is a population-weighted mean of SA1 medians.
- ABS perturbation means totals differ slightly between tables.
