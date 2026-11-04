"""
run_layer8_breakdown.py  -  WHERE the hours and the rupees come from, package by package.

    python experiments/run_layer8_breakdown.py          (~3 min, 2 cores)
    python experiments/run_layer8_breakdown.py quick

Supervisor (Nov 2026): "giving the final number is not enough - show the breakdown of how
the time and the money savings arise", and "relate the improvements to each other".

Base: the COAL (open BOXN) profile of Layer 6 (wagons, payload, overload rate, siding
type and freight from the ER RR register; free time 5+2+1 h from the IR Compendium),
50 rakes x 30 paired replications, FCFS, full admin chain. Same random numbers in every
scenario, so every difference below is paired.

Improvement levers (as in the 2-Nov pilot):
  H  terminal paperwork 24/7 (M4 placement advice, M5 weighment, M6 release reporting)
  D  digital release reporting (M6: 24/7, no rejections, half the time)
  P  precise loading (no overloading -> no weighment rework; removes punitive charges and
     paid-but-unused capacity, both from the RR register)
  L  loading 50 % faster (extra labour / equipment)
  Y  yard clutter present: loading 20 % slower (scenario for longer loader travel; ASSUMED)
Packages: TODAY; A = H+D (no construction); B = A+P; C = B+L.

Outputs (results/):
  layer8_B1_time_breakdown.csv   mean hours per rake in every segment, arrival -> departure
  layer8_B2_cause_split.csv      billed window split into loading / paperwork working time /
                                 rework / waiting for the office to open (counterfactual runs)
  layer8_B3_money.csv            demurrage per rake by IR band, data leak, per-year value, wagons,
                                 line capacity
  layer8_B4_shapley.csv          fair split of each package's saving among its levers (Shapley)
  layer8_B5_factorial.csv        all 32 combinations of H, D, P, L, Y
  layer8_B6_parties.csv          who gains what (client / siding owner, Railway)
  layer8_B7_damage.csv           wagon-damage scenarios (rtsim/damage.py), detach vs return rake
  layer8_B8_next_bottleneck.csv  RR + payment (M7) digital as well: the rake's time after removal
  layer8_results.png

Conversions (every one stated, so every rupee can be traced):
  rakes per year      = 8,760 h / mean arrival gap (model traffic: 30 h -> 292 rakes/yr)
  demurrage per year  = demurrage per rake x rakes per year
  wagon-hours saved   = (arrival -> departure saved per rake) x wagons per rake x rakes per year
  wagons freed        = wagon-hours saved / 8,760 h  (wagons kept busy all year)
  fleet value         = wagons freed x Rs 44.1 lakh  (Rs 1,140 crore / 2,583 BOXNHL/BOXNS wagons,
                        Ministry of Railways order, Oct 2026)
  line capacity       = 8,760 h / hours a rake holds the line (placement start -> removed);
                        a theoretical ceiling (locos, crews and arrivals may bind first)
  data leak per rake  = overload incidence x punitive charge + unused paid tonnes x freight/t
                        (ER RR register medians, Layer 6)
Demurrage is a transfer from client to Railway, not a saving for the economy; it is
reported per party, never added to wagon value.
"""
import _bootstrap  # noqa: F401

import itertools
import math
import sys
from dataclasses import replace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from rtsim.admin import digitalise, CAL_24_7, remove_calendar, no_rework
from rtsim.distributions import Dist
from rtsim.terminal import simulate
from rtsim.accounting import rake_table
from rtsim import policies
import run_layer5_sensitivity as L5
import run_layer6_commodities as L6

QUICK = len(sys.argv) > 1 and sys.argv[1] == "quick"
N_REPS = 10 if QUICK else 30
KS = ["M1", "M2", "M3", "M4", "M5", "M6", "M7"]
WAGON_VALUE_RS = 1140e7 / 2583              # Rs per wagon, MoR order Oct 2026 (ThePrint, 29-Oct-2026)
YARD_CLUTTER_FACTOR = 0.8                   # ASSUMED scenario: loading 20 % slower
PACKAGES = {"TODAY": "", "A paperwork 24/7 + digital release": "HD",
            "B = A + precise loading": "HDP", "C = B + faster loading": "HDPL"}
SEGMENTS = [  # column, label, inside the IR free-time window (billed)?, owner
    ("wait_hr", "waiting before placement", False, "terminal / railway"),
    ("placement_hr", "placement shunting", False, "railway"),
    ("preload_idle_hr", "placed -> loading starts (M4 advice, M2, crew, repairs)", True, "terminal"),
    ("loading_hr", "loading", True, "terminal"),
    ("release_lag_hr", "loading ends -> released (M5 weighment, M6 release)", True, "terminal"),
    ("removal_hr", "removal shunting", False, "railway"),
    ("rr_lag_hr", "removed -> departs (M7 RR + payment)", False, "client"),
]


# ---------------------------------------------------------------- scenario builders
def apply(c, s, levers="", clutter=False, calendars=True, rework=True, damage=None):
    if "H" in levers:
        s = {**s, **{k: replace(s[k], calendar=CAL_24_7) for k in ("M4", "M5", "M6")}}
    if "D" in levers:
        s = digitalise(["M6"], s)
    if "P" in levers:
        s = {**s, "M5": replace(s["M5"], rework_prob=0.0)}
    f = (1.5 if "L" in levers else 1.0) * (YARD_CLUTTER_FACTOR if clutter else 1.0)
    if f != 1.0:
        r = c.rake.load_rate_tph
        c = replace(c, rake=replace(c.rake, load_rate_tph=Dist("logn", mean=f * r.mean, sd=f * r.sd),
                                    load_rate_floor=f * c.rake.load_rate_floor))
    if not calendars:
        s = remove_calendar(KS, s)
    if not rework:
        s = no_rework(KS, s)
    if damage is not None:
        c = replace(c, damage=replace(c.damage, enabled=True, **damage))
    return c, s


def evaluate(point):
    """One configuration, all replications -> per-replication means."""
    c, s = point
    rows = []
    for rep in range(c.run.n_reps):
        log, _, term = simulate(c, policies.build("FCFS", c), c.run.base_seed + rep, admin_steps=s)
        rt = rake_table(log, c)
        rt = rt[rt.rake > c.run.warmup_rakes]
        d = {col: rt[col].mean() for col, *_ in SEGMENTS}
        d.update(detention=rt.detention_hr.mean(), cycle=rt.cycle_hr.mean(),
                 demurrage_pr=rt.demurrage.mean(), breach=(rt.excess_hr > 0).mean(),
                 occupancy=(rt.removed - rt.placement_start).mean())
        for b, val in band_split(rt.excess_hr, c).items():
            d[b] = val
        if term.damage is not None:
            dl = pd.DataFrame.from_dict(term.damage_log, orient="index")
            dl = dl[dl.index > c.run.warmup_rakes]
            d.update(rejected_share=(dl.rejected > 0).mean(), trial_line_hr=dl.trial_line_hr.mean(),
                     replacement_wait_hr=dl.replacement_wait_hr.mean(),
                     wagons_detached=dl.wagons_detached.mean(), defects_per_rake=dl.n_defect.mean(),
                     repairs_per_rake=dl.n_repairable.mean(), unfit_per_rake=dl.n_unfit.mean(),
                     loading_damage_per_rake=dl.n_loading_damage.mean(),
                     tonnes_lost=dl.tonnes_lost.mean())
            d["occupancy"] += dl.trial_line_hr.mean()      # rejected visits also hold the line
        rows.append(d)
    return pd.DataFrame(rows)


def band_split(excess, c):
    """Demurrage per rake split by IR band [IR-COMP 3.1]: Rs from the hours in each band."""
    ch, out, prev = c.charges, {}, 0.0
    w = c.rake.wagons
    for upper, mult in ch.demurrage_grades:
        hrs = (excess.clip(upper=upper) - prev).clip(lower=0)
        lab = f"dem_band_{int(prev)}_{'inf' if math.isinf(upper) else int(upper)}h"
        out[lab] = (hrs * ch.demurrage_per_wagon_hr * mult * ch.penal_multiplier * w).mean()
        prev = upper
    return out


def mean_of(df):
    return df.mean()


# ---------------------------------------------------------------- Shapley
def shapley(values, players):
    """values: dict frozenset(levers) -> scalar (e.g. detention). Returns each lever's
    average marginal effect over all orders in which the levers could be added."""
    n, out = len(players), {}
    for p in players:
        tot = 0.0
        others = [q for q in players if q != p]
        for k in range(len(others) + 1):
            for S in itertools.combinations(others, k):
                S = frozenset(S)
                w = math.factorial(len(S)) * math.factorial(n - len(S) - 1) / math.factorial(n)
                tot += w * (values[S | {p}] - values[S])
        out[p] = tot
    return out


def main():
    prof = [p for p in L6.refresh_from_field([dict(p) for p in L6.PROFILES])
            if p["name"] == "COAL (open BOXN)"][0]
    c0, s0 = L6.build(prof, n_reps=N_REPS)
    rakes_yr = 8760.0 / c0.rake.arrival_gap.mean
    W = c0.rake.wagons
    leak = L6.leak_per_rake(prof)

    # ------------------------------------------------ build every scenario once
    pts, keys = [], []
    for combo in itertools.product([0, 1], repeat=5):            # B5 factorial (H D P L Y)
        lev = "".join(x for x, on in zip("HDPL", combo[:4]) if on)
        pts.append(apply(c0, s0, lev, clutter=bool(combo[4]))); keys.append(("fact", combo))
    for name, lev in PACKAGES.items():                           # B2 counterfactuals
        for tag, kw in (("no_calendar", dict(calendars=False)), ("no_rework", dict(rework=False)),
                        ("neither", dict(calendars=False, rework=False))):
            pts.append(apply(c0, s0, lev, **kw)); keys.append(("cause", name, tag))
    dmg_levels = [0.005, 0.01, 0.02]                              # B7 damage
    for name in ("TODAY", "C = B + faster loading"):
        for pol in ("detach", "return_rake"):
            for p in dmg_levels:
                pts.append(apply(c0, s0, PACKAGES[name], damage=dict(p_defect_per_wagon=p, unfit_policy=pol)))
                keys.append(("dmg", name, pol, p))
        pts.append(apply(c0, s0, PACKAGES[name], damage=dict(p_loading_damage_per_wagon=0.01)))
        keys.append(("dmg", name, "loading damage 1 %", 0.0))
    for name in PACKAGES:                                         # B8
        c_, s_ = apply(c0, s0, PACKAGES[name])
        pts.append((c_, digitalise(["M7"], s_))); keys.append(("m7", name))
    res = dict(zip(keys, run_all(pts)))

    fact = {k[1]: v for k, v in res.items() if k[0] == "fact"}
    def F(lev="", clutter=0):
        return fact[tuple(int(x in lev) for x in "HDPL") + (clutter,)]
    pk = {name: F(lev) for name, lev in PACKAGES.items()}
    today = pk["TODAY"].mean()

    # ------------------------------------------------ B1 time breakdown
    b1 = []
    for name, df in pk.items():
        m = df.mean()
        row = {"package": name}
        for col, lab, billed, owner in SEGMENTS:
            row[col] = m[col]
        row.update(detention_billed_window=m.detention, arrival_to_departure=m.cycle,
                   line_held_per_rake=m.occupancy, breach_share=m.breach)
        b1.append(row)
    b1 = pd.DataFrame(b1)
    seg_meta = pd.DataFrame(SEGMENTS, columns=["column", "segment", "inside_free_time_window", "owner"])

    # ------------------------------------------------ B2 cause split of the billed window
    b2 = []
    for name in PACKAGES:
        full = pk[name].detention.mean()
        nocal = res[("cause", name, "no_calendar")].detention.mean()
        neither = res[("cause", name, "neither")].detention.mean()
        load = pk[name].loading_hr.mean()
        b2.append({"package": name, "detention_h": full,
                   "loading_physical_h": load,
                   "paperwork_working_time_h": neither - load,
                   "rework_h": nocal - neither,
                   "waiting_for_office_to_open_h": full - nocal,
                   "check_sum_h": load + (neither - load) + (nocal - neither) + (full - nocal)})
    b2 = pd.DataFrame(b2)

    # ------------------------------------------------ B3 money, wagons, capacity
    b3 = []
    for name, lev in PACKAGES.items():
        m = pk[name].mean()
        leak_now = 0.0 if "P" in lev else leak
        hrs_saved = today.cycle - m.cycle
        wagons = hrs_saved * W * rakes_yr / 8760.0
        row = {"package": name, "demurrage_per_rake": m.demurrage_pr,
               **{k: m[k] for k in m.index if k.startswith("dem_band_")},
               "data_leak_per_rake": leak_now, "client_cost_per_rake": m.demurrage_pr + leak_now,
               "rakes_per_year": rakes_yr,
               "demurrage_saved_Rs_cr_per_yr": (today.demurrage_pr - m.demurrage_pr) * rakes_yr / 1e7,
               "leak_saved_Rs_cr_per_yr": (leak - leak_now) * rakes_yr / 1e7,
               "rake_hours_saved_per_rake": hrs_saved,
               "wagon_hours_saved_per_yr": hrs_saved * W * rakes_yr,
               "wagons_freed": wagons, "fleet_value_Rs_cr": wagons * WAGON_VALUE_RS / 1e7,
               "wagons_freed_wait_plus_detention_basis": ((today.wait_hr + today.detention)
                                                          - (m.wait_hr + m.detention)) * W * rakes_yr / 8760.0,
               "line_held_h": m.occupancy, "line_capacity_rakes_per_yr": 8760.0 / m.occupancy,
               "capacity_vs_today": today.occupancy / m.occupancy}
        b3.append(row)
    b3 = pd.DataFrame(b3)

    # ------------------------------------------------ B4 Shapley split of each package's saving
    b4 = []
    for name, lev in PACKAGES.items():
        if not lev:
            continue
        players = list(lev)
        for metric in ("detention", "demurrage_pr", "cycle"):
            vals = {frozenset(S): F("".join(S))[metric].mean()
                    for k in range(len(players) + 1) for S in itertools.combinations(players, k)}
            sh = shapley(vals, players)
            singles = {p: vals[frozenset(p)] - vals[frozenset()] for p in players}
            for p in players:
                b4.append({"package": name, "metric": metric, "lever": p,
                           "shapley_change": sh[p], "alone_change": singles[p],
                           "package_change": vals[frozenset(players)] - vals[frozenset()],
                           "sum_of_alone": sum(singles.values())})
    b4 = pd.DataFrame(b4)
    b4["lever_name"] = b4.lever.map({"H": "terminal paperwork 24/7", "D": "digital release reporting",
                                     "P": "precise loading", "L": "loading 50 % faster"})

    # ------------------------------------------------ B5 factorial table
    b5 = pd.DataFrame([dict(zip("HDPLY", k), **v.mean()[["detention", "wait_hr", "demurrage_pr", "occupancy",
                                                            "cycle"]].to_dict()) for k, v in fact.items()])

    # ------------------------------------------------ B6 parties
    b6 = []
    for _, r in b3.iterrows():
        if r.package == "TODAY":
            continue
        b6 += [
            {"package": r.package, "party": "client / siding owner",
             "gain": "demurrage avoided", "Rs_cr_per_yr": r.demurrage_saved_Rs_cr_per_yr},
            {"package": r.package, "party": "client / siding owner",
             "gain": "overload penalties + paid-unused capacity avoided (data)", "Rs_cr_per_yr": r.leak_saved_Rs_cr_per_yr},
            {"package": r.package, "party": "client / siding owner",
             "gain": f"line capacity x{r.capacity_vs_today:.2f} ({r.line_capacity_rakes_per_yr:.0f} rakes/yr ceiling)",
             "Rs_cr_per_yr": np.nan},
            {"package": r.package, "party": "Railway",
             "gain": f"wagon time back: {r.wagons_freed:.1f} wagons (one-time fleet value Rs {r.fleet_value_Rs_cr:.1f} cr)",
             "Rs_cr_per_yr": np.nan},
            {"package": r.package, "party": "Railway",
             "gain": "demurrage income forgone (transfer, not a loss to the economy)",
             "Rs_cr_per_yr": -r.demurrage_saved_Rs_cr_per_yr},
        ]
    b6 = pd.DataFrame(b6)

    # ------------------------------------------------ B7 damage
    b7 = []
    for name in ("TODAY", "C = B + faster loading"):
        ref = pk[name].mean()
        for k, df in res.items():
            if k[0] != "dmg" or k[1] != name:
                continue
            m = df.mean()
            b7.append({"package": name, "policy": k[2], "p_defect_per_wagon": k[3],
                       "defects_per_rake": m.get("defects_per_rake", np.nan),
                       "unfit_per_rake": m.get("unfit_per_rake", np.nan),
                       "rakes_rejected_share": m.get("rejected_share", np.nan),
                       "wagons_detached_per_rake": m.get("wagons_detached", np.nan),
                       "loading_damage_per_rake": m.get("loading_damage_per_rake", np.nan),
                       "detention_h": m.detention, "d_detention_h": m.detention - ref.detention,
                       "wait_h": m.wait_hr, "d_wait_h": m.wait_hr - ref.wait_hr,
                       "d_arrival_to_departure_h": m.cycle - ref.cycle,
                       "demurrage_per_rake": m.demurrage_pr, "d_demurrage_per_rake": m.demurrage_pr - ref.demurrage_pr,
                       "d_demurrage_Rs_cr_per_yr": (m.demurrage_pr - ref.demurrage_pr) * rakes_yr / 1e7,
                       "wagons_tied_up": (m.cycle - ref.cycle) * W * rakes_yr / 8760.0,
                       "line_held_h": m.occupancy, "tonnes_lost_per_rake": m.get("tonnes_lost", np.nan)})
    b7 = pd.DataFrame(b7)

    # ------------------------------------------------ B8 next bottleneck: RR + payment (M7)
    # The ER register shows RR issue and payment are already electronic for coal full rakes
    # (eT-RR 99.7 %, e-payment 87 %, on-account 13 %, manual 0.02 %), so the model's M7 on
    # railway-office hours is pessimistic. Both bases are reported; savings are always
    # compared like for like (TODAY under the same M7 assumption).
    b8 = []
    today_dig = res[("m7", "TODAY")].mean()
    for name in PACKAGES:
        for m7_digital in (False, True):
            m = (res[("m7", name)] if m7_digital else pk[name]).mean()
            ref = today_dig if m7_digital else today
            hrs = ref.cycle - m.cycle
            b8.append({"package": name, "RR_and_payment_digital": m7_digital, "detention_h": m.detention,
                       "removed_to_departure_h": m.rr_lag_hr, "arrival_to_departure_h": m.cycle,
                       "rake_hours_saved_vs_today_same_basis": hrs,
                       "wagons_freed": hrs * W * rakes_yr / 8760.0,
                       "fleet_value_Rs_cr": hrs * W * rakes_yr / 8760.0 * WAGON_VALUE_RS / 1e7})
    b8 = pd.DataFrame(b8)
    dig = b8[b8.RR_and_payment_digital].set_index("package")
    b3["wagons_freed_RR_digital"] = b3.package.map(dig.wagons_freed)
    b3["fleet_value_RR_digital_Rs_cr"] = b3.package.map(dig.fleet_value_Rs_cr)
    for i, r in b6.iterrows():
        if r.gain.startswith("wagon time back"):
            row = b3.set_index("package").loc[r.package]
            b6.loc[i, "gain"] = (f"wagon time back: {row.wagons_freed_RR_digital:.1f} wagons (Rs "
                                 f"{row.fleet_value_RR_digital_Rs_cr:.1f} cr one-time fleet value) with RR + payment "
                                 f"digital as the data show; {row.wagons_freed:.1f} wagons (Rs {row.fleet_value_Rs_cr:.1f} cr) "
                                 f"if RR waits for office hours")

    # ------------------------------------------------ print + save
    pd.set_option("display.width", 220)
    ff = lambda v: f"{v:,.2f}"
    print(f"\n>>> BASE: COAL (open BOXN), {W} wagons, {c0.rake.wagons * c0.rake.tonnes_per_wagon:,.0f} t/rake, "
          f"{N_REPS} reps x {c0.run.n_rakes} rakes, {rakes_yr:.0f} rakes/yr, free time {c0.charges.free_time_hr:.0f} h")
    print("\n>>> B1  TIME BREAKDOWN (h per rake, arrival -> departure)")
    print(b1.set_index("package").T.to_string(float_format=ff))
    print("\n>>> B2  WHY THE BILLED WINDOW IS THAT LONG (h per rake)")
    print(b2.to_string(index=False, float_format=ff))
    print("\n>>> B3  MONEY, WAGONS, CAPACITY")
    print(b3.set_index("package").T.to_string(float_format=ff))
    print("\n>>> B4  SHAPLEY SPLIT OF EACH PACKAGE'S SAVING")
    print(b4.to_string(index=False, float_format=ff))
    print("\n>>> B6  WHO GAINS WHAT")
    print(b6.to_string(index=False, float_format=ff))
    print("\n>>> B7  WAGON DAMAGE (change vs the same package without damage)")
    print(b7.to_string(index=False, float_format=ff))
    print("\n>>> B8  NEXT BOTTLENECK: RR + PAYMENT (M7) - rake time after it leaves the line")
    print(b8.to_string(index=False, float_format=ff))
    seg_meta.to_csv("layer8_B0_segment_definitions.csv", index=False)
    for nm, t in (("B1_time_breakdown", b1), ("B2_cause_split", b2), ("B3_money", b3), ("B4_shapley", b4),
                  ("B5_factorial", b5), ("B6_parties", b6), ("B7_damage", b7), ("B8_next_bottleneck", b8)):
        t.round(4).to_csv(f"layer8_{nm}.csv", index=False)
    chart(b1, b2, b3, b4, b7)
    print("\nSaved: layer8_B0..B8 CSVs and layer8_results.png")


def run_all(pts):
    from concurrent.futures import ProcessPoolExecutor
    if L5.WORKERS == 1:
        return [evaluate(p) for p in pts]
    with ProcessPoolExecutor(L5.WORKERS) as ex:
        return list(ex.map(evaluate, pts, chunksize=1))


def chart(b1, b2, b3, b4, b7):
    fig, ax = plt.subplots(2, 2, figsize=(17, 11))
    a = ax[0, 0]
    cols = ["loading_physical_h", "paperwork_working_time_h", "rework_h", "waiting_for_office_to_open_h"]
    b2.set_index("package")[cols].plot.barh(stacked=True, ax=a)
    a.set_xlabel("h per rake (IR detention, placement -> release)"); a.set_title("B2  Why the billed window is that long")
    a.invert_yaxis()
    a = ax[0, 1]
    bands = [c for c in b3.columns if c.startswith("dem_band_")]
    (b3.set_index("package")[bands] / 1e3).plot.barh(stacked=True, ax=a)
    a.set_xlabel("Rs thousand per rake"); a.set_title("B3  Demurrage per rake by IR band"); a.invert_yaxis()
    a = ax[1, 0]
    s = b4[(b4.metric == "detention") & (b4.package == b4.package.iloc[-1])]
    a.barh(s.lever_name, -s.shapley_change, label="share of the package saving (Shapley)")
    a.barh(s.lever_name, -s.alone_change, height=0.3, label="saving if done alone")
    a.set_xlabel("h of detention saved per rake"); a.legend(); a.set_title("B4  Package C: fair split of the saving")
    a = ax[1, 1]
    for (pkg, pol), g in b7[b7.policy.isin(["detach", "return_rake"])].groupby(["package", "policy"]):
        a.plot(100 * g.p_defect_per_wagon, g.d_arrival_to_departure_h, marker="o", label=f"{pkg[:5]} {pol}")
    a.set_xlabel("wagons defective on arrival (%)"); a.set_ylabel("extra rake hours per rake (arrival -> departure)")
    a.legend(fontsize=8); a.set_title("B7  Wagon damage: detach vs return the rake")
    fig.suptitle("Layer 8 - breakdown of time and money | coal BOXN profile | admin durations, damage rates ASSUMED",
                 y=1.0)
    fig.tight_layout()
    fig.savefig("layer8_results.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
