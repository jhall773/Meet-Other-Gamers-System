import pandas as pd
import sqlite3
import ast

def deep_flatten(value):
    """Flatten nested lists until a plain value remains."""
    while isinstance(value, list):
        if len(value) == 0:
            return ""
        value = value[0]
    return value

def extract_lonlat(value, key):
    if isinstance(value, dict):
        return value.get(key)
    if isinstance(value, str) and value.startswith("{"):
        return ast.literal_eval(value).get(key)
    return None

# ---------------------------------------------------------
# Load JSON
# ---------------------------------------------------------
df = pd.read_json("georef-united-states-of-america-zcta5-millesime.json", orient="records")

# ⭐ Filter to latest year (2023)
df = df[df["year"] == 2023]

rows = []

for _, r in df.iterrows():

    zip_code = deep_flatten(r["zcta5_code"])

    raw_states = deep_flatten(r["ste_name"])
    states = raw_states if isinstance(raw_states, list) else [raw_states]

    lon = extract_lonlat(r["geo_point_2d"], "lon")
    lat = extract_lonlat(r["geo_point_2d"], "lat")

    # Split multi-state ZIPs, drop counties
    for st in states:
        rows.append({
            "zcta5_code": str(zip_code),
            "ste_name": str(st),
            "longitude": float(lon),
            "latitude": float(lat)
        })

clean_df = pd.DataFrame(rows)

# ⭐ No duplicates needed — filtering by year already removed them

conn = sqlite3.connect("US_zip_codes.db")
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS zipcodes")

cur.execute("""
CREATE TABLE zipcodes (
    zcta5_code TEXT,
    ste_name TEXT,
    longitude REAL,
    latitude REAL,
    PRIMARY KEY (zcta5_code, ste_name)
)
""")

clean_df.to_sql("zipcodes", conn, if_exists="append", index=False)
conn.close()

print("Done! Using only 2023 data — clean ZIP/state rows.")