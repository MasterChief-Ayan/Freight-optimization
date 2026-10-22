"""Run-from-anywhere shim for the experiment scripts.

Importing this module (first line of every runner) does two things and
nothing else:
  1. puts the repository root on sys.path, so `import rtsim` works whether
     you run  `python experiments/run_layer0.py`  from the repo root or from
     inside experiments/;
  2. changes the working directory to  results/,  so every chart, CSV and
     log the runner writes lands there instead of next to the code.

It touches no model logic, so outputs are identical to the original flat
layout (verified with tools/compare_outputs.py).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.makedirs(RESULTS, exist_ok=True)
os.chdir(RESULTS)
