"""
run_layer2.py  -  the road side: results and charts.

    python run_layer2.py

E4  LANE REGIME     one-way passage (blocking) vs organised queue
E5  APPOINTMENTS    none vs quota; gate servers sweep
E6  FAIRNESS        FCFS vs MINMAX deviation across transport companies
E7  STOCHASTIC RAKE the contribution: the appointment schedule is built
                    against the rake's EXPECTED arrival, then the rake
                    actually arrives late. Measures hard infeasibility.
"""
import _bootstrap  # noqa: F401  repo root on sys.path; outputs go to results/

from dataclasses import replace
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from rtsim.config import default_config
from rtsim.distributions import Dist
from rtsim.verify import run_checks as v0
from rtsim.verify_admin import run_checks as v1
from rtsim.verify_trucks import run_checks as v2
from rtsim.terminal import simulate
from rtsim.accounting import rake_table, kpis, _time_weighted_mean
from rtsim.experiment import ci95
from rtsim.admin import default_steps
from rtsim import policies

STEPS = default_steps()


def base_cfg(n_rakes=15, n_reps=8, **tk):
    c = default_config()
    c = replace(c, trucks=replace(c.trucks, enabled=True, **tk))
    return replace(c, run=replace(c.run, n_rakes=n_rakes, n_reps=n_reps))


def evaluate(cfg, rule="FCFS"):
    rows = []
    for rep in range(cfg.run.n_reps):
        seed = cfg.run.base_seed + rep
        log, _, term = simulate(cfg, policies.build("FCFS", cfg), seed,
                                admin_steps=STEPS, tas_rule=rule)
        rt = rake_table(log, cfg)
        rt = rt[rt.rake > cfg.run.warmup_rakes]
        k = kpis(rt, term, cfg)
        road = term.road
        tf = log.to_frame()
        tf = tf[tf.entity_type == "truck"]
        arr = tf[tf.name == "truck_arrive"][["entity_id", "t"]].set_index("entity_id").t
        ext = tf[tf.name == "truck_exit"][["entity_id", "t"]].set_index("entity_id").t
        turn = (ext - arr).dropna()
        k.update({
            "truck_turnaround_hr": turn.mean(),
            "truck_p90_hr": turn.quantile(0.90),
            "gate_queue": _time_weighted_mean(road.gate_queue_samples),
            "hard_infeasible_pct": 100 * road.hard_infeasible / max(1, road.trucks_done),
            "total_deviation_cost": term.tas["total_deviation_cost"],
            "max_company_cost": term.tas["max_company_cost"],
            "deviated_pct": 100 * term.tas["deviated"] / max(1, len(term.trucks)),
            "trucks": len(term.trucks)})
        rows.append(k)
    df = pd.DataFrame(rows)
    return df


def row(df, label, cols):
    out = {"scenario": label}
    for c in cols:
        m, h = ci95(df[c].tolist())
        out[c], out[c + "_ci"] = m, h
    return out


def main():
    print("\n>>> VERIFICATION")
    if not (v0() and v1() and v2()):
        raise SystemExit("verification failed")

    C = ["truck_turnaround_hr", "truck_p90_hr", "gate_queue",
         "mean_detention_hr", "hard_infeasible_pct"]

    # ------------------------------------------------------------ E4
    print("\n\n>>> E4  ACCESS LANE: one-way passage vs organised queue")
    e4 = []
    for cap in (1, 2, 3, 4):
        cfg = base_cfg(lane_capacity=cap)
        e4.append(row(evaluate(cfg), f"lane capacity {cap}"
                      + (" (ONE-WAY)" if cap == 1 else ""), C))
    e4 = pd.DataFrame(e4)
    print(e4[["scenario", "truck_turnaround_hr", "truck_turnaround_hr_ci",
              "truck_p90_hr", "gate_queue"]].to_string(
        index=False, float_format=lambda x: f"{x:,.2f}"))

    # ------------------------------------------------------------ E5
    print("\n>>> E5  APPOINTMENT SYSTEM and gate capacity")
    e5 = []
    for rule in ("NONE", "FCFS"):
        for g in (2, 4, 8):
            cfg = base_cfg(gate_servers=g)
            e5.append(row(evaluate(cfg, rule), f"{rule}, {g} gate servers", C))
    e5 = pd.DataFrame(e5)
    print(e5[["scenario", "truck_turnaround_hr", "truck_p90_hr",
              "gate_queue"]].to_string(index=False,
                                       float_format=lambda x: f"{x:,.2f}"))

    # ------------------------------------------------------------ E6
    print("\n>>> E6  FAIRNESS: who absorbs the reschedules?")
    # A fairness rule can only act while deviations are SCARCE. Once the
    # quota binds so hard that nearly every truck is deviated, ordering has
    # nothing left to allocate and the rule cannot equalise anything. The
    # sweep below shows exactly where that boundary lies.
    e6 = []
    for slots in (8, 12, 20):
        for rule in ("FCFS", "MINMAX"):
            df = evaluate(base_cfg(slots_per_period=slots), rule)
            e6.append(row(df, f"{rule}, quota {slots}",
                          ["total_deviation_cost", "max_company_cost",
                           "deviated_pct", "truck_turnaround_hr"]))
    e6 = pd.DataFrame(e6)
    print(e6[["scenario", "total_deviation_cost", "max_company_cost",
              "deviated_pct"]].to_string(index=False,
                                         float_format=lambda x: f"{x:,.1f}"))
    for i in range(0, len(e6), 2):
        a, b = e6.iloc[i], e6.iloc[i + 1]
        print(f"  quota {a.scenario.split()[-1]}: MINMAX moves the worst-off "
              f"company by {100*(b.max_company_cost/a.max_company_cost-1):+.1f}% "
              f"at {100*(b.total_deviation_cost/a.total_deviation_cost-1):+.1f}% "
              f"total cost  ({a.deviated_pct:.0f}% of trucks deviated)")

    # ------------------------------------------------------------ E7
    print("\n>>> E7  ADMIN VARIANCE PROPAGATES TO THE ROAD SIDE (the contribution)")
    print("  Truck appointments are planned against the rake's EXPECTED arrival,")
    print("  which depends on the administrative lead time M1. Widening M1's")
    print("  spread - same mean - moves the rake away from the plan in BOTH")
    print("  directions and the appointment schedule cannot absorb it.")
    print("  The source paper assumes deterministic arrivals; this is the gap.")
    from rtsim.admin import default_steps as _ds
    from dataclasses import replace as _rep
    e7 = []
    for mult in (0.25, 1.0, 2.0, 3.0):
        st = dict(_ds())
        m1 = st["M1"]
        st["M1"] = _rep(m1, service=Dist(m1.service.kind, mean=m1.service.mean,
                                         sd=m1.service.sd * mult))
        cfg = base_cfg()
        rows = []
        for rep in range(cfg.run.n_reps):
            seed = cfg.run.base_seed + rep
            log, _, term = simulate(cfg, policies.build("FCFS", cfg), seed,
                                    admin_steps=st, tas_rule="FCFS")
            rt = rake_table(log, cfg)
            rt = rt[rt.rake > cfg.run.warmup_rakes]
            road = term.road
            tf = log.to_frame(); tf = tf[tf.entity_type == "truck"]
            arr = tf[tf.name == "truck_arrive"][["entity_id", "t"]].set_index("entity_id").t
            ext = tf[tf.name == "truck_exit"][["entity_id", "t"]].set_index("entity_id").t
            k = kpis(rt, term, cfg)
            k["truck_turnaround_hr"] = (ext - arr).dropna().mean()
            k["hard_infeasible_pct"] = 100 * road.hard_infeasible / max(1, road.trucks_done)
            k["arrival_error_sd_hr"] = rt.rake_arrive.diff().std()
            rows.append(k)
        e7.append(row(pd.DataFrame(rows),
                      f"M1 sd x{mult:g}",
                      ["hard_infeasible_pct", "truck_turnaround_hr",
                       "mean_detention_hr", "arrival_error_sd_hr"]))
    e7 = pd.DataFrame(e7)
    print(e7[["scenario", "hard_infeasible_pct", "hard_infeasible_pct_ci",
              "arrival_error_sd_hr", "truck_turnaround_hr",
              "mean_detention_hr"]].to_string(
        index=False, float_format=lambda x: f"{x:,.2f}"))

    # ------------------------------------------------------------ charts
    fig, ax = plt.subplots(2, 2, figsize=(14, 9))

    a = ax[0, 0]
    x = [1, 2, 3, 4]
    a.errorbar(x, e4.truck_turnaround_hr, yerr=e4.truck_turnaround_hr_ci,
               marker="o", capsize=4, color="#c1440e", label="mean")
    a.plot(x, e4.truck_p90_hr, marker="s", ls="--", color="#8c8c8c", label="p90")
    a.set_xticks(x); a.set_xlabel("access lane capacity (1 = one-way passage)")
    a.set_ylabel("truck turnaround (hr)")
    a.set_title("E4  One-way passage vs organised queue")
    a.legend()

    a = ax[0, 1]
    w = 0.35
    none = e5[e5.scenario.str.startswith("NONE")]
    fcfs = e5[e5.scenario.str.startswith("FCFS")]
    idx = range(3)
    a.bar([i - w/2 for i in idx], none.truck_turnaround_hr, w,
          yerr=none.truck_turnaround_hr_ci, capsize=4,
          label="no appointments", color="#8c8c8c")
    a.bar([i + w/2 for i in idx], fcfs.truck_turnaround_hr, w,
          yerr=fcfs.truck_turnaround_hr_ci, capsize=4,
          label="appointment quota", color="#c1440e")
    a.set_xticks(list(idx)); a.set_xticklabels(["2 gates", "4 gates", "8 gates"])
    a.set_ylabel("truck turnaround (hr)")
    a.set_title("E5  Appointments vs gate capacity")
    a.legend()

    a = ax[1, 0]
    quotas = [8, 12, 20]
    fc = e6[e6.scenario.str.startswith("FCFS")].max_company_cost.values
    mm = e6[e6.scenario.str.startswith("MINMAX")].max_company_cost.values
    w = 0.35
    a.bar([i - w/2 for i in range(3)], fc, w, label="FCFS", color="#8c8c8c")
    a.bar([i + w/2 for i in range(3)], mm, w, label="MINMAX", color="#c1440e")
    a.set_xticks(range(3)); a.set_xticklabels([f"quota {q}" for q in quotas])
    a.set_ylabel("cost borne by the worst-off company")
    a.set_title("E6  Fairness works only where deviations are scarce")
    a.legend()

    a = ax[1, 1]
    ms = [0.25, 1.0, 2.0, 3.0]
    a.errorbar(ms, e7.hard_infeasible_pct, yerr=e7.hard_infeasible_pct_ci,
               marker="o", capsize=4, color="#c1440e")
    a.set_xlabel("multiplier on the spread of admin lead time M1")
    a.set_ylabel("trucks hard-infeasible (%)")
    a.set_title("E7  Admin variance propagates into road-side infeasibility")

    for r in ax:
        for a in r:
            a.grid(alpha=.25); a.set_axisbelow(True)
    fig.suptitle("Layer 2 - road side  |  8 replications, 95% CI  |  ALL RATES ASSUMED",
                 y=1.00)
    fig.tight_layout()
    fig.savefig("layer2_results.png", dpi=150, bbox_inches="tight")

    e4.round(3).to_csv("layer2_E4_lane.csv", index=False)
    e5.round(3).to_csv("layer2_E5_appointments.csv", index=False)
    e6.round(3).to_csv("layer2_E6_fairness.csv", index=False)
    e7.round(3).to_csv("layer2_E7_stochastic_rake.csv", index=False)
    print("\nSaved: layer2_results.png and four CSVs")


if __name__ == "__main__":
    main()
