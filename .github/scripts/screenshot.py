"""Render each built page in headless Chromium and save a screenshot (CI previews)."""
import os, sys
from playwright.sync_api import sync_playwright

pages = [("dist/index.html", "shots/west.png"), ("dist/metro/index.html", "shots/metro.png")]
os.makedirs("shots", exist_ok=True)
errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for src, out in pages:
        if not os.path.exists(src):
            continue
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        pg.on("pageerror", lambda e, s=src: errors.append(f"{s}: {e}"))
        pg.goto("file://" + os.path.abspath(src), wait_until="load", timeout=120000)
        pg.wait_for_timeout(4000)
        pg.screenshot(path=out)
        print(out, "SA1 paths:", pg.eval_on_selector_all("path.sa1", "e => e.length"))
    b.close()
if errors:
    sys.exit("page errors:\n" + "\n".join(errors))
