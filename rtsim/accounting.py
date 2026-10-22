"""
accounting.py  -  L4. Turns timestamps into money.

This module NEVER affects the simulation. It only scores it. That is why
you can change the objective function freely without touching the model.

IR rules implemented:
  * Excess detention = (release - placement) - free time
  * Demurrage       = excess x wagons x rate,  part-hours charged as full hours
  * Siding charge   = engine hour cost x engine trip time (placement + removal)
  * Shunting charge = flat, for use of a railway loco
  * Idle cost       = economic opportunity cost of a rake standing in queue
                      (not an IR charge - flagged separately)

Verify the current rate figures against the Railway Board circular before
quoting any absolute rupee number outside your own work.
"""
import math
import numpy as np
import pandas as pd

from .config import Config
from .eventlog import EventLog


def graded_demurrage(excess_hr: float, cfg: Config) -> float:
    """Rupees PER WAGON for `excess_hr` hours of excess detention.

    [IR-COMP 3.1] The charge is graded, not flat. Each band applies only to
    the hours that fall inside it, so the schedule is piecewise linear and
    convex - the marginal cost of an extra hour RISES the longer a rake is
    held. Modelling it flat understates the charge on precisely the long
    detentions this work is about.

        up to  6 h  base                (Rs 150/wagon/h)
         6-12 h     base + 10%          (Rs 165)
        12-24 h     base + 25%          (Rs 187.50)
        24-48 h     base + 50%          (Rs 225)
        48-72 h     twice base          (Rs 300)
        beyond 72 h thrice base         (Rs 450)
    """
    c = cfg.charges
    if excess_hr <= 0:
        return 0.0
    if not c.graded_demurrage:
        return excess_hr * c.demurrage_per_wagon_hr * c.penal_multiplier
    total, prev = 0.0, 0.0
    for upper, mult in c.demurrage_grades:
        if excess_hr <= prev:
            break
        band = min(excess_hr, upper) - prev
        total += band * c.demurrage_per_wagon_hr * mult
        prev = upper
    return total * c.penal_multiplier


def rake_table(log: EventLog, cfg: Config) -> pd.DataFrame:
    """One row per rake: every timestamp, every duration, every charge."""
    w = log.pivot_rakes()
    if w.empty:
        return w
    w = w.dropna(subset=["departed"]).copy()          # drop no-shows
    c = cfg.charges

    # ---- durations ----------------------------------------------------
    w["wait_hr"] = w["placement_start"] - w["rake_arrive"]
    w["placement_hr"] = w["placed"] - w["placement_start"]
    w["preload_idle_hr"] = w["loading_start"] - w["placed"]
    w["loading_hr"] = w["loading_end"] - w["loading_start"]
    w["release_lag_hr"] = w["released"] - w["loading_end"]
    w["removal_hr"] = w["removed"] - w["removal_start"]

    # DETENTION as IR defines it: placement -> release
    w["detention_hr"] = w["released"] - w["placed"]
    # DWELL as the terminal experiences it: arrival -> back on main line
    w["dwell_hr"] = w["removed"] - w["rake_arrive"]
    # time to actually leave the station: adds RR + freight settlement (M7)
    w["rr_lag_hr"] = w["departed"] - w["removed"]
    w["cycle_hr"] = w["departed"] - w["rake_arrive"]

    # ---- IR charges ---------------------------------------------------
    excess = (w["detention_hr"] - c.free_time_hr).clip(lower=0.0)
    if c.demurrage_part_hour_rounding:
        excess = excess.apply(lambda x: math.ceil(x) if x > 0 else 0.0)
    w["excess_hr"] = excess
    w["demurrage"] = excess.apply(
        lambda e: graded_demurrage(e, cfg) * cfg.rake.wagons)

    engine_hours = w["placement_hr"] + w["removal_hr"]
    w["siding_charge"] = (engine_hours * c.engine_hour_cost
                          if c.siding_charge_enabled else 0.0)
    w["shunting_charge"] = float(c.shunting_charge)
    w["idle_cost"] = w["wait_hr"] * c.idle_cost_per_hr

    # ---- P&L ----------------------------------------------------------
    w["revenue"] = cfg.rake.wagons * cfg.rake.tonnes_per_wagon * c.freight_per_tonne
    w["controllable_cost"] = (w["demurrage"] + w["idle_cost"]
                              + w["siding_charge"] + w["shunting_charge"])
    w["profit"] = w["revenue"] - w["controllable_cost"]
    return w


def kpis(rt: pd.DataFrame, term=None, cfg: Config = None) -> dict:
    """Scalar KPIs for one replication."""
    if rt.empty:
        return {}
    horizon = rt["removed"].max() - rt["rake_arrive"].min()
    k = {
        # primary - the professor's brief
        "mean_detention_hr": rt.detention_hr.mean(),
        "p90_detention_hr": rt.detention_hr.quantile(0.90),
        "mean_dwell_hr": rt.dwell_hr.mean(),
        "mean_cycle_hr": rt.cycle_hr.mean(),
        "mean_rr_lag_hr": rt.rr_lag_hr.mean(),
        "mean_wait_hr": rt.wait_hr.mean(),
        # commercial
        "total_demurrage": rt.demurrage.sum(),
        "freetime_breaches": int((rt.excess_hr > 0).sum()),
        "breach_rate": float((rt.excess_hr > 0).mean()),
        "total_controllable_cost": rt.controllable_cost.sum(),
        "total_profit": rt.profit.sum(),
        # throughput
        "rakes_completed": len(rt),
        "throughput_per_day": len(rt) / (horizon / 24.0) if horizon > 0 else np.nan,
    }
    if term is not None and cfg is not None:
        k["line_utilisation"] = _time_weighted_mean(
            term.line_busy_samples) / cfg.resources.loading_lines
        k["mean_queue_len"] = _time_weighted_mean(term.queue_len_samples)
    return k


def _time_weighted_mean(samples) -> float:
    """Correct way to average a step function over time. A plain mean of the
    samples would be wrong because the samples are not equally spaced."""
    if len(samples) < 2:
        return 0.0
    tot_t = samples[-1][0] - samples[0][0]
    if tot_t <= 0:
        return 0.0
    area = sum(samples[i][1] * (samples[i + 1][0] - samples[i][0])
               for i in range(len(samples) - 1))
    return area / tot_t


def attribution(rt: pd.DataFrame) -> pd.DataFrame:
    """Decompose dwell time by which party controls each segment.

    This is the machinery behind the demurrage-attribution contribution:
    if most detention is caused by a party that is not the one being
    charged, the penalty fails its own incentive purpose.
    """
    if rt.empty:
        return pd.DataFrame()
    seg = pd.DataFrame({
        "queueing_for_line": rt.wait_hr,        # terminal capacity
        "placement_shunting": rt.placement_hr,  # railway
        "waiting_for_crew": rt.preload_idle_hr,  # terminal
        "loading": rt.loading_hr,               # terminal
        "release_reporting": rt.release_lag_hr,  # terminal (admin: M5+M6)
        "removal_shunting": rt.removal_hr,      # railway
        "rr_and_payment": rt.rr_lag_hr,         # client (admin: M7)
    })
    owner = {
        "queueing_for_line": "terminal",
        "placement_shunting": "railway",
        "waiting_for_crew": "terminal",
        "loading": "terminal",
        "release_reporting": "terminal",
        "removal_shunting": "railway",
        "rr_and_payment": "client",
    }
    out = pd.DataFrame({
        "segment": seg.columns,
        "owner": [owner[c] for c in seg.columns],
        "total_hr": seg.sum().values,
        "mean_hr": seg.mean().values,
    })
    out["share_pct"] = 100 * out.total_hr / out.total_hr.sum()
    return out.sort_values("total_hr", ascending=False).reset_index(drop=True)
