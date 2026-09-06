"""
run_daily.py — runs the whole pipeline in order, one command.

  1. load_health.py  -> daily_health.csv
  2. estimate.py     -> estimate.json
  3. targets.py      -> targets.json
  4. agents.py       -> briefs/<today>.md

Run it with:   python run_daily.py
Later, Windows Task Scheduler can run this every morning automatically.
"""

import subprocess
import sys

STEPS = ["load_health.py", "estimate.py", "targets.py", "agents.py"]

for script in STEPS:
    print(f"\n>>> {script}")
    result = subprocess.run([sys.executable, script])
    if result.returncode != 0:
        print(f"!!! {script} failed — stopping.")
        sys.exit(1)

print("\nPipeline complete.")
