"""
RAKE SIDING SIMULATION  v2   -  Phase 1
Adds: distribution objects, profit-aware dispatch, replications + confidence
intervals, paired statistical test, warm-up cut.

ASSUMPTION A1 (per supervisor): coal is always available at the siding.
                                Only the RAKE can be late, never the material.
ALL RATES ARE ASSUMED. Replace CFG when real invoice/log data arrives.
"""

import simpy, random, math, statistics as st
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ======================================================================
# 1. DISTRIBUTIONS  (swap any one line to change the realism assumption)
# ======================================================================
class Dist:
    """Wraps a random draw so the model never calls rng directly."""
    def __init__(self, kind, **p): self.kind, self.p = kind, p
    def draw(self, rng):
        k, p = self.kind, self.p
        if k == "exp":   return rng.expovariate(1.0 / p["mean"])
        if k == "const": return p["value"]
        if k == "logn":
            # mean/sd given on the REAL scale, converted to log scale
            m, s = p["mean"], p["sd"]
            mu = math.log(m**2 / math.sqrt(s**2 + m**2))
            sg = math.sqrt(math.log(1 + (s/m)**2))
            return rng.lognormvariate(mu, sg)
        raise ValueError(k)


# ======================================================================
# 2. CONFIG  -  every assumption lives here
# ======================================================================
CFG = {
    "n_rakes":        40,
    "warmup_rakes":   5,          # discard first N (siding starts empty = unrealistic)
    "n_reps":         50,         # independent replications
    "loading_lines":  1,

    "arrival_gap":    Dist("exp",  mean=4.0),      # hours between rake arrivals
    "load_rate":      Dist("logn", mean=900.0, sd=250.0),   # tonnes/hour
    "placement":      Dist("logn", mean=1.0, sd=0.3),       # hours, shunt IN
    "removal":        Dist("logn", mean=1.0, sd=0.3),       # hours, shunt OUT

    "wagons":            58,
    "tonnes_per_wagon":  65,
    "free_time_hr":      7.0,

    "freight_per_tonne":      1400.0,
    "demurrage_per_wagon_hr":  150.0,
    "shunting_charge":       25000.0,
    "idle_cost_per_hr":       3000.0,
}
POLICIES = ["FCFS", "SPT", "PROFIT"]


# ======================================================================
# 3. SCENARIO  -  the world, identical for every policy (paired design)
# ======================================================================
def make_scenario(cfg, seed):
    rng = random.Random(seed)
    tonnes = cfg["wagons"] * cfg["tonnes_per_wagon"]
    jobs, t = [], 0.0
    for i in range(cfg["n_rakes"]):
        t += cfg["arrival_gap"].draw(rng)
        rate = max(300.0, cfg["load_rate"].draw(rng))
        jobs.append(dict(
            rake=i + 1,
            arrive=t,
            tonnes=tonnes,
            load_hr=tonnes / rate,
            place_hr=max(0.1, cfg["placement"].draw(rng)),
            remove_hr=max(0.1, cfg["removal"].draw(rng))))
    return jobs


# ======================================================================
# 4. THE SIDING
# ======================================================================
class Siding:
    def __init__(self, env, cfg, policy):
        self.env, self.cfg, self.policy = env, cfg, policy
        self.line = simpy.PriorityResource(env, capacity=cfg["loading_lines"])
        self.log = []

    # ---- the ONLY place a dispatch decision is made --------------------
    def priority(self, job):
        c = self.cfg
        if self.policy == "FCFS":
            return job["arrive"]                    # arrival order
        if self.policy == "SPT":
            return job["load_hr"]                   # shortest job first
        if self.policy == "PROFIT":
            # marginal controllable cost this rake will inflict if served next
            detention = job["place_hr"] + job["load_hr"]
            excess    = max(0.0, detention - c["free_time_hr"])
            demurrage = excess * c["wagons"] * c["demurrage_per_wagon_hr"]
            blocking  = detention * c["idle_cost_per_hr"]   # it blocks the line
            # serve first whoever costs LEAST to clear -> frees line soonest
            return demurrage + blocking
        raise ValueError(self.policy)

    def handle(self, job):
        c = self.cfg
        t_arrive = self.env.now
        with self.line.request(priority=self.priority(job)) as req:
            yield req
            t_start = self.env.now                       # placement begins
            yield self.env.timeout(job["place_hr"])
            t_placed = self.env.now                      # FREE TIME STARTS
            yield self.env.timeout(job["load_hr"])
            t_released = self.env.now                    # FREE TIME STOPS
            yield self.env.timeout(job["remove_hr"])
            t_removed = self.env.now

        detention = t_released - t_placed
        excess    = max(0.0, detention - c["free_time_hr"])
        demurrage = excess * c["wagons"] * c["demurrage_per_wagon_hr"]
        wait_hr   = t_start - t_arrive
        idle_cost = wait_hr * c["idle_cost_per_hr"]
        revenue   = job["tonnes"] * c["freight_per_tonne"]
        cost      = demurrage + idle_cost + c["shunting_charge"]

        self.log.append(dict(
            rake=job["rake"], arrive=t_arrive, placed=t_placed,
            released=t_released, removed=t_removed,
            wait_hr=wait_hr, load_hr=job["load_hr"],
            detention_hr=detention, excess_hr=excess,
            revenue=revenue, demurrage=demurrage, idle_cost=idle_cost,
            cost=cost, profit=revenue - cost,
            cycle_hr=t_removed - t_arrive))


def run_once(policy, cfg, jobs):
    env = simpy.Environment()
    s = Siding(env, cfg, policy)

    def feed():
        prev = 0.0
        for j in jobs:
            yield env.timeout(j["arrive"] - prev)
            prev = j["arrive"]
            env.process(s.handle(j))
    env.process(feed())
    env.run()

    df = pd.DataFrame(s.log).sort_values("rake")
    return df[df.rake > cfg["warmup_rakes"]]          # warm-up cut


# ======================================================================
# 5. REPLICATIONS + CONFIDENCE INTERVALS
# ======================================================================
def ci95(v):
    if len(v) < 2: return (v[0], 0.0)
    return st.mean(v), 1.96 * st.stdev(v) / math.sqrt(len(v))


def experiment(cfg, policies=POLICIES):
    per_rep = {p: [] for p in policies}
    for seed in range(cfg["n_reps"]):
        jobs = make_scenario(cfg, seed)               # SAME world for all policies
        for p in policies:
            d = run_once(p, cfg, jobs)
            per_rep[p].append(dict(
                seed=seed,
                profit=d.profit.sum(),
                cost=d.cost.sum(),
                demurrage=d.demurrage.sum(),
                idle=d.idle_cost.sum(),
                wait=d.wait_hr.mean(),
                cycle=d.cycle_hr.mean(),
                breaches=int((d.excess_hr > 0).sum())))
    return {p: pd.DataFrame(v) for p, v in per_rep.items()}


def summarise(res):
    rows = []
    for p, df in res.items():
        r = {"policy": p}
        for col, lab in [("profit", "profit"), ("cost", "cost"),
                         ("demurrage", "demurrage"), ("idle", "idle"),
                         ("wait", "wait_hr"), ("cycle", "cycle_hr"),
                         ("breaches", "breaches")]:
            m, h = ci95(df[col].tolist())
            r[lab], r[lab + "_ci"] = m, h
        rows.append(r)
    return pd.DataFrame(rows)


def paired_test(res, base, alt):
    """Paired difference per seed -> CI. Excludes 0 => real effect."""
    d = (res[alt].profit - res[base].profit).tolist()
    m, h = ci95(d)
    return m, h, (m - h > 0 or m + h < 0)


# ======================================================================
# 6. RUN
# ======================================================================
if __name__ == "__main__":
    cfg = CFG
    res = experiment(cfg)
    sm  = summarise(res)

    print(f"\n=== SIDING SIMULATION v2  |  {cfg['n_reps']} replications, "
          f"{cfg['n_rakes']} rakes, warm-up {cfg['warmup_rakes']} ===")
    print("(all rates ASSUMED; +/- is 95% confidence half-width)\n")
    for _, r in sm.iterrows():
        print(f"{r.policy:>7} | profit {r.profit/1e6:8.3f} +/-{r.profit_ci/1e6:.3f} M"
              f" | cost {r.cost/1e6:6.3f} +/-{r.cost_ci/1e6:.3f} M"
              f" | wait {r.wait_hr:6.2f} +/-{r.wait_hr_ci:.2f} h"
              f" | cycle {r.cycle_hr:6.2f} h"
              f" | breaches {r.breaches:5.2f}")

    print("\n--- paired comparison vs FCFS (same seeds) ---")
    for alt in ["SPT", "PROFIT"]:
        m, h, sig = paired_test(res, "FCFS", alt)
        base = sm.loc[sm.policy == "FCFS", "cost"].iloc[0]
        print(f"{alt:>7} : profit {m:+,.0f} +/-{h:,.0f} Rs "
              f"({m/base*100:+.1f}% of controllable cost) "
              f"-> {'SIGNIFICANT' if sig else 'not significant'}")

    # ---- charts with error bars --------------------------------------
    cols = ["#8c8c8c", "#5b7c99", "#c1440e"]
    fig, ax = plt.subplots(1, 3, figsize=(13.5, 4.2))
    specs = [("cost", "cost_ci", "Controllable cost (Rs M)", 1e6),
             ("wait", "wait_hr_ci", "Avg wait for placement (hr)", 1),
             ("cycle", "cycle_hr_ci", "Avg siding cycle time (hr)", 1)]
    sm2 = sm.rename(columns={"cost": "cost", "wait_hr": "wait",
                             "wait_hr_ci": "wait_hr_ci", "cycle_hr": "cycle"})
    for a, (c, cc, title, scale) in zip(ax, specs):
        vals = sm2[c] / scale
        errs = sm2[cc if cc in sm2 else c + "_ci"] / scale
        a.bar(sm2.policy, vals, yerr=errs, capsize=5, color=cols)
        a.set_title(title); a.grid(axis="y", alpha=.3); a.set_axisbelow(True)
    fig.suptitle("Siding dispatch policies  |  50 replications, 95% CI  (assumed rates)",
                 y=1.03)
    fig.tight_layout()
    fig.savefig("siding_v2_comparison.png", dpi=150, bbox_inches="tight")

    for p, df in res.items():
        df.to_csv(f"reps_{p}.csv", index=False)
    sm.round(3).to_csv("summary_v2.csv", index=False)
    print("\nSaved: siding_v2_comparison.png, summary_v2.csv, reps_*.csv")
