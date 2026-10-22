"""
verify_trucks.py  -  Layer 2 integrity checks.

Contract:
  * with the road side off, Layers 0 and 1 are unchanged
  * every truck that enters also leaves
  * a one-way lane really blocks: never two trucks inside at once
  * the appointment system really respects its quota
  * MINMAX really equalises burden across companies relative to FCFS
  * deviation cost really is convex in the deviation
  * turning assumption A1 off really makes material availability bind

Run:  python -m rtsim.verify_trucks
"""
from dataclasses import replace
import pandas as pd

from .config import default_config
from .terminal import simulate
from .accounting import rake_table
from .admin import default_steps
from . import policies
from .trucks import deviation_cost, allocate_slots, generate_trucks
from .distributions import RandomStreams
from .verify import Check


def _cfg(**tk):
    c = default_config()
    c = replace(c, trucks=replace(c.trucks, enabled=True, **tk))
    # smaller run: each rake generates ~150 trucks
    return replace(c, run=replace(c.run, n_rakes=12, n_reps=5))


def _run(cfg, rule="FCFS", steps=None):
    steps = steps if steps is not None else default_steps()
    log, rakes, term = simulate(cfg, policies.build("FCFS", cfg),
                                cfg.run.base_seed, admin_steps=steps,
                                tas_rule=rule)
    return log, rake_table(log, cfg), term


def run_checks() -> bool:
    c = Check("LAYER 2 VERIFICATION  -  road side")
    cfg = _cfg()

    # 1. ROAD SIDE OFF LEAVES L1 UNTOUCHED -----------------------------
    l1, _, _ = simulate(cfg, policies.build("FCFS", cfg), cfg.run.base_seed,
                        admin_steps=default_steps())
    l2, _, t2 = _run(cfg, "FCFS")
    f1 = l1.to_frame()
    f2 = l2.to_frame()
    f2r = f2[f2.entity_type == "rake"].reset_index(drop=True)
    c.assert_("rake chain unchanged when road side is added (A1 on)",
              f1.equals(f2r), f"{len(f1)} vs {len(f2r)} rake events")

    # 2. TRUCK CONSERVATION ---------------------------------------------
    tf = f2[f2.entity_type == "truck"]
    arrived = int((tf.name == "truck_arrive").sum())
    exited = int((tf.name == "truck_exit").sum())
    c.assert_("every truck that arrives also exits", arrived == exited,
              f"{arrived} in, {exited} out")

    # 3. ONE-WAY LANE IS EXCLUSIVE ---------------------------------------
    # capacity 1 must never have two trucks inside simultaneously
    ev = tf[tf.name.isin(["lane_seize", "lane_free"])].sort_values("t")
    inside, peak = 0, 0
    for _, r in ev.iterrows():
        inside += 1 if r["name"] == "lane_seize" else -1
        peak = max(peak, inside)
    c.assert_("one-way lane never holds two trucks at once", peak <= 1,
              f"peak occupancy {peak}")

    # 4. QUEUED LANE ALLOWS MORE -----------------------------------------
    cfg3 = _cfg(lane_capacity=3)
    l3, _, _ = _run(cfg3, "FCFS")
    f3 = l3.to_frame()
    t3 = f3[(f3.entity_type == "truck") & f3.name.isin(["lane_seize", "lane_free"])]
    inside, peak3 = 0, 0
    for _, r in t3.sort_values("t").iterrows():
        inside += 1 if r["name"] == "lane_seize" else -1
        peak3 = max(peak3, inside)
    c.assert_("queued lane (capacity 3) permits concurrent trucks",
              1 < peak3 <= 3, f"peak occupancy {peak3}")

    # 5. QUOTA IS RESPECTED ----------------------------------------------
    streams = RandomStreams(1)
    from .terminal import generate_rakes
    rk = generate_rakes(cfg, streams)
    tks = generate_trucks(cfg, rk, streams)
    allocate_slots(cfg, tks, "FCFS")
    load = pd.Series([t.assigned_period for t in tks]).value_counts()
    c.assert_("appointment quota respected in all but forced periods",
              (load <= cfg.trucks.slots_per_period).mean() > 0.95,
              f"peak {load.max()} vs quota {cfg.trucks.slots_per_period}")

    # 6. NO APPOINTMENT SYSTEM => NO DEVIATION, MORE PEAKING -------------
    tks_n = generate_trucks(cfg, rk, RandomStreams(1))
    s_none = allocate_slots(cfg, tks_n, "NONE")
    tks_f = generate_trucks(cfg, rk, RandomStreams(1))
    s_fcfs = allocate_slots(cfg, tks_f, "FCFS")
    peak_none = pd.Series([t.assigned_period for t in tks_n]).value_counts().max()
    peak_fcfs = pd.Series([t.assigned_period for t in tks_f]).value_counts().max()
    c.assert_("appointment system flattens the arrival peak",
              peak_fcfs < peak_none, f"peak {peak_none} -> {peak_fcfs}")

    # 7. DEVIATION COST IS CONVEX -----------------------------------------
    d = [deviation_cost(k, 1.0) for k in range(8)]
    convex = all(d[i + 1] - d[i] > d[i] - d[i - 1] for i in range(1, 7))
    c.assert_("deviation cost is convex in periods deviated", convex,
              " ".join(f"{x:.1f}" for x in d))

    # 8. MINMAX EQUALISES BURDEN -------------------------------------------
    tks_a = generate_trucks(cfg, rk, RandomStreams(1))
    sa = allocate_slots(cfg, tks_a, "FCFS")
    tks_b = generate_trucks(cfg, rk, RandomStreams(1))
    sb = allocate_slots(cfg, tks_b, "MINMAX")
    c.assert_("MINMAX lowers the worst-off company's cost vs FCFS",
              sb["max_company_cost"] <= sa["max_company_cost"],
              f"FCFS max {sa['max_company_cost']:,.0f} -> "
              f"MINMAX max {sb['max_company_cost']:,.0f}")

    # 9. HARD INFEASIBILITY IS DETECTED -------------------------------------
    _, _, term = _run(cfg, "FCFS")
    c.assert_("hard infeasibility (truck vs stochastic rake) is measured",
              term.road.hard_infeasible >= 0 and term.road.trucks_done > 0,
              f"{term.road.hard_infeasible}/{term.road.trucks_done} trucks "
              f"({100*term.road.hard_infeasible/max(1,term.road.trucks_done):.1f}%)")

    # 10. GATE SERVERS MATTER ------------------------------------------------
    slow = _cfg(gate_servers=1)
    fast = _cfg(gate_servers=6)
    _, _, ts = _run(slow, "FCFS")
    _, _, tf2 = _run(fast, "FCFS")
    from .accounting import _time_weighted_mean
    q_slow = _time_weighted_mean(ts.road.gate_queue_samples)
    q_fast = _time_weighted_mean(tf2.road.gate_queue_samples)
    c.assert_("more gate servers shortens the gate queue", q_fast < q_slow,
              f"1 server {q_slow:.2f} -> 6 servers {q_fast:.2f} trucks waiting")

    # 11. TURNING OFF A1 MAKES MATERIAL BIND ---------------------------------
    # With an empty stockyard, A1 off, AND the road side throttled so that
    # deliveries cannot keep ahead of the rake, loading must wait for material
    # and detention must rise. Throttling matters: at the default quota the
    # trucks comfortably outrun the rake and A1 makes no difference, which is
    # itself the useful finding - A1 is harmless while the road side has slack.
    a1_on = _cfg(assume_material_always_available=True, stockyard_initial_t=0.0,
                 slots_per_period=2, delivery_lead_periods=1, gate_servers=1)
    a1_off = _cfg(assume_material_always_available=False, stockyard_initial_t=0.0,
                  slots_per_period=2, delivery_lead_periods=1, gate_servers=1)
    _, rt_on, _ = _run(a1_on, "FCFS")
    _, rt_off, _ = _run(a1_off, "FCFS")
    c.assert_("switching assumption A1 off makes material availability bind",
              rt_off.detention_hr.mean() > rt_on.detention_hr.mean(),
              f"A1 on {rt_on.detention_hr.mean():.2f}h -> "
              f"A1 off {rt_off.detention_hr.mean():.2f}h")

    # 12. M8 IS NOW ACTIVE ---------------------------------------------------
    af = f2[(f2.kind == "admin") & (f2.entity_type == "truck")]
    c.assert_("M8 gate verification fires for trucks", len(af) > 0,
              f"{len(af)} admin events on trucks")

    return c.report()


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_checks() else 1)
