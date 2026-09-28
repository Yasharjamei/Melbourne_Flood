"""Validate the A/B circle counts on the built map against an independent recomputation.

The page counts a circle in JavaScript (web/template.html, agg/sumW). This script recomputes
the same quantities in Python from data/processed/<study>.json with a different distance
formula (haversine on the sphere), then drives the built page in headless Chromium and
compares. It also checks rules that must hold whatever the data:

  data   each SA1's mesh-block resident shares sum to 1; overlay shares lie in [0, 1]
  count  page == independent count for random circles, radii and council filters
  rules  bigger radius never counts fewer residents; same place gives the same answer;
         moving away and back restores it; residents in an overlay never exceed residents;
         age-sex shares sum to 100%; a circle out at sea counts nobody
  UI     dragging pin A with the mouse and clicking the map update the headline figure to
         the independent count at the pin's new position

Usage:  python .github/scripts/check_circles.py [study]     (after 03_bundle.py; default metro)
Exits non-zero on any failure, so CI does not deploy.
"""
import json, math, os, random, sys
from collections import defaultdict
from playwright.sync_api import sync_playwright

STUDY = sys.argv[1] if len(sys.argv) > 1 else "metro"
PAGE = "dist/index.html"
D = json.load(open(f"data/processed/{STUDY}.json"))
S, MB = D["sa1"], D["mb"]
EARTH = 6371008.8          # mean radius, m; the page's 111195 m per degree is the same sphere
BAND = 0.25                # m: the page's flat-earth distance differs from haversine by <= 0.2 m at 2 km,
                           #    so mesh blocks this close to the ring may legitimately fall either side
fails = []


def fail(msg):
    fails.append(msg); print("FAIL", msg)


def dist(lon1, lat1, lon2, lat2):
    """Great-circle (haversine) distance in metres: deliberately not the page's formula."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH * math.asin(math.sqrt(h))


def expected(lon, lat, r, keep=None, full=False):
    """Residents counted by a circle: sum over mesh blocks inside r of (resident share x SA1
    residents), and of that times the block's riverine / overland-flow share for the flood rows.
    Returns (low, high) for residents, or dicts per quantity with full=True: blocks within
    BAND of the ring can go either way."""
    lo, hi = dict(pop=0.0, riv=0.0, sbo=0.0), dict(pop=0.0, riv=0.0, sbo=0.0)
    for x, y, i, w, riv, sbo, *_ in MB:
        if keep is not None and not keep(i):
            continue
        d = dist(lon, lat, x, y)
        if d > r + BAND:
            continue
        v = w * S[i]["pop"]
        for k, f in (("pop", 1), ("riv", riv), ("sbo", sbo)):
            hi[k] += v * f
            if d <= r - BAND: lo[k] += v * f
    return (lo, hi) if full else (lo["pop"], hi["pop"])


# ---- data invariants (no browser)
tot = defaultdict(float)
for x, y, i, w, *sh in MB:
    tot[i] += w
    if not all(0 <= v <= 1 + 1e-9 for v in sh):
        fail(f"mesh block in SA1 {S[i]['id']}: overlay share outside [0, 1]: {sh}")
bad = [S[i]["id"] for i, t in tot.items() if abs(t - 1) > 1e-3]
nomb = [s["id"] for i, s in enumerate(S) if s["pop"] > 0 and i not in tot]
if bad: fail(f"{len(bad)} SA1s whose mesh-block shares do not sum to 1, e.g. {bad[:3]}")
if nomb: fail(f"{len(nomb)} SA1s with residents but no mesh blocks, e.g. {nomb[:3]}")
print(f"data: {len(S):,} SA1s, {len(MB):,} mesh blocks; shares sum to 1 in all but {len(bad)}; "
      f"{len(nomb)} populated SA1s without mesh blocks")

lons, lats = [m[0] for m in MB], [m[1] for m in MB]
rng = random.Random(20260928)
populated = [m for m in MB if S[m[2]]["pop"] * m[3] >= 5]   # centre circles near where people live

with sync_playwright() as p:
    # CHROMIUM overrides the browser binary (e.g. a preinstalled Chromium); CI uses Playwright's own
    b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM") or None,
                          args=["--use-gl=angle", "--use-angle=swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    nm = os.environ.get("LIBS")   # offline runs: serve D3 and MapLibre from a local node_modules
    if nm:
        pg.route("**/{cdn.jsdelivr.net,cdnjs.cloudflare.com}/**", lambda r: r.fulfill(path=os.path.join(
            nm, "d3/dist/d3.min.js" if "d3" in r.request.url else "maplibre-gl/dist/" + r.request.url.rsplit("/", 1)[1])))
        pg.route("**/{basemaps.cartocdn.com,tiles-ap1.arcgis.com}/**", lambda r: r.abort())
    pg.goto("file://" + os.path.abspath(PAGE), wait_until="load", timeout=120000)
    pg.wait_for_function("window.__ready === true", timeout=120000)

    def page_agg(lon, lat, r):
        """The page's own aggregation for a circle, via its agg() at radius r."""
        return pg.evaluate("""([lon,lat,r])=>{const T=window.__test,o=T.agg({lon,lat},r);
          let pyr=0;for(let b=0;b<T.NB;b++)pyr+=o.M[b]+o.F[b];
          return {pop:o.pop,riv:o.popRiv,sbo:o.popSbo,o75:o.o75,o75Fl:o.o75Fl,ages:o.ages,pyr};}""", [lon, lat, r])

    def check(tag, lon, lat, r, keep=None):
        o = page_agg(lon, lat, r); L, H = expected(lon, lat, r, keep, full=True); lo, hi = L["pop"], H["pop"]
        for k, name in (("pop", "residents"), ("riv", "residents in riverine overlay"), ("sbo", "residents in overland-flow overlay")):
            if not (L[k] - 0.01 <= o[k] <= H[k] + 0.01):
                fail(f"{tag}: page shows {o[k]:.1f} {name}, independent {L[k]:.1f}-{H[k]:.1f} ({lon:.5f}, {lat:.5f}, {r} m)")
        for k in ("riv", "sbo"):
            if o[k] > o["pop"] + 1e-6: fail(f"{tag}: residents in {k} overlay {o[k]:.1f} > residents {o['pop']:.1f}")
        if o["o75Fl"] > o["o75"] + 1e-6: fail(f"{tag}: 75+ in overlays {o['o75Fl']:.1f} > 75+ {o['o75']:.1f}")
        if o["ages"] > 0 and abs(o["pyr"] / o["ages"] - 1) > 1e-6: fail(f"{tag}: age-sex shares sum to {o['pyr'] / o['ages']:.4f}")
        return o, lo, hi

    # 1. random circles, whole study area
    n = edge = 0
    for _ in range(300):
        c = rng.choice(populated); r = rng.choice([300, 500, 800, 1200, 2000])
        # centre offset from the mesh-block point so circles are not all centred on data points
        lon, lat = c[0] + rng.uniform(-0.004, 0.004), c[1] + rng.uniform(-0.003, 0.003)
        o, lo, hi = check("random", lon, lat, r); n += 1; edge += hi > lo
    print(f"count: {n} random circles match the independent residents and flood-overlay counts ({edge} had a mesh block within {BAND} m of the ring)")

    # 2. council filter: residents of the selected council only
    lgas = sorted({s["lga"] for s in S})
    for lga in rng.sample(lgas, min(4, len(lgas))):
        pg.evaluate("l=>window.__test.filter(l)", lga)
        inl = [m for m in populated if S[m[2]]["lga"] == lga]
        for c in rng.sample(inl, min(10, len(inl))):
            o, lo, hi = check(f"council {lga}", c[0], c[1], 2000, keep=lambda i, l=lga: S[i]["lga"] == l)
        # every counted SA1 belongs to the council
        stray = pg.evaluate("([lon,lat])=>{const T=window.__test,o=T.agg({lon,lat},2000);return [...o.w.keys()].filter(i=>o.w[i]>0&&!T.visible(i)).length}", [inl[0][0], inl[0][1]])
        if stray: fail(f"council {lga}: {stray} SA1s outside the council were counted")
    pg.evaluate("()=>window.__test.filter('')")
    print(f"count: council filter checked in {min(4, len(lgas))} councils")

    # 3. rules
    c = rng.choice(populated)
    pops = [page_agg(c[0], c[1], r)["pop"] for r in range(300, 2001, 50)]
    if any(b_ < a_ - 1e-9 for a_, b_ in zip(pops, pops[1:])): fail(f"radius: count fell as the radius grew at {c[:2]}: {pops}")
    a1 = page_agg(c[0], c[1], 800); a2 = page_agg(c[0] + 0.05, c[1], 800); a3 = page_agg(c[0], c[1], 800)
    if a1 != a3: fail("moving a circle away and back did not restore its figures")
    sea = page_agg(144.95, -38.15, 2000)   # Port Phillip Bay
    if sea["pop"] > 0: fail(f"a circle in Port Phillip Bay counts {sea['pop']:.1f} residents")
    print("rules: monotonic in radius, repeatable, zero at sea, overlays <= residents, pyramid sums to 100%")

    # 4. the real UI path: drag pin A with the mouse onto a populated spot, then click the map
    #    near pin B, which moves B (the nearer pin) there. Each time the headline must show the
    #    independent count at the pin's new position.
    def headline(sel):
        t = pg.inner_text(sel).replace(",", "").strip()
        return int(t) if t.isdigit() else None

    def ui_check(tag, sel, pid, target):
        got = pg.evaluate(f"window.__test.areas().find(a=>a.id==='{pid}')")
        r = pg.evaluate("window.__test.radius()")
        moved = dist(got["lon"], got["lat"], *target) if target else 0
        lo, hi = expected(got["lon"], got["lat"], r)
        h = headline(sel)
        if target and moved > 60:
            fail(f"{tag}: pin {pid} ended {moved:.0f} m from where it was released")
        if h is None or not (round(lo) - 1 <= h <= round(hi) + 1):
            fail(f"{tag}: headline shows {h}, independent count at the pin is {lo:.0f}-{hi:.0f}")
        else:
            print(f"UI: {tag}: headline {h:,} = independent {lo:,.0f} (pin within {moved:.0f} m of target)")
        return h

    def drag_to(pid, target):
        """Centre the view between the pin and target (both on screen), then drag the pin there."""
        a = pg.evaluate(f"window.__test.areas().find(a=>a.id==='{pid}')")
        pg.evaluate("([lon,lat])=>window.__test.jump(lon,lat)", [(a["lon"] + target[0]) / 2, (a["lat"] + target[1]) / 2])
        pg.wait_for_timeout(800)
        sx, sy = pg.evaluate("([lon,lat])=>window.__test.px(lon,lat)", [a["lon"], a["lat"]])
        tx, ty = pg.evaluate("([lon,lat])=>window.__test.px(lon,lat)", target)
        hit = pg.evaluate(f"document.elementFromPoint({sx},{sy}).closest('.pin') !== null")
        if not hit: fail(f"drag pin {pid}: the pin is not under the mouse at its projected position")
        pg.mouse.move(sx, sy); pg.mouse.down(); pg.mouse.move((sx + tx) / 2, (sy + ty) / 2, steps=10)
        pg.mouse.move(tx, ty, steps=10); pg.mouse.up(); pg.wait_for_timeout(700)

    def populated_near(a, lo_m=300, hi_m=1500):
        """Most populous mesh-block point 300-1500 m from pin a: a nearby, non-empty target."""
        c = [m for m in populated if lo_m < dist(a["lon"], a["lat"], m[0], m[1]) < hi_m]
        return list(max(c, key=lambda m: S[m[2]]["pop"] * m[3])[:2]) if c else None

    a0 = pg.evaluate("window.__test.areas().find(a=>a.id==='a')")
    tgt = populated_near(a0) or list(rng.choice(populated)[:2])
    drag_to("a", tgt)
    ha = ui_check("drag pin A", "#popA", "a", tgt)
    if not ha: fail("drag pin A: the test landed on 0 residents, so it proves nothing")

    b0 = pg.evaluate("window.__test.areas().find(a=>a.id==='b')")
    near_b = populated_near(b0)
    a_now = pg.evaluate("window.__test.areas().find(a=>a.id==='a')")
    if near_b and dist(a_now["lon"], a_now["lat"], *near_b) > dist(b0["lon"], b0["lat"], *near_b):
        pg.evaluate("([lon,lat])=>window.__test.jump(lon,lat)", [(b0["lon"] + near_b[0]) / 2, (b0["lat"] + near_b[1]) / 2])
        pg.wait_for_timeout(1200)   # also clears the page's short "ignore clicks after a drag" window
        cx, cy = pg.evaluate("([lon,lat])=>window.__test.px(lon,lat)", near_b)
        pg.mouse.click(cx, cy); pg.wait_for_timeout(700)
        ui_check("click near pin B", "#popB", "b", near_b)
        a1 = pg.evaluate("window.__test.areas().find(a=>a.id==='a')")
        if dist(a1["lon"], a1["lat"], a_now["lon"], a_now["lat"]) > 1: fail("clicking nearer pin B moved pin A")
    if errs: fail("page errors: " + "; ".join(errs))
    b.close()

if fails:
    sys.exit(f"{len(fails)} circle check(s) failed")
print("circle checks passed")
