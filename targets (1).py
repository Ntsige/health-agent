"""
targets.py — Phase 4 of the health agent project.

Reads today's burn estimate (from estimate.py) and turns it into a
calorie target and macro split for your goal. Uses standard, widely
used rules of thumb — every number is a setting at the top so you can
adjust as you learn what works for you.

Run it with:   python targets.py
"""

import json
import pandas as pd

# ---------------------------------------------------------------
# 1. Settings — edit these, not the code below
# ---------------------------------------------------------------
GOAL = "recomp"          # "recomp" (lose fat + build muscle), "cut", "bulk", "maintain"
BODYWEIGHT_LBS = 158     # fallback if no weight is logged in Health yet

# Calorie target as a fraction of estimated burn, per goal.
# recomp = modest deficit so fat drops while protein supports muscle.
GOAL_MULTIPLIER = {
    "recomp":   0.88,    # ~12% below burn
    "cut":      0.80,    # ~20% below
    "maintain": 1.00,
    "bulk":     1.10,    # ~10% above
}

# Macros in grams per pound of bodyweight. Protein high for recomp,
# fat moderate, carbs = whatever calories are left.
PROTEIN_G_PER_LB = 0.9   # ~140 g at 158 lb
FAT_G_PER_LB     = 0.30  # ~47 g at 158 lb

KCAL_PER_G = {"protein": 4, "carbs": 4, "fat": 9}


# ---------------------------------------------------------------
# 2. Load today's estimate and the latest logged weight (if any)
# ---------------------------------------------------------------
with open("estimate.json") as f:
    est = json.load(f)

daily = pd.read_csv("daily_health.csv")
logged_weight = daily["weight_lbs"].dropna()
weight = float(logged_weight.iloc[-1]) if len(logged_weight) else BODYWEIGHT_LBS
weight_source = "Health app" if len(logged_weight) else "settings fallback"


# ---------------------------------------------------------------
# 3. Calorie target
# ---------------------------------------------------------------
burn = est["estimate_today_kcal"]
target_kcal = round(burn * GOAL_MULTIPLIER[GOAL])
deficit = burn - target_kcal


# ---------------------------------------------------------------
# 4. Macro split
# ---------------------------------------------------------------
# Protein and fat are set from bodyweight. Carbs get the remaining
# calories. That order matters: protein is the non-negotiable for recomp.
protein_g = round(weight * PROTEIN_G_PER_LB)
fat_g     = round(weight * FAT_G_PER_LB)
protein_kcal = protein_g * KCAL_PER_G["protein"]
fat_kcal     = fat_g * KCAL_PER_G["fat"]
carbs_g      = round((target_kcal - protein_kcal - fat_kcal) / KCAL_PER_G["carbs"])

# Sanity floor: never let carbs go negative on a very low-burn day.
carbs_g = max(carbs_g, 50)


# ---------------------------------------------------------------
# 5. Print and save
# ---------------------------------------------------------------
print(f"Goal: {GOAL}   Bodyweight: {weight:.0f} lb ({weight_source})")
print("-" * 55)
print(f"  Estimated burn today : {burn:,} kcal  (± {est['expected_error_kcal']})")
print(f"  Calorie target       : {target_kcal:,} kcal  ({deficit:+,} vs burn)")
print()
print(f"  Protein : {protein_g:>4} g   ({protein_kcal:>4} kcal)")
print(f"  Fat     : {fat_g:>4} g   ({fat_kcal:>4} kcal)")
print(f"  Carbs   : {carbs_g:>4} g   ({carbs_g * 4:>4} kcal)")

targets = {
    "as_of": est["as_of"],
    "goal": GOAL,
    "bodyweight_lbs": weight,
    "estimated_burn_kcal": burn,
    "target_kcal": target_kcal,
    "protein_g": protein_g,
    "fat_g": fat_g,
    "carbs_g": carbs_g,
}
with open("targets.json", "w") as f:
    json.dump(targets, f, indent=2)
print("\nSaved targets.json")
