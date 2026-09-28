"""Record a short captioned demo of the built map for sharing (GIF and, if ffmpeg exists, MP4).

Scenes: all of Greater Melbourne -> the papers' study area -> drag circle A and watch the
figures change -> switch variables -> 10 m terrain -> the analysis page. Frames are
screenshots taken between scripted actions, so the timing does not depend on machine speed.

Usage (after 03_bundle.py):  python .github/scripts/demo_gif.py   ->  shots/demo.gif, shots/demo.mp4
Optional env: CHROMIUM (browser binary), LIBS (local node_modules for offline runs).
"""
import io, os, shutil, subprocess
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

W, H = 1280, 720          # output size: 16:9, the shape LinkedIn and most feeds show without cropping
VW, VH = 1600, 900        # browser window (same shape, larger, so the map gets more room), scaled to W x H
GIF_W = 960               # GIF scaled down to keep the file small; the MP4 keeps full size
os.makedirs("shots", exist_ok=True)
frames = []               # (PIL image, milliseconds)


def font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size=size)


FONT = font(26)


def snap(pg, caption, ms):
    """Screenshot the page, add the scene caption as a band along the bottom, keep for ms."""
    im = Image.open(io.BytesIO(pg.screenshot())).convert("RGB").resize((W, H), Image.LANCZOS)
    d = ImageDraw.Draw(im, "RGBA")
    tw = d.textlength(caption, font=FONT)
    d.rectangle([0, H - 58, W, H], fill=(15, 20, 25, 215))
    d.text(((W - tw) / 2, H - 45), caption, font=FONT, fill=(255, 255, 255, 255))
    frames.append((im, ms))


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM") or None,
                          args=["--use-gl=angle", "--use-angle=swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": VW, "height": VH})
    nm = os.environ.get("LIBS")
    if nm:
        pg.route("**/{cdn.jsdelivr.net,cdnjs.cloudflare.com}/**", lambda r: r.fulfill(path=os.path.join(
            nm, "d3/dist/d3.min.js" if "d3" in r.request.url else "maplibre-gl/dist/" + r.request.url.rsplit("/", 1)[1])))
        pg.route("**/{basemaps.cartocdn.com,tiles-ap1.arcgis.com}/**", lambda r: r.abort())
    settle = 1500 if nm else 4000      # time for basemap tiles after each view change
    pg.goto("file://" + os.path.abspath("dist/index.html"), wait_until="load", timeout=120000)
    pg.wait_for_function("window.__ready === true", timeout=120000)
    # no first-visit hint or hover tooltips in the recording
    pg.add_style_tag(content="#hint,.tip{display:none!important}")

    # 1. the whole study area
    pg.select_option("#metric", "flood"); pg.wait_for_timeout(settle)
    snap(pg, "Who lives in the flood path? Greater Melbourne, 4.8 million residents", 2600)

    # 2. the papers' study area
    pg.select_option("#lgasel", "__paper"); pg.wait_for_timeout(settle)
    snap(pg, "Zoom to any council, river basin or suburb", 2000)

    # 3. drag circle A across the area and watch the figures change
    T = "window.__test"
    a = pg.evaluate(f"{T}.areas().find(a=>a.id==='a')")
    sx, sy = pg.evaluate(f"{T}.px({a['lon']},{a['lat']})")
    # towards the middle of the map, which after the preset zoom is the middle of the study area
    cx, cy = pg.evaluate("(()=>{const r=document.getElementById('map').getBoundingClientRect();return [r.left+r.width*0.55,r.top+r.height*0.5]})()")
    path = [(sx + (cx - sx) * k / 8, sy + (cy - sy) * k / 8) for k in range(1, 9)]
    pg.mouse.move(sx, sy); pg.mouse.down()
    for x, y in path:
        pg.mouse.move(x, y, steps=6); pg.wait_for_timeout(250)
        snap(pg, "Drag a circle: residents, ages and flood exposure update live", 420)
    pg.mouse.up(); pg.wait_for_timeout(500)
    snap(pg, "Compare any two places side by side (A and B)", 2200)

    # 4. switch what the map shows
    for key, cap in (("o75", "Map who is most vulnerable: residents aged 75+"),
                     ("ls5", "Flood resilience index (Lama & Sun 2026), per neighbourhood")):
        if pg.query_selector(f'#metric option[value="{key}"]'):
            pg.select_option("#metric", key); pg.wait_for_timeout(settle)
            snap(pg, cap, 2200)

    # 5. terrain
    pg.check("#relief"); pg.wait_for_timeout(settle + 1000)
    snap(pg, "10 m terrain shows the valleys water follows", 2200)

    # 6. the statistics page
    pg.goto("file://" + os.path.abspath("dist/analysis/index.html"), wait_until="load", timeout=120000)
    pg.wait_for_timeout(settle + 1500)
    snap(pg, "Correlations and MGWR: which factors matter where", 2800)
    b.close()

# GIF (smaller) and MP4 (full size, if ffmpeg is available)
small = [im.resize((GIF_W, GIF_W * H // W), Image.LANCZOS) for im, _ in frames]
pal = [s.quantize(colors=128, method=Image.MEDIANCUT, dither=Image.NONE) for s in small]
pal[0].save("shots/demo.gif", save_all=True, append_images=pal[1:], duration=[ms for _, ms in frames],
            loop=0, optimize=True)
print(f"shots/demo.gif: {len(frames)} frames, {sum(ms for _, ms in frames) / 1000:.1f} s, "
      f"{os.path.getsize('shots/demo.gif') / 1e6:.1f} MB")
# ffmpeg: the system one if present, else the static build bundled by the imageio-ffmpeg package
# (GitHub's ubuntu runners no longer ship ffmpeg; Playwright's own copy has no H.264 encoder).
ffmpeg = shutil.which("ffmpeg")
if not ffmpeg:
    try:
        import imageio_ffmpeg; ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        print("no ffmpeg: MP4 skipped (pip install imageio-ffmpeg)")
if ffmpeg:
    os.makedirs("shots/frames", exist_ok=True)
    with open("shots/frames/list.txt", "w") as f:
        for k, (im, ms) in enumerate(frames):
            im.save(f"shots/frames/{k:03d}.png"); f.write(f"file '{k:03d}.png'\nduration {ms / 1000}\n")
        f.write(f"file '{len(frames) - 1:03d}.png'\n")   # concat demuxer needs the last frame repeated
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-i", "shots/frames/list.txt",
                    "-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-crf", "20", "-movflags", "+faststart",
                    "shots/demo.mp4"], check=True)
    shutil.rmtree("shots/frames")
    print(f"shots/demo.mp4: {os.path.getsize('shots/demo.mp4') / 1e6:.1f} MB")
