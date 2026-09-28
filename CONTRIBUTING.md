# Contributing

Thanks for helping. This guide covers setting up, running the pipeline, checking a change and getting it onto `main`. For how the code fits together, read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) first: it has a section-by-section tour and the data contract between the pipeline and the pages.

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
python pipeline/01_fetch.py     # Greater Melbourne; the first run takes ~30 minutes (3 M address points, canopy tiles)
python pipeline/02_build.py     # ~20 minutes, mostly the two GWR/MGWR models
python pipeline/03_bundle.py    # writes dist/index.html and dist/analysis/index.html
```

Open `dist/index.html` in a browser; no server is needed. The first fetch downloads about 1 GB, which is cached in `data/raw/`; later runs reuse it.

**Faster iteration on a small area:** add a study to `STUDIES` in `pipeline/config.py` with just a few councils, and pass `--study <key>` to steps 1 and 2.

The fetch step needs these hosts:

- `geo.abs.gov.au`
- `www.abs.gov.au`
- `opendata.maps.vic.gov.au`
- `copernicus-dem-30m.s3.amazonaws.com`
- `maps.isric.org`
- `tiles-ap1.arcgis.com` (Vicmap 10 m DEM)
- `cl-isd-prd-datashare-s3-delivery.s3.amazonaws.com` and `s3.ap-southeast-2.amazonaws.com` (tree canopy, road casement)
- `minedbuildings.z5.web.core.windows.net` (building footprints)

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
3. **CI is green after you push.** CI rebuilds everything from live data and opens both pages in a headless browser. The screenshots are attached to the run under *Artifacts*: the map for all councils, the paper preset with terrain relief, Casey, and the analysis page. A failing run is not deployed.

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

## 5. Getting a change onto `main`

The repository keeps **one branch on GitHub, `main`**, and doesn't use pull requests. Every change is made in its own **git worktree**: a second working folder beside your main checkout. Your main checkout stays clean on `main`, and two changes can be in progress at once without stashing.

Git never lets two worktrees check out the same branch, so each worktree gets a **local-only** branch named `wt/<topic>`. It is never pushed; the work reaches GitHub as `main`.

```bash
# from your main checkout (Melbourne_Flood/)
git fetch origin main
git worktree add -b wt/<topic> ../mf-<topic> origin/main
ln -s "$PWD/data/raw" ../mf-<topic>/data/raw     # share the ~1 GB download cache
#   Windows (admin or developer mode): mklink /D ..\mf-<topic>\data\raw %CD%\data\raw
cd ../mf-<topic>

# ... edit, run the checks in section 3, commit ...

git fetch origin main && git rebase origin/main  # only if main moved meanwhile
git push origin HEAD:main                        # fast-forwards main; never use --force

cd ../Melbourne_Flood
git worktree remove ../mf-<topic>
git branch -D wt/<topic>                         # local only; nothing to delete on GitHub
git pull --ff-only origin main
```

- **Never push a `wt/` branch** (`git push origin wt/...`). That would put a second branch back on GitHub.
- **The data cache:** `data/raw` is ignored by git whether it is a folder or a link, so the link is never committed. Without it, the first pipeline run in a new worktree downloads everything again.
- **Pushing:** if `git push origin HEAD:main` is rejected, someone pushed first. Rebase on `origin/main` and push again.

After the push:
1. Watch the run under **Actions**. If it fails, nothing is deployed and the live site keeps its last good version. Fix the problem in a worktree and push again.
2. A green run deploys to https://yasharjamei.github.io/Melbourne_Flood/.

**External contributors:** fork the repository and send a patch or open an issue describing the change. The owner applies it to `main`.

## 6. Where to start

The README's [Roadmap](README.md#roadmap) and "Data still to add" list open work in priority order. Good first changes:

- a new map variable (see ARCHITECTURE §4)
- rates instead of counts for the collinear Lama & Sun indicators
- modelled 1% AEP flood extents in place of planning overlays
