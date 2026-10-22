"""
RAKE SIDING SIMULATION  -  Phase 1
Models one loading siding: placement -> free time -> loading -> release -> removal
Compares two dispatch policies on total profit.

ALL RATES BELOW ARE ASSUMED. Replace when real data arrives.
"""

import simpy, random
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ----------------------------------------------------------------------
# 1. ASSUMPTIONS  (every number here is a knob you can vary later)
# ----------------------------------------------------------------------
CFG = {
    "n_rakes":            30,      # rakes arriving in the run
    "mean_gap_hr":        4.0,     # average hours between arrivals
    "loading_lines":      1,       # how many rakes the siding can load at once

    "wagons":             58,      # wagons per rake
    "tonnes_per_wagon":   65,      # payload
    "load_rate_tph":      900.0,   # tonnes per hour (mean)
    "load_rate_sd":       250.0,   # variability in loading rate

    "placement_hr":       1.0,     # shunting rake INTO the siding
    "removal_hr":         1.0,     # shunting rake OUT of the siding
    "free_time_hr":       7.0,     # free time: placement -> release

    "freight_per_tonne":  1400.0,  # Rs/tonne revenue for the haul
    "demurrage_per_wagon_hr": 150.0,   # Rs per wagon per hour beyond free time
    "shunting_charge":    25000.0, # Rs flat, per placement+removal
    "idle_cost_per_hr":   3000.0,  # Rs/hr opportunity cost of a rake standing idle

    "seed":               42,
}


# ----------------------------------------------------------------------
# 2. THE SIDING MODEL
# ----------------------------------------------------------------------
class Siding:
    def __init__(self, env, cfg, policy):
        self.env, self.cfg, self.policy = env, cfg, policy
        self.line = simpy.PriorityResource(env, capacity=cfg["loading_lines"])
        self.log = []

    def priority(self, load_hr):
        """Lower number = served first."""
        if self.policy == "FCFS":
            return 0                    # all equal -> served in arrival order
        if self.policy == "SPT":
            return load_hr              # shortest loading job first
        raise ValueError(self.policy)

    def handle(self, rake_id, tonnes, load_hr):
        cfg = self.cfg
        t_arrive = self.env.now                       # EVENT 1: arrives at serving stn

        with self.line.request(priority=self.priority(load_hr)) as req:
            yield req                                 # EVENT 2: waiting for placement
            t_place_start = self.env.now
            yield self.env.timeout(cfg["placement_hr"])
            t_placed = self.env.now                   # EVENT 3: placed -> FREE TIME STARTS

            yield self.env.timeout(load_hr)           # EVENT 4-5: loading
            t_released = self.env.now                 # EVENT 6: release reported

            yield self.env.timeout(cfg["removal_hr"])
            t_removed = self.env.now                  # EVENT 8: back on main line

        # --- the money -------------------------------------------------
        detention = t_released - t_placed
        excess    = max(0.0, detention - cfg["free_time_hr"])
        demurrage = excess * cfg["wagons"] * cfg["demurrage_per_wagon_hr"]
        wait_hr   = t_place_start - t_arrive
        idle_cost = wait_hr * cfg["idle_cost_per_hr"]
        revenue   = tonnes * cfg["freight_per_tonne"]
        cost      = demurrage + idle_cost + cfg["shunting_charge"]
        profit    = revenue - cost

        self.log.append(dict(
            rake=rake_id, arrive=t_arrive, placed=t_placed, released=t_released,
            removed=t_removed, wait_hr=wait_hr, load_hr=load_hr,
            detention_hr=detention, excess_hr=excess,
            revenue=revenue, demurrage=demurrage,
            idle_cost=idle_cost, cost=cost, profit=profit,
            cycle_hr=t_removed - t_arrive))


def arrivals(env, siding, cfg, jobs):
    for rake_id, (gap, tonnes, load_hr) in enumerate(jobs, start=1):
        yield env.timeout(gap)
        env.process(siding.handle(rake_id, tonnes, load_hr))


def make_jobs(cfg):
    """Generate the SAME arrival stream for every policy - fair comparison."""
    rng = random.Random(cfg["seed"])
    jobs = []
    for _ in range(cfg["n_rakes"]):
        gap    = rng.expovariate(1.0 / cfg["mean_gap_hr"])
        tonnes = cfg["wagons"] * cfg["tonnes_per_wagon"]
        rate   = max(350.0, rng.gauss(cfg["load_rate_tph"], cfg["load_rate_sd"]))
        jobs.append((gap, tonnes, tonnes / rate))
    return jobs


def run(policy, cfg, jobs):
    env = simpy.Environment()
    s = Siding(env, cfg, policy)
    env.process(arrivals(env, s, cfg, jobs))
    env.run()
    return pd.DataFrame(s.log)


# ----------------------------------------------------------------------
# 3. RUN + COMPARE
# ----------------------------------------------------------------------
if __name__ == "__main__":
    cfg  = CFG
    jobs = make_jobs(cfg)
    results = {p: run(p, cfg, jobs) for p in ["FCFS", "SPT"]}

    print("\n=== SIDING SIMULATION (assumed rates) ===")
    summary = []
    for p, df in results.items():
        summary.append(dict(
            policy=p,
            total_profit=df.profit.sum(),
            controllable_cost=df.cost.sum(),
            demurrage=df.demurrage.sum(),
            idle_cost=df.idle_cost.sum(),
            avg_wait_hr=df.wait_hr.mean(),
            avg_cycle_hr=df.cycle_hr.mean(),
            rakes_over_freetime=int((df.excess_hr > 0).sum())))
    sm = pd.DataFrame(summary)
    print(sm.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))

    base, alt = sm.iloc[0], sm.iloc[1]
    gain = alt.total_profit - base.total_profit
    cut = base.controllable_cost - alt.controllable_cost
    print(f"\nSPT vs FCFS  ->  profit {gain:+,.0f} Rs | "
          f"controllable cost {-cut:+,.0f} Rs ({-cut/base.controllable_cost*100:+.1f}%) | "
          f"avg wait {alt.avg_wait_hr - base.avg_wait_hr:+.2f} hr")

    results["FCFS"].round(2).to_csv("siding_rake_log_FCFS.csv", index=False)
    results["SPT"].round(2).to_csv("siding_rake_log_SPT.csv", index=False)

    # ---- chart -------------------------------------------------------
    fig, ax = plt.subplots(1, 3, figsize=(13, 4))
    pol = sm.policy
    ax[0].bar(pol, sm.total_profit / 1e6, color=["#8c8c8c", "#c1440e"])
    ax[0].set_title("Total profit (Rs million)")
    ax[1].bar(pol, sm.controllable_cost / 1e6, color=["#8c8c8c", "#c1440e"])
    ax[1].set_title("Controllable cost (Rs million)")
    ax[2].bar(pol, sm.avg_wait_hr, color=["#8c8c8c", "#c1440e"])
    ax[2].set_title("Avg wait for placement (hr)")
    for a in ax:
        a.grid(axis="y", alpha=.3)
        a.set_axisbelow(True)
    fig.suptitle("Siding dispatch policy comparison  (assumed rates)", y=1.02)
    fig.tight_layout()
    fig.savefig("siding_policy_comparison.png", dpi=150, bbox_inches="tight")
    print("\nSaved: siding_policy_comparison.png, siding_rake_log_*.csv")
