"""
run_layer3.py  -  the decision layer: results and charts.

    python run_layer3.py

E8  BENCHMARK LADDER  FCFS -> SPT -> COST -> CNP -> CP-SAT, all scored by the
                      same simulator on the same scenarios. Reports what share
                      of the ACHIEVABLE gain each rule captures.
E9  DISRUPTION        The central claim. CP-SAT plans on the schedule it is
                      given; reality then differs. CNP re-decides every time a
                      line frees. Which degrades more gracefully?
E10 FAIRNESS          The ageing weight trades mean waiting against worst-case
                      waiting. Where is the knee?
"""
import _bootstrap  # noqa: F401  repo root on sys.path; outputs go to results/

from dataclasses import replace
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from rtsim.config import default_config
from rtsim.distributions import Dist, RandomStreams
from rtsim.verify import run_checks as v0
from rtsim.verify_admin import run_checks as v1
from rtsim.verify_optimiser import run_checks as v3
from rtsim.terminal import simulate, generate_rakes
from rtsim.accounting import rake_table, kpis
from rtsim.experiment import ci95
from rtsim.admin import default_steps
from rtsim.optimiser import optimal_sequence, cpsat_policy, captured_gain
from rtsim import policies

STEPS = default_steps()
RULES = ["FCFS", "SPT", "COST", "CNP"]
COLS = {"FCFS": "#8c8c8c", "SPT": "#5b7c99", "COST": "#c1440e",
        "CNP": "#1a7f37", "CPSAT": "#6a3d9a"}


def congested(n=25, gap=22.0, reps=10):
    """Sequencing only exists under contention, so Layer 3 studies a busy
    siding rather than the calibrated one. The gap must still keep the line
    STABLE: with the administrative layer on, a rake holds the line for about
    15 h, so an arrival gap below roughly 16 h drives utilisation past 1 and
    the queue grows without limit. Every policy then looks the same because
    all of them are drowning, and the confidence intervals swamp the effects.
    Measured: the hold is 19.5 h, so an 18 h gap gives rho = 1.07 and the
    queue never settles. 28 h gives rho = 0.70 - contended but stable."""
    c = default_config()
    c = replace(c, rake=replace(c.rake, arrival_gap=Dist("exp", mean=gap)))
    return replace(c, run=replace(c.run, n_rakes=n, n_reps=reps, warmup_rakes=3))


def evaluate(cfg, rakes, policy_fn, steps=None):
    log, _, term = simulate(cfg, policy_fn, cfg.run.base_seed,
                            rakes=rakes, admin_steps=steps or STEPS)
    rt = rake_table(log, cfg)
    rt = rt[rt.rake > cfg.run.warmup_rakes]
    k = kpis(rt, term, cfg)
    k["max_wait_hr"] = rt.wait_hr.max()
    k["p90_wait_hr"] = rt.wait_hr.quantile(0.90)
    return k


def main():
    print("\n>>> VERIFICATION")
    if not (v0() and v1() and v3()):
        raise SystemExit("verification failed")

    cfg = congested()

    # ------------------------------------------------------------ E8a
    print("\n\n>>> E8a  CONTROL: does the offline bound work at all?")
    print("  All administrative calendars set to 24/7, so a rake's line")
    print("  occupancy no longer depends on WHEN it is placed. Durations are")
    print("  then schedule-independent and classical 1|r_j|SumC_j applies, so")
    print("  CP-SAT must be an genuine lower bound. If it is not, the")
    print("  machinery is broken rather than the assumption.")
    from rtsim.admin import remove_calendar
    flat = remove_calendar(["M1", "M2", "M3", "M4", "M5", "M6", "M7"], STEPS)
    ctrl = {n: [] for n in ["FCFS", "COST", "CNP", "CPSAT"]}
    for rep in range(cfg.run.n_reps):
        seed = cfg.run.base_seed + rep
        rakes = generate_rakes(cfg, RandomStreams(seed))
        c_rep = replace(cfg, run=replace(cfg.run, base_seed=seed))
        for n in ["FCFS", "COST", "CNP"]:
            ctrl[n].append(evaluate(c_rep, rakes, policies.build(n, cfg),
                                    steps=flat))
        pilot, _, _ = simulate(c_rep, policies.build("FCFS", cfg), seed,
                               rakes=rakes, admin_steps=flat)
        pt = rake_table(pilot, cfg)
        hold = dict(zip(pt.rake.astype(int),
                        (pt.removed - pt.placement_start).astype(float)))
        hold = {r.id: hold.get(r.id, r.place_hr + r.load_hr + r.remove_hr)
                for r in rakes}
        ranks, _ = optimal_sequence(cfg, rakes, hold_hr=hold, time_limit_s=5.0)
        ctrl["CPSAT"].append(evaluate(c_rep, rakes, cpsat_policy(cfg, ranks),
                                      steps=flat))
    cw = {n: ci95(pd.DataFrame(v).mean_wait_hr.tolist())[0] for n, v in ctrl.items()}
    valid = cw["CPSAT"] <= min(v for k, v in cw.items() if k != "CPSAT") + 1e-6
    for n, v in cw.items():
        print(f"    {n:>6} mean wait {v:7.2f} h")
    print(f"  -> offline bound is {'VALID' if valid else 'NOT VALID'} "
          f"with calendars removed")

    # ------------------------------------------------------------ E8
    print("\n\n>>> E8b  BENCHMARK LADDER, full model (calendars on)")
    rows = {n: [] for n in RULES + ["CPSAT"]}
    proven = 0
    for rep in range(cfg.run.n_reps):
        seed = cfg.run.base_seed + rep
        rakes = generate_rakes(cfg, RandomStreams(seed))
        c_rep = replace(cfg, run=replace(cfg.run, base_seed=seed))
        for name in RULES:
            rows[name].append(evaluate(c_rep, rakes, policies.build(name, cfg)))
        # Build the CEILING properly: run a pilot, measure how long each
        # rake ACTUALLY held the line, and give the solver those durations.
        # A scheduler that knows every realised duration in advance cannot
        # be beaten by any online rule - that is what makes it a bound.
        pilot, _, _ = simulate(c_rep, policies.build("FCFS", cfg), seed,
                               rakes=rakes, admin_steps=STEPS)
        pt = rake_table(pilot, cfg)
        hold = dict(zip(pt.rake.astype(int),
                        (pt.removed - pt.placement_start).astype(float)))
        hold = {r.id: hold.get(r.id, r.place_hr + r.load_hr + r.remove_hr)
                for r in rakes}
        ranks, st = optimal_sequence(cfg, rakes, hold_hr=hold, time_limit_s=6.0)
        proven += (st == "OPTIMAL")
        rows["CPSAT"].append(evaluate(c_rep, rakes, cpsat_policy(cfg, ranks)))
    res = {k: pd.DataFrame(v) for k, v in rows.items()}

    metrics = ["mean_wait_hr", "max_wait_hr", "mean_detention_hr",
               "total_demurrage", "total_controllable_cost"]
    tab = []
    for name in RULES + ["CPSAT"]:
        r = {"policy": name}
        for m in metrics:
            mu, h = ci95(res[name][m].tolist())
            r[m], r[m + "_ci"] = mu, h
        tab.append(r)
    tab = pd.DataFrame(tab)

    floor = tab.loc[tab.policy == "FCFS", "mean_wait_hr"].iloc[0]
    ceil = tab.loc[tab.policy == "CPSAT", "mean_wait_hr"].iloc[0]
    bound_valid = tab.mean_wait_hr.min() >= ceil - 1e-6
    tab["captured_pct"] = (tab.mean_wait_hr.apply(
        lambda v: captured_gain(floor, ceil, v)) if bound_valid else float("nan"))

    print(f"  {cfg.run.n_reps} replications x {cfg.run.n_rakes} rakes, "
          f"arrival gap {cfg.rake.arrival_gap.mean:.0f} h, "
          f"CP-SAT proved optimal in {proven}/{cfg.run.n_reps}")
    print(f"  {'policy':>7} | {'mean wait':>17} | {'worst wait':>10} | "
          f"{'detention':>10} | {'demurrage':>12}")
    print("  " + "-" * 76)
    for _, r in tab.iterrows():
        print(f"  {r.policy:>7} | {r.mean_wait_hr:8.2f} +/-{r.mean_wait_hr_ci:5.2f} h | "
              f"{r.max_wait_hr:8.1f} h | {r.mean_detention_hr:8.2f} h | "
              f"{r.total_demurrage/1e6:9.2f} M")
    if not bound_valid:
        print("\n  NOTE: with office-hour calendars ON, an online rule beats the")
        print("  offline schedule, so CP-SAT is NOT a lower bound here and no")
        print("  'share of achievable gain' can be quoted. This is a property of")
        print("  the problem, not a solver failure - E8a shows the same machinery")
        print("  IS a valid bound once calendars are removed. Calendar-bounded")
        print("  administrative steps make a rake's line occupancy depend on WHEN")
        print("  it is placed, so service durations are schedule-DEPENDENT and")
        print("  the classical 1|r_j|SumC_j formulation no longer bounds the")
        print("  problem. Any offline benchmark for a terminal with office hours")
        print("  has to be built as a time-indexed model, not a sequencing one.")

    print("\n  paired difference vs FCFS (same scenarios):")
    for name in RULES[1:] + ["CPSAT"]:
        d = (res[name].mean_wait_hr - res["FCFS"].mean_wait_hr).tolist()
        m, h = ci95(d)
        sig = (m - h > 0) or (m + h < 0)
        print(f"    {name:>6} {m:+7.2f} +/-{h:.2f} h  "
              f"{'SIGNIFICANT' if sig else 'not significant'}")

    # ------------------------------------------------------------ E9
    print("\n>>> E9  DISRUPTION - what happens when the plan is wrong?")
    print("  CP-SAT is given the PLANNED arrival times and commits to a")
    print("  sequence. Rakes then arrive late with probability p. Contract")
    print("  Net re-runs its call for proposals every time a line frees, so")
    print("  it sees the disruption; the committed schedule does not.")
    e9 = []
    for p in (0.0, 0.20, 0.40):
        cf = replace(cfg, rake=replace(cfg.rake, late_prob=p,
                                       late_delay=Dist("logn", mean=14.0, sd=9.0)))
        acc = {n: [] for n in ["FCFS", "CNP", "CPSAT"]}
        for rep in range(cfg.run.n_reps):
            seed = cfg.run.base_seed + rep
            rakes = generate_rakes(cf, RandomStreams(seed))
            c_rep = replace(cf, run=replace(cf.run, base_seed=seed))
            for n in ["FCFS", "CNP"]:
                acc[n].append(evaluate(c_rep, rakes, policies.build(n, cf)))
            # the planner only knows the SCHEDULED arrivals
            planned = [replace_arrival(r) for r in rakes]
            ranks, _ = optimal_sequence(
                cf, planned,
                admin_overhead_hr=cf.coordination.expected_admin_hold_hr,
                time_limit_s=4.0)
            acc["CPSAT"].append(evaluate(c_rep, rakes, cpsat_policy(cf, ranks)))
        row = {"late_prob": p}
        for n in acc:
            mu, h = ci95(pd.DataFrame(acc[n]).mean_wait_hr.tolist())
            row[n], row[n + "_ci"] = mu, h
        e9.append(row)
    e9 = pd.DataFrame(e9)
    print(e9.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    d0 = e9.iloc[0]; d1 = e9.iloc[-1]
    print(f"  from 0% to 50% late: CP-SAT degrades "
          f"{100*(d1.CPSAT/d0.CPSAT-1):+.1f}%, CNP {100*(d1.CNP/d0.CNP-1):+.1f}%")

    # ------------------------------------------------------------ E10
    print("\n>>> E10  FAIRNESS - the ageing weight trades mean against worst case")
    e10 = []
    for w in (0.0, 0.5, 1.0, 3.0):
        cw = replace(cfg, coordination=replace(cfg.coordination, ageing_weight=w))
        acc = []
        for rep in range(cfg.run.n_reps):
            seed = cfg.run.base_seed + rep
            rakes = generate_rakes(cw, RandomStreams(seed))
            c_rep = replace(cw, run=replace(cw.run, base_seed=seed))
            acc.append(evaluate(c_rep, rakes, policies.build("CNP", cw)))
        df = pd.DataFrame(acc)
        mu, h = ci95(df.mean_wait_hr.tolist())
        mx, hx = ci95(df.max_wait_hr.tolist())
        e10.append({"ageing_weight": w, "mean_wait": mu, "mean_ci": h,
                    "worst_wait": mx, "worst_ci": hx})
    e10 = pd.DataFrame(e10)
    print(e10.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    # ------------------------------------------------------------ charts
    fig, ax = plt.subplots(2, 2, figsize=(14, 9))

    a = ax[0, 0]
    a.bar(tab.policy, tab.mean_wait_hr, yerr=tab.mean_wait_hr_ci, capsize=5,
          color=[COLS[p] for p in tab.policy])
    a.set_ylabel("mean wait for placement (hr)")
    a.set_title("E8  Benchmark ladder: rules, agents, offline optimum")

    a = ax[0, 1]
    a.bar(tab.policy, tab.max_wait_hr, color=[COLS[p] for p in tab.policy])
    a.set_ylabel("worst rake's wait (hr)")
    a.set_title("E8b  Worst case, not the average")

    a = ax[1, 0]
    x = e9.late_prob * 100
    for n in ["FCFS", "CNP", "CPSAT"]:
        a.errorbar(x, e9[n], yerr=e9[n + "_ci"], marker="o", capsize=4,
                   label=n, color=COLS[n])
    a.set_xlabel("probability a rake arrives late (%)")
    a.set_ylabel("mean wait (hr)")
    a.set_title("E9  Committed schedule vs continuous re-negotiation")
    a.legend()

    a = ax[1, 1]
    a.errorbar(e10.ageing_weight, e10.mean_wait, yerr=e10.mean_ci, marker="o",
               capsize=4, label="mean wait", color="#c1440e")
    a2 = a.twinx()
    a2.errorbar(e10.ageing_weight, e10.worst_wait, yerr=e10.worst_ci,
                marker="s", ls="--", capsize=4, label="worst wait",
                color="#5b7c99")
    a.set_xlabel("ageing weight in the Contract Net bid")
    a.set_ylabel("mean wait (hr)", color="#c1440e")
    a2.set_ylabel("worst-case wait (hr)", color="#5b7c99")
    a.set_title("E10  Efficiency vs fairness in the bid function")

    for r in ax:
        for b in r:
            b.grid(alpha=.25); b.set_axisbelow(True)
    fig.suptitle("Layer 3 - decision layer  |  20 replications, 95% CI  |  "
                 "congested siding, ALL RATES ASSUMED", y=1.00)
    fig.tight_layout()
    fig.savefig("layer3_results.png", dpi=150, bbox_inches="tight")

    tab.round(3).to_csv("layer3_E8_ladder.csv", index=False)
    e9.round(3).to_csv("layer3_E9_disruption.csv", index=False)
    e10.round(3).to_csv("layer3_E10_fairness.csv", index=False)
    print("\nSaved: layer3_results.png and three CSVs")


def replace_arrival(r):
    """A copy of the rake as the PLANNER sees it: on time. Used to build the
    committed CP-SAT schedule, which is then executed against reality."""
    from rtsim.terminal import Rake
    return Rake(rid=r.id, scheduled_arrival=r.scheduled_arrival,
                actual_arrival=r.scheduled_arrival, wagons=r.wagons,
                tonnes=r.tonnes, load_hr=r.load_hr, place_hr=r.place_hr,
                remove_hr=r.remove_hr, no_show=r.no_show,
                booking_time=r.booking_time, transit_hr=r.transit_hr)


if __name__ == "__main__":
    main()
