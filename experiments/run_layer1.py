"""
run_layer1.py  -  the administrative layer: results and charts.

    python run_layer1.py

E1  ABLATION        remove each step in turn; rank by leverage
E2  DIGITALISATION  put each step online (24/7, no rejections, half the work)
E3  MECHANISM       is it the mean, the variance, the calendar, or the rework?
"""
import _bootstrap  # noqa: F401  repo root on sys.path; outputs go to results/

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from rtsim.config import default_config
from rtsim.verify import run_checks as verify_l0
from rtsim.verify_admin import run_checks as verify_l1
from rtsim.terminal import simulate
from rtsim.accounting import rake_table, kpis, attribution
from rtsim.experiment import ci95
from rtsim.admin import (default_steps, all_disabled, ablate, digitalise,
                         halve_mean, halve_variance, remove_calendar, no_rework)
from rtsim import policies

STEPS = ["M1", "M2", "M3", "M4", "M5", "M6", "M7"]
METRICS = ["mean_detention_hr", "total_demurrage", "breach_rate",
           "mean_dwell_hr", "mean_cycle_hr", "total_controllable_cost"]


def evaluate(cfg, steps, n_reps=None):
    """Run n replications of one administrative configuration."""
    n = n_reps or cfg.run.n_reps
    rows = []
    for rep in range(n):
        seed = cfg.run.base_seed + rep
        log, _, term = simulate(cfg, policies.build("FCFS", cfg), seed,
                                admin_steps=steps)
        rt = rake_table(log, cfg)
        rt = rt[rt.rake > cfg.run.warmup_rakes]
        rows.append(kpis(rt, term, cfg))
    df = pd.DataFrame(rows)
    return {m: ci95(df[m].tolist()) for m in METRICS if m in df.columns}, df


def delta(base_df, alt_df, metric):
    """Paired difference across seeds; CI excluding zero means real."""
    d = (alt_df[metric] - base_df[metric]).tolist()
    m, h = ci95(d)
    return m, h, (m - h > 0) or (m + h < 0)


def main():
    print("\n>>> VERIFICATION")
    if not (verify_l0() and verify_l1()):
        raise SystemExit("verification failed - results below are not trustworthy")

    cfg = default_config()
    steps = default_steps()

    # ---------------------------------------------------------------- 0
    print("\n\n>>> CALIBRATION CHECK")
    base_ci, base_df = evaluate(cfg, steps)
    _, phys_df = evaluate(cfg, all_disabled())
    print(f"  physical model only : detention {phys_df.mean_detention_hr.mean():5.2f} h")
    print(f"  with admin chain    : detention {base_df.mean_detention_hr.mean():5.2f} h  "
          f"<- TERI benchmark for Indian freight terminals is 14-17 h")
    print(f"  free-time breaches  : {100*base_df.breach_rate.mean():.0f}% of rakes "
          f"(vs {100*phys_df.breach_rate.mean():.0f}% physical only)")

    # ---------------------------------------------------------------- 1
    print("\n>>> E1  ABLATION - which step costs the most?")
    e1 = []
    for k in STEPS:
        _, df = evaluate(cfg, ablate([k], steps))
        d_det, h_det, sig = delta(base_df, df, "mean_detention_hr")
        d_dem, _, _ = delta(base_df, df, "total_demurrage")
        d_cyc, _, _ = delta(base_df, df, "mean_cycle_hr")
        e1.append({"step": k, "name": steps[k].name, "owner": steps[k].owner,
                   "d_detention_hr": d_det, "ci": h_det, "significant": sig,
                   "d_demurrage": d_dem, "d_cycle_hr": d_cyc})
    e1 = pd.DataFrame(e1).sort_values("d_detention_hr")
    print(e1[["step", "owner", "d_detention_hr", "ci", "significant",
              "d_demurrage", "d_cycle_hr"]].to_string(
        index=False, float_format=lambda x: f"{x:,.2f}"))
    print("  (negative = removing the step REDUCES detention, i.e. it is a bottleneck)")

    # ---------------------------------------------------------------- 2
    print("\n>>> E2  DIGITALISATION - IR's own initiatives, one at a time")
    e2 = []
    for k in STEPS:
        _, df = evaluate(cfg, digitalise([k], steps))
        d_det, h, sig = delta(base_df, df, "mean_detention_hr")
        d_dem, _, _ = delta(base_df, df, "total_demurrage")
        e2.append({"step": k, "name": steps[k].name,
                   "d_detention_hr": d_det, "ci": h, "significant": sig,
                   "d_demurrage": d_dem})
    _, df_all = evaluate(cfg, digitalise(STEPS, steps))
    d_all, h_all, sig_all = delta(base_df, df_all, "mean_detention_hr")
    d_all_dem, _, _ = delta(base_df, df_all, "total_demurrage")
    e2.append({"step": "ALL", "name": "full digitalisation",
               "d_detention_hr": d_all, "ci": h_all, "significant": sig_all,
               "d_demurrage": d_all_dem})
    e2 = pd.DataFrame(e2)
    print(e2.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    # ---------------------------------------------------------------- 3
    print("\n>>> E3  MECHANISM - what actually causes the delay?")
    top = e1.iloc[0].step          # the step ablation said matters most
    arms = {
        "halve the mean work time": halve_mean([top], steps),
        "halve the variance": halve_variance([top], steps),
        "remove office hours (24/7)": remove_calendar([top], steps),
        "remove rework (no rejections)": no_rework([top], steps),
        "remove the step entirely": ablate([top], steps),
    }
    e3 = []
    for label, st in arms.items():
        _, df = evaluate(cfg, st)
        d, h, sig = delta(base_df, df, "mean_detention_hr")
        e3.append({"intervention": label, "d_detention_hr": d, "ci": h,
                   "significant": sig})
    e3 = pd.DataFrame(e3).sort_values("d_detention_hr")
    print(f"  all interventions applied to {top} ({steps[top].name})")
    print(e3.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    # ---------------------------------------------------------------- 4
    print("\n>>> ATTRIBUTION - who owns the delay?")
    log, _, _ = simulate(cfg, policies.build("FCFS", cfg), cfg.run.base_seed,
                         admin_steps=steps)
    att = attribution(rake_table(log, cfg))
    print(att.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    by_owner = att.groupby("owner").share_pct.sum().sort_values(ascending=False)
    print("\n  by party: " + " | ".join(f"{k} {v:.1f}%" for k, v in by_owner.items()))

    # ---------------------------------------------------------------- charts
    fig, ax = plt.subplots(2, 2, figsize=(14, 9))

    a = ax[0, 0]
    d = e1.copy()
    a.barh(d.step, -d.d_detention_hr, xerr=d.ci, capsize=3,
           color=["#c1440e" if o == "terminal" else
                  "#5b7c99" if o == "railway" else "#7a9b76" for o in d.owner])
    a.set_xlabel("hours of detention removed if this step vanished")
    a.set_title("E1  Ablation: step leverage\n(orange terminal, blue railway, green client)")
    a.invert_yaxis()

    a = ax[0, 1]
    d2 = e2[e2.step != "ALL"]
    a.barh(d2.step, -d2.d_detention_hr, xerr=d2.ci, capsize=3, color="#5b7c99")
    a.axvline(-d_all, ls="--", c="crimson", lw=1.5)
    a.text(-d_all, len(d2) - 0.4, " all steps", color="crimson", fontsize=8)
    a.set_xlabel("detention hours saved")
    a.set_title("E2  Digitalisation: 24/7 + no rejections + half the work")
    a.invert_yaxis()

    a = ax[1, 0]
    d3 = e3.copy()
    a.barh(d3.intervention, -d3.d_detention_hr, xerr=d3.ci, capsize=3,
           color="#c1440e")
    a.set_xlabel("detention hours saved")
    a.set_title(f"E3  Mechanism, applied to {top}\nwhich lever actually works?")
    a.invert_yaxis()

    a = ax[1, 1]
    a.barh(att.segment, att.share_pct,
           color=["#c1440e" if o == "terminal" else
                  "#5b7c99" if o == "railway" else "#7a9b76" for o in att.owner])
    a.set_xlabel("% of total time from arrival to departure")
    a.set_title("Attribution: where the time goes, and whose it is")
    a.invert_yaxis()

    for row in ax:
        for a in row:
            a.grid(axis="x", alpha=.25); a.set_axisbelow(True)
    fig.suptitle("Layer 1 - administrative chain  |  "
                 f"{cfg.run.n_reps} replications, 95% CI  |  ALL RATES ASSUMED",
                 y=1.00)
    fig.tight_layout()
    fig.savefig("layer1_results.png", dpi=150, bbox_inches="tight")

    e1.round(3).to_csv("layer1_E1_ablation.csv", index=False)
    e2.round(3).to_csv("layer1_E2_digitalisation.csv", index=False)
    e3.round(3).to_csv("layer1_E3_mechanism.csv", index=False)
    att.round(3).to_csv("layer1_attribution.csv", index=False)
    print("\nSaved: layer1_results.png and four CSVs")


if __name__ == "__main__":
    main()
