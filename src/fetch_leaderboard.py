import os, json, time, requests, pandas as pd
from dotenv import load_dotenv

load_dotenv()
BASE = "https://api.llm-stats.com/stats/v1"
HEAD = {"Authorization": f"Bearer {os.environ['LLM_STATS_API_KEY']}"}

def call(path, **params):
    r = requests.get(f"{BASE}{path}", headers=HEAD, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def rows_of(d):
    return d if isinstance(d, list) else next(
        v for v in d.values() if isinstance(v, list))

def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path.lower(), obj

def find(detail, must, avoid=()):
    hits = [v for p, v in walk(detail)
            if isinstance(v, (int, float)) and not isinstance(v, bool)
            and all(m in p for m in must)
            and not any(a in p for a in avoid)]
    return min(hits) if hits else None

seen, ranks = set(), []
for i in range(1, 8):
    batch = rows_of(call("/rankings", category="coding", limit=50, page=i))
    new = [r for r in batch if r["model_id"] not in seen]
    seen.update(r["model_id"] for r in batch)
    ranks += new
    print(f"rankings page {i}: {len(batch)} got, {len(new)} new, {len(ranks)} total")
    if not new:
        break

rows = []
for n, r in enumerate(ranks, 1):
    mid = r["model_id"]
    try:
        d = call(f"/models/{mid}")
    except Exception as e:
        print(f"  {mid}: {e}")
        d = {}
    if n == 1:
        json.dump(d, open("data/sample_detail.json", "w"), indent=2)

    p_in = find(d, ["input"], avoid=["cache", "context", "window"])
    p_out = find(d, ["output"], avoid=["cache", "throughput", "speed", "token_per"])
    speed = find(d, ["throughput"]) or find(d, ["chars"]) or find(d, ["speed"])

    rows.append({
        "rank": r["rank"],
        "model_id": mid,
        "name": r["model_name"],
        "rating": r["conservative_rating"],
        "price_in": p_in,
        "price_out": p_out,
        "speed": speed,
    })
    print(f"{n:3} {r['model_name'][:28]:28} rate={r['conservative_rating']:5} "
          f"in={p_in} out={p_out} speed={speed}")
    time.sleep(0.3)

df = pd.DataFrame(rows).sort_values("rank")
df["price_blended"] = (4 * df["price_in"] + df["price_out"]) / 5

out = df[["name", "rating", "price_blended", "speed"]]
os.makedirs("data", exist_ok=True)
out.to_csv("data/leaderboard.csv", index=False)
df.to_csv("data/leaderboard_full.csv", index=False)
print(f"\nsaved {len(out)} rows")
print(out.head(10).to_string(index=False))