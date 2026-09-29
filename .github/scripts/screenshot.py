"""Render each built page in headless Chromium and save a screenshot (CI previews)."""
import os, sys
from playwright.sync_api import sync_playwright

pages = [("dist/index.html", "shots/metro.png"), ("dist/analysis/index.html", "shots/analysis.png")]
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
        # Second view: the papers' study area preset, SEIFA disadvantage, 10 m terrain relief on.
        if pg.query_selector('#metric option[value="seifa0"]'):   # SEIFA is optional
            pg.select_option("#metric", "seifa0")
        pg.check("#relief"); pg.select_option("#lgasel", "__paper")
        pg.wait_for_timeout(6000); pg.screenshot(path="shots/paper_seifa_relief.png")
        print("  paper preset:", pg.inner_text("#popA"), "| variables:", pg.eval_on_selector_all("#metric option", "o => o.length"),
              "| legend:", pg.inner_text("#legend").replace("\n", " | ")[:160])
        # Third view: IFRI, zoomed to one council.
        pg.uncheck("#relief"); pg.select_option("#metric", "ls5"); pg.select_option("#lgasel", "Casey")
        pg.wait_for_timeout(5000); pg.screenshot(path="shots/casey_ifri.png")
    # Phones: the same map in iPhone- and Android-sized emulation (Chromium's engine for both;
    # real iOS Safari is WebKit, which CI does not run).
    for dev, out in (("iPhone 13", "shots/mobile_iphone.png"), ("Pixel 7", "shots/mobile_android.png")):
        if not os.path.exists("dist/index.html"):
            break
        ctx = b.new_context(**p.devices[dev]); pg = ctx.new_page()
        pg.on("pageerror", lambda e, d=dev: errors.append(f"{d}: {e}"))
        pg.goto("file://" + os.path.abspath("dist/index.html"), wait_until="load", timeout=120000)
        pg.wait_for_function("window.__ready === true", timeout=120000)
        pg.wait_for_timeout(5000); pg.screenshot(path=out)
        print(out, "readout:", pg.inner_text("#mini"))
        ctx.close()
    b.close()
if errors:
    sys.exit("page errors:\n" + "\n".join(errors))
