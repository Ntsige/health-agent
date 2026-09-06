"""
agents.py — Phase 5 of the health agent project.

Three agents, each a function with a clear input and output, chained
by an orchestrator that passes each one's result to the next:

  activity_agent   -> what did yesterday look like, what will today look like
  nutrition_agent  -> what did you eat vs burn, are you on track
  planner_agent    -> given both, what should today's target be
  orchestrator     -> runs them in order, then asks Claude to write the brief

Run it with:   python agents.py
"""

import json
import os
from datetime import date
import pandas as pd
import anthropic

MODEL = "claude-sonnet-5"      # good quality, cheap enough to run daily

# ---------------------------------------------------------------
# Shared inputs — outputs of the earlier phases
# ---------------------------------------------------------------
daily = pd.read_csv("daily_health.csv", parse_dates=["date"])
hist = daily[~daily["partial_day"]].sort_values("date").reset_index(drop=True)
with open("estimate.json") as f:
    estimate = json.load(f)
with open("targets.json") as f:
    targets = json.load(f)


# ---------------------------------------------------------------
# Agent 1: Activity
# ---------------------------------------------------------------
def activity_agent() -> dict:
    """
    Looks at yesterday's movement and the recent trend, decides what
    kind of day yesterday was, and hands forward today's burn estimate.
    """
    y = hist.iloc[-1]                                # last complete day
    week = hist.tail(7)
    median_steps = hist["steps"].median()

    day_type = "high" if y["steps"] > median_steps else "low"
    trend = week["total_burn_kcal"].mean() - hist.head(7)["total_burn_kcal"].mean()

    return {
        "yesterday_date": str(y["date"].date()),
        "yesterday_burn": round(y["total_burn_kcal"]),
        "yesterday_steps": int(y["steps"]),
        "yesterday_exercise_min": int(y["exercise_min"]),
        "yesterday_day_type": day_type,              # vs your own median
        "week_avg_burn": round(week["total_burn_kcal"].mean()),
        "week_avg_steps": round(week["steps"].mean()),
        "trend_vs_first_week": round(trend),         # + means more active now
        "today_estimate": estimate["estimate_today_kcal"],
        "estimate_error": estimate["expected_error_kcal"],
    }


# ---------------------------------------------------------------
# Agent 2: Nutrition
# ---------------------------------------------------------------
def nutrition_agent() -> dict:
    """
    Compares what you ate to what you burned. If no food is logged yet,
    says so instead of inventing numbers.
    """
    y = hist.iloc[-1]
    logged = hist.dropna(subset=["eaten_kcal"])

    if logged.empty:
        return {"has_food_data": False,
                "message": "No food logged yet. Log meals in MyFitnessPal so this agent can work."}

    week = logged.tail(7)
    return {
        "has_food_data": True,
        "days_logged": len(logged),
        "yesterday_eaten": round(y["eaten_kcal"]) if pd.notna(y["eaten_kcal"]) else None,
        "yesterday_protein": round(y["protein_g"]) if pd.notna(y["protein_g"]) else None,
        "yesterday_net": round(y["net_kcal"]) if pd.notna(y["net_kcal"]) else None,
        "week_avg_eaten": round(week["eaten_kcal"].mean()),
        "week_avg_net": round(week["net_kcal"].mean()),     # negative = deficit
        "week_avg_protein": round(week["protein_g"].mean()),
        "protein_target": targets["protein_g"],
    }


# ---------------------------------------------------------------
# Agent 3: Planner
# ---------------------------------------------------------------
def planner_agent(activity: dict, nutrition: dict) -> dict:
    """
    Takes both agents' output and sets today's numbers. Starts from the
    formula target, then adjusts if the week is drifting off course.
    """
    plan = {
        "target_kcal": targets["target_kcal"],
        "protein_g": targets["protein_g"],
        "fat_g": targets["fat_g"],
        "carbs_g": targets["carbs_g"],
        "adjustment": "none",
    }

    if nutrition["has_food_data"] and nutrition["week_avg_net"] is not None:
        intended_deficit = targets["estimated_burn_kcal"] - targets["target_kcal"]
        actual_deficit = -nutrition["week_avg_net"]
        # If the week's real deficit is far off the plan, nudge today by up to 150 kcal
        drift = intended_deficit - actual_deficit
        if abs(drift) > 200:
            nudge = max(-150, min(150, -drift))
            plan["target_kcal"] += nudge
            plan["carbs_g"] += round(nudge / 4)
            plan["adjustment"] = f"{nudge:+} kcal (week ran {'under' if drift < 0 else 'over'} planned deficit)"

    return plan


# ---------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------
def write_brief(activity: dict, nutrition: dict, plan: dict) -> str:
    """Asks Claude to turn the three agents' outputs into a short morning brief."""
    client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY from the environment
    system = (
        "You are a concise fitness data assistant. Write a morning brief in plain "
        "English, 5-8 sentences, no headers, no bullet lists. Use the numbers given. "
        "Do not invent data. If food data is missing, say so in one sentence and move on. "
        "Tone: direct, like a coach who reads spreadsheets."
    )
    user = (
        f"Today is {date.today():%A, %B %d}. Goal: {targets['goal']} at {targets['bodyweight_lbs']:.0f} lb.\n\n"
        f"ACTIVITY AGENT: {json.dumps(activity)}\n\n"
        f"NUTRITION AGENT: {json.dumps(nutrition)}\n\n"
        f"PLANNER AGENT: {json.dumps(plan)}\n\n"
        "Write the brief: what yesterday looked like, what today is expected to look like, "
        "and the exact calorie and macro targets for today."
    )
    msg = client.messages.create(model=MODEL, max_tokens=500, system=system,
                                 messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in msg.content if b.type == "text")


def orchestrate():
    activity = activity_agent()
    nutrition = nutrition_agent()
    plan = planner_agent(activity, nutrition)

    print("ACTIVITY :", json.dumps(activity))
    print("NUTRITION:", json.dumps(nutrition))
    print("PLANNER  :", json.dumps(plan))
    print()

    brief = write_brief(activity, nutrition, plan)

    os.makedirs("briefs", exist_ok=True)
    path = f"briefs/{date.today()}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Morning brief — {date.today():%A, %B %d, %Y}\n\n{brief}\n")

    print("=" * 60)
    print(brief)
    print("=" * 60)
    print("Saved", path)


if __name__ == "__main__":
    orchestrate()
