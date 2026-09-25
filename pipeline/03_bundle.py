"""Inline each data/processed/<study>.json into web/template.html -> dist/<study page>."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from config import STUDIES

tpl = open("web/template.html").read()
atpl = open("web/analysis.html").read()
built = 0
for key, st in STUDIES.items():
    src = f"data/processed/{key}.json"
    if not os.path.exists(src):
        continue
    dst = os.path.join("dist", st["out"])
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    data = open(src).read()
    html = tpl.replace("__DATA__", data)
    open(dst, "w").write(html)
    print(f"{dst}: {len(html) / 1e6:.1f} MB")
    adst = os.path.join(os.path.dirname(dst), "analysis", "index.html")   # correlation + GWR/MGWR page
    os.makedirs(os.path.dirname(adst), exist_ok=True)
    open(adst, "w").write(atpl.replace("__DATA__", data))
    print(f"{adst}: written")
    built += 1
if not built:
    sys.exit("nothing to bundle: run 02_build.py first")
