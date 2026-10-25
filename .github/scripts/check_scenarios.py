"""Open the scenarios preview (preview/scenarios/index.html, from disk as the owner does) in desktop and
phone browsers and print what the map shows: the A/B panel for the two example areas, the SA1 level
(features drawn and coloured, zoomed to one council), script errors, and small screenshots as gzip+base64
JPEGs between BEGIN_SHOT/END_SHOT, so a reviewer who cannot download artifacts can still see the page.
It only reports; the workflow step does not fail the run.

    python .github/scripts/check_scenarios.py        (LIBS=<node_modules> serves MapLibre locally, basemap blocked)
"""
import base64, gzip, io, json, os
from playwright.sync_api import sync_playwright

PAGE = os.path.abspath("preview/scenarios/index.html")
COUNCIL = "Maribyrnong"

STATE = """() => { const m = __scen.map, A = window.SA1DATA;
  const rows = [...document.querySelectorAll('#abtab tr')].map(t => t.innerText.replace(/\\s+/g, ' ').trim());
  let ta = 0, tb = 0; if (A && m.getSource('sa1')) for (let i = 0; i < A.codes.length; i++) {
    const s = m.getFeatureState({source: 'sa1', id: i}); if (s.ta > 0) ta++; if (s.tb > 0) tb++; }
  const fc = m.getLayer('sa1-fill') && m.getPaintProperty('sa1-fill', 'fill-color');
  return {sa1Loaded: !!A, mbPoints: A && A.mb ? A.mb.s.length : 0, pins: document.querySelectorAll('.pin').length,
    A: popA.textContent + ' | ' + subA.textContent, B: popB.textContent + ' | ' + subB.textContent, tintedA: ta, tintedB: tb,
    table: rows.slice(0, 8), state: mstate.textContent, note: mnote.textContent,
    sa1Visible: m.getLayer('sa1-fill') ? m.getLayoutProperty('sa1-fill', 'visibility') : 'no layer',
    sa1Drawn: m.getLayer('sa1-fill') ? m.queryRenderedFeatures({layers: ['sa1-fill']}).length : 0,
    sa1Coloured: Array.isArray(fc) ? fc.filter((v, k) => k > 2 && k % 2 === 0 && typeof v === 'string' && !v.startsWith('rgba(0,0,0,0')).length : 0}; }"""
IDLE = "() => new Promise(r => { __scen.map.once('idle', r); __scen.map.triggerRepaint(); setTimeout(r, 15000); })"


def shot(pg, sel, name, width):
    from PIL import Image
    im = Image.open(io.BytesIO(pg.query_selector(sel).screenshot())).convert("RGB")
    im = im.resize((width, int(im.height * width / im.width)))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=62)
    print(f"BEGIN_SHOT {name}"); print(base64.b64encode(gzip.compress(buf.getvalue())).decode()); print("END_SHOT", flush=True)


def run(b, name, ctx, libs):
    pg = b.new_context(**ctx).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    pg.on("console", lambda m: m.type == "error" and errs.append("console: " + m.text[:200]))
    if libs:
        pg.route("**/cdn.jsdelivr.net/**", lambda r: r.fulfill(path=os.path.join(libs, "maplibre-gl/dist/" + r.request.url.rsplit("/", 1)[1])))
        pg.route(lambda u: "cartocdn.com" in u or "fonts.g" in u, lambda r: r.abort())
    pg.goto("file://" + PAGE, wait_until="load", timeout=120000)
    pg.wait_for_function("window.__ready === true", timeout=120000)
    try:
        pg.wait_for_function("window.SA1DATA && document.querySelectorAll('.pin').length === 2", timeout=120000)
    except Exception as e:
        print(f"{name}: SA1 file or example pins did not appear: {e}"[:300])
    pg.evaluate(IDLE)
    width = 560 if name == "phone" else 900
    print(f"{name} start:", json.dumps(pg.evaluate(STATE), ensure_ascii=False), flush=True)
    shot(pg, "#mapsec", f"{name}-start", width)
    code = pg.evaluate(f"[...document.querySelectorAll('#lgasel option')].find(o => o.textContent.includes('{COUNCIL}'))?.value || ''")
    if code:
        pg.select_option("#lgasel", code)
    pg.click("#unitseg button:nth-child(3)")
    pg.wait_for_timeout(2500); pg.evaluate(IDLE)
    print(f"{name} SA1 level, {COUNCIL}:", json.dumps(pg.evaluate(STATE), ensure_ascii=False), flush=True)
    shot(pg, "#mapsec", f"{name}-sa1", width)
    print(f"{name}: page width {pg.evaluate('document.documentElement.scrollWidth')} px; errors: {errs or 'none'}", flush=True)


def main():
    libs = os.environ.get("LIBS")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM") or None,
                              args=["--use-gl=angle", "--use-angle=swiftshader", "--ignore-gpu-blocklist"])
        run(b, "desktop", {"viewport": {"width": 1280, "height": 1000}}, libs)
        run(b, "phone", {k: v for k, v in p.devices["iPhone 13"].items() if k != "default_browser_type"}, libs)
        b.close()


if __name__ == "__main__":
    main()
