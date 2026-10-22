"""
verify.py  -  Layer 0 integrity checks.

A simulation that runs is not a simulation that is correct. Before any
result from this model is presented, these checks must pass. They are the
standard verification battery for a discrete-event model (Law, Simulation
Modeling and Analysis, ch. 5).

Run:  python -m rtsim.verify
"""
import numpy as np
import pandas as pd

from .config import Config, default_config
from .distributions import RandomStreams
from .eventlog import RAKE_EVENT_ORDER
from .terminal import simulate, generate_rakes
from .accounting import rake_table, kpis, _time_weighted_mean
from . import policies


class Check:
    def __init__(self, title="VERIFICATION"):
        self.results = []
        self.title = title

    def assert_(self, name, ok, detail=""):
        self.results.append((name, bool(ok), detail))
        return ok

    def report(self) -> bool:
        w = max(len(n) for n, _, _ in self.results)
        print("\n" + "=" * (w + 30))
        print(getattr(self, "title", "VERIFICATION"))
        print("=" * (w + 30))
        for n, ok, d in self.results:
            print(f"  [{'PASS' if ok else 'FAIL'}] {n:<{w}}  {d}")
        n_fail = sum(1 for _, ok, _ in self.results if not ok)
        print("-" * (w + 30))
        print(f"  {len(self.results) - n_fail}/{len(self.results)} passed")
        print("=" * (w + 30))
        return n_fail == 0


# ----------------------------------------------------------------------
def run_checks(cfg: Config = None) -> bool:
    cfg = cfg or default_config()
    c = Check("LAYER 0 VERIFICATION  -  physical model")

    pol = policies.build("FCFS", cfg)
    log, rakes, term = simulate(cfg, pol, seed=cfg.run.base_seed)
    wide = log.pivot_rakes()
    rt = rake_table(log, cfg)

    # 1. CONSERVATION -------------------------------------------------
    expected = sum(1 for r in rakes if not r.no_show)
    c.assert_("conservation: every rake that arrives also leaves",
              len(rt) == expected, f"{len(rt)}/{expected} completed")

    # 2. EVENT ORDERING -----------------------------------------------
    bad = 0
    for _, row in wide.dropna().iterrows():
        ts = [row[e] for e in RAKE_EVENT_ORDER]
        if any(ts[i] > ts[i + 1] + 1e-9 for i in range(len(ts) - 1)):
            bad += 1
    c.assert_("event chain is monotonic for every rake", bad == 0,
              f"{bad} violations")

    # 3. NO NEGATIVE DURATIONS ----------------------------------------
    dur_cols = ["wait_hr", "placement_hr", "preload_idle_hr", "loading_hr",
                "release_lag_hr", "removal_hr", "detention_hr", "dwell_hr"]
    neg = int((rt[dur_cols] < -1e-9).sum().sum())
    c.assert_("no negative durations", neg == 0, f"{neg} negatives")

    # 4. RESOURCE CAPACITY --------------------------------------------
    max_busy = max(n for _, n in term.line_busy_samples) if term.line_busy_samples else 0
    c.assert_("loading lines never over capacity",
              max_busy <= cfg.resources.loading_lines,
              f"peak {max_busy} <= {cfg.resources.loading_lines}")

    # 5. FREE-TIME CLOCK ----------------------------------------------
    # detention must equal released - placed, exactly, by construction
    err = float((rt.detention_hr - (rt["released"] - rt["placed"])).abs().max())
    c.assert_("detention == release - placement (IR definition)", err < 1e-9,
              f"max err {err:.2e}")

    # 6. DEMURRAGE RULE ------------------------------------------------
    # zero demurrage exactly when detention <= free time
    ft = cfg.charges.free_time_hr
    mism = int(((rt.detention_hr <= ft) & (rt.demurrage > 0)).sum()
               + ((rt.detention_hr > ft) & (rt.demurrage <= 0)).sum())
    c.assert_("demurrage charged iff free time exceeded", mism == 0,
              f"{mism} mismatches")

    # 6b. GRADED DEMURRAGE MATCHES THE CIRCULAR -------------------------
    # Hand-checked against [IR-COMP] 3.1. Each band applies only to the hours
    # inside it, so the schedule is piecewise linear and convex.
    from .accounting import graded_demurrage
    cases = [
        (0.0, 0.0),
        (6.0, 6 * 150),                                   # all at base
        (12.0, 6 * 150 + 6 * 165),                        # +10% band
        (24.0, 6 * 150 + 6 * 165 + 12 * 187.5),           # +25% band
        (48.0, 6 * 150 + 6 * 165 + 12 * 187.5 + 24 * 225),
    ]
    errs = [abs(graded_demurrage(e, cfg) - want) for e, want in cases]
    c.assert_("graded demurrage reproduces the IR rate table",
              max(errs) < 1e-6, f"max err {max(errs):.2e} over {len(cases)} bands")

    # 6c. MARGINAL RATE IS NON-DECREASING -------------------------------
    marg = [graded_demurrage(h + 1, cfg) - graded_demurrage(h, cfg)
            for h in range(0, 90)]
    c.assert_("marginal demurrage never falls as detention grows",
              all(marg[i + 1] >= marg[i] - 1e-9 for i in range(len(marg) - 1)),
              f"Rs{marg[0]:.0f}/wagon/h at 0h -> Rs{marg[-1]:.0f} at 89h")

    # 6d. FREE TIME IS BUILT FROM CITED COMPONENTS ----------------------
    ch = cfg.charges
    want_ft = (ch.base_free_time_hr + ch.siding_additional_free_time_hr
               + (ch.tarpaulin_free_time_hr if ch.tarpaulin_applies else 0.0))
    c.assert_("free time = 5:00 base + 2:00 siding + 1:00 tarpaulin",
              abs(ch.free_time_hr - want_ft) < 1e-9 and abs(want_ft - 8.0) < 1e-9,
              f"{ch.free_time_hr:.1f} h  [IR-COMP 2.2(a)(i), 2.2.1(a), 2.7]")

    # 7. LITTLE'S LAW --------------------------------------------------
    # L = lambda * W  for the whole terminal. Independent check that the
    # queue statistics and the per-rake durations tell the same story.
    horizon = rt["removed"].max() - rt["rake_arrive"].min()
    lam = len(rt) / horizon
    W = rt.dwell_hr.mean()
    L_formula = lam * W
    L_observed = _time_weighted_mean(term.queue_len_samples) + \
        _time_weighted_mean(term.line_busy_samples)
    rel = abs(L_formula - L_observed) / max(L_formula, 1e-9)
    c.assert_("Little's Law L = lambda*W holds within 5%", rel < 0.05,
              f"L_formula={L_formula:.3f} L_obs={L_observed:.3f} rel={rel:.1%}")

    # 8. DETERMINISM ---------------------------------------------------
    log2, _, _ = simulate(cfg, policies.build("FCFS", cfg), seed=cfg.run.base_seed)
    same = log.to_frame().equals(log2.to_frame())
    c.assert_("same seed reproduces byte-identical event log", same)

    # 8b. CROSS-PROCESS REPRODUCIBILITY --------------------------------
    # Python salts str hashing per process. If the RNG sub-seeds depended on
    # hash(), results would differ between runs while still looking
    # deterministic inside one run. Pinning a known digest catches that.
    known = RandomStreams.substream_seed(1000, "loading")
    c.assert_("RNG sub-seeds are process-independent",
              known == 1948952355, f"substream_seed(1000,'loading')={known}")

    # 8c. COMMON RANDOM NUMBERS SURVIVE A POLICY CHANGE -----------------
    # The strongest form of the requirement: change the dispatch order and
    # every rake must still receive IDENTICAL durations. A stream shared
    # across entities is drawn in execution order and silently fails this,
    # which confounds every paired comparison downstream.
    from .admin import default_steps as _ds
    dur = {}
    for pol_name in ["FCFS", "LPT"]:
        lg, _, _ = simulate(cfg, policies.build(pol_name, cfg),
                            cfg.run.base_seed, admin_steps=_ds())
        t = rake_table(lg, cfg)
        dur[pol_name] = dict(zip(t.rake.astype(int),
                                 t.loading_hr + t.placement_hr))
    err = max(abs(dur["FCFS"][k] - dur["LPT"][k])
              for k in dur["FCFS"] if k in dur["LPT"])
    c.assert_("PHYSICAL durations identical under different policies",
              err < 1e-5, f"max diff {err:.2e} h")

    # 8d. ADMIN ELAPSED TIME IS SCHEDULE-DEPENDENT ----------------------
    # The counterpart, and a property of the problem rather than a defect.
    # Physical durations are drawn once per rake and never move. Elapsed
    # ADMINISTRATIVE time does move, because an office-hours calendar makes a
    # step's wall-clock cost depend on WHAT TIME OF DAY it starts - which
    # depends on the sequence. Consequence for the methodology: a rake's line
    # occupancy is not a fixed processing time, so the classical
    # 1|r_j|SumC_j sequencing formulation cannot bound this problem; an
    # offline benchmark has to be time-indexed.
    adm = {}
    for pol_name in ["FCFS", "LPT"]:
        lg, _, _ = simulate(cfg, policies.build(pol_name, cfg),
                            cfg.run.base_seed, admin_steps=_ds())
        t = rake_table(lg, cfg)
        adm[pol_name] = dict(zip(t.rake.astype(int), t.release_lag_hr))
    spread = max(abs(adm["FCFS"][k] - adm["LPT"][k])
                 for k in adm["FCFS"] if k in adm["LPT"])
    c.assert_("admin elapsed time DOES depend on the schedule (expected)",
              spread > 1.0, f"up to {spread:.1f} h difference on the same rake")

    # 9. COMMON RANDOM NUMBERS ----------------------------------------
    # different policies must face an IDENTICAL scenario, else the paired
    # comparison is invalid
    s = RandomStreams(cfg.run.base_seed)
    r1 = generate_rakes(cfg, s)
    s2 = RandomStreams(cfg.run.base_seed)
    r2 = generate_rakes(cfg, s2)
    ident = all((a.actual_arrival == b.actual_arrival and a.load_hr == b.load_hr)
                for a, b in zip(r1, r2))
    c.assert_("common random numbers: scenario identical across runs", ident)

    # 10. POLICY SENSITIVITY -------------------------------------------
    # A sequencing rule can only show its effect when rakes actually
    # contend for the line. At the calibrated arrival rate the physical
    # model alone is lightly loaded, so this check deliberately uses a
    # CONGESTED variant. Testing it at low load would prove nothing.
    from dataclasses import replace as _replace
    from .distributions import Dist as _Dist
    stress = _replace(cfg, label="stress",
                      rake=_replace(cfg.rake, arrival_gap=_Dist("exp", mean=6.0)))
    res = {}
    for name in ["FCFS", "SPT", "LPT"]:
        lg, _, tm = simulate(stress, policies.build(name, stress),
                             seed=stress.run.base_seed)
        res[name] = kpis(rake_table(lg, stress), tm, stress)["mean_wait_hr"]
    spread = max(res.values()) - min(res.values())
    c.assert_("policy hook changes outcomes (congested variant)", spread > 1e-6,
              f"wait: " + ", ".join(f"{k}={v:.2f}h" for k, v in res.items()))

    # 11. SPT DOMINATES LPT --------------------------------------------
    # sanity against scheduling theory: shortest-first must beat longest-first
    # on mean waiting time
    c.assert_("SPT beats LPT on mean wait (scheduling theory)",
              res["SPT"] < res["LPT"],
              f"SPT={res['SPT']:.2f}h < LPT={res['LPT']:.2f}h")

    # 12. THROUGHPUT INVARIANCE ----------------------------------------
    # sequencing cannot change HOW MANY rakes are served, only when
    counts = set()
    for name in ["FCFS", "SPT", "LPT", "COST"]:
        lg, _, _ = simulate(cfg, policies.build(name, cfg), seed=cfg.run.base_seed)
        counts.add(len(rake_table(lg, cfg)))
    c.assert_("all policies serve the same number of rakes", len(counts) == 1,
              f"counts={counts}")

    return c.report()


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_checks() else 1)
