"""
load_health.py — Phase 1 of the health agent project.

Reads the daily CSV from Health Auto Export, keeps the columns that
matter, cleans them, and saves a tidy daily table for everything
downstream (analysis, estimation, agents, dashboard).

Run it with:   python load_health.py
"""

import glob
import pandas as pd

# ---------------------------------------------------------------
# 1. Find the newest export file
# ---------------------------------------------------------------
# glob finds every file matching a pattern. Health Auto Export names
# the daily file "HealthAutoExport-<start>-<end>.csv", so we grab
# all of them and take the most recent one.
EXPORT_FOLDER = "."   # change to r"C:\Users\tsige\iCloudDrive\health_export" once iCloud is set up

files = sorted(glob.glob(f"{EXPORT_FOLDER}/HealthAutoExport-*.csv"))
if not files:
    raise FileNotFoundError("No HealthAutoExport CSV found in " + EXPORT_FOLDER)
latest = files[-1]
print("Reading:", latest)

raw = pd.read_csv(latest)
print("Raw shape:", raw.shape)   # (days, columns) — expect ~125 columns, mostly empty


# ---------------------------------------------------------------
# 2. Keep only the columns we care about, and give them short names
# ---------------------------------------------------------------
# The export has 125 columns; we need about a dozen. A dict maps the
# long export names to short names that are easier to type later.
COLUMNS = {
    "Date/Time":                        "date",
    "Active Energy (kcal)":             "active_kcal",
    "Resting Energy (kcal)":            "resting_kcal",
    "Step Count (steps)":               "steps",
    "Apple Exercise Time (min)":        "exercise_min",
    "Walking + Running Distance (mi)":  "distance_mi",
    "Resting Heart Rate (bpm)":         "resting_hr",
    "Sleep Analysis [Asleep] (hr)":     "sleep_hr",
    "Weight (lbs)":                     "weight_lbs",
    "Dietary Energy (kcal)":            "eaten_kcal",
    "Protein (g)":                      "protein_g",
    "Carbohydrates (g)":                "carbs_g",
    "Total Fat (g)":                    "fat_g",
}

# Only keep columns that actually exist in this export (defensive —
# if a metric wasn't selected in the app, it won't be in the file).
present = {k: v for k, v in COLUMNS.items() if k in raw.columns}
daily = raw[list(present.keys())].rename(columns=present)


# ---------------------------------------------------------------
# 3. Fix types and add derived columns
# ---------------------------------------------------------------
daily["date"] = pd.to_datetime(daily["date"]).dt.date
daily = daily.sort_values("date").reset_index(drop=True)

# Total burn = what the watch measured moving + what the body burns at rest.
daily["total_burn_kcal"] = daily["active_kcal"] + daily["resting_kcal"]

# Net = eaten - burned. Positive = surplus, negative = deficit.
# Will be NaN until food logging starts, which is fine.
daily["net_kcal"] = daily["eaten_kcal"] - daily["total_burn_kcal"]

# Day of week (Mon=0 ... Sun=6) and a readable label. The estimator
# uses this later to learn "Saturdays look different from Tuesdays".
daily["dow"] = pd.to_datetime(daily["date"]).dt.dayofweek
daily["dow_name"] = pd.to_datetime(daily["date"]).dt.day_name()


# ---------------------------------------------------------------
# 4. Flag days that shouldn't be trusted
# ---------------------------------------------------------------
# Resting energy is roughly constant day to day (~1,850-1,950 for you).
# A day well below that usually means the watch was off for hours,
# so the whole day's numbers are incomplete. Flag rather than delete —
# you keep the data, but averages can skip it.
typical_resting = daily["resting_kcal"].median()
daily["partial_day"] = daily["resting_kcal"] < 0.8 * typical_resting

# The last row is today and today isn't over yet.
daily.loc[daily.index[-1], "partial_day"] = True


# ---------------------------------------------------------------
# 5. Save and summarize
# ---------------------------------------------------------------
daily.to_csv("daily_health.csv", index=False)
print("Saved daily_health.csv with", len(daily), "days")
print()

complete = daily[~daily["partial_day"]]
print("Complete days:", len(complete), " | Flagged partial:", daily["partial_day"].sum())
print()
print("Average on complete days:")
print(f"  Total burn : {complete['total_burn_kcal'].mean():,.0f} kcal")
print(f"  Steps      : {complete['steps'].mean():,.0f}")
print(f"  Exercise   : {complete['exercise_min'].mean():.0f} min")
print()
print("Burn by day of week (complete days):")
print(complete.groupby("dow_name")["total_burn_kcal"].mean()
      .reindex(["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"])
      .round(0).to_string())
