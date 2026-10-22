"""
run_layer4.py  -  the scenario campaign. Config only; no new model code.

    python run_layer4.py

Every scenario is a variation on the SAME verified model, run on the SAME
random scenarios, scored by the SAME accounting. That is the point of having
spent three layers on structure: a policy question is now a config change.

E12  INTERVENTIONS   ten levers, ranked by effect on detention and demurrage
E13  TERMINAL TYPE   public goods shed vs private siding vs through-distance
E14  PRICING LEVERS  free time and penal demurrage - the Railway's own
                     instruments, which change the CHARGE without changing
                     any physical thing
E15  BREAK-EVEN      infrastructure versus administration, framed so that no
                     capital-cost figure has to be invented
"""
import _bootstrap  # noqa: F401  repo root on sys.path; outputs go to results/

from dataclasses import replace
import math
import statistics as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from rtsim.config import default_config
from rtsim.distributions import Dist, RandomStreams
from rtsim.verify import run_checks as v0
from rtsim.verify_admin import run_checks as v1
from rtsim.terminal import simulate, generate_rakes
from rtsim.accounting import rake_table, kpis
from rtsim.admin import (default_steps, digitalise, remove_calendar,
                         no_rework, CAL_24_7)
from rtsim import policies

KS = ["M1", "M2", "M3", "M4", "M5", "M6", "M7"]
N_REPS = 10


def base_cfg():
    c = default_config()
    c = replace(c, rake=replace(c.rake, arrival_gap=Dist("exp", mean=22.0)))
    return replace(c, run=replace(c.run, n_rakes=25, n_reps=N_REPS,
                                 warmup_rakes=3))


def terminal_24_7(steps):
    """[IR-COMP 4.1] terminal working hours are 06:00-22:00, but the DRM may
    introduce round-the-clock working case by case. Only the steps the
    TERMINAL owns move; the railway office and the client do not."""
    out = dict(steps)
    for k in ("M4", "M5", "M6"):
        out[k] = replace(out[k], calendar=CAL_24_7)
    return out


def ci95(v):
    if len(v) < 2:
        return (v[0], 0.0)
    return st.mean(v), 1.96 * st.stdev(v) / math.sqrt(len(v))


def evaluate(cfg, steps, label):
    """Same seeds for every scenario - paired design across the campaign."""
    rows = []
    for rep in range(cfg.run.n_reps):
        seed = cfg.run.base_seed + rep
        rakes = generate_rakes(cfg, RandomStreams(seed))
        log, _, term = simulate(cfg, policies.build("FCFS", cfg), seed,
                                rakes=rakes, admin_steps=steps)
        rt = rake_table(log, cfg)
        rt = rt[rt.rake > cfg.run.warmup_rakes]
        k = kpis(rt, term, cfg)
        k["seed"] = seed
        rows.append(k)
    df = pd.DataFrame(rows)
    df["scenario"] = label
    return df


def summarise(dfs, base_label):
    """Report every scenario as a PAIRED difference from the base case."""
    base = dfs[base_label]
    out = []
    for label, df in dfs.items():
        r = {"scenario": label}
        for m in ["mean_detention_hr", "total_demurrage", "breach_rate",
                  "mean_wait_hr", "throughput_per_day",
                  "total_controllable_cost"]:
            mu, h = ci95(df[m].tolist())
            r[m], r[m + "_ci"] = mu, h
        for m in ["mean_detention_hr", "total_demurrage"]:
            d = (df[m] - base[m]).tolist()
            dm, dh = ci95(d)
            r["d_" + m], r["d_" + m + "_ci"] = dm, dh
            r["sig_" + m] = (dm - dh > 0) or (dm + dh < 0)
        out.append(r)
    return pd.DataFrame(out)


def main():
    print("\n>>> VERIFICATION")
    if not (v0() and v1()):
        raise SystemExit("verification failed")

    cfg = base_cfg()
    steps = default_steps()

    # ============================================================== E12
    print("\n\n>>> E12  INTERVENTIONS - ten levers on the same model")
    scen = {}

    scen["base (private siding)"] = (cfg, steps)

    # --- administrative levers, all cost procedure not concrete ---------
    scen["terminal works 24/7"] = (cfg, terminal_24_7(steps))
    scen["digitalise M5+M6"] = (cfg, digitalise(["M5", "M6"], steps))
    scen["digitalise all admin"] = (cfg, digitalise(KS, steps))
    scen["no rework anywhere"] = (cfg, no_rework(KS, steps))
    scen["all calendars 24/7"] = (cfg, remove_calendar(KS, steps))

    # --- physical levers, all cost capital -----------------------------
    scen["2nd loading line"] = (
        replace(cfg, resources=replace(cfg.resources, loading_lines=2)), steps)
    scen["2nd line + 2nd crew"] = (
        replace(cfg, resources=replace(cfg.resources, loading_lines=2, crews=2)),
        steps)
    scen["2nd shunting loco"] = (
        replace(cfg, resources=replace(cfg.resources, shunting_locos=2)), steps)
    scen["+50% loading rate"] = (
        replace(cfg, rake=replace(
            cfg.rake, load_rate_tph=Dist("logn", mean=1350.0, sd=375.0))), steps)

    dfs = {k: evaluate(c, s, k) for k, (c, s) in scen.items()}
    e12 = summarise(dfs, "base (private siding)").sort_values("d_mean_detention_hr")
    print(f"  {cfg.run.n_reps} replications x {cfg.run.n_rakes} rakes, "
          f"arrival gap {cfg.rake.arrival_gap.mean:.0f} h, FCFS throughout")
    print(f"  {'scenario':<24} | {'detention':>9} | {'change':>16} | "
          f"{'demurrage':>10} | {'breach':>7}")
    print("  " + "-" * 82)
    for _, r in e12.iterrows():
        flag = "*" if r.sig_mean_detention_hr else " "
        print(f"  {r.scenario:<24} | {r.mean_detention_hr:7.2f} h | "
              f"{r.d_mean_detention_hr:+7.2f} +/-{r.d_mean_detention_hr_ci:4.2f}{flag} | "
              f"{r.total_demurrage/1e6:8.2f} M | {100*r.breach_rate:6.0f}%")
    print("  (* = paired 95% CI excludes zero)")

    # ============================================================== E13
    print("\n>>> E13  TERMINAL TYPE - the free-time build-up differs")
    print("  [IR-COMP 2.2(a)(i)] mechanized loading, open wagons      5:00")
    print("  [IR-COMP 2.2.1(a)]  private siding NOT on through-distance +2:00")
    print("  [IR-COMP 2.7]       tarpaulin, coal and coke             +1:00")
    types = {
        "private siding (5+2+1)": cfg,
        "through-distance siding (5+1)": replace(
            cfg, charges=replace(cfg.charges, siding_additional_free_time_hr=0.0,
                                 siding_charge_enabled=False)),
        "public goods shed (5+1)": replace(
            cfg, charges=replace(cfg.charges, siding_additional_free_time_hr=0.0)),
    }
    e13 = []
    for label, c in types.items():
        df = evaluate(c, steps, label)
        mu, h = ci95(df.total_demurrage.tolist())
        br, _ = ci95(df.breach_rate.tolist())
        cc, _ = ci95(df.total_controllable_cost.tolist())
        e13.append({"terminal type": label,
                    "free_time_hr": c.charges.free_time_hr,
                    "demurrage": mu, "demurrage_ci": h,
                    "breach_rate": br, "controllable_cost": cc})
    e13 = pd.DataFrame(e13)
    print(e13.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print("  Note: detention is IDENTICAL across all three - nothing physical")
    print("  changed. Only who pays, and how much, moves.")

    # ============================================================== E14
    print("\n>>> E14  PRICING LEVERS - the Railway's own instruments")
    print("  These change the CHARGE without changing any physical process,")
    print("  so detention is unmoved. That is the point: a penalty is only an")
    print("  incentive if the party charged could have acted differently.")
    e14 = []
    for bft in (3.0, 4.0, 5.0, 7.0):
        for pen in (1.0, 2.0):
            c = replace(cfg, charges=replace(cfg.charges,
                                             base_free_time_hr=bft,
                                             penal_multiplier=pen))
            df = evaluate(c, steps, f"ft{bft}/pen{pen}")
            mu, _ = ci95(df.total_demurrage.tolist())
            br, _ = ci95(df.breach_rate.tolist())
            dt, _ = ci95(df.mean_detention_hr.tolist())
            e14.append({"base_free_time_hr": bft, "penal_x": pen,
                        "effective_ft_hr": c.charges.free_time_hr,
                        "demurrage": mu, "breach_rate": br,
                        "detention_hr": dt})
    e14 = pd.DataFrame(e14)
    print(e14.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    # ============================================================== E15
    print("\n>>> E15  BREAK-EVEN - administration versus concrete")
    print("  No capital-cost figure is invented here. Instead each physical")
    print("  intervention is expressed as the administrative reform it would")
    print("  have to beat. Raballand et al. (2012) make the same argument for")
    print("  ports: speeding up clearance raises capacity far more cheaply")
    print("  than building more of it.")
    b = e12.set_index("scenario")
    admin_best = b.loc["all calendars 24/7", "d_mean_detention_hr"]
    print(f"\n  {'intervention':<24} | {'kind':<14} | {'detention saved':>15} | "
          f"{'vs best admin':>13}")
    print("  " + "-" * 76)
    kind = {"terminal works 24/7": "procedure", "digitalise M5+M6": "procedure",
            "digitalise all admin": "procedure", "no rework anywhere": "procedure",
            "all calendars 24/7": "procedure", "2nd loading line": "CAPITAL",
            "2nd line + 2nd crew": "CAPITAL", "2nd shunting loco": "CAPITAL",
            "+50% loading rate": "CAPITAL"}
    for sc in e12.scenario:
        if sc.startswith("base"):
            continue
        d = b.loc[sc, "d_mean_detention_hr"]
        share = 100 * d / admin_best if admin_best != 0 else float("nan")
        print(f"  {sc:<24} | {kind.get(sc,'?'):<14} | {-d:+13.2f} h | "
              f"{share:11.0f}%")

    # -------------------------------------------------------------- charts
    fig, ax = plt.subplots(2, 2, figsize=(14.5, 9.5))

    a = ax[0, 0]
    d = e12[~e12.scenario.str.startswith("base")]
    cols = ["#c1440e" if kind.get(s) == "procedure" else "#5b7c99"
            for s in d.scenario]
    a.barh(d.scenario, -d.d_mean_detention_hr, xerr=d.d_mean_detention_hr_ci,
           capsize=3, color=cols)
    a.set_xlabel("detention hours saved per rake")
    a.set_title("E12  Procedure (orange) vs capital (blue)")
    a.invert_yaxis()

    a = ax[0, 1]
    a.barh(d.scenario, -d.d_total_demurrage / 1e6,
           xerr=d.d_total_demurrage_ci / 1e6, capsize=3, color=cols)
    a.set_xlabel("demurrage avoided (Rs million per 22 rakes)")
    a.set_title("E12  Same levers, priced")
    a.invert_yaxis()

    a = ax[1, 0]
    for pen, mk in ((1.0, "o"), (2.0, "s")):
        sub = e14[e14.penal_x == pen]
        a.plot(sub.effective_ft_hr, sub.demurrage / 1e6, marker=mk,
               label=f"penal x{pen:g}",
               color="#8c8c8c" if pen == 1 else "#c1440e")
    a.set_xlabel("effective free time (hr)")
    a.set_ylabel("demurrage (Rs million)")
    a.set_title("E14  Pricing moves the charge, not the operation")
    a.legend()

    a = ax[1, 1]
    a.bar(range(len(e13)), e13.demurrage / 1e6, yerr=e13.demurrage_ci / 1e6,
          capsize=5, color=["#c1440e", "#5b7c99", "#7a9b76"])
    a.set_xticks(range(len(e13)))
    a.set_xticklabels([t.split(" (")[0] for t in e13["terminal type"]],
                      rotation=12, ha="right", fontsize=8)
    a.set_ylabel("demurrage (Rs million)")
    a.set_title("E13  Terminal type: same operation, different bill")

    for r in ax:
        for b2 in r:
            b2.grid(axis="x", alpha=.25); b2.set_axisbelow(True)
    fig.suptitle("Layer 4 - policy scenario campaign  |  "
                 f"{N_REPS} replications, 95% CI  |  ALL RATES ASSUMED "
                 "except IR charge rules", y=1.00)
    fig.tight_layout()
    fig.savefig("layer4_results.png", dpi=150, bbox_inches="tight")

    e12.round(3).to_csv("layer4_E12_interventions.csv", index=False)
    e13.round(3).to_csv("layer4_E13_terminal_type.csv", index=False)
    e14.round(3).to_csv("layer4_E14_pricing.csv", index=False)
    print("\nSaved: layer4_results.png and three CSVs")


if __name__ == "__main__":
    main()
