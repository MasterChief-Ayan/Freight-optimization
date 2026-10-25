"""
run_layer5b_hours_sweep.py  -  detention for EVERY length of the terminal working day.

    python experiments/run_layer5b_hours_sweep.py          (~1 min, 2 cores)
    python experiments/run_layer5b_hours_sweep.py quick

Layer 5 found terminal working hours (the calendar of M4 placement advice, M5 weighment,
M6 release reporting) to be the single largest factor, but sampled it at only five levels
(8, 12, 16, 20, 24 h). This sweep fills in every hour from 8 to 24 h a day on the same
calibrated base (50 rakes, 30 paired replications, FCFS, full admin chain), so the
shape of the curve and the saving per extra hour can be read directly.

Day starts at 06:00 as in the cited base [IR-COMP 4.1: 06:00-22:00 = 16 h]; 24 h = round
the clock (the DRM may allow it). Same random numbers at every level (paired).

Outputs: layer5b_hours_sweep.csv, layer5b_hours_sweep.png
"""
import _bootstrap  # noqa: F401

import sys
from dataclasses import replace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from rtsim.config import default_config
from rtsim.admin import default_steps, CAL_TERMINAL_SHIFT
import run_layer5_sensitivity as L5

QUICK = len(sys.argv) > 1 and sys.argv[1] == "quick"
N_REPS = 10 if QUICK else 30
HOURS = list(range(8, 25))                 # 8, 9, ..., 24 h a day
BASE_H = CAL_TERMINAL_SHIFT.close_hr - CAL_TERMINAL_SHIFT.open_hr


def main():
    c0 = default_config()
    c0 = replace(c0, run=replace(c0.run, n_reps=N_REPS))
    s0 = default_steps()
    pts = [(c0, L5._with_steps(s0, ["M4", "M5", "M6"],
                               lambda t, h=h: replace(t, calendar=L5._cal_hours(CAL_TERMINAL_SHIFT, h))),
            "FCFS") for h in HOURS]
    res = dict(zip(HOURS, L5.run_points(pts)))
    base = res[int(BASE_H)]
    rows = []
    for h in HOURS:
        df = res[h]
        d, ci, sig = L5.paired(base, df, "detention")
        rows.append({"terminal_hours_per_day": h, "detention_h": df.detention.mean(),
                     "detention_ci95": 1.96 * df.detention.std(ddof=1) / len(df) ** 0.5,
                     "d_detention_vs_16h": d, "d_ci": ci, "significant": sig,
                     "demurrage_per_rake": df.demurrage_pr.mean(), "breach_rate": df.breach.mean(),
                     "wait_h": df.wait.mean()})
    t = pd.DataFrame(rows)
    t["saving_from_one_more_hour_h"] = -t.detention_h.diff()
    print(f"\n>>> DETENTION vs TERMINAL WORKING HOURS (M4-M6)  ({N_REPS} reps x {c0.run.n_rakes} rakes)")
    print(t.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    t.round(4).to_csv("layer5b_hours_sweep.csv", index=False)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.errorbar(t.terminal_hours_per_day, t.detention_h, yerr=t.detention_ci95, marker="o", capsize=3)
    ax.axvline(BASE_H, ls="--", color="grey")
    ax.set_xlabel("terminal working hours per day (M4-M6)")
    ax.set_ylabel("mean detention (h)")
    ax.set_title("Layer 5b - detention vs length of the terminal working day")
    fig.tight_layout()
    fig.savefig("layer5b_hours_sweep.png", dpi=150)
    plt.close(fig)
    print("\nSaved: layer5b_hours_sweep.csv, layer5b_hours_sweep.png")


if __name__ == "__main__":
    main()
