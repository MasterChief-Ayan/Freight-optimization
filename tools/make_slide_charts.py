"""Rebuild the three slide-ready charts used in the mid-term presentation.

    python tools/make_slide_charts.py        (after experiments have run)

Reads   results/layer3_E11_decomposition.csv   (from experiments/decompose.py)
        results/layer4_results.png             (from experiments/run_layer4.py)
Writes  results/slide_decomposition.png        78 / 8 / 14 split
        results/slide_calibration.png          simulated detention vs TERI band
        results/slide_procedural_vs_capital.png  E12 panel cropped from Layer 4

Logic is the same as the original chat version (turn 109); only the file
paths now point at results/, and the calibration marker value is an
optional argument.
"""
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(ROOT, "results"))
plt.rcParams.update({"font.size": 20, "font.family": "DejaVu Sans"})

# ------------------------------------------------------------------ A
d = pd.read_csv("layer3_E11_decomposition.csv")
full, flat, bound = d.full.mean(), d.flat.mean(), d.bound.mean()
admin_pct = 100 * (full - flat) / full
seq_pct = 100 * (flat - bound) / full
cong_pct = 100 * bound / full

fig, ax = plt.subplots(figsize=(11, 3.2))
labels = ["Administrative\n(office hours + rework)", "Optimal\nsequencing",
          "Irreducible\ncongestion"]
vals = [admin_pct, seq_pct, cong_pct]
cols = ["#c1440e", "#5b7c99", "#8c8c8c"]
left = 0
for v, c in zip(vals, cols):
    ax.barh(0, v, left=left, color=c, height=0.6)
    ax.text(left + v / 2, 0, f"{v:.0f}%", ha="center", va="center",
            color="white", fontsize=22, fontweight="bold")
    left += v
ax.set_xlim(0, 100); ax.set_ylim(-1, 1.3)
ax.axis("off")
for i, l in enumerate(labels):
    ax.text(sum(vals[:i]) + vals[i] / 2, -0.85, l, ha="center", va="top", fontsize=15)
fig.suptitle("Where rake waiting time actually comes from", fontsize=22, y=1.05)
fig.tight_layout()
fig.savefig("slide_decomposition.png", dpi=150, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"admin={admin_pct:.1f}% seq={seq_pct:.1f}% cong={cong_pct:.1f}%")

# ------------------------------------------------------------------ B
# Simulated detention marker. Order of preference:
#   1. a value given on the command line      python tools/make_slide_charts.py 15.7
#   2. the calibration line written by experiments/run_layer1.py into l1.log
#      ("with admin chain    : detention 15.53 h")  - the final-code value
#   3. 15.7 h, the value on the mid-term slide (turn-67 code state)
det = 15.7
if os.path.exists("l1.log"):
    m = re.search(r"with admin chain\s*:\s*detention\s+([\d.]+)\s*h", open("l1.log").read())
    if m:
        det = float(m.group(1))
if len(sys.argv) > 1:
    det = float(sys.argv[1])
print(f"calibration marker: {det:.2f} h")
fig, ax = plt.subplots(figsize=(9, 3.2))
ax.axvspan(14, 17, color="#c8e6c9", alpha=0.7, label="Published range (TERI, 2023)")
ax.scatter([det], [0], s=400, color="#c1440e", zorder=5, label="Simulated (this model)")
ax.text(det, 0.35, f"{det:.2f} h\n(simulated)", ha="center", fontsize=16,
        color="#c1440e", fontweight="bold")
ax.text(15.5, -0.55, "14–17 h published range", ha="center", fontsize=14, color="#2e7d32")
ax.set_xlim(8, 22); ax.set_ylim(-1, 1)
ax.set_yticks([]); ax.set_xlabel("Average rake detention (hours)", fontsize=15)
for spine in ["top", "right", "left"]:
    ax.spines[spine].set_visible(False)
fig.suptitle("Model output checked against published reality", fontsize=20, y=1.02)
fig.tight_layout()
fig.savefig("slide_calibration.png", dpi=150, bbox_inches="tight", facecolor="white")
plt.close(fig)

# ------------------------------------------------------------------ C
im = Image.open("layer4_results.png")
w, h = im.size
im.crop((0, int(h * 0.05), int(w * 0.50), int(h * 0.52))).save(
    "slide_procedural_vs_capital.png")
print("saved slide_decomposition.png, slide_calibration.png, "
      "slide_procedural_vs_capital.png")
