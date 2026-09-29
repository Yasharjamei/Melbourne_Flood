"""Draw the home-screen icons (a house above flood waves). Run once; the PNGs are committed.
python web/icons/make_icons.py"""
import math, os
from PIL import Image, ImageDraw

NAVY, WHITE, WATER = (27, 58, 92), (255, 255, 255), (86, 160, 230)


def icon(size, pad=0.0, rounded=True):
    s = 4 * size                                     # draw large, downsample for smooth edges
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if rounded:
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * .22), fill=NAVY)
    else:
        d.rectangle([0, 0, s, s], fill=NAVY)         # full bleed: maskable and Apple icons
    k = s * (1 - 2 * pad); o = s * pad               # content box
    P = lambda x, y: (o + x * k, o + y * k)
    d.polygon([P(.24, .47), P(.50, .22), P(.76, .47)], fill=WHITE)           # roof
    d.rectangle([P(.31, .46), P(.69, .66)], fill=WHITE)                    # walls
    d.rectangle([P(.46, .54), P(.54, .66)], fill=NAVY)                     # door
    for j, y in enumerate((.70, .80)):                                     # two waves
        pts = [P(.14 + t * .72, y + .035 * math.sin(t * 4 * math.pi)) for t in [i / 60 for i in range(61)]]
        d.line(pts, fill=WATER if j == 0 else WHITE, width=int(k * .045), joint="curve")
    return im.resize((size, size), Image.LANCZOS)


here = os.path.dirname(os.path.abspath(__file__))
icon(192).save(f"{here}/icon-192.png")
icon(512).save(f"{here}/icon-512.png")
icon(512, pad=.12, rounded=False).save(f"{here}/icon-maskable-512.png")          # Android crops to a circle/shape
icon(180, pad=.04, rounded=False).convert("RGB").save(f"{here}/apple-touch-icon.png")  # iOS rounds it itself
print("icons written to", here)
