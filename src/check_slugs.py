"""
Verify every OpenRouter slug in MODELS is live before spending credits on a run.
"""
import sys, os, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model_openrouter_slug import MODELS

live = {m["id"] for m in requests.get("https://openrouter.ai/api/v1/models").json()["data"]}

missing = []
for name, slug in MODELS:
    ok = slug in live
    print(f"{'OK     ' if ok else 'MISSING'} {name:22s} {slug}")
    if not ok:
        missing.append((name, slug))

for name, slug in missing:
    hint = slug.split("/")[-1].split("-")[0].lower()
    matches = sorted(s for s in live if hint in s.lower())
    print(f"\n{name} candidates: {matches[:10] or 'none found'}")
    