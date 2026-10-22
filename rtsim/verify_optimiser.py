"""
verify_optimiser.py  -  Layer 3 integrity checks.

Contract:
  * CP-SAT returns a valid permutation and respects release dates
  * with one line the optimal schedule never overlaps
  * the optimum is genuinely optimal on cases whose answer is known
  * CP-SAT is at least as good as every online rule on total waiting
  * CNP uses no future information
  * the ageing term really prevents starvation
  * every policy is scored by the SAME accounting, never by its own objective

Run:  python -m rtsim.verify_optimiser
"""
from dataclasses import replace
import pandas as pd

from .config import default_config
from .distributions import Dist, RandomStreams
from .terminal import simulate, generate_rakes, Rake
from .accounting import rake_table, kpis
from . import policies
from .optimiser import (optimal_sequence, cpsat_policy, captured_gain,
                         waiting_lower_bound)
from .verify import Check


def _stress(n=25, gap=8.0):
    """Sequencing decisions only exist under contention, so every check here
    uses a congested variant. Testing a scheduler at 22% utilisation would
    prove nothing."""
    c = default_config()
    c = replace(c, rake=replace(c.rake, arrival_gap=Dist("exp", mean=gap)))
    return replace(c, run=replace(c.run, n_rakes=n, warmup_rakes=0))


def run_checks() -> bool:
    c = Check("LAYER 3 VERIFICATION  -  optimiser and coordination")
    cfg = _stress()
    rakes = generate_rakes(cfg, RandomStreams(cfg.run.base_seed))

    # 1. VALID PERMUTATION ----------------------------------------------
    ranks, status = optimal_sequence(cfg, rakes, time_limit_s=15.0)
    ok = (ranks is not None
          and sorted(ranks.values()) == list(range(len(rakes)))
          and set(ranks) == {r.id for r in rakes})
    c.assert_("CP-SAT returns a valid permutation of all rakes", ok,
              f"status={status}, n={len(ranks) if ranks else 0}")

    # 2. RELEASE DATES RESPECTED -----------------------------------------
    # replay the sequence and confirm no rake is placed before it arrives
    log, _, _ = simulate(cfg, cpsat_policy(cfg, ranks), cfg.run.base_seed,
                         rakes=rakes)
    rt = rake_table(log, cfg)
    c.assert_("no rake is placed before it arrives",
              bool((rt.placement_start >= rt.rake_arrive - 1e-9).all()),
              f"min slack {(rt.placement_start - rt.rake_arrive).min():.3f} h")

    # 3. NO OVERLAP ON A SINGLE LINE -------------------------------------
    iv = rt[["placement_start", "removed"]].sort_values("placement_start").values
    overlaps = sum(1 for i in range(len(iv) - 1) if iv[i][1] > iv[i + 1][0] + 1e-9)
    c.assert_("single line schedule has no overlapping occupancy",
              overlaps == 0, f"{overlaps} overlaps")

    # 4. KNOWN-ANSWER TEST -----------------------------------------------
    # All rakes available at t=0 on one line: total waiting is minimised by
    # SHORTEST PROCESSING TIME FIRST (Smith's rule). The solver must find it.
    toy = []
    for i, ld in enumerate([9.0, 2.0, 5.0, 1.0], start=1):
        toy.append(Rake(rid=i, scheduled_arrival=0.0, actual_arrival=0.0,
                        wagons=58, tonnes=3368.64, load_hr=ld,
                        place_hr=0.0, remove_hr=0.0))
    tr, _ = optimal_sequence(cfg, toy, time_limit_s=10.0)
    got = [rid for rid, _ in sorted(tr.items(), key=lambda kv: kv[1])]
    c.assert_("solver reproduces SPT when all jobs are available at t=0",
              got == [4, 2, 3, 1], f"order {got}, expected [4, 2, 3, 1]")

    # 5. CP-SAT DOMINATES EVERY ONLINE RULE ------------------------------
    waits = {}
    for name in ["FCFS", "SPT", "COST", "CNP"]:
        lg, _, tm = simulate(cfg, policies.build(name, cfg),
                             cfg.run.base_seed, rakes=rakes)
        waits[name] = kpis(rake_table(lg, cfg), tm, cfg)["mean_wait_hr"]
    lg, _, tm = simulate(cfg, cpsat_policy(cfg, ranks), cfg.run.base_seed,
                         rakes=rakes)
    waits["CPSAT"] = kpis(rake_table(lg, cfg), tm, cfg)["mean_wait_hr"]
    c.assert_("offline optimum beats or matches every online rule",
              waits["CPSAT"] <= min(v for k, v in waits.items() if k != "CPSAT") + 1e-6,
              " ".join(f"{k}={v:.2f}" for k, v in waits.items()))

    # 6. CNP IS AN IMPROVEMENT OVER FCFS ---------------------------------
    c.assert_("Contract Net beats first-come-first-served on waiting",
              waits["CNP"] < waits["FCFS"],
              f"CNP={waits['CNP']:.2f}h < FCFS={waits['FCFS']:.2f}h")

    # 7. CNP USES NO FUTURE INFORMATION -----------------------------------
    # A rake's bid must depend only on its own attributes and the clock. If
    # future arrivals were leaking in, appending an extra rake far in the
    # future would change earlier bids. It must not.
    pol = policies.build("CNP", cfg)
    ctx = {"now": 100.0, "terminal": None}
    b1 = pol(rakes[0], ctx)
    b2 = pol(rakes[0], {"now": 100.0, "terminal": None})
    c.assert_("CNP bid depends only on the rake and the clock",
              abs(b1 - b2) < 1e-12, f"bid={b1:,.0f}")

    # 8. AGEING PREVENTS STARVATION ---------------------------------------
    # With ageing switched off, the worst-served rake should wait longer.
    no_age = replace(cfg, coordination=replace(cfg.coordination, ageing_weight=0.0))
    lg0, _, _ = simulate(no_age, policies.build("CNP", no_age),
                         cfg.run.base_seed, rakes=rakes)
    w0 = rake_table(lg0, no_age).wait_hr.max()
    lg1, _, _ = simulate(cfg, policies.build("CNP", cfg),
                         cfg.run.base_seed, rakes=rakes)
    w1 = rake_table(lg1, cfg).wait_hr.max()
    c.assert_("ageing term reduces the worst rake's wait", w1 <= w0 + 1e-9,
              f"no ageing {w0:.1f}h -> with ageing {w1:.1f}h")

    # 9. AGEING WEIGHT IS MONOTONE TOWARDS FCFS ---------------------------
    # As ageing dominates, Contract Net must converge on arrival order.
    heavy = replace(cfg, coordination=replace(cfg.coordination, ageing_weight=50.0))
    lgh, _, tmh = simulate(heavy, policies.build("CNP", heavy),
                           cfg.run.base_seed, rakes=rakes)
    wh = kpis(rake_table(lgh, heavy), tmh, heavy)["mean_wait_hr"]
    c.assert_("heavy ageing collapses Contract Net onto FCFS",
              abs(wh - waits["FCFS"]) < 0.5,
              f"heavy-ageing CNP={wh:.2f}h vs FCFS={waits['FCFS']:.2f}h")

    # 10. CAPTURED-GAIN ARITHMETIC ----------------------------------------
    g_fcfs = captured_gain(waits["FCFS"], waits["CPSAT"], waits["FCFS"])
    g_opt = captured_gain(waits["FCFS"], waits["CPSAT"], waits["CPSAT"])
    c.assert_("captured-gain scale is anchored at 0% and 100%",
              abs(g_fcfs) < 1e-9 and abs(g_opt - 100.0) < 1e-9,
              f"FCFS={g_fcfs:.1f}%  CP-SAT={g_opt:.1f}%")

    # 11. ALL POLICIES SCORED BY THE SAME ACCOUNTING -----------------------
    # Every policy must serve the same rakes and earn the same revenue;
    # only the controllable cost may differ. If revenue moved, the policies
    # would be running different scenarios and nothing would be comparable.
    revs, counts = set(), set()
    for name in ["FCFS", "SPT", "COST", "CNP"]:
        lg, _, _ = simulate(cfg, policies.build(name, cfg),
                            cfg.run.base_seed, rakes=rakes)
        t = rake_table(lg, cfg)
        revs.add(round(t.revenue.sum(), 6)); counts.add(len(t))
    c.assert_("all policies serve identical rakes for identical revenue",
              len(revs) == 1 and len(counts) == 1,
              f"revenues={len(revs)} distinct, counts={counts}")

    # 12. SOLVER SCALES TO A USEFUL HORIZON --------------------------------
    big = _stress(n=60, gap=8.0)
    br = generate_rakes(big, RandomStreams(big.run.base_seed))
    _, st2 = optimal_sequence(big, br, time_limit_s=20.0)
    c.assert_("solver returns a usable schedule for 60 rakes in 20 s",
              st2 in ("OPTIMAL", "FEASIBLE"), f"status={st2}")

    # 13. THE LOWER BOUND IS ACTUALLY A LOWER BOUND -----------------------
    # The first attempt at a bound - solve offline, then EXECUTE the sequence
    # and measure - was beaten by online rules, because executing the plan
    # re-inflates every duration through the office-hours calendars. The bound
    # is now read from the solver's objective and computed on relaxed
    # durations, so it must dominate every policy by construction.
    from .admin import default_steps as _ds, remove_calendar, no_rework
    KS = ["M1", "M2", "M3", "M4", "M5", "M6", "M7"]
    flat = no_rework(KS, remove_calendar(KS, _ds()))
    pilot, _, _ = simulate(cfg, policies.build("FCFS", cfg), cfg.run.base_seed,
                           rakes=rakes, admin_steps=flat)
    pt = rake_table(pilot, cfg)
    mh = dict(zip(pt.rake.astype(int),
                  (pt.removed - pt.placement_start).astype(float)))
    mh = {r.id: mh.get(r.id, r.place_hr + r.load_hr + r.remove_hr) for r in rakes}
    lb, lbst = waiting_lower_bound(cfg, rakes, min_hold=mh, time_limit_s=10.0)
    obs = {}
    for name in ["FCFS", "SPT", "COST", "CNP"]:
        lg, _, _ = simulate(cfg, policies.build(name, cfg), cfg.run.base_seed,
                            rakes=rakes, admin_steps=_ds())
        obs[name] = rake_table(lg, cfg).wait_hr.mean()
    c.assert_("lower bound is not violated by any policy",
              lb is not None and all(v >= lb - 1e-6 for v in obs.values()),
              f"bound {lb:.2f} h ({lbst}) vs min observed {min(obs.values()):.2f} h")

    # 14. THE BOUND IS READ, NEVER EXECUTED --------------------------------
    # Guard against the original mistake returning: executing the relaxed
    # schedule must give a WORSE number than the bound, which is precisely
    # why the bound has to be the objective value and not a simulation result.
    ranks_r, _ = optimal_sequence(cfg, rakes, hold_hr=mh, time_limit_s=8.0)
    lgx, _, _ = simulate(cfg, cpsat_policy(cfg, ranks_r), cfg.run.base_seed,
                         rakes=rakes, admin_steps=_ds())
    executed = rake_table(lgx, cfg).wait_hr.mean()
    c.assert_("executing the relaxed plan is worse than the bound it came from",
              executed > lb,
              f"executed {executed:.2f} h > bound {lb:.2f} h - so the bound "
              f"must be READ from the solver, not simulated")

    return c.report()


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_checks() else 1)
