"""
verify_admin.py  -  Layer 1 integrity checks.

The contract this layer must honour:
  * with every step disabled, Layer 1 == Layer 0, exactly
  * calendars really truncate work
  * rework really costs a full office cycle, not a service time
  * gates really block the physical events they claim to gate
  * detention rises when a step sits inside the free-time window,
    and does NOT rise when a step sits outside it

Run:  python -m rtsim.verify_admin
"""
import simpy

from .config import default_config
from .distributions import Dist, RandomStreams
from .eventlog import EventLog
from .terminal import simulate
from .accounting import rake_table
from . import policies
from .admin import (AdminChain, Calendar, AdminStep, default_steps,
                    all_disabled, ablate, digitalise, CAL_24_7,
                    PARTY_TERMINAL)
from .verify import Check


def _run(cfg, steps, seed=None):
    seed = seed or cfg.run.base_seed
    log, rakes, term = simulate(cfg, policies.build("FCFS", cfg), seed,
                                admin_steps=steps)
    return log, rake_table(log, cfg), term


def run_checks() -> bool:
    cfg = default_config()
    c = Check("LAYER 1 VERIFICATION  -  administrative chain")

    # 1. REDUCTION TO LAYER 0 ------------------------------------------
    log0, _, _ = simulate(cfg, policies.build("FCFS", cfg), cfg.run.base_seed)
    log1, _, _ = simulate(cfg, policies.build("FCFS", cfg), cfg.run.base_seed,
                          admin_steps=all_disabled())
    f0 = log0.to_frame()
    f1 = log1.to_frame()
    f1 = f1[f1.kind != "admin"].reset_index(drop=True)
    same = f0.equals(f1)
    c.assert_("all steps disabled reproduces Layer 0 exactly", same,
              f"{len(f0)} vs {len(f1)} physical events")

    # 2. CALENDAR TRUNCATION -------------------------------------------
    # a 1-hour task started at 17:30 in a 10:00-18:00 office must finish
    # next morning at 10:30, i.e. 17 hours later on the clock
    env = simpy.Environment()
    lg = EventLog()
    ch = AdminChain(env, lg, RandomStreams(1), {
        "T": AdminStep("T", "test", PARTY_TERMINAL, Dist("const", value=1.0),
                       Calendar("t", 10.0, 18.0, (0, 1, 2, 3, 4, 5, 6)))})

    def proc():
        yield env.timeout(17.5)
        t0 = env.now
        yield from ch.run_step("T", "rake", 1)
        proc.elapsed = env.now - t0
    env.process(proc())
    env.run()
    c.assert_("calendar truncation: 1h task at 17:30 costs 17h",
              abs(proc.elapsed - 17.0) < 1e-6, f"elapsed {proc.elapsed:.3f}h")

    # 3. 24/7 CALENDAR DOES NOT TRUNCATE -------------------------------
    env = simpy.Environment()
    lg = EventLog()
    ch = AdminChain(env, lg, RandomStreams(1), {
        "T": AdminStep("T", "test", PARTY_TERMINAL, Dist("const", value=1.0),
                       CAL_24_7)})

    def proc2():
        yield env.timeout(17.5)
        t0 = env.now
        yield from ch.run_step("T", "rake", 1)
        proc2.elapsed = env.now - t0
    env.process(proc2())
    env.run()
    c.assert_("24/7 calendar: same task costs exactly 1h",
              abs(proc2.elapsed - 1.0) < 1e-6, f"elapsed {proc2.elapsed:.3f}h")

    # 4. WEEKEND SKIP ---------------------------------------------------
    # day 5 = Saturday, day 6 = Sunday. A Mon-Fri office asked to work on
    # Saturday morning must wait until Monday.
    cal = Calendar("wk", 10.0, 18.0, (0, 1, 2, 3, 4))
    sat_11 = 5 * 24 + 11.0
    c.assert_("weekend skip: Saturday work waits for Monday",
              abs(cal.next_open(sat_11) - (7 * 24 + 10.0)) < 1e-9,
              f"next_open={cal.next_open(sat_11):.2f} expected={7*24+10.0:.2f}")

    # 5. REWORK COSTS MORE THAN ITS SERVICE TIME ------------------------
    base = default_steps()
    no_rw = {k: v.__class__(**{**v.__dict__, "rework_prob": 0.0}) for k, v in base.items()}
    _, rt_rw, _ = _run(cfg, base)
    _, rt_no, _ = _run(cfg, no_rw)
    c.assert_("removing rework reduces mean detention",
              rt_no.detention_hr.mean() < rt_rw.detention_hr.mean(),
              f"{rt_no.detention_hr.mean():.2f}h < {rt_rw.detention_hr.mean():.2f}h")

    # 6. GATES ACTUALLY GATE --------------------------------------------
    # M6 (release reporting) sits between loading_end and released, so
    # removing it must reduce detention
    _, rt_full, _ = _run(cfg, base)
    _, rt_noM6, _ = _run(cfg, ablate(["M6"]))
    c.assert_("ablating M6 (release reporting) cuts detention",
              rt_noM6.detention_hr.mean() < rt_full.detention_hr.mean(),
              f"{rt_noM6.detention_hr.mean():.2f}h < {rt_full.detention_hr.mean():.2f}h")

    # 7. STEPS AFTER LINE RELEASE DO NOT TOUCH DETENTION OR DWELL -------
    # M7 (RR + freight payment) runs after the rake is off the loading line.
    # It must shorten the fleet cycle time and leave detention and terminal
    # dwell EXACTLY unchanged. If it moves them, M7 is wrongly holding a
    # terminal resource somewhere.
    _, rt_noM7, _ = _run(cfg, ablate(["M7"]))
    d_det = abs(rt_noM7.detention_hr.mean() - rt_full.detention_hr.mean())
    d_dwl = abs(rt_noM7.dwell_hr.mean() - rt_full.dwell_hr.mean())
    d_cyc = rt_full.cycle_hr.mean() - rt_noM7.cycle_hr.mean()
    c.assert_("ablating M7 cuts fleet cycle but not detention or dwell",
              d_det < 1e-9 and d_dwl < 1e-9 and d_cyc > 0,
              f"d_detention={d_det:.1e}h d_dwell={d_dwl:.1e}h d_cycle={d_cyc:+.2f}h")

    # 8. DIGITALISATION IS AN IMPROVEMENT -------------------------------
    _, rt_dig, _ = _run(cfg, digitalise(["M5", "M6"]))
    c.assert_("digitalising M5+M6 reduces detention",
              rt_dig.detention_hr.mean() < rt_full.detention_hr.mean(),
              f"{rt_dig.detention_hr.mean():.2f}h < {rt_full.detention_hr.mean():.2f}h")

    # 9. ADMIN EVENTS ARE ATTRIBUTED ------------------------------------
    log, _, _ = _run(cfg, base)
    af = log.to_frame()
    af = af[af.kind == "admin"]
    owners = set(af.owner.unique())
    c.assert_("every admin event carries a party owner",
              len(owners) >= 3 and "" not in owners, f"owners={sorted(owners)}")

    # 10. MONOTONIC CHAIN STILL HOLDS WITH ADMIN ------------------------
    from .eventlog import RAKE_EVENT_ORDER
    wide = log.pivot_rakes().dropna()
    bad = 0
    for _, row in wide.iterrows():
        ts = [row[e] for e in RAKE_EVENT_ORDER]
        if any(ts[i] > ts[i + 1] + 1e-9 for i in range(len(ts) - 1)):
            bad += 1
    c.assert_("event chain still monotonic with admin gates", bad == 0,
              f"{bad} violations")

    # 11. DETERMINISM ----------------------------------------------------
    l1, _, _ = _run(cfg, base)
    l2, _, _ = _run(cfg, base)
    c.assert_("Layer 1 is deterministic under a fixed seed",
              l1.to_frame().equals(l2.to_frame()))

    # 12. ADMIN DOMINATES PHYSICAL --------------------------------------
    # the whole point of the layer: with realistic assumed parameters the
    # administrative share of dwell must be substantial, or the layer has
    # been parameterised into irrelevance
    physical = (rt_full.placement_hr + rt_full.loading_hr + rt_full.removal_hr).sum()
    total = rt_full.dwell_hr.sum()
    share = 100 * (1 - physical / total)
    c.assert_("non-physical time is a majority of dwell", share > 50.0,
              f"non-physical = {share:.1f}% of dwell")

    # 13. CALIBRATION AGAINST THE TERI BENCHMARK ------------------------
    # The admin service times are ASSUMED and were tuned so that detention
    # lands in TERI's measured 14-17 h band for Indian freight terminals.
    # This check guards that calibration: if a later edit drifts the model
    # out of the band, the number stops being defensible and this fails.
    import statistics as _st, math as _m
    ds = []
    for rep in range(15):
        _, rt, _ = _run(cfg, base, seed=cfg.run.base_seed + rep)
        rt = rt[rt.rake > cfg.run.warmup_rakes]
        ds.append(rt.detention_hr.mean())
    mu = _st.mean(ds)
    c.assert_("detention lands inside TERI's 14-17 h benchmark band",
              14.0 <= mu <= 17.0,
              f"{mu:.2f} h (calibrated, not validated - see admin.py header)")

    return c.report()


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_checks() else 1)
