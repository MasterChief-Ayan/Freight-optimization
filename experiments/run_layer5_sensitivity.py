"""
run_layer5_sensitivity.py  -  how does EACH parameter and condition move the outcome?

    python experiments/run_layer5_sensitivity.py            full run (~10 min, 2 cores)
    python experiments/run_layer5_sensitivity.py quick      fewer reps / trajectories

Supervisor's mid-term ask: "analyse how each identified parameter or administrative
step INDIVIDUALLY affects the outcome - find a lower bound, upper bound or range for
each, on an absolute scale."

Design (all on the calibrated Layer-1 baseline: 50 rakes, 30 replications, FCFS,
full administrative chain, road side off - the configuration whose detention is
checked against TERI's 14-17 h band):

S1  ONE-AT-A-TIME (OAT) RANGES. Every continuous parameter is swept over five
    levels between a stated LOW and HIGH while everything else stays at base.
    Ranges:  CITED parameters  -> the range the rule itself allows
                                  (e.g. base free time 3-7 h, penal x1-x6);
             ASSUMED parameters -> a uniform +/-50 % stress band around base
                                  (same relative width for all, so swings are
                                  comparable), unless a physical or published
                                  range is tighter or wider (stated per row).
    For each parameter: output at LOW and HIGH, the min and max over the sweep
    (= the parameter's absolute lower/upper bound on that output), the SWING
    (max - min, the tornado length), the paired 95 % CI of each difference from
    base, and a range elasticity  ((Y_hi - Y_lo)/Y_0) / ((x_hi - x_lo)/x_0).

S2  CONDITIONS. Discrete switches (an office going 24/7, a step removed, number
    of lines/locos/crews, crew shifts, dispatch rule, graded vs flat demurrage,
    tarpaulin hour, siding extra free time, office working days) - each against
    the base, paired.

S3  MORRIS ELEMENTARY EFFECTS (Morris 1991; Campolongo et al. 2007 mu*). OAT
    cannot see interactions. Morris moves every factor along random trajectories
    and reports mu* (overall importance) and sigma (non-linearity / interaction).
    A factor with sigma comparable to mu* must not be read from its OAT bar alone.

S4  ENVELOPE. Every continuous time-affecting factor set to the end that OAT
    found favourable (then unfavourable) simultaneously -> absolute best and worst
    detention the model admits within the stated ranges, interactions included.

Common random numbers throughout: the same 30 seeds for every point, so every
difference is paired and the CI is on the difference, not on two noisy means.
"""
import _bootstrap  # noqa: F401  repo root on sys.path; outputs go to results/

import math
import os
import random
import statistics as st
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from rtsim.config import default_config
from rtsim.distributions import Dist
from rtsim.terminal import simulate
from rtsim.accounting import rake_table, kpis
from rtsim.admin import (default_steps, Calendar, CAL_24_7, CAL_RAILWAY_OFFICE,
                         CAL_TERMINAL_OFFICE, CAL_TERMINAL_SHIFT)
from rtsim import policies

QUICK = len(sys.argv) > 1 and sys.argv[1] == "quick"
N_REPS = 10 if QUICK else 30
MORRIS_R = 6 if QUICK else 20          # trajectories
MORRIS_REPS = 6 if QUICK else 12
WORKERS = max(1, min(4, os.cpu_count() or 1))
STEP_KEYS = ["M1", "M2", "M3", "M4", "M5", "M6", "M7"]

KPI = {   # column -> (label, unit)
    "detention": ("mean detention (placement->release)", "h"),
    "wait": ("mean wait before placement", "h"),
    "dwell": ("mean dwell (arrival->removal)", "h"),
    "cycle": ("mean cycle (arrival->departure)", "h"),
    "demurrage_pr": ("demurrage per rake", "Rs"),
    "cost_pr": ("controllable cost per rake", "Rs"),
    "breach": ("share of rakes over free time", "-"),
}


# ======================================================================
# evaluation (one point = one configuration, all replications)
# ======================================================================
def _evaluate(point):
    cfg, steps, pol = point
    rows = []
    for rep in range(cfg.run.n_reps):
        seed = cfg.run.base_seed + rep
        log, _, term = simulate(cfg, policies.build(pol, cfg), seed,
                                admin_steps=steps)
        rt = rake_table(log, cfg)
        rt = rt[rt.rake > cfg.run.warmup_rakes]
        k = kpis(rt, term, cfg)
        n = max(1, k["rakes_completed"])
        rows.append({
            "detention": k["mean_detention_hr"], "wait": k["mean_wait_hr"],
            "dwell": k["mean_dwell_hr"], "cycle": k["mean_cycle_hr"],
            "demurrage_pr": k["total_demurrage"] / n,
            "cost_pr": k["total_controllable_cost"] / n,
            "breach": k["breach_rate"],
        })
    return pd.DataFrame(rows)


def run_points(points):
    if WORKERS == 1:
        return [_evaluate(p) for p in points]
    with ProcessPoolExecutor(WORKERS) as ex:
        return list(ex.map(_evaluate, points, chunksize=1))


def paired(base_df, df, col):
    d = (df[col] - base_df[col]).tolist()
    m = st.mean(d)
    h = 1.96 * st.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else 0.0
    return m, h, (m - h > 0) or (m + h < 0)


# ======================================================================
# parameter catalogue
# ======================================================================
def _svc(step, mean=None, sd=None):
    s = step.service
    return replace(step, service=Dist(s.kind, mean=s.mean if mean is None else mean,
                                      sd=s.sd if sd is None else sd))


def _with_steps(steps, keys, fn):
    out = dict(steps)
    for k in keys:
        out[k] = fn(out[k])
    return out


def _cal_hours(cal: Calendar, hours: float) -> Calendar:
    """Same office, same opening time and days, different length of day.

    Rounded to the half hour: an office closing at an arbitrary float time
    (e.g. 13.333 h) lets AdminChain._work take sub-microsecond chunks at the
    boundary and trip its convergence guard. Real offices close on the half
    hour, so this changes nothing of substance (only Morris draws non-round
    values; every OAT level is already a whole or half hour)."""
    hours = round(hours * 2) / 2
    if hours >= 24 - 1e-9:
        return CAL_24_7
    return replace(cal, close_hr=min(24.0, cal.open_hr + hours), always_on=False)


def _lin(lo, base, hi):
    """Five levels: lo, mid(lo,base), base, mid(base,hi), hi."""
    return [lo, (lo + base) / 2, base, (base + hi) / 2, hi]


def catalogue(cfg0, steps0):
    """Each entry: id, group, label, unit, status, base, levels, apply(cfg, steps, x),
    note on why that range."""
    P = []

    def add(pid, group, label, unit, status, base, levels, fn, why):
        P.append(dict(id=pid, group=group, label=label, unit=unit, status=status,
                      base=base, levels=levels, fn=fn, why=why))

    rk, sh, ch = cfg0.rake, cfg0.shunting, cfg0.charges

    # ---------------- operational (physical) ---------------------------
    add("arrival_gap", "operational", "mean rake inter-arrival gap", "h", "ASSUMED",
        30.0, [20.0, 25.0, 30.0, 38.0, 48.0],
        lambda c, s, x: (replace(c, rake=replace(c.rake, arrival_gap=Dist("exp", mean=x))), s),
        "36 to 15 rakes/month; 48 h = TERI's typical one-line terminal (15/month)")
    add("load_rate", "operational", "mean loading rate", "t/h", "ASSUMED",
        900.0, _lin(450.0, 900.0, 1350.0),
        lambda c, s, x: (replace(c, rake=replace(c.rake, load_rate_tph=Dist(
            "logn", mean=x, sd=c.rake.load_rate_tph.sd))), s), "+/-50 %")
    add("load_rate_sd", "operational", "loading-rate variability (sd)", "t/h", "ASSUMED",
        250.0, _lin(125.0, 250.0, 375.0),
        lambda c, s, x: (replace(c, rake=replace(c.rake, load_rate_tph=Dist(
            "logn", mean=c.rake.load_rate_tph.mean, sd=x))), s), "+/-50 %")
    add("placement", "operational", "mean placement (shunting in) time", "h", "ASSUMED",
        1.0, _lin(0.5, 1.0, 1.5),
        lambda c, s, x: (replace(c, shunting=replace(c.shunting, placement=Dist(
            "logn", mean=x, sd=0.3 * x))), s), "+/-50 %, cv kept at 0.3")
    add("removal", "operational", "mean removal (shunting out) time", "h", "ASSUMED",
        1.0, _lin(0.5, 1.0, 1.5),
        lambda c, s, x: (replace(c, shunting=replace(c.shunting, removal=Dist(
            "logn", mean=x, sd=0.3 * x))), s), "+/-50 %, cv kept at 0.3")
    add("transit", "operational", "mean transit to serving station", "h", "ASSUMED",
        12.0, _lin(6.0, 12.0, 18.0),
        lambda c, s, x: (replace(c, rake=replace(c.rake, transit=Dist(
            "logn", mean=x, sd=x / 3))), s), "+/-50 %")
    add("wagons", "operational", "wagons per rake", "wagons", "CITED (BOXN 58)",
        58.0, [42.0, 46.0, 50.0, 58.0, 59.0],
        lambda c, s, x: (replace(c, rake=replace(c.rake, wagons=int(round(x)))), s),
        "short rakes (data IQR 10-58) up to 59-wagon BOXN/BOXNHL rakes")
    add("t_per_wagon", "operational", "payload per wagon", "t", "CITED (BOXN 58.08)",
        58.08, [52.0, 55.0, 58.08, 64.5, 71.0],
        lambda c, s, x: (replace(c, rake=replace(c.rake, tonnes_per_wagon=x)), s),
        "under-loaded BOXN to BOXNHL 71 t (wagon type is commodity-specific)")
    add("late_prob", "operational", "probability a rake arrives late", "-", "ASSUMED",
        0.0, [0.0, 0.1, 0.2, 0.3, 0.4],
        lambda c, s, x: (replace(c, rake=replace(c.rake, late_prob=x)), s),
        "one-sided: base model has no lateness (late delay logn 6+/-4 h)")

    # ---------------- administrative (per step) ------------------------
    for k in STEP_KEYS:
        stp = steps0[k]
        m0, sd0, q0 = stp.service.mean, stp.service.sd, stp.rework_prob
        add(f"{k}_mean", "administrative", f"{k} mean work time", "h", "ASSUMED",
            m0, _lin(0.5 * m0, m0, 1.5 * m0),
            (lambda kk: lambda c, s, x: (c, _with_steps(s, [kk], lambda t: _svc(
                t, mean=x, sd=t.service.sd * x / t.service.mean))))(k),
            "+/-50 %, coefficient of variation kept")
        add(f"{k}_sd", "administrative", f"{k} work-time variability (sd)", "h", "ASSUMED",
            sd0, _lin(0.5 * sd0, sd0, 1.5 * sd0),
            (lambda kk: lambda c, s, x: (c, _with_steps(s, [kk], lambda t: _svc(t, sd=x))))(k),
            "+/-50 %, mean kept")
        add(f"{k}_rework", "administrative", f"{k} rejection probability", "-", "ASSUMED",
            q0, _lin(0.0, q0, min(0.5, 2 * q0)),
            (lambda kk: lambda c, s, x: (c, _with_steps(s, [kk], lambda t: replace(
                t, rework_prob=x))))(k),
            "0 (never rejected) to 2x base")

    def hours_param(pid, label, cal, keys, levels, why):
        base_h = cal.close_hr - cal.open_hr
        add(pid, "administrative", label, "h/day", "CITED" if cal is CAL_TERMINAL_SHIFT
            else "ASSUMED", base_h, levels,
            lambda c, s, x: (c, _with_steps(s, keys, lambda t: replace(
                t, calendar=_cal_hours(cal, x)))), why)

    hours_param("hours_terminal_shift", "terminal working hours (M4, M5, M6)",
                CAL_TERMINAL_SHIFT, ["M4", "M5", "M6"], [8.0, 12.0, 16.0, 20.0, 24.0],
                "06-14 ... 06-22 [IR-COMP 4.1] ... round the clock (DRM may allow)")
    hours_param("hours_railway_office", "railway office hours (M1, M2, M7)",
                CAL_RAILWAY_OFFICE, ["M1", "M2", "M7"], [5.0, 6.0, 7.0, 10.0, 14.0],
                "10-15 ... 10-17 base ... 10-24")
    hours_param("hours_terminal_office", "terminal office hours (M3)",
                CAL_TERMINAL_OFFICE, ["M3"], [6.0, 7.5, 9.0, 12.0, 15.0],
                "09-15 ... 09-18 base ... 09-24")

    # ---------------- commercial (charges; move money, not time) -------
    add("base_free_time", "commercial", "base free time", "h", "CITED",
        5.0, [3.0, 4.0, 5.0, 6.0, 7.0],
        lambda c, s, x: (replace(c, charges=replace(c.charges, base_free_time_hr=x)), s),
        "3:00 coal single-line cut [IR-COMP 2.2(c)] ... 7:00 (mech. unloading level)")
    add("penal", "commercial", "penal demurrage multiplier", "x", "CITED",
        1.0, [1.0, 2.0, 3.0, 4.5, 6.0],
        lambda c, s, x: (replace(c, charges=replace(c.charges, penal_multiplier=x)), s),
        "x1 ... x6 [IR-COMP 3.4.1]")
    add("demurrage_rate", "commercial", "demurrage base rate", "Rs/wagon/h", "CITED",
        150.0, _lin(75.0, 150.0, 225.0),
        lambda c, s, x: (replace(c, charges=replace(c.charges, demurrage_per_wagon_hr=x)), s),
        "+/-50 % around the cited Rs 150 (tariff revision what-if)")
    add("engine_hour_cost", "commercial", "engine-hour cost (siding charge)", "Rs/h", "ASSUMED",
        6000.0, _lin(3000.0, 6000.0, 9000.0),
        lambda c, s, x: (replace(c, charges=replace(c.charges, engine_hour_cost=x)), s), "+/-50 %")
    add("shunting_charge", "commercial", "shunting charge", "Rs/rake", "ASSUMED",
        25000.0, _lin(12500.0, 25000.0, 37500.0),
        lambda c, s, x: (replace(c, charges=replace(c.charges, shunting_charge=x)), s), "+/-50 %")
    add("idle_cost", "commercial", "opportunity cost of an idle rake", "Rs/h", "ASSUMED",
        3000.0, _lin(1500.0, 3000.0, 4500.0),
        lambda c, s, x: (replace(c, charges=replace(c.charges, idle_cost_per_hr=x)), s), "+/-50 %")
    return P


def conditions(cfg0, steps0):
    C = []

    def add(cid, group, label, fn):
        C.append(dict(id=cid, group=group, label=label, fn=fn))

    for k in STEP_KEYS:
        add(f"{k}_24x7", "administrative", f"{k} office works 24/7",
            (lambda kk: lambda c, s: (c, _with_steps(s, [kk], lambda t: replace(
                t, calendar=CAL_24_7)), "FCFS"))(k))
        add(f"{k}_removed", "administrative", f"{k} step removed",
            (lambda kk: lambda c, s: (c, _with_steps(s, [kk], lambda t: t.disabled()),
                                      "FCFS"))(k))
    add("railway_7days", "administrative", "railway office open 7 days (M1, M2, M7)",
        lambda c, s: (c, _with_steps(s, ["M1", "M2", "M7"], lambda t: replace(
            t, calendar=replace(t.calendar, weekdays=(0, 1, 2, 3, 4, 5, 6)))), "FCFS"))
    for n in (2, 3):
        add(f"lines_{n}", "operational", f"{n} loading lines (crew unchanged)",
            lambda c, s, n=n: (replace(c, resources=replace(c.resources, loading_lines=n)),
                               s, "FCFS"))
    add("lines2_crews2", "operational", "2 lines + 2 crews",
        lambda c, s: (replace(c, resources=replace(c.resources, loading_lines=2, crews=2)),
                      s, "FCFS"))
    add("locos_2", "operational", "2 shunting locos",
        lambda c, s: (replace(c, resources=replace(c.resources, shunting_locos=2)), s, "FCFS"))
    add("crews_2", "operational", "2 loading crews (1 line)",
        lambda c, s: (replace(c, resources=replace(c.resources, crews=2)), s, "FCFS"))
    add("crew_shift", "operational", "loading crew works 06-22 only",
        lambda c, s: (replace(c, resources=replace(c.resources, crew_shifts_enabled=True)),
                      s, "FCFS"))
    for p in ("SPT", "COST", "CNP"):
        add(f"policy_{p}", "coordination", f"dispatch rule {p}",
            lambda c, s, p=p: (c, s, p))
    add("flat_demurrage", "commercial", "flat (ungraded) demurrage",
        lambda c, s: (replace(c, charges=replace(c.charges, graded_demurrage=False)), s, "FCFS"))
    add("no_tarpaulin_hr", "commercial", "no tarpaulin hour (non-coal open cargo)",
        lambda c, s: (replace(c, charges=replace(c.charges, tarpaulin_applies=False)), s, "FCFS"))
    add("no_siding_2h", "commercial", "no +2 h siding free time (through-distance)",
        lambda c, s: (replace(c, charges=replace(c.charges, siding_additional_free_time_hr=0.0)),
                      s, "FCFS"))
    return C


# ======================================================================
# S1 - OAT
# ======================================================================
def run_oat(cfg0, steps0, base_df):
    P = catalogue(cfg0, steps0)
    pts, keys = [], []
    for p in P:
        for x in p["levels"]:
            c, s = p["fn"](cfg0, steps0, x)
            pts.append((c, s, "FCFS")); keys.append((p["id"], x))
    res = run_points(pts)
    long_rows = []
    for (pid, x), df in zip(keys, res):
        r = {"param": pid, "x": x}
        for col in KPI:
            m, h, sig = paired(base_df, df, col)
            r[col] = df[col].mean(); r[f"d_{col}"] = m; r[f"d_{col}_ci"] = h
            r[f"sig_{col}"] = sig
        long_rows.append(r)
    lv = pd.DataFrame(long_rows)

    bounds = []
    for p in P:
        sub = lv[lv.param == p["id"]].sort_values("x")
        lo, hi = sub.iloc[0], sub.iloc[-1]
        row = {"group": p["group"], "param": p["id"], "label": p["label"],
               "unit": p["unit"], "status": p["status"], "base": p["base"],
               "low": lo.x, "high": hi.x, "range_basis": p["why"]}
        for col in ("detention", "wait", "cycle", "demurrage_pr", "cost_pr", "breach"):
            y0 = base_df[col].mean()
            row[f"{col}_at_low"] = lo[col]
            row[f"{col}_at_high"] = hi[col]
            row[f"{col}_min"] = sub[col].min()
            row[f"{col}_max"] = sub[col].max()
            row[f"{col}_swing"] = sub[col].max() - sub[col].min()
            row[f"{col}_sig"] = bool(sub[f"sig_{col}"].any())
            dx = (hi.x - lo.x) / p["base"] if p["base"] else float("nan")
            row[f"{col}_elasticity"] = ((hi[col] - lo[col]) / y0 / dx
                                        if (dx and y0 and not math.isnan(dx)) else float("nan"))
        bounds.append(row)
    return P, lv, pd.DataFrame(bounds)


# ======================================================================
# S2 - conditions
# ======================================================================
def run_conditions(cfg0, steps0, base_df):
    C = conditions(cfg0, steps0)
    res = run_points([c["fn"](cfg0, steps0) for c in C])
    rows = []
    for c, df in zip(C, res):
        r = {"group": c["group"], "condition": c["id"], "label": c["label"]}
        for col in KPI:
            m, h, sig = paired(base_df, df, col)
            r[col] = df[col].mean(); r[f"d_{col}"] = m; r[f"d_{col}_ci"] = h
            r[f"sig_{col}"] = sig
        rows.append(r)
    return pd.DataFrame(rows).sort_values("d_detention")


# ======================================================================
# S3 - Morris elementary effects
# ======================================================================
def run_morris(cfg0, steps0, P, out_col="detention"):
    # only factors that can move TIME (commercial factors only reprice it)
    F = [p for p in P if p["group"] != "commercial"]
    k, levels = len(F), 4
    delta = levels / (2 * (levels - 1))            # 2/3 on the unit cube
    grid = [i / (levels - 1) for i in range(levels)]
    rng = random.Random(20261022)
    cfg_m = replace(cfg0, run=replace(cfg0.run, n_reps=MORRIS_REPS))

    def to_x(p, u):
        lo, hi = min(p["levels"]), max(p["levels"])
        return lo + u * (hi - lo)

    def build(u):
        c, s = cfg_m, steps0
        for p, ui in zip(F, u):
            c, s = p["fn"](c, s, to_x(p, ui))
        return (c, s, "FCFS")

    traj_pts, traj_meta = [], []
    for _ in range(MORRIS_R):
        u = [rng.choice([g for g in grid if g + delta <= 1 + 1e-9]) for _ in range(k)]
        order = list(range(k)); rng.shuffle(order)
        pts = [list(u)]
        for i in order:
            u = list(u); u[i] = u[i] + delta
            pts.append(u)
        traj_pts.extend(build(v) for v in pts)
        traj_meta.append(order)
    res = run_points(traj_pts)
    ys = [df[out_col].mean() for df in res]

    ee = {p["id"]: [] for p in F}
    idx = 0
    for order in traj_meta:
        y = ys[idx: idx + k + 1]
        for j, i in enumerate(order):
            ee[F[i]["id"]].append((y[j + 1] - y[j]) / delta)
        idx += k + 1
    rows = []
    for p in F:
        e = ee[p["id"]]
        rows.append({"group": p["group"], "param": p["id"], "label": p["label"],
                     "mu": st.mean(e), "mu_star": st.mean(abs(v) for v in e),
                     "sigma": st.stdev(e) if len(e) > 1 else 0.0, "n_ee": len(e)})
    out = pd.DataFrame(rows).sort_values("mu_star", ascending=False)
    out["sigma_over_mu_star"] = out.sigma / out.mu_star.replace(0, np.nan)
    return out


# ======================================================================
# S4 - envelope
# ======================================================================
def run_envelope(cfg0, steps0, P, bounds, base_df):
    F = [p for p in P if p["group"] != "commercial"]
    b = bounds.set_index("param")
    best, worst = (cfg0, steps0), (cfg0, steps0)
    for p in F:
        r = b.loc[p["id"]]
        x_best = r.low if r.detention_at_low <= r.detention_at_high else r.high
        x_worst = r.high if x_best == r.low else r.low
        best = p["fn"](best[0], best[1], x_best)
        worst = p["fn"](worst[0], worst[1], x_worst)
    # demand (arrival gap) is exogenous to the terminal; a third case holds it at
    # base so the worst case is not just "the line saturates"
    worst_t = (cfg0, steps0)
    for p in F:
        if p["id"] == "arrival_gap":
            continue
        r = b.loc[p["id"]]
        x_w = r.high if r.detention_at_high >= r.detention_at_low else r.low
        worst_t = p["fn"](worst_t[0], worst_t[1], x_w)
    res = run_points([(best[0], best[1], "FCFS"), (worst[0], worst[1], "FCFS"),
                      (worst_t[0], worst_t[1], "FCFS")])
    rows = []
    for lab, df in (("base", base_df), ("all favourable ends", res[0]),
                    ("all unfavourable ends", res[1]),
                    ("unfavourable ends, demand at base", res[2])):
        rows.append({"case": lab, **{c: df[c].mean() for c in KPI},
                     **{f"{c}_ci": 1.96 * df[c].std() / math.sqrt(len(df)) for c in KPI}})
    return pd.DataFrame(rows)


# ======================================================================
def main():
    cfg0 = default_config()
    cfg0 = replace(cfg0, run=replace(cfg0.run, n_reps=N_REPS))
    steps0 = default_steps()
    base_df = _evaluate((cfg0, steps0, "FCFS"))
    print(f"\n>>> BASE  ({N_REPS} reps x {cfg0.run.n_rakes} rakes, FCFS, full admin chain)")
    for c, (lab, u) in KPI.items():
        print(f"  {lab:<38} {base_df[c].mean():>12,.2f} {u}")

    print("\n>>> S1  ONE-AT-A-TIME RANGES")
    P, lv, bounds = run_oat(cfg0, steps0, base_df)
    show = bounds.sort_values("detention_swing", ascending=False)
    print(f"  {'parameter':<42} {'range':>17} | {'detention h  lo..hi':>21} | "
          f"{'swing':>6} | {'Rs demurrage/rake lo..hi':>26}")
    print("  " + "-" * 124)
    for _, r in show.iterrows():
        rng_s = f"{r.low:g}..{r.high:g}"
        print(f"  {r.label[:42]:<42} {rng_s:>17} | {r.detention_at_low:8.2f} .. "
              f"{r.detention_at_high:8.2f} | {r.detention_swing:6.2f}{'*' if r.detention_sig else ' '}| "
              f"{r.demurrage_pr_at_low:11,.0f} .. {r.demurrage_pr_at_high:11,.0f}")
    print("  (* = at least one level differs from base, paired 95 % CI)")

    print("\n>>> S2  CONDITIONS")
    cond = run_conditions(cfg0, steps0, base_df)
    for _, r in cond.iterrows():
        print(f"  {r.label[:46]:<46} detention {r.d_detention:+7.2f} +/-{r.d_detention_ci:4.2f}"
              f"{'*' if r.sig_detention else ' '}  wait {r.d_wait:+8.2f}  "
              f"demurrage/rake {r.d_demurrage_pr:+11,.0f}")

    print("\n>>> S3  MORRIS SCREENING  (detention; mu* = importance, sigma = interaction)")
    mor = run_morris(cfg0, steps0, P)
    print(mor.head(15).to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    print("\n>>> S4  ENVELOPE  (all time-affecting factors at once)")
    env = run_envelope(cfg0, steps0, P, bounds, base_df)
    print(env[["case", "detention", "wait", "cycle", "demurrage_pr", "breach"]].to_string(
        index=False, float_format=lambda x: f"{x:,.2f}"))

    # ------------------------------------------------------------ outputs
    lv.round(4).to_csv("layer5_S1_oat_levels.csv", index=False)
    bounds.round(4).to_csv("layer5_S1_bounds.csv", index=False)
    cond.round(4).to_csv("layer5_S2_conditions.csv", index=False)
    mor.round(4).to_csv("layer5_S3_morris.csv", index=False)
    env.round(4).to_csv("layer5_S4_envelope.csv", index=False)
    charts(base_df, bounds, cond, mor, env)
    print("\nSaved: layer5_results.png, layer5_tornado_cost.png and five CSVs")


def charts(base_df, bounds, cond, mor, env):
    gcol = {"operational": "#5b7c99", "administrative": "#c1440e",
            "commercial": "#7a9b76", "coordination": "#8c6bb1"}
    y0 = base_df.detention.mean()

    fig, ax = plt.subplots(2, 2, figsize=(16, 13))
    a = ax[0, 0]
    t = bounds.sort_values("detention_swing").tail(20)
    for i, (_, r) in enumerate(t.iterrows()):
        lo, hi = r.detention_at_low, r.detention_at_high
        a.barh(i, lo - y0, left=y0, color=gcol[r.group], alpha=.45)
        a.barh(i, hi - y0, left=y0, color=gcol[r.group])
    a.axvline(y0, c="k", lw=1)
    a.set_yticks(range(len(t)))
    a.set_yticklabels([f"{r.label} [{r.low:g}..{r.high:g}]" for _, r in t.iterrows()],
                      fontsize=8)
    a.set_xlabel("mean detention (h)  -  light = LOW end, dark = HIGH end")
    a.set_title(f"S1  Tornado: each parameter alone (base {y0:.2f} h)")

    a = ax[0, 1]
    c = cond.sort_values("d_detention").copy()
    a.barh(c.label, c.d_detention, xerr=c.d_detention_ci, capsize=2,
           color=[gcol[g] for g in c.group])
    a.axvline(0, c="k", lw=1)
    a.tick_params(axis="y", labelsize=7)
    a.set_xlabel("change in mean detention vs base (h), paired 95 % CI")
    a.set_title("S2  Conditions switched one at a time")

    a = ax[1, 0]
    for _, r in mor.iterrows():
        a.scatter(r.mu_star, r.sigma, color=gcol[r.group], s=40)
        if r.mu_star >= mor.mu_star.quantile(0.7):
            a.annotate(r.param, (r.mu_star, r.sigma), fontsize=7,
                       xytext=(3, 3), textcoords="offset points")
    m = max(mor.mu_star.max(), mor.sigma.max()) * 1.05
    a.plot([0, m], [0, m], ls="--", c="grey", lw=.8)
    a.set_xlabel("mu*  (h of detention per full-range move)")
    a.set_ylabel("sigma  (non-linearity / interaction)")
    a.set_title("S3  Morris screening (points above the dashed line interact)")

    a = ax[1, 1]
    a.bar([c.replace(", ", ",\n").replace(" ends", "\nends") for c in env.case], env.detention, yerr=env.detention_ci, capsize=5,
          color=["#8c8c8c", "#7a9b76", "#c1440e", "#e08a5f"])
    a.axhspan(14, 17, color="#c8e6c9", alpha=.5, label="TERI 14-17 h")
    for i, v in enumerate(env.detention):
        a.text(i, v, f"{v:.1f} h", ha="center", va="bottom")
    a.set_ylabel("mean detention (h)")
    a.set_title("S4  Envelope: absolute best / worst within the stated ranges")
    a.legend()

    for r in ax:
        for b in r:
            b.grid(alpha=.25); b.set_axisbelow(True)
    handles = [plt.Rectangle((0, 0), 1, 1, color=v) for v in gcol.values()]
    fig.legend(handles, list(gcol), loc="lower center", ncol=4)
    fig.suptitle("Layer 5 - sensitivity of detention to every parameter and condition "
                 f"| {N_REPS} paired replications | ASSUMED ranges +/-50 %", y=0.995)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig("layer5_results.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # cost tornado
    fig, a = plt.subplots(figsize=(11, 8))
    c0 = base_df.cost_pr.mean()
    t = bounds.sort_values("cost_pr_swing").tail(20)
    for i, (_, r) in enumerate(t.iterrows()):
        a.barh(i, (r.cost_pr_at_low - c0) / 1e3, left=c0 / 1e3, color=gcol[r.group], alpha=.45)
        a.barh(i, (r.cost_pr_at_high - c0) / 1e3, left=c0 / 1e3, color=gcol[r.group])
    a.axvline(c0 / 1e3, c="k", lw=1)
    a.set_yticks(range(len(t)))
    a.set_yticklabels([f"{r.label} [{r.low:g}..{r.high:g}]" for _, r in t.iterrows()],
                      fontsize=8)
    a.set_xlabel("controllable cost per rake (Rs '000)  -  light = LOW end, dark = HIGH end")
    a.set_title(f"Tornado on controllable cost per rake (base Rs {c0:,.0f})")
    a.grid(alpha=.25)
    fig.tight_layout()
    fig.savefig("layer5_tornado_cost.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
