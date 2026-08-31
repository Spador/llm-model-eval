import pandas as pd

W_RATING = 0.9
W_SPEED = 0.1

df = pd.read_csv("data/leaderboard.csv")
print(f"{len(df)} rows")
print(f"missing rating: {df['rating'].isna().sum()}, "
      f"missing speed: {df['speed'].isna().sum()}")

df["rating"] = df["rating"].fillna(df["rating"].min())
df["speed"] = df["speed"].fillna(df["speed"].min())

def norm(s):
    lo, hi = s.min(), s.max()
    return pd.Series(1.0, index=s.index) if hi == lo else (s - lo) / (hi - lo)

df["norm_rating"] = norm(df["rating"])
df["norm_speed"] = norm(df["speed"])
df["final_score"] = W_RATING * df["norm_rating"] + W_SPEED * df["norm_speed"]

df = df.sort_values("final_score", ascending=False).reset_index(drop=True)
df.index += 1
df.index.name = "new_rank"

df.to_csv("data/ranked.csv")
print(f"\nsaved data/ranked.csv, {len(df)} rows\n")
print(df.round(3).to_string())