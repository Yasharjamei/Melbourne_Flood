"""Render the scenarios page locally for review, without touching dist/ or the site:
preview/scenarios/index.html, from data/processed/scenarios.json if it exists, else the sample.
Open it in a browser, or serve preview/ to check it on a phone."""
import os, shutil

src = "data/processed/scenarios.json" if os.path.exists("data/processed/scenarios.json") else "web/scenarios_sample.json"
dst = "preview/scenarios/index.html"
os.makedirs(os.path.dirname(dst), exist_ok=True)
open(dst, "w").write(open("web/scenarios.html").read().replace("__DATA__", open(src).read()))
shutil.copy("web/manifest.webmanifest", "preview/manifest.webmanifest")
shutil.copytree("web/icons", "preview/icons", dirs_exist_ok=True)
print(f"{dst}: written from {src}")
