"""
run_layer9_capacity.py  -  HOW MANY MORE RAKES can the siding take, package by package?

    python experiments/run_layer9_capacity.py          (~5 min, 2 cores)
    python experiments/run_layer9_capacity.py quick

Supervisor (final meeting, 11-Nov-2026): "do not stop at the cost - show the capacity: can the
siding take more rakes?"  This layer answers it with the Layer 8 coal (open BOXN) siding and its
packages, by raising the traffic offered to the siding and watching the queue.

Configurations (levers exactly as in Layer 8):
  TODAY, A = H+D (paperwork 24/7 + digital release), B = A+P (precise loading), C = B+L (faster
  loading), and two capital options for comparison: TODAY + 2nd line + 2nd crew, A + 2nd line +
  2nd crew. The single shunting loco is kept in every case.
Traffic: offered rakes a year R = 250 ... 1,600 (step 50) plus today's 292; Poisson bookings with
  mean gap 8,760 / R h.
Runs: 200 rakes per replication (first 20 discarded as warm-up, so long queues can build up),
  30 replications, same random numbers in every cell (common random numbers).

Capacity measures (each stated, so every number can be traced):
  ceiling              Lambda = K x 8,760 / mean line hold (placement start -> removed); the
                       rakes a year at which K lines are busy 100 % of the time
  same-service capacity  the largest offered R whose mean wait before placement is no longer than
                       TODAY's wait at 292 rakes a year (linear interpolation between grid points);
                       no new threshold is assumed - today's service level is the yardstick
  utilisation          line = R x hold / (K x 8,760); crew = R x loading time / (crews x 8,760);
                       loco = R x (placement + removal shunting) / 8,760
  throughput           rakes actually removed per year in the run (after warm-up)
Outputs (results/):
  layer9_K1_traffic_sweep.csv    every configuration x traffic level
  layer9_K2_capacity.csv         ceiling, same-service capacity, gain over today, next bottleneck
  layer9_K3_queue_check.csv      simulated queue wait vs the Pollaczek-Khinchine M/G/1 formula
  layer9_results.png
"""
import _bootstrap  # noqa: F401

import sys
from dataclasses import replace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from rtsim.distributions import Dist
from rtsim.admin import remove_calendar
from rtsim.terminal import simulate
from rtsim.accounting import rake_table
from rtsim import policies
import run_layer5_sensitivity as L5
import run_layer6_commodities as L6
import run_layer8_breakdown as L8

QUICK = len(sys.argv) > 1 and sys.argv[1] == "quick"
N_REPS = 8 if QUICK else 30
N_RAKES, WARMUP = 200, 20
TODAY_RAKES = 292
LEVELS = sorted(set([TODAY_RAKES] + list(range(250, 1601, 50 if not QUICK else 150))))
CONFIGS = {  # name: (levers, lines, crews)
    "TODAY": ("", 1, 1),
    "A paperwork 24/7 + digital release": ("HD", 1, 1),
    "B = A + precise loading": ("HDP", 1, 1),
    "C = B + faster loading": ("HDPL", 1, 1),
    "TODAY + 2nd line + 2nd crew": ("", 2, 2),
    "A + 2nd line + 2nd crew": ("HD", 2, 2),
}


def build(c0, s0, levers, lines, crews, rakes_yr):
    c, s = L8.apply(c0, s0, levers)
    c = replace(c,
                rake=replace(c.rake, arrival_gap=Dist("exp", mean=8760.0 / rakes_yr)),
                resources=replace(c.resources, loading_lines=lines, crews=crews),
                run=replace(c.run, n_rakes=N_RAKES, warmup_rakes=WARMUP, n_reps=N_REPS))
    return c, s


def evaluate(point):
    c, s = point
    rows = []
    for rep in range(c.run.n_reps):
        log, _, _ = simulate(c, policies.build("FCFS", c), c.run.base_seed + rep, admin_steps=s)
        rt = rake_table(log, c)
        rt = rt[rt.rake > c.run.warmup_rakes].sort_values("removed")
        span = rt.removed.iloc[-1] - rt.removed.iloc[0]
        rows.append(dict(
            wait=rt.wait_hr.mean(), detention=rt.detention_hr.mean(), cycle=rt.cycle_hr.mean(),
            demurrage_pr=rt.demurrage.mean(), breach=(rt.excess_hr > 0).mean(),
            hold=(rt.removed - rt.placement_start).mean(),
            hold_sq=((rt.removed - rt.placement_start) ** 2).mean(),
            queue_wait=(rt.placement_start - rt.queue_start).mean(), loading=rt.loading_hr.mean(),
            shunting=(rt.placement_hr + rt.removal_hr).mean(),
            throughput=(len(rt) - 1) / span * 8760.0 if span > 0 else np.nan))
    return pd.DataFrame(rows)


def run_all(pts):
    from concurrent.futures import ProcessPoolExecutor
    if L5.WORKERS == 1:
        return [evaluate(p) for p in pts]
    with ProcessPoolExecutor(L5.WORKERS) as ex:
        return list(ex.map(evaluate, pts, chunksize=1))


def same_service_capacity(levels, waits, target):
    """Largest offered R with mean wait <= target (linear interpolation on the first crossing)."""
    lv, w = np.asarray(levels, float), np.asarray(waits, float)
    if w[0] > target:
        return np.nan
    for i in range(1, len(lv)):
        if w[i] > target:
            return lv[i - 1] + (target - w[i - 1]) * (lv[i] - lv[i - 1]) / (w[i] - w[i - 1])
    return float(lv[-1])          # never crosses inside the grid: at least the top level


def main():
    prof = [p for p in L6.refresh_from_field([dict(p) for p in L6.PROFILES])
            if p["name"] == "COAL (open BOXN)"][0]
    c0, s0 = L6.build(prof, n_reps=N_REPS)

    keys, pts = [], []
    for name, (lev, k, cr) in CONFIGS.items():
        for R in LEVELS:
            keys.append((name, R)); pts.append(build(c0, s0, lev, k, cr, R))
    for name in ("TODAY", "A paperwork 24/7 + digital release"):     # K3: every office open
        lev, k, cr = CONFIGS[name]
        for R in [x for x in LEVELS if x <= 700]:
            c, s = build(c0, s0, lev, k, cr, R)
            keys.append(("check:" + name, R)); pts.append((c, remove_calendar(L8.KS, s)))
    out = dict(zip(keys, run_all(pts)))
    res = {k: v for k, v in out.items() if not k[0].startswith("check:")}
    chk = {k: v for k, v in out.items() if k[0].startswith("check:")}

    # ------------------------------------------------ K1 sweep
    k1 = []
    for (name, R), df in res.items():
        lev, k, cr = CONFIGS[name]
        m, sd, n = df.mean(), df.std(ddof=1), len(df)
        k1.append(dict(config=name, lines=k, crews=cr, offered_rakes_per_yr=R,
                       wait_h=m.wait, wait_ci95=1.96 * sd.wait / np.sqrt(n),
                       detention_h=m.detention, cycle_h=m.cycle, demurrage_per_rake=m.demurrage_pr,
                       breach_share=m.breach, line_hold_h=m.hold,
                       line_util=R * m.hold / (k * 8760.0), crew_util=R * m.loading / (cr * 8760.0),
                       loco_util=R * m.shunting / 8760.0, throughput_per_yr=m.throughput,
                       demurrage_Rs_cr_per_yr=R * m.demurrage_pr / 1e7,
                       queue_wait_h=m.queue_wait, line_hold_sq_h2=m.hold_sq))
    k1 = pd.DataFrame(k1)

    # ------------------------------------------------ K3 analytical cross-check (one line only)
    # Pollaczek-Khinchine: an M/G/1 queue with arrival rate lam and service S waits
    # Wq = lam E[S^2] / (2 (1 - rho)), rho = lam E[S]. Service = line hold (placement start ->
    # removed), queue = queue_start -> placement_start. Offices make S depend on the clock, so
    # this is a check of the queue mechanics, not an identity.
    rows = []
    for (name, R), df in chk.items():
        m = df.mean()
        rows.append(dict(config=name[6:], offered_rakes_per_yr=R, line_hold_h=m.hold,
                         line_hold_sq_h2=m.hold_sq, queue_wait_h=m.queue_wait,
                         line_util=R * m.hold / 8760.0))
    k3 = pd.concat([k1[k1.lines == 1].assign(offices="as modelled"),
                    pd.DataFrame(rows).assign(offices="all open 24/7")], ignore_index=True)
    k3 = k3[k3.line_util < 0.9].copy()
    lam = k3.offered_rakes_per_yr / 8760.0
    k3["queue_wait_PK_h"] = lam * k3.line_hold_sq_h2 / (2 * (1 - k3.line_util))
    k3["sim_over_PK"] = k3.queue_wait_h / k3.queue_wait_PK_h
    k3 = k3[["config", "offices", "offered_rakes_per_yr", "line_util", "line_hold_h", "queue_wait_h",
             "queue_wait_PK_h", "sim_over_PK"]]

    # ------------------------------------------------ K2 capacity per configuration
    w_today = k1[(k1.config == "TODAY") & (k1.offered_rakes_per_yr == TODAY_RAKES)].wait_h.iloc[0]
    k2 = []
    for name, (lev, k, cr) in CONFIGS.items():
        t = k1[k1.config == name].sort_values("offered_rakes_per_yr")
        at292 = t[t.offered_rakes_per_yr == TODAY_RAKES].iloc[0]
        ceiling = k * 8760.0 / at292.line_hold_h
        ssc = same_service_capacity(t.offered_rakes_per_yr, t.wait_h, w_today)
        utils = {"line": at292.line_util, "crew": at292.crew_util, "loco": at292.loco_util}
        k2.append(dict(config=name, lines=k, crews=cr,
                       line_hold_h_at_292=at292.line_hold_h, detention_h_at_292=at292.detention_h,
                       wait_h_at_292=at292.wait_h, ceiling_rakes_per_yr=ceiling,
                       same_service_capacity_rakes_per_yr=ssc,
                       extra_rakes_vs_today=np.nan, extra_pct_vs_today=np.nan,
                       line_util_at_292=utils["line"], crew_util_at_292=utils["crew"],
                       loco_util_at_292=utils["loco"],
                       busiest_resource_at_292=max(utils, key=utils.get),
                       crew_util_at_capacity=ssc * at292.crew_util / TODAY_RAKES if ssc == ssc else np.nan,
                       loco_util_at_capacity=ssc * at292.loco_util / TODAY_RAKES if ssc == ssc else np.nan))
    k2 = pd.DataFrame(k2)
    base = k2.loc[k2.config == "TODAY", "same_service_capacity_rakes_per_yr"].iloc[0]
    k2["extra_rakes_vs_today"] = k2.same_service_capacity_rakes_per_yr - base
    k2["extra_pct_vs_today"] = 100 * k2.extra_rakes_vs_today / base
    k2["today_wait_target_h"] = w_today

    k1.round(4).to_csv("layer9_K1_traffic_sweep.csv", index=False)
    k2.round(4).to_csv("layer9_K2_capacity.csv", index=False)
    k3.round(4).to_csv("layer9_K3_queue_check.csv", index=False)

    pd.set_option("display.width", 200)
    print(f"Layer 9 capacity: {N_REPS} reps x {N_RAKES} rakes (warm-up {WARMUP}), coal BOXN siding,"
          f" today's wait at {TODAY_RAKES} rakes/yr = {w_today:.2f} h")
    print(k2[["config", "ceiling_rakes_per_yr", "same_service_capacity_rakes_per_yr",
              "extra_rakes_vs_today", "extra_pct_vs_today", "busiest_resource_at_292",
              "crew_util_at_capacity", "loco_util_at_capacity"]].round(2).to_string(index=False))
    print("\nK3 simulation vs Pollaczek-Khinchine (one line, utilisation < 0.9):")
    print(k3.round(3).to_string(index=False))
    chart(k1, k2, w_today)
    print("\nSaved: layer9_K1..K3 CSVs and layer9_results.png")


def chart(k1, k2, w_today):
    fig, ax = plt.subplots(1, 2, figsize=(15, 5.5))
    for name in CONFIGS:
        t = k1[k1.config == name]
        ax[0].plot(t.offered_rakes_per_yr, t.wait_h, marker="o", ms=3, label=name)
    ax[0].axhline(w_today, ls=":", c="k"); ax[0].set_yscale("log")
    ax[0].set_xlabel("offered rakes per year"); ax[0].set_ylabel("mean wait before placement (h, log)")
    ax[0].legend(fontsize=8); ax[0].set_title("K1  Queue vs traffic")
    k2.set_index("config")[["same_service_capacity_rakes_per_yr", "ceiling_rakes_per_yr"]].plot.barh(ax=ax[1])
    ax[1].invert_yaxis(); ax[1].set_xlabel("rakes per year"); ax[1].set_title("K2  Capacity")
    fig.tight_layout(); fig.savefig("layer9_results.png", dpi=110)


if __name__ == "__main__":
    main()
