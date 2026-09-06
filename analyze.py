"""
analyze.py — Phase 2 of the health agent project.

Reads daily_health.csv (from load_health.py), finds the patterns that
drive daily calorie burn, and saves 4 charts + a findings summary.
These patterns are what the estimator (Phase 3) will use.

Run it with:   python analyze.py
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")          # save charts to files instead of popping windows
import matplotlib.pyplot as plt

# ---------------------------------------------------------------
# 1. Load the clean daily table and drop untrustworthy days
# ---------------------------------------------------------------
daily = pd.read_csv("daily_health.csv", parse_dates=["date"])
complete = daily[~daily["partial_day"]].copy()
print(f"Analyzing {len(complete)} complete days "
      f"({complete['date'].min().date()} to {complete['date'].max().date()})\n")


# ---------------------------------------------------------------
# 2. How much does burn vary, and what drives it?
# ---------------------------------------------------------------
# .describe() gives min / max / mean / spread in one call.
print("Total daily burn (kcal):")
print(complete["total_burn_kcal"].describe().round(0).to_string())
print()

# .corr() measures how strongly two columns move together.
# 1.0 = perfectly together, 0 = no relationship.
# This answers: is burn driven by steps, or by workout minutes?
corr = complete[["total_burn_kcal", "active_kcal", "steps", "exercise_min"]].corr()
print("Correlation with total burn:")
print(corr["total_burn_kcal"].drop("total_burn_kcal").round(2).to_string())
print()


# ---------------------------------------------------------------
# 3. Day-of-week pattern
# ---------------------------------------------------------------
order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
by_dow = (complete.groupby("dow_name")[["total_burn_kcal", "steps", "exercise_min"]]
          .mean().reindex(order).round(0))
print("Average by day of week:")
print(by_dow.to_string())
print()

weekday = complete[complete["dow"] < 5]["total_burn_kcal"].mean()
weekend = complete[complete["dow"] >= 5]["total_burn_kcal"].mean()
print(f"Weekday avg: {weekday:,.0f} kcal   Weekend avg: {weekend:,.0f} kcal   "
      f"Difference: {weekend - weekday:+,.0f}\n")


# ---------------------------------------------------------------
# 4. High-activity days vs low-activity days
# ---------------------------------------------------------------
# Split days at the median step count. This is the "gym day vs rest
# day" gap the estimator needs to know about.
median_steps = complete["steps"].median()
complete["activity_level"] = complete["steps"].apply(
    lambda s: "High (above median steps)" if s > median_steps else "Low (below median steps)"
)
by_level = complete.groupby("activity_level")[["total_burn_kcal", "steps", "exercise_min"]].mean().round(0)
print(f"Split at median steps ({median_steps:,.0f}):")
print(by_level.to_string())
gap = by_level.loc["High (above median steps)", "total_burn_kcal"] - \
      by_level.loc["Low (below median steps)", "total_burn_kcal"]
print(f"High-activity days burn {gap:,.0f} kcal more than low-activity days\n")


# ---------------------------------------------------------------
# 5. Trend over time — 7-day rolling average
# ---------------------------------------------------------------
# .rolling(7).mean() smooths out daily noise so the trend is visible.
complete = complete.sort_values("date")
complete["burn_7d_avg"] = complete["total_burn_kcal"].rolling(7, min_periods=3).mean()
first_week = complete.head(7)["total_burn_kcal"].mean()
last_week = complete.tail(7)["total_burn_kcal"].mean()
print(f"First 7 days avg: {first_week:,.0f}   Last 7 days avg: {last_week:,.0f}   "
      f"Change: {last_week - first_week:+,.0f} kcal/day\n")


# ---------------------------------------------------------------
# 6. Charts — one figure with 4 panels
# ---------------------------------------------------------------
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("Daily Energy Burn — Aug 7 to Sep 6, 2026", fontsize=15, fontweight="bold")

# Panel 1: daily burn over time + 7-day rolling average
ax = axes[0, 0]
ax.plot(complete["date"], complete["total_burn_kcal"], marker="o", markersize=4,
        alpha=0.5, label="Daily")
ax.plot(complete["date"], complete["burn_7d_avg"], linewidth=2.5, label="7-day avg")
ax.set_title("Total burn over time")
ax.set_ylabel("kcal")
ax.legend()
ax.tick_params(axis="x", rotation=45)

# Panel 2: burn by day of week
ax = axes[0, 1]
ax.bar(by_dow.index, by_dow["total_burn_kcal"])
ax.set_title("Average burn by day of week")
ax.set_ylabel("kcal")
ax.tick_params(axis="x", rotation=45)
ax.axhline(complete["total_burn_kcal"].mean(), linestyle="--", color="gray", label="overall avg")
ax.legend()

# Panel 3: steps vs burn scatter — shows how tightly steps predict burn
ax = axes[1, 0]
ax.scatter(complete["steps"], complete["total_burn_kcal"], alpha=0.7)
ax.set_title(f"Steps vs total burn  (correlation {corr.loc['steps', 'total_burn_kcal']:.2f})")
ax.set_xlabel("steps")
ax.set_ylabel("kcal")

# Panel 4: active vs resting stacked — how much of burn is movement vs baseline
ax = axes[1, 1]
ax.bar(complete["date"], complete["resting_kcal"], label="Resting")
ax.bar(complete["date"], complete["active_kcal"], bottom=complete["resting_kcal"], label="Active")
ax.set_title("Resting vs active energy")
ax.set_ylabel("kcal")
ax.legend()
ax.tick_params(axis="x", rotation=45)

plt.tight_layout()
plt.savefig("burn_analysis.png", dpi=130)
print("Saved burn_analysis.png")
