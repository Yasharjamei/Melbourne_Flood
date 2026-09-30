"""Record a short captioned demo of the built map for sharing (GIF and, if ffmpeg exists, MP4).

Scenes: all of Greater Melbourne -> three councils chosen from the data (highest share of
residents in flood overlays, outside the papers' study area), each through a different variable, with
circle A dragged to the most exposed spot in the first -> 10 m terrain -> the analysis page. Frames are
screenshots taken between scripted actions, so the timing does not depend on machine speed.

Usage (after 03_bundle.py):  python .github/scripts/demo_gif.py   ->  shots/demo.gif, shots/demo.mp4
Or from the live site, no build:  DEMO_URL=https://yasharjamei.github.io/Melbourne_Flood/ python .github/scripts/demo_gif.py
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
    # DEMO_URL records the live site (no build needed); otherwise the freshly built dist/.
    url = os.environ.get("DEMO_URL")
    page = url or "file://" + os.path.abspath("dist/index.html")
    apage = (url.rstrip("/") + "/analysis/") if url else "file://" + os.path.abspath("dist/analysis/index.html")
    pg.goto(page, wait_until="load", timeout=180000)
    pg.wait_for_function("window.__ready === true", timeout=180000)
    # no first-visit hint or hover tooltips in the recording
    pg.add_style_tag(content="#hint,.tip{display:none!important}")
    T = "window.__test"

    # The councils to tour are chosen from the data, not by hand: the three with the highest
    # SHARE of residents in flood overlays, leaving out the two councils of the papers' own study
    # area. (Ranking by total favoured dense inner-city councils, where much of the count is
    # apartment residents above ground level.)
    # For each, the mesh-block point with the most residents in an overlay is where circle A goes.
    tour = pg.evaluate("""()=>{
      const D=JSON.parse(document.getElementById('data').textContent);
      const paper=new Set(((D.meta.presets||[]).find(p=>p.key==='__paper')||{lgas:[]}).lgas);
      const t={},p={};D.sa1.forEach(s=>{t[s.lga]=(t[s.lga]||0)+s.pop*(s.fl||0);p[s.lga]=(p[s.lga]||0)+s.pop;});
      const all=Object.entries(t).map(([k,v])=>[k,v,v/p[k]]).sort((a,b)=>b[2]-a[2]);
      const pick=(all.filter(([n])=>!paper.has(n)).length?all.filter(([n])=>!paper.has(n)):all).slice(0,3);
      return pick.map(([name,n,share])=>{let best=null,bs=-1;
        for(const m of D.mb){const s=D.sa1[m[2]];if(s.lga!==name)continue;
          const v=m[3]*s.pop*Math.min(1,m[4]+m[5]);if(v>bs){bs=v;best=[m[0],m[1]];}}
        return {name,n,share,hot:best};});}""")
    print("tour:", ", ".join(f"{c['name']} ({c['share']:.1%}, {c['n']:,.0f} residents in overlays)" for c in tour))
    about = lambda n: f"{round(n, -2):,.0f}" if n >= 1000 else f"{n:,.0f}"

    def drag_a(target, caption, steps=8):
        """Drag circle A to target (lon, lat) with the mouse, one captioned frame per step."""
        a = pg.evaluate(f"{T}.areas().find(a=>a.id==='a')")
        sx, sy = pg.evaluate(f"([lon,lat])=>{T}.px(lon,lat)", [a["lon"], a["lat"]])
        tx, ty = pg.evaluate(f"([lon,lat])=>{T}.px(lon,lat)", target)
        pg.mouse.move(sx, sy); pg.mouse.down()
        for k in range(1, steps + 1):
            pg.mouse.move(sx + (tx - sx) * k / steps, sy + (ty - sy) * k / steps, steps=6)
            pg.wait_for_timeout(250); snap(pg, caption, 420)
        pg.mouse.up(); pg.wait_for_timeout(500)

    # 1. the whole study area
    pg.select_option("#metric", "flood"); pg.wait_for_timeout(settle)
    snap(pg, "Who lives in the flood path? 31 councils, 4.8 million residents", 2600)

    # 2. three councils, each with a different lens
    lenses = [("flood", "{c}: {p} of residents ({n}) have their home in a flood overlay"),
              ("o75", "{c}: where residents aged 75+ live"),
              ("ls5", "{c}: flood resilience index, per neighbourhood")]
    for k, (c, (key, cap)) in enumerate(zip(tour, lenses)):
        if not pg.query_selector(f'#metric option[value="{key}"]'):
            key = "flood"
        pg.select_option("#metric", key)
        pg.select_option("#lgasel", c["name"]); pg.wait_for_timeout(settle)
        snap(pg, cap.format(c=c["name"], n=about(c["n"]), p=f"{c['share']:.0%}"), 2400)
        if k == 0 and c["hot"]:
            drag_a(c["hot"], "Drag a circle: residents, ages and flood exposure update live")
            snap(pg, "Compare any two places side by side (A and B)", 2200)
        if k == len(tour) - 1:
            pg.check("#relief"); pg.wait_for_timeout(settle + 1000)
            snap(pg, "10 m terrain shows the valleys water follows", 2200)

    # 3. the statistics page
    pg.goto(apage, wait_until="load", timeout=180000)
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
