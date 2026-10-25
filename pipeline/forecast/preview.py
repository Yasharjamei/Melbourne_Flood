"""Render the scenarios page locally for review, without touching dist/ or the site:
preview/scenarios/index.html, from data/processed/scenarios.json if it exists, else the sample.
Open it in a browser, or serve preview/ to check it on a phone."""
import os, shutil

src = "data/processed/scenarios.json" if os.path.exists("data/processed/scenarios.json") else "web/scenarios_sample.json"
dst = "preview/scenarios/index.html"
os.makedirs(os.path.dirname(dst), exist_ok=True)
html = open("web/scenarios.html").read().replace("__DATA__", open(src).read())
# SA1 level and A/B data built into the page, so the preview is one file: opened from a zip or copied on
# its own, a separate sa1.js was left behind and the SA1 level and A/B stayed empty. (The site keeps it
# as a separate file, loaded on demand.)
if os.path.exists("data/processed/scenarios_sa1.js"):
    html = html.replace('<script id="data"', "<script>" + open("data/processed/scenarios_sa1.js").read() + "</script>\n<script id=\"data\"", 1)
open(dst, "w").write(html)
if os.path.exists("preview/scenarios/sa1.js"):
    os.remove("preview/scenarios/sa1.js")
shutil.copy("web/manifest.webmanifest", "preview/manifest.webmanifest")
shutil.copytree("web/icons", "preview/icons", dirs_exist_ok=True)
print(f"{dst}: written from {src}")
