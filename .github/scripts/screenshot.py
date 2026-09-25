"""Render each built page in headless Chromium and save a screenshot (CI previews)."""
import os, sys
from playwright.sync_api import sync_playwright

pages = [("dist/index.html", "shots/west.png"), ("dist/metro/index.html", "shots/metro.png"),
         ("dist/analysis/index.html", "shots/west_analysis.png"), ("dist/metro/analysis/index.html", "shots/metro_analysis.png")]
os.makedirs("shots", exist_ok=True)
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--ignore-gpu-blocklist"])
    for src, out in pages:
        if not os.path.exists(src):
            continue
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        pg.on("pageerror", lambda e, s=src: errors.append(f"{s}: {e}"))
        pg.goto("file://" + os.path.abspath(src), wait_until="load", timeout=120000)
        pg.wait_for_function("window.__ready === true", timeout=120000)
        pg.wait_for_timeout(5000)  # basemap tiles
        if "analysis" in src:
            pg.screenshot(path=out, full_page=True); print(out); continue
        pg.screenshot(path=out)
        print(out, "residents in A:", pg.inner_text("#popA"), "| legend:", pg.inner_text("#legend").replace("\n", " | ")[:200])
        if "metro" in src:  # a second view: IFRI, zoomed to one council
            pg.select_option("#metric", "ls5"); pg.select_option("#lgasel", "Casey")
            pg.wait_for_timeout(5000); pg.screenshot(path=out.replace(".png", "_casey_ifri.png"))
    b.close()
if errors:
    sys.exit("page errors:\n" + "\n".join(errors))
