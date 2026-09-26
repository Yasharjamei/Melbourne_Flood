# Contributing

Thanks for helping. This guide covers setting up, running the pipeline, checking a change and opening a pull request. For how the code fits together, read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) first: it has a section-by-section tour and the data contract between the pipeline and the pages.

## 1. Set up

You need Python 3.11 or newer and git.

```bash
git clone https://github.com/Yasharjamei/Melbourne_Flood.git
cd Melbourne_Flood
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Build the pages locally

```bash
python pipeline/01_fetch.py  --study west    # about 1 minute; downloads into data/raw/ (git-ignored)
python pipeline/02_build.py  --study west    # about 10 minutes, mostly GWR/MGWR
python pipeline/03_bundle.py                 # writes dist/index.html and dist/analysis/index.html
```

Open `dist/index.html` in a browser; no server is needed. For all 31 councils, run the first two steps with `--study metro`. That takes about 10 minutes and several hundred MB of downloads the first time.

The fetch step needs these hosts:

- `geo.abs.gov.au`
- `www.abs.gov.au`
- `opendata.maps.vic.gov.au`
- `copernicus-dem-30m.s3.amazonaws.com`
- `maps.isric.org`

**Front-end only?** If you're only editing `web/*.html`, re-run `03_bundle.py` on the existing `data/processed/*.json`. It takes seconds.

**Refetch one input:** delete its file under `data/raw/`.

## 3. Check your change

There's no unit-test suite yet. The checks are:

1. **The pipeline runs clean.**
   - Look for `WARNING` lines in the build output. Each fallback is also listed in the page footer.
   - The coverage check in `02_build.py` fails the build if any council's SA1s cover less than 90% or more than 110% of its area.
2. **The pages load without console errors.** Try:
   - switching variables
   - choosing a council, then a suburb
   - dragging both circles
   - switching between dark and light mode
3. **CI is green on your pull request.** CI rebuilds everything from live data and pushes screenshots of both pages and both analysis pages to the `ci-preview` branch. Look at them before asking for review.

## 4. Conventions

- **Python:** plain scripts, top to bottom, with a `# ----` banner per stage. Add a docstring to any new function. Keep comments on *why*, not *what*.
- **JavaScript:** vanilla code plus D3 and MapLibre, with no build step. Mark sections with `// ----`.
- **Every substitution or fallback goes into `NOTES`**, so the page states it. Never fail silently.
- **Colours:** each map variable has its own ColorBrewer scheme. Violet and orange are reserved for circles A and B.
- **Data:** only public, openly licensed sources. Record the licence in the README's data table.
- **Docs travel with code.**
  - A user-visible change adds a line to `CHANGELOG.md`.
  - A method change updates the README's Method section.
  - A decision worth remembering goes in `docs/PROJECT_LOG.md`.
- **Commits:** imperative subject of 72 characters or less. The body explains why.

## 5. Pull requests

1. Branch from `main` with a short descriptive name, such as `address-points` or `fix-legend-dark-mode`.
2. Push, then open a pull request against `main`. Say what changed, why, and how you checked it.
3. Wait for CI, review the `ci-preview` screenshots, then merge. Merging to `main` deploys to https://yasharjamei.github.io/Melbourne_Flood/.

## 6. Where to start

The README's [Roadmap](README.md#roadmap) and "Data still to add" list open work in priority order. Good first changes:

- a new map variable (see ARCHITECTURE §4)
- rates instead of counts for the collinear Lama & Sun indicators
- modelled 1% AEP flood extents in place of planning overlays
