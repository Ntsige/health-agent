"""
estimate.py — Phase 3 of the health agent project.

Predicts today's total calorie burn BEFORE the day happens, using two
signals that Phase 2 showed matter:
  1. Recent trend      — your average burn over the last 7 complete days
  2. Day-of-week effect — how this weekday usually compares to your average

It also backtests: for every past day, it predicts that day using only
the days before it, then measures how far off it was. That tells you
whether the model is actually better than just guessing the average.

Run it with:   python estimate.py
"""

import json
import pandas as pd

# ---------------------------------------------------------------
# 1. Load complete days only
# ---------------------------------------------------------------
daily = pd.read_csv("daily_health.csv", parse_dates=["date"])
hist = daily[~daily["partial_day"]].sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------
# 2. The prediction function
# ---------------------------------------------------------------
def predict(history: pd.DataFrame, dow: int, weight_recent: float = 0.6) -> float:
    """
    Predict burn for a day with weekday `dow`, using only rows in `history`.

    recent  = mean of the last 7 days                     (captures trend)
    dow_adj = how this weekday differs from overall mean  (captures pattern)
    prediction = blend of (recent) and (overall mean + dow_adj)

    weight_recent controls the blend: 1.0 = trust only the last 7 days,
    0.0 = trust only the day-of-week pattern.
    """
    recent = history["total_burn_kcal"].tail(7).mean()
    overall = history["total_burn_kcal"].mean()

    same_dow = history[history["dow"] == dow]["total_burn_kcal"]
    # Need at least 2 examples of this weekday to trust the adjustment
    dow_adj = (same_dow.mean() - overall) if len(same_dow) >= 2 else 0.0

    return weight_recent * recent + (1 - weight_recent) * (overall + dow_adj)


# ---------------------------------------------------------------
# 3. Backtest — how good is this, honestly?
# ---------------------------------------------------------------
def backtest(weight_recent: float, min_history: int = 7) -> float:
    """
    Walk forward through history. For each day after the first
    `min_history` days, predict it using ONLY earlier days, then record
    the absolute error. Return the mean absolute error (MAE).
    """
    errors = []
    for i in range(min_history, len(hist)):
        past = hist.iloc[:i]                 # everything before day i
        actual = hist.loc[i, "total_burn_kcal"]
        pred = predict(past, hist.loc[i, "dow"], weight_recent)
        errors.append(abs(actual - pred))
    return sum(errors) / len(errors)


# Baseline to beat: just guess the running average every day.
def baseline_mae(min_history: int = 7) -> float:
    errors = []
    for i in range(min_history, len(hist)):
        pred = hist.iloc[:i]["total_burn_kcal"].mean()
        errors.append(abs(hist.loc[i, "total_burn_kcal"] - pred))
    return sum(errors) / len(errors)


print("Backtest (predicting each day from only earlier days)")
print("-" * 55)
base = baseline_mae()
print(f"  Baseline (always guess the average) : MAE {base:6.0f} kcal")

# Try several blends and keep the best. This is the simplest form of
# "model tuning" — pick the setting that made the fewest mistakes.
results = {}
for w in [0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0]:
    results[w] = backtest(w)
    print(f"  weight_recent = {w:.1f}                : MAE {results[w]:6.0f} kcal")

best_w = min(results, key=results.get)
best_mae = results[best_w]
print(f"\n  Best blend: weight_recent = {best_w:.1f}  (MAE {best_mae:.0f} vs baseline {base:.0f}, "
      f"{(1 - best_mae / base) * 100:+.0f}% better)\n")


# ---------------------------------------------------------------
# 4. Predict today and tomorrow
# ---------------------------------------------------------------
today = pd.Timestamp.today().normalize()
tomorrow = today + pd.Timedelta(days=1)

est_today = predict(hist, today.dayofweek, best_w)
est_tomorrow = predict(hist, tomorrow.dayofweek, best_w)

print("Estimates")
print("-" * 55)
print(f"  Last complete day  : {hist['date'].iloc[-1].date()}  "
      f"({hist['total_burn_kcal'].iloc[-1]:,.0f} kcal)")
print(f"  7-day average      : {hist['total_burn_kcal'].tail(7).mean():,.0f} kcal")
print(f"  Today    {today.day_name():<9}: {est_today:,.0f} kcal  (± {best_mae:.0f})")
print(f"  Tomorrow {tomorrow.day_name():<9}: {est_tomorrow:,.0f} kcal  (± {best_mae:.0f})")


# ---------------------------------------------------------------
# 5. Save for the agents (Phase 5) to read
# ---------------------------------------------------------------
out = {
    "as_of": str(today.date()),
    "last_complete_day": str(hist["date"].iloc[-1].date()),
    "last_burn_kcal": round(float(hist["total_burn_kcal"].iloc[-1])),
    "recent_7d_avg_kcal": round(float(hist["total_burn_kcal"].tail(7).mean())),
    "estimate_today_kcal": round(est_today),
    "estimate_tomorrow_kcal": round(est_tomorrow),
    "expected_error_kcal": round(best_mae),
    "model": {"weight_recent": best_w, "backtest_mae": round(best_mae),
              "baseline_mae": round(base), "days_used": len(hist)},
}
with open("estimate.json", "w") as f:
    json.dump(out, f, indent=2)
print("\nSaved estimate.json")
