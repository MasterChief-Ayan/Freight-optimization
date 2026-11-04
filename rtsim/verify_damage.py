"""
verify_damage.py  -  integrity checks for the optional wagon-damage module.

Run:  python -m rtsim.verify_damage

The module must (a) change nothing when it is off or when nothing is damaged,
(b) put each effect where the rules put it (inside or outside the IR free-time
window), and (c) never break the physical invariants of the base model.
"""
from dataclasses import replace

import numpy as np
import pandas as pd

from .config import default_config
from .admin import default_steps
from .eventlog import RAKE_EVENT_ORDER
from .terminal import simulate
from .accounting import rake_table
from . import policies
from .verify import Check


def _run(cfg, seed=1000, admin=True):
    log, rakes, term = simulate(cfg, policies.build("FCFS", cfg), seed,
                                admin_steps=default_steps() if admin else None)
    return log, rake_table(log, cfg), term


def _dmg(c0, **kw):
    return replace(c0, damage=replace(c0.damage, enabled=True, **kw))


def run_checks() -> bool:
    c = Check("WAGON-DAMAGE MODULE VERIFICATION")
    c0 = default_config()
    _, base, _ = _run(c0)

    # 1-2. switching on with nothing damaged changes nothing (L1 and L0)
    _, rt0, _ = _run(_dmg(c0))
    c.assert_("enabled with p = 0 reproduces the model exactly (Layer 1)", rt0.equals(base),
              f"{len(rt0)} rakes, mean detention {rt0.detention_hr.mean():.4f} h")
    _, b0, _ = _run(c0, admin=False)
    _, r00, _ = _run(_dmg(c0), admin=False)
    c.assert_("enabled with p = 0 reproduces the model exactly (Layer 0)", r00.equals(b0), "")

    # 3. repairable-only damage raises mean detention and the placed -> loading gap.
    #    (Not rake by rake: office calendars make one rake's detention depend on
    #    when the previous one finished, so a delay can shorten a later rake's
    #    detention - the schedule dependence verify.py already documents.)
    rep = _dmg(c0, p_defect_per_wagon=0.03, share_minor=0.0, share_repairable=1.0)
    _, rr, tr = _run(rep)
    c.assert_("repairs at the siding raise detention and the pre-loading gap",
              rr.detention_hr.mean() > base.detention_hr.mean()
              and rr.preload_idle_hr.mean() > base.preload_idle_hr.mean(),
              f"detention {base.detention_hr.mean():.2f} -> {rr.detention_hr.mean():.2f} h; "
              f"pre-loading {base.preload_idle_hr.mean():.2f} -> {rr.preload_idle_hr.mean():.2f} h")

    # 4. a repair shorter than the placement paperwork costs (almost) nothing:
    #    it runs IN PARALLEL with M4, it is not added on top
    tiny = _dmg(c0, p_defect_per_wagon=0.03, share_minor=0.0, share_repairable=1.0,
                repair_hr_per_wagon=type(c0.damage.repair_hr_per_wagon)("const", mean=0.001))
    _, rt_tiny, _ = _run(tiny)
    c.assert_("repairs run in parallel with M4 (tiny repairs add ~0 h)",
              abs(rt_tiny.detention_hr.mean() - base.detention_hr.mean()) < 0.01,
              f"diff {rt_tiny.detention_hr.mean() - base.detention_hr.mean():+.4f} h")

    # 5. detach policy: every unfit wagon is detached, and the time sits INSIDE detention
    det = _dmg(c0, p_defect_per_wagon=0.03, share_minor=0.0, share_repairable=0.0, unfit_policy="detach")
    log_d, rd, td = _run(det)
    dl = pd.DataFrame.from_dict(td.damage_log, orient="index")
    c.assert_("detach: every unfit wagon is detached",
              (dl.wagons_detached == dl.n_unfit.clip(upper=c0.rake.wagons - 1)).all(),
              f"{int(dl.wagons_detached.sum())} wagons detached")
    c.assert_("detach: the delay falls inside the free-time window (detention rises)",
              rd.detention_hr.mean() > base.detention_hr.mean(),
              f"{base.detention_hr.mean():.2f} -> {rd.detention_hr.mean():.2f} h")

    # 6. return_rake: rejected visits sit OUTSIDE the free-time clock; the wait rises
    ret = _dmg(c0, p_defect_per_wagon=0.03, share_minor=0.0, share_repairable=0.0, unfit_policy="return_rake")
    log_r, rr2, tr2 = _run(ret)
    dl2 = pd.DataFrame.from_dict(tr2.damage_log, orient="index")
    rej = dl2[dl2.rejected > 0].index
    mm = base.set_index("rake").join(rr2.set_index("rake"), rsuffix="_r")
    c.assert_("return_rake: rejected rakes wait at least the replacement lead time longer",
              len(rej) > 0 and all(mm.loc[i, "wait_hr_r"] >= dl2.loc[i, "replacement_wait_hr"] for i in rej),
              f"{len(rej)} rakes rejected")
    ev2 = log_r.to_frame()
    last_trial = ev2[ev2.name == "trial_removed"].groupby("entity_id").t.max()
    placed = log_r.pivot_rakes().set_index("rake").placed
    c.assert_("return_rake: free-time clock starts only after the rejected visit",
              len(last_trial) > 0 and all(placed[i] > last_trial[i] for i in last_trial.index),
              f"{len(last_trial)} rakes; detention {rr2.detention_hr.mean():.2f} h (return) "
              f"vs {rd.detention_hr.mean():.2f} h (detach)")

    # 7. physical invariants still hold with damage on (both policies)
    ok_order, ok_lines = True, True
    for lg, rt in ((log_d, rd), (log_r, rr2)):
        w = lg.pivot_rakes().dropna(subset=["departed"])
        vals = w[RAKE_EVENT_ORDER].to_numpy(dtype=float)
        ok_order &= bool((np.diff(vals, axis=1) >= -1e-9).all())
        ev = lg.to_frame()
        occ = []
        for _, r in w.iterrows():
            occ.append((r.placement_start, +1)); occ.append((r.removed, -1))
        trial = ev[ev.name.isin(["trial_placement_start", "trial_removed"])]
        for _, e in trial.iterrows():
            occ.append((e.t, +1 if e.name == "trial_placement_start" else -1))
        level, peak = 0, 0
        for _, d in sorted(occ, key=lambda x: (x[0], x[1])):
            level += d; peak = max(peak, level)
        ok_lines &= peak <= c0.resources.loading_lines
    c.assert_("event chain stays in order with damage on", ok_order, "both policies")
    c.assert_("loading line never over capacity (incl. rejected visits)", ok_lines, "both policies")

    # 8. loading damage is repaired after loading and before release
    ld = _dmg(c0, p_loading_damage_per_wagon=0.02)
    log_l, rl, tl = _run(ld)
    ev = log_l.to_frame()
    w = log_l.pivot_rakes().set_index("rake")
    s = ev[ev.name == "loading_damage_repair_start"].set_index("entity_id").t
    e = ev[ev.name == "loading_damage_repair_end"].set_index("entity_id").t
    ok = len(s) > 0 and all(w.loc[i, "loading_end"] <= s[i] + 1e-9 and e[i] <= w.loc[i, "released"] + 1e-9
                            for i in s.index)
    c.assert_("loading damage repaired between loading end and release", ok, f"{len(s)} rakes")

    # 9. more damage, longer detention (monotone)
    means = []
    for p in (0.0, 0.02, 0.05):
        _, r, _ = _run(_dmg(c0, p_defect_per_wagon=p, unfit_policy="detach"))
        means.append(r.detention_hr.mean())
    c.assert_("detention rises with the damage rate", means[0] <= means[1] <= means[2],
              " -> ".join(f"{m:.2f}" for m in means))

    # 10. every damage event names a responsible party
    allev = pd.concat([log_d.to_frame(), log_r.to_frame(), log_l.to_frame()])
    dev = allev[allev.name.str.contains("repair|detach|rejected|trial_|replacement")]
    c.assert_("every damage event has an owner", dev.owner.notna().all() and (dev.owner != "").all(),
              f"{len(dev)} events")
    return c.report()


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_checks() else 1)
