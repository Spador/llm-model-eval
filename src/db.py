"""
Build a SQLite DB of IPL 2021-2024 from the Kaggle IPL complete dataset.
Expects matches.csv and deliveries.csv in data/raw/.
Produces data/ipl_2021_2024.db with two linked tables, plus data/schema.sql
"""
import sqlite3
import pandas as pd

MATCHES_CSV = "data/raw/matches.csv"
DELIVERIES_CSV = "data/raw/deliveries.csv"
DB_PATH = "data/ipl_2021_2024.db"
SCHEMA_PATH = "data/schema.sql"
YEARS = {2021, 2022, 2023, 2024}

# ---------- 1. Load matches ----------
matches = pd.read_csv(MATCHES_CSV)

# The 'season' column is messy: some rows are "2021", others "2020/21".
# Filtering on the match date is safer than the season string.
parsed = pd.to_datetime(matches["date"], errors="coerce")

# Date format varies across rows, so retry the failures with dayfirst.
if parsed.isna().any():
    parsed = parsed.fillna(pd.to_datetime(matches["date"], errors="coerce", dayfirst=True))
if parsed.isna().any():
    print(f"warning: {parsed.isna().sum()} unparseable dates, dropped")
matches["date"] = parsed

matches_filtered = matches[matches["date"].dt.year.isin(YEARS)].copy()

# 'id' is the match identifier in this dataset, used to filter deliveries below.
match_ids = set(matches_filtered["id"])
print(f"matches 2021-2024: {len(matches_filtered)}")

# ---------- 2. Load deliveries, keep only balls from those matches ----------
# deliveries.csv is large (~260k rows), so read it fully then filter on match_id.
deliveries = pd.read_csv(DELIVERIES_CSV)
deliveries_filtered = deliveries[deliveries["match_id"].isin(match_ids)].copy()
print(f"deliveries: {len(deliveries_filtered)}")

# ---------- 3. Write to SQLite ----------
conn = sqlite3.connect(DB_PATH)
matches_filtered.to_sql("matches", conn, if_exists="replace", index=False)
deliveries_filtered.to_sql("deliveries", conn, if_exists="replace", index=False)

# ---------- 4. Index the join columns so queries stay fast ----------
cur = conn.cursor()
cur.execute("CREATE INDEX IF NOT EXISTS idx_deliveries_match ON deliveries(match_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_matches_id ON matches(id)")
conn.commit()

# ---------- 5. Sanity checks ----------
print("\n--- verification ---")
print("matches rows:", cur.execute("SELECT COUNT(*) FROM matches").fetchone()[0])
print("deliveries rows:", cur.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0])

# Every delivery must link to a real match, otherwise the filter went wrong.
orphans = cur.execute("""
    SELECT COUNT(*) FROM deliveries d
    LEFT JOIN matches m ON d.match_id = m.id
    WHERE m.id IS NULL
""").fetchone()[0]
print("orphan deliveries (should be 0):", orphans)

# Confirms the date filter captured the years intended, and nothing else.
print("date range:", cur.execute("SELECT MIN(date), MAX(date) FROM matches").fetchone())
print("seasons:", [r[0] for r in cur.execute(
    "SELECT DISTINCT season FROM matches ORDER BY season").fetchall()])


conn.close()
print(f"done, wrote {DB_PATH}")