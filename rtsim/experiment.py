"""
experiment.py  -  replications, confidence intervals, paired comparison.

Nothing here touches the model. It runs it many times and does statistics,
because a single run is a single sample and proves nothing.
"""
import math
import statistics as st
from typing import Dict, List

import pandas as pd

from .config import Config
from .distributions import RandomStreams
from .terminal import simulate, generate_rakes
from .accounting import rake_table, kpis, attribution
from . import policies


def ci95(v: List[float]):
    if len(v) < 2:
        return (v[0] if v else float("nan"), 0.0)
    return st.mean(v), 1.96 * st.stdev(v) / math.sqrt(len(v))


def run_policies(cfg: Config, policy_names: List[str]) -> Dict[str, pd.DataFrame]:
    """Run every policy on the SAME set of scenarios (paired design)."""
    out = {p: [] for p in policy_names}
    for rep in range(cfg.run.n_reps):
        seed = cfg.run.base_seed + rep
        scenario_rakes = generate_rakes(cfg, RandomStreams(seed))
        for name in policy_names:
            log, _, term = simulate(cfg, policies.build(name, cfg), seed,
                                    rakes=scenario_rakes)
            rt = rake_table(log, cfg)
            rt = rt[rt.rake > cfg.run.warmup_rakes]        # warm-up cut
            row = kpis(rt, term, cfg)
            row["seed"] = seed
            out[name].append(row)
    return {k: pd.DataFrame(v) for k, v in out.items()}


def summarise(res: Dict[str, pd.DataFrame], metrics=None) -> pd.DataFrame:
    metrics = metrics or ["mean_detention_hr", "mean_wait_hr", "mean_dwell_hr",
                          "total_demurrage", "breach_rate",
                          "total_controllable_cost", "line_utilisation",
                          "throughput_per_day"]
    rows = []
    for name, df in res.items():
        r = {"policy": name}
        for m in metrics:
            if m in df.columns:
                mu, h = ci95(df[m].tolist())
                r[m], r[m + "_ci"] = mu, h
        rows.append(r)
    return pd.DataFrame(rows)


def paired(res: Dict[str, pd.DataFrame], base: str, alt: str, metric: str):
    """Per-seed difference. If the CI excludes zero the effect is real."""
    d = (res[alt][metric] - res[base][metric]).tolist()
    m, h = ci95(d)
    return {"metric": metric, "base": base, "alt": alt, "diff": m, "ci": h,
            "significant": (m - h > 0) or (m + h < 0)}


def print_summary(cfg: Config, sm: pd.DataFrame):
    print(f"\n{'=' * 96}")
    print(f"SCENARIO: {cfg.label}   |   {cfg.run.n_reps} reps x "
          f"{cfg.run.n_rakes} rakes, warm-up {cfg.run.warmup_rakes}   |   "
          f"lines={cfg.resources.loading_lines} locos={cfg.resources.shunting_locos} "
          f"crews={cfg.resources.crews}")
    print(f"NOTE: {cfg.notes}")
    print("=" * 96)
    hdr = (f"{'policy':>8} | {'detention':>14} | {'wait':>14} | {'dwell':>9} | "
           f"{'demurrage':>12} | {'breach':>7} | {'util':>6}")
    print(hdr)
    print("-" * 96)
    for _, r in sm.iterrows():
        print(f"{r.policy:>8} | "
              f"{r.mean_detention_hr:7.2f} +/-{r.mean_detention_hr_ci:4.2f} h | "
              f"{r.mean_wait_hr:7.2f} +/-{r.mean_wait_hr_ci:4.2f} h | "
              f"{r.mean_dwell_hr:7.2f} h | "
              f"{r.total_demurrage / 1e3:9.1f} k | "
              f"{100 * r.breach_rate:6.1f}% | "
              f"{100 * r.line_utilisation:5.1f}%")
