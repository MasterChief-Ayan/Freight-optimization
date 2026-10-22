"""
RAKE SIDING SIMULATION  v3   -  Phase 1
Adds OPTIMAL: an OR-Tools CP-SAT offline optimum (global maximum profit),
used as the ceiling against which the greedy rules are measured.

ASSUMPTION A1: coal always available; only the rake can be late.
ALL RATES ARE ASSUMED.
"""

import simpy, random, math, copy
import statistics as stat
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ortools.sat.python import cp_model


# ======================================================================
# 1. DISTRIBUTIONS
# ======================================================================
class Dist:
    def __init__(self, kind, **p): self.kind, self.p = kind, p
    def draw(self, rng):
        k, p = self.kind, self.p
        if k == "exp":   return rng.expovariate(1.0 / p["mean"])
        if k == "const": return p["value"]
        if k == "logn":
            m, s = p["mean"], p["sd"]
            mu = math.log(m**2 / math.sqrt(s**2 + m**2))
            sg = math.sqrt(math.log(1 + (s / m) ** 2))
            return rng.lognormvariate(mu, sg)
        raise ValueError(k)


CFG = {
    "n_rakes":       25,
    "warmup_rakes":  0,          # OPTIMAL is offline; keep all rakes for fairness
    "n_reps":        30,
    "loading_lines": 1,

    "arrival_gap": Dist("exp",  mean=4.0),
    "load_rate":   Dist("logn", mean=900.0, sd=250.0),
    "placement":   Dist("logn", mean=1.0, sd=0.3),
    "removal":     Dist("logn", mean=1.0, sd=0.3),

    "wagons": 58, "tonnes_per_wagon": 65, "free_time_hr": 7.0,
    "freight_per_tonne": 1400.0,
    "demurrage_per_wagon_hr": 150.0,
    "shunting_charge": 25000.0,
    "idle_cost_per_hr": 3000.0,

    "solver_time_s": 10.0,       # CP-SAT budget per replication
}
POLICIES = ["FCFS", "SPT", "PROFIT", "OPTIMAL"]


# ======================================================================
# 2. SCENARIO
# ======================================================================
def make_scenario(cfg, seed):
    rng = random.Random(seed)
    tonnes = cfg["wagons"] * cfg["tonnes_per_wagon"]
    jobs, t = [], 0.0
    for i in range(cfg["n_rakes"]):
        t += cfg["arrival_gap"].draw(rng)
        rate = max(300.0, cfg["load_rate"].draw(rng))
        jobs.append(dict(rake=i + 1, arrive=t, tonnes=tonnes,
                         load_hr=tonnes / rate,
                         place_hr=max(0.1, cfg["placement"].draw(rng)),
                         remove_hr=max(0.1, cfg["removal"].draw(rng))))
    return jobs


# ======================================================================
# 3. ONE COST FUNCTION  -  used by every policy, so comparison is fair
# ======================================================================
def evaluate(starts, jobs, cfg):
    """starts[j] = time the rake begins PLACEMENT. Returns per-rake dataframe."""
    c, rows = cfg, []
    for j in jobs:
        s = starts[j["rake"]]
        placed    = s + j["place_hr"]                 # free-time clock STARTS
        released  = placed + j["load_hr"]             # free-time clock STOPS
        removed   = released + j["remove_hr"]
        detention = released - placed
        excess    = max(0.0, detention - c["free_time_hr"])
        demurrage = excess * c["wagons"] * c["demurrage_per_wagon_hr"]
        wait      = s - j["arrive"]
        idle      = wait * c["idle_cost_per_hr"]
        revenue   = j["tonnes"] * c["freight_per_tonne"]
        cost      = demurrage + idle + c["shunting_charge"]
        rows.append(dict(rake=j["rake"], arrive=j["arrive"], start=s,
                         placed=placed, released=released, removed=removed,
                         wait_hr=wait, load_hr=j["load_hr"],
                         detention_hr=detention, excess_hr=excess,
                         revenue=revenue, demurrage=demurrage, idle_cost=idle,
                         cost=cost, profit=revenue - cost,
                         cycle_hr=removed - j["arrive"]))
    return pd.DataFrame(rows)


# ======================================================================
# 4a. GREEDY POLICIES  (simulated, online - decide as rakes arrive)
# ======================================================================
class Siding:
    def __init__(self, env, cfg, policy):
        self.env, self.cfg, self.policy = env, cfg, policy
        self.line = simpy.PriorityResource(env, capacity=cfg["loading_lines"])
        self.starts = {}

    def priority(self, job):
        c = self.cfg
        if self.policy == "FCFS":  return job["arrive"]
        if self.policy == "SPT":   return job["load_hr"]
        if self.policy == "PROFIT":
            det = job["place_hr"] + job["load_hr"]
            dem = max(0.0, det - c["free_time_hr"]) * c["wagons"] * c["demurrage_per_wagon_hr"]
            return dem + det * c["idle_cost_per_hr"]
        raise ValueError(self.policy)

    def handle(self, job):
        with self.line.request(priority=self.priority(job)) as req:
            yield req
            self.starts[job["rake"]] = self.env.now
            yield self.env.timeout(job["place_hr"] + job["load_hr"] + job["remove_hr"])


def run_greedy(policy, cfg, jobs):
    env = simpy.Environment()
    s = Siding(env, cfg, policy)

    def feed():
        prev = 0.0
        for j in jobs:
            yield env.timeout(j["arrive"] - prev); prev = j["arrive"]
            env.process(s.handle(j))
    env.process(feed()); env.run()
    return s.starts


# ======================================================================
# 4b. OPTIMAL  -  CP-SAT, sees ALL rakes at once -> global optimum
# ======================================================================
SCALE = 60   # work in minutes (CP-SAT needs integers)

def run_optimal(cfg, jobs):
    c = cfg
    mdl = cp_model.CpModel()
    horizon = int(sum((j["place_hr"] + j["load_hr"] + j["remove_hr"]) for j in jobs) * SCALE
                  + max(j["arrive"] for j in jobs) * SCALE) + 10

    S, ivs, waits = {}, [], []
    for j in jobs:
        r   = int(round(j["arrive"] * SCALE))
        dur = int(round((j["place_hr"] + j["load_hr"] + j["remove_hr"]) * SCALE))
        s   = mdl.NewIntVar(r, horizon, f"s{j['rake']}")          # start >= arrival
        e   = mdl.NewIntVar(r, horizon + dur, f"e{j['rake']}")
        ivs.append(mdl.NewIntervalVar(s, dur, e, f"i{j['rake']}"))
        S[j["rake"]] = s
        w = mdl.NewIntVar(0, horizon, f"w{j['rake']}")
        mdl.Add(w == s - r)                                        # waiting time
        waits.append(w)

    mdl.AddNoOverlap(ivs) if c["loading_lines"] == 1 else \
        mdl.AddCumulative(ivs, [1] * len(ivs), c["loading_lines"])

    # demurrage here is sequence-independent (see note), so minimising total
    # waiting == maximising total profit
    mdl.Minimize(sum(waits))

    slv = cp_model.CpSolver()
    slv.parameters.max_time_in_seconds = c["solver_time_s"]
    slv.parameters.num_search_workers  = 8
    st = slv.Solve(mdl)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, None
    return ({j["rake"]: slv.Value(S[j["rake"]]) / SCALE for j in jobs},
            slv.StatusName(st))


# ======================================================================
# 5. EXPERIMENT
# ======================================================================
def ci95(v):
    if len(v) < 2: return (v[0], 0.0)
    return stat.mean(v), 1.96 * stat.stdev(v) / math.sqrt(len(v))


def experiment(cfg):
    per = {p: [] for p in POLICIES}
    proven = 0
    for seed in range(cfg["n_reps"]):
        jobs = make_scenario(cfg, seed)
        for p in POLICIES:
            if p == "OPTIMAL":
                starts, status = run_optimal(cfg, jobs)
                if starts is None: continue
                proven += (status == "OPTIMAL")
            else:
                starts = run_greedy(p, cfg, jobs)
            d = evaluate(starts, jobs, cfg)
            d = d[d.rake > cfg["warmup_rakes"]]
            per[p].append(dict(seed=seed, profit=d.profit.sum(), cost=d.cost.sum(),
                               demurrage=d.demurrage.sum(), idle=d.idle_cost.sum(),
                               wait=d.wait_hr.mean(), cycle=d.cycle_hr.mean(),
                               breaches=int((d.excess_hr > 0).sum())))
    return {p: pd.DataFrame(v) for p, v in per.items()}, proven


def summarise(res):
    rows = []
    for p, df in res.items():
        r = {"policy": p}
        for col in ["profit", "cost", "demurrage", "idle", "wait", "cycle", "breaches"]:
            m, h = ci95(df[col].tolist()); r[col], r[col + "_ci"] = m, h
        rows.append(r)
    return pd.DataFrame(rows)


# ======================================================================
# 6. RUN
# ======================================================================
if __name__ == "__main__":
    cfg = CFG
    res, proven = experiment(cfg)
    sm = summarise(res)

    print(f"\n=== SIDING v3 | {cfg['n_reps']} reps x {cfg['n_rakes']} rakes | "
          f"CP-SAT proved optimal in {proven}/{cfg['n_reps']} reps ===")
    print("(assumed rates; +/- = 95% CI half-width)\n")
    for _, r in sm.iterrows():
        print(f"{r.policy:>8} | cost {r.cost/1e6:6.3f} +/-{r.cost_ci/1e6:.3f} M"
              f" | idle {r['idle']/1e6:6.3f} M | demurrage {r.demurrage/1e3:7.1f} k"
              f" | wait {r.wait:6.2f} +/-{r.wait_ci:.2f} h")

    opt = sm.loc[sm.policy == "OPTIMAL", "cost"].iloc[0]
    fc  = sm.loc[sm.policy == "FCFS",    "cost"].iloc[0]
    print("\n--- gap to global optimum (controllable cost) ---")
    for p in POLICIES:
        c = sm.loc[sm.policy == p, "cost"].iloc[0]
        d = (res[p].cost - res["OPTIMAL"].cost).tolist()
        m, h = ci95(d)
        captured = (fc - c) / (fc - opt) * 100 if fc != opt else 100
        print(f"{p:>8} : {c/1e6:.3f} M | +{m:>9,.0f} +/-{h:,.0f} above optimum "
              f"| captures {captured:5.1f}% of the achievable gain")

    # charts
    cols = ["#8c8c8c", "#5b7c99", "#c1440e", "#1a7f37"]
    fig, ax = plt.subplots(1, 3, figsize=(13.5, 4.2))
    for a, (col, cc, ttl, sc) in zip(ax, [
            ("cost", "cost_ci", "Controllable cost (Rs M)", 1e6),
            ("idle", "idle_ci", "Idle cost (Rs M)", 1e6),
            ("wait", "wait_ci", "Avg wait for placement (hr)", 1)]):
        a.bar(sm.policy, sm[col] / sc, yerr=sm[cc] / sc, capsize=5, color=cols)
        a.set_title(ttl); a.grid(axis="y", alpha=.3); a.set_axisbelow(True)
    fig.suptitle("Greedy rules vs CP-SAT global optimum | 30 reps, 95% CI (assumed rates)",
                 y=1.03)
    fig.tight_layout(); fig.savefig("siding_v3_optimal.png", dpi=150, bbox_inches="tight")
    sm.round(3).to_csv("summary_v3.csv", index=False)
    for p, df in res.items(): df.to_csv(f"repsv3_{p}.csv", index=False)
    print("\nSaved: siding_v3_optimal.png, summary_v3.csv, repsv3_*.csv")
