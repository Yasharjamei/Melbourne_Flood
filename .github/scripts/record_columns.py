"""Record the 3D column animation for sharing: one column per SA2, height = residents in flood areas,
colour = change since 2025. Story: 2025 -> 2036 in today's flood areas, then (2036 population) the
1-in-100-year storm tide at today's sea level, +0.20 m, +0.47 m and +0.82 m. Same style idea as
column maps of stream gauges; the numbers are this project's forecast (data/processed/scenarios.json).

Usage (after pipeline/forecast/forecast.py):
    python .github/scripts/record_columns.py   ->  shots/columns.mp4, shots/columns.gif, shots/columns.html
Optional env: CHROMIUM (browser binary), LIBS (local node_modules, for offline runs without basemap tiles).
"""
import io, json, math, os, shutil, subprocess, time
import geopandas as gpd
from PIL import Image
from playwright.sync_api import sync_playwright

W, H, VW, VH, FPS = 1280, 720, 1280, 720, 20   # browser at output size: no resize, less to render
GIF_W, GIF_EVERY = 640, 3      # the first real GIF was 48.7 MB at 800 px every 2nd frame; the MP4 is the one to share
BUDGET_S = 12 * 60          # if frames render slowly (software GL on CI), keep every k-th frame to fit this
OUT = "shots"
CALM, STORM = "none", ["st", "st0.2", "st0.47", "st0.82"]
LABELS = {"none": "Today's flood areas", "st": "1-in-100-year storm tide, today's sea level",
          "st0.2": "Storm tide + 0.20 m sea level (2040)", "st0.47": "Storm tide + 0.47 m sea level (2070)",
          "st0.82": "Storm tide + 0.82 m sea level (2100)"}


def data():
    sc = json.load(open("data/processed/scenarios.json"))
    pc = gpd.read_file("data/static/sa2_council_pieces_7855.geojson")
    pc["geometry"] = pc.geometry.make_valid()
    pc = pc.loc[pc.area.groupby(pc["sa2_code_2021"]).idxmax()]       # largest part of each SA2 (no merge needed)
    pt = pc.set_geometry(pc.geometry.representative_point()).to_crs(4326)
    xy = {r.sa2_code_2021: (round(r.geometry.x, 5), round(r.geometry.y, 5)) for r in pt.itertuples()}
    ids = [CALM] + STORM
    areas = [{"code": a["code"], "lon": xy[a["code"]][0], "lat": xy[a["code"]][1],
              "v": {k: [row[0] for row in a["v"][k]] for k in ids}} for a in sc["areas"] if a["code"] in xy]
    top = max(max(a["v"][k]) for a in areas for k in ids)
    # name the places the story is about: largest 2025->2036 increases, and largest storm-tide additions
    nm = {a["code"]: a["name"] for a in sc["areas"]}
    rename = {"Port Melbourne Industrial": "Fishermans Bend"}
    grow = sorted(areas, key=lambda a: -(a["v"][CALM][-1] - a["v"][CALM][0]))[:5]
    storm = sorted(areas, key=lambda a: -(a["v"]["st0.82"][-1] - a["v"][CALM][-1]))[:3]
    seen, places = set(), []
    for a in grow + storm:
        n = rename.get(nm[a["code"]], nm[a["code"]].split(" - ")[0])
        near = any(((p["lon"] - a["lon"]) * 88) ** 2 + ((p["lat"] - a["lat"]) * 111) ** 2 < 4 for p in places)   # within 2 km
        if n not in seen and not near:
            seen.add(n); places.append({"name": n, "lon": a["lon"], "lat": a["lat"]})
    credit = ("Forecast: housing-unit model, VIF2023 council totals, Urban Development Program 2025 (DTP; DEECA licence). "
              if sc["meta"].get("restricted") else "Forecast: housing-unit model, VIF2023 council totals. ")
    credit += ("Flood areas: Vicmap planning overlays (LSIO, FO, SBO) + Victorian Coastal Inundation Dataset (bathtub model). "
               "Exposure, not flood depth. Data: ABS, DataVic, DEECA. yasharjamei.github.io/Melbourne_Flood")
    return {"years": sc["meta"]["years"], "areas": areas, "total": {k: [t[0] for t in sc["total"][k]] for k in ids},
            "labels": LABELS, "credit": credit, "places": places, "metres_per_resident": 14000 / top, "radius_m": 520,
            "center": [145.02, -37.93], "zoom": 8.9, "pitch": 55, "bearing": -25}


def story(y0, y1, tot):
    """Frame states: (year, from-scenario, to-scenario, blend, caption, explanation card shown)."""
    seq = []
    f = lambda v: f"{round(v, -2):,.0f}"
    grow_cap = f"{y0} \u2192 {y1}: new homes go into flood-prone areas"
    hold_cap = f"{y1}: about {f(tot[CALM][-1])} residents in flood-prone areas (from {f(tot[CALM][0])})"
    storm_cap = {"st": "Then a 1-in-100-year storm tide, at today's sea level",
                 "st0.2": "Storm tide with +0.20 m sea level (2040)", "st0.47": "Storm tide with +0.47 m sea level (2070)",
                 "st0.82": "Storm tide with +0.82 m sea level (2100)"}
    end_cap = f"{y1} population, +0.82 m sea and a storm tide: about {f(tot['st0.82'][-1])} residents"
    ease = lambda f: f * f * (3 - 2 * f)
    def add(n, fn):
        for i in range(n):
            seq.append(fn(i / max(n - 1, 1)))
    add(80, lambda f: (y0, CALM, CALM, 0, "", 1))                                  # how to read it
    add(20, lambda f: (y0, CALM, CALM, 0, f"{y0}: today", 0))
    add(120, lambda f: (y0 + (y1 - y0) * ease(f), CALM, CALM, 0, grow_cap, 0))
    add(40, lambda f: (y1, CALM, CALM, 0, hold_cap, 0))
    prev = CALM
    for k in STORM:
        add(40 if k != "st" else 30, lambda f, a=prev, b=k: (y1, a, b, ease(f), storm_cap[b], 0))
        add(14, lambda f, b=k: (y1, b, b, 0, storm_cap[b], 0))
        prev = k
    add(60, lambda f: (y1, prev, prev, 0, end_cap, 0))
    n = len(seq)
    return [{"year": y, "a": a, "b": b, "t": t, "caption": c, "explain": e, "bearing": -25 + 40 * i / (n - 1)}
            for i, (y, a, b, t, c, e) in enumerate(seq)]


def main():
    os.makedirs(f"{OUT}/colframes", exist_ok=True)
    d = data()
    html = open("web/columns.html").read().replace("__DATA__", json.dumps(d, separators=(",", ":")))
    page = os.path.abspath(f"{OUT}/columns.html")
    open(page, "w").write(html)
    frames = story(d["years"][0], d["years"][-1], d["total"])
    gif = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM") or None,
                              args=["--use-gl=angle", "--use-angle=swiftshader", "--ignore-gpu-blocklist"])
        pg = b.new_page(viewport={"width": VW, "height": VH})
        pg.on("console", lambda m: m.type in ("error", "warning") and print("  page:", m.text[:160]))
        nm = os.environ.get("LIBS")
        if nm:
            pg.route("**/cdn.jsdelivr.net/**", lambda r: r.fulfill(path=os.path.join(nm, "maplibre-gl/dist/" + r.request.url.rsplit("/", 1)[1])))
            pg.route(lambda u: "cartocdn.com" in u or "amazonaws.com" in u, lambda r: r.abort())
        pg.goto("file://" + page, wait_until="load", timeout=120000)
        pg.wait_for_function("window.__ready === true", timeout=120000)
        # First view: wait for the tiles properly. Per frame only the columns change and the camera turns a
        # fraction of a degree, so one rendered frame is enough (capped at 1.5 s, not 'idle' with 6 s: the
        # first CI recording spent ~10 s a frame waiting for idle).
        idle = "() => new Promise(r => { map.once('idle', r); map.triggerRepaint(); setTimeout(r, 15000); })"
        frame = "() => new Promise(r => { map.once('render', () => requestAnimationFrame(() => r())); map.triggerRepaint(); setTimeout(r, 1500); })"
        pg.evaluate(idle); pg.wait_for_timeout(1500 if nm else 4000)
        t0, stride, n_out = time.time(), 1, 0
        for i, st in enumerate(frames):
            if i % stride:
                continue
            pg.evaluate("st => window.setFrame(st)", st)
            pg.evaluate(frame)
            if i % 60 == 0:
                pg.evaluate(idle)                                        # let any newly visible tiles in
            im = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
            if im.size != (W, H):
                im = im.resize((W, H), Image.LANCZOS)
            im.save(f"{OUT}/colframes/{n_out:04d}.png"); n_out += 1
            if n_out == 1:
                t1 = time.time()                                         # time from frame 2: frame 1 waits for tiles
            if n_out == 9 and stride == 1:                               # decide once, from the first frames
                per = (time.time() - t1) / 8
                stride = max(1, math.ceil(per * len(frames) / BUDGET_S))
                print(f"  {per:.2f} s per frame; keeping every {stride} frame(s)", flush=True)
            if n_out % GIF_EVERY == 0:
                gif.append(im.resize((GIF_W, int(H * GIF_W / W)), Image.LANCZOS).quantize(colors=128))
            if n_out % 25 == 0:
                print(f"  frame {i} of {len(frames)}, {time.time() - t0:.0f} s", flush=True)
        b.close()
    gif[0].save(f"{OUT}/columns.gif", save_all=True, append_images=gif[1:], duration=int(1000 * GIF_EVERY * stride / FPS), loop=0, optimize=True)
    print(f"{OUT}/columns.gif: {len(gif)} frames, {os.path.getsize(f'{OUT}/columns.gif') / 1e6:.1f} MB")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg; ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            print("no ffmpeg: MP4 skipped (pip install imageio-ffmpeg)")
    if ffmpeg:
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-framerate", f"{FPS / stride:g}", "-i", f"{OUT}/colframes/%04d.png",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", f"{OUT}/columns.mp4"], check=True)
        print(f"{OUT}/columns.mp4: {n_out * stride / FPS:.1f} s, {n_out} frames, {os.path.getsize(f'{OUT}/columns.mp4') / 1e6:.1f} MB")
    # Sample frames into the log as small JPEGs (gzip+base64), so a reviewer who cannot download artifacts
    # can still see what the video shows before anyone shares it.
    import base64, gzip
    for k in sorted({0, n_out // 4, n_out // 2, 3 * n_out // 4, n_out - 1}):
        buf = io.BytesIO(); Image.open(f"{OUT}/colframes/{k:04d}.png").convert("RGB").resize((640, 360)).save(buf, "JPEG", quality=70)
        print(f"BEGIN_FRAME {k}"); print(base64.b64encode(gzip.compress(buf.getvalue())).decode()); print("END_FRAME")
    shutil.rmtree(f"{OUT}/colframes")


if __name__ == "__main__":
    main()
