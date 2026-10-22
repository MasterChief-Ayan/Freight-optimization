"""
run_layer0.py  -  produces every Layer 0 result and chart.

    python run_layer0.py
"""
import _bootstrap  # noqa: F401  repo root on sys.path; outputs go to results/

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from rtsim.config import default_config, scenario
from rtsim.distributions import Dist
from rtsim.verify import run_checks
from rtsim.experiment import run_policies, summarise, paired, print_summary
from rtsim.terminal import simulate
from rtsim.accounting import rake_table, attribution
from rtsim import policies

POLICIES = ["FCFS", "SPT", "COST", "LPT"]
COLS = {"FCFS": "#8c8c8c", "SPT": "#5b7c99", "COST": "#c1440e", "LPT": "#b8a44a"}


def main():
    # ---------------------------------------------------------------- 1
    print("\n>>> STEP 1  verification")
    if not run_checks():
        raise SystemExit("verification failed - do not trust any result below")

    cfg = default_config()

    # ---------------------------------------------------------------- 2
    print("\n>>> STEP 2  policy comparison, paired design")
    res = run_policies(cfg, POLICIES)
    sm = summarise(res)
    print_summary(cfg, sm)

    print("\n  paired difference vs FCFS (same scenarios):")
    for alt in ["SPT", "COST", "LPT"]:
        for metric in ["mean_detention_hr", "mean_wait_hr", "total_controllable_cost"]:
            p = paired(res, "FCFS", alt, metric)
            unit = "h" if metric.endswith("_hr") else "Rs"
            print(f"    {alt:>5} {metric:<26} {p['diff']:+12,.2f} "
                  f"+/-{p['ci']:,.2f} {unit:<3} "
                  f"{'SIGNIFICANT' if p['significant'] else 'not significant'}")

    # ---------------------------------------------------------------- 3
    print("\n>>> STEP 3  where the time actually goes")
    log, _, _ = simulate(cfg, policies.build("FCFS", cfg), cfg.run.base_seed)
    att = attribution(rake_table(log, cfg))
    print(att.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    # ---------------------------------------------------------------- 3b
    print("\n>>> STEP 3b  LOAD SWEEP: at what traffic does sequencing matter?")
    print("  At the calibrated arrival rate (about 24 rakes/month, against")
    print("  TERI's 15/month for an average one-line terminal) the PHYSICAL")
    print("  model is lightly loaded and no sequencing rule can help. That is")
    print("  itself the Layer 0 finding: the physical layer is not the")
    print("  bottleneck at realistic Indian siding throughput. Sequencing only")
    print("  earns its keep once the line is genuinely contended - which is")
    print("  what the administrative layer causes, and Layer 1 shows.")
    load = []
    for gap in (5.0, 8.0, 12.0, 18.0, 30.0):
        s2 = scenario(cfg, f"gap {gap}h", **{"rake.arrival_gap": Dist("exp", mean=gap)})
        r = run_policies(s2, ["FCFS", "COST"])
        t = summarise(r)
        base_w = t.loc[t.policy == "FCFS", "mean_wait_hr"].iloc[0]
        alt_w = t.loc[t.policy == "COST", "mean_wait_hr"].iloc[0]
        load.append({"arrival_gap_hr": gap,
                     "rakes_per_month": 730.0 / gap,
                     "line_util": t.loc[t.policy == "FCFS", "line_utilisation"].iloc[0],
                     "wait_FCFS": base_w, "wait_COST": alt_w,
                     "gain_pct": 100 * (base_w - alt_w) / base_w if base_w > 0 else 0.0})
    ld = pd.DataFrame(load)
    print(ld.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    # ---------------------------------------------------------------- 4
    print("\n>>> STEP 4  scenario sweep: build capacity vs schedule better")
    sweep = []
    for k in (1, 2, 3):
        s = scenario(cfg, f"{k} line(s)", **{"resources.loading_lines": k})
        r = run_policies(s, ["FCFS", "COST"])
        t = summarise(r)
        for _, row in t.iterrows():
            sweep.append({"lines": k, "policy": row.policy,
                          "detention": row.mean_detention_hr,
                          "detention_ci": row.mean_detention_hr_ci,
                          "wait": row.mean_wait_hr,
                          "wait_ci": row.mean_wait_hr_ci,
                          "cost": row.total_controllable_cost,
                          "util": row.line_utilisation})
    sw = pd.DataFrame(sweep)
    print(sw.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    # ---------------------------------------------------------------- 5
    print("\n>>> STEP 5  free-time sensitivity (the commercial lever)")
    # free_time_hr is DERIVED (5:00 base + 2:00 siding + 1:00 tarpaulin), so
    # the lever is the BASE free time, which is what [IR-COMP] 2.2(c) lets a
    # Zonal Railway cut to 3:00 for coal rakes loaded from a single line.
    ft_rows = []
    for base_ft in (3.0, 4.0, 5.0, 6.0, 7.0, 9.0):
        s = scenario(cfg, f"base free time {base_ft}h",
                     **{"charges.base_free_time_hr": base_ft})
        r = run_policies(s, ["FCFS"])
        t = summarise(r).iloc[0]
        ft_rows.append({"base_free_time_hr": base_ft,
                        "effective_free_time_hr": s.charges.free_time_hr,
                        "demurrage": t.total_demurrage,
                        "breach_rate": t.breach_rate})
    ft_df = pd.DataFrame(ft_rows)
    print(ft_df.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    # ---------------------------------------------------------------- charts
    fig, ax = plt.subplots(2, 2, figsize=(13, 8.5))

    a = ax[0, 0]
    a.bar(sm.policy, sm.mean_detention_hr, yerr=sm.mean_detention_hr_ci,
          capsize=5, color=[COLS[p] for p in sm.policy])
    a.axhline(cfg.charges.free_time_hr, ls="--", c="crimson", lw=1)
    a.text(0.02, cfg.charges.free_time_hr, " free time", color="crimson",
           va="bottom", fontsize=8, transform=a.get_yaxis_transform())
    a.set_title("Mean detention, placement to release (hr)")

    a = ax[0, 1]
    a.bar(sm.policy, sm.mean_wait_hr, yerr=sm.mean_wait_hr_ci, capsize=5,
          color=[COLS[p] for p in sm.policy])
    a.set_title("Mean wait for placement (hr)")

    a = ax[1, 0]
    a.barh(att.segment, att.share_pct,
           color=["#c1440e" if o == "terminal" else "#5b7c99" for o in att.owner])
    a.set_xlabel("% of total dwell time")
    a.set_title("Where the time goes (orange = terminal, blue = railway)")
    a.invert_yaxis()

    a = ax[1, 1]
    a.plot(ld.line_util * 100, ld.wait_FCFS, marker="o", label="FCFS",
           color=COLS["FCFS"])
    a.plot(ld.line_util * 100, ld.wait_COST, marker="s", label="COST",
           color=COLS["COST"])
    a.axvline(ld.line_util.iloc[-1] * 100, ls=":", c="k", lw=1)
    a.text(ld.line_util.iloc[-1] * 100, a.get_ylim()[1] * 0.6,
           " calibrated\n operating point", fontsize=8)
    a.set_xlabel("line utilisation (%)")
    a.set_ylabel("mean wait for placement (hr)")
    a.set_title("Sequencing only pays once the line is contended")
    a.legend()

    for row in ax:
        for a in row:
            a.grid(axis="both", alpha=.25); a.set_axisbelow(True)
    fig.suptitle(f"Layer 0 - siding physical model  |  {cfg.run.n_reps} replications, "
                 f"95% CI  |  ALL RATES ASSUMED", y=1.00)
    fig.tight_layout()
    fig.savefig("layer0_results.png", dpi=150, bbox_inches="tight")

    sm.round(3).to_csv("layer0_policy_summary.csv", index=False)
    att.round(3).to_csv("layer0_attribution.csv", index=False)
    sw.round(3).to_csv("layer0_capacity_sweep.csv", index=False)
    ft_df.round(3).to_csv("layer0_freetime_sensitivity.csv", index=False)
    ld.round(3).to_csv("layer0_load_sweep.csv", index=False)
    print("\nSaved: layer0_results.png and four CSVs")


if __name__ == "__main__":
    main()
