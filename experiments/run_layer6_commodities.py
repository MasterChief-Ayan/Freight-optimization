"""
run_layer6_commodities.py  -  which levers matter for WHICH mineral?

    python experiments/run_layer6_commodities.py          (~6 min, 2 cores)
    python experiments/run_layer6_commodities.py quick

Supervisor's ask (8-9 Oct): "in case of multiple minerals, what should we focus on
in each, so that time or cost is reduced - some features are material-specific,
some are general."

Each commodity becomes a PROFILE of the same verified model (no model code changes):

  from the field data (ER RR register 2022-26, tools/analyse_rr_register.py)
      wagons per full rake, payload per wagon, overload incidence (-> M5
      weighment-rework probability), private-siding vs goods-shed share
      (-> +2 h siding free time or not), freight per tonne, punitive overloading
      charge, capacity paid for but not loaded
  from the MoR Compendium 03.04.2024, para 2.2 / 2.2(b) / 2.7
      LOADING free time of the dominant wagon type (open/hopper mech 5:00,
      covered manual 31+ wagons 9:00, crane-handled >30 wagons 7:00,
      container 3:00, tank 30+ wagons 8:00), tarpaulin +1:00 for coal only
  ASSUMED (no field measurement exists - flagged on every output)
      loading rate by handling method: mechanised bulk 900 t/h (model base),
      manual bagged into covered wagons 300-350 t/h, crane 450 t/h,
      reach-stacker 600 t/h, pumping 600 t/h; sd = 28 % of mean

Everything else (admin chain M1-M7, calendars, arrivals, charges) is the calibrated
base. The model represents the LOADING terminal; the RR register is the
RECEIVING side of the same consignments, so commodity attributes (wagon type,
rake size, payload, overloading) carry over, terminal-side times do not.

C1  BASELINE per commodity: detention, wait, demurrage, model cost per rake, plus
    the data's 'leak' per rake (expected punitive overloading + unused paid capacity).
C2  LEVERS per commodity, paired against that commodity's own base:
      general   G1 terminal 24/7 (M4-M6)  G2 digitalise M6  G3 digitalise M5
                G4 2nd line + 2nd crew
      specific  S1 loading rate +50 % (more labour / mechanisation)
                S2 precise loading (no overload -> M5 rework 0; removes punitive
                   charge and unused-capacity leak, both from data)
      risk      R1 free time cut to 3:00 - only where IR allows it (coal, iron
                   ore single-line loading, [IR-COMP 2.2(c)]): a pricing change
    Classes (spread = (max-min)/|mean| of the detention effect across commodities):
      GENERAL, uniform                   same sign everywhere, spread < 0.5
      GENERAL, size depends on material  same sign everywhere, spread < 1.5
      MATERIAL-SPECIFIC                  sign changes, or spread >= 1.5
      PRICING                            changes the bill, not the time
C3  PER-COMMODITY TORNADO: the nine time-moving parameters of Layer 5, each moved
    -50 % / +50 % around THAT commodity's base -> swing in detention and in cost per
    rake, per commodity (heat map).
C4  LABOUR BREAK-EVEN: S1's saving per rake is the most one can spend per rake on
    extra loading labour/equipment before it stops paying (no labour cost invented).
"""
import _bootstrap  # noqa: F401

import math
import os
import sys
from dataclasses import replace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from rtsim.config import default_config
from rtsim.distributions import Dist
from rtsim.admin import default_steps, digitalise, CAL_24_7
import run_layer5_sensitivity as L5

QUICK = len(sys.argv) > 1 and sys.argv[1] == "quick"
N_REPS = 10 if QUICK else 30
FIELD = os.path.join(_bootstrap.RESULTS, "field")

# ----------------------------------------------------------------------
# commodity profiles  (data values are read from results/field when present;
# the numbers below are the 22-Oct-2026 values, used as fallback)
# ----------------------------------------------------------------------
PROFILES = [
    # name, wagon, wagons, t/wagon, overload, private siding, freight Rs/t,
    # base free time h, tarpaulin, load rate t/h (method), punitive Rs/overloaded RR,
    # unused paid t/rake, 3h-cut allowed
    dict(name="COAL (open BOXN)", wagon="open", wagons=58, tpw=67.21, overload=0.304,
         private=0.81, freight_t=899.7, base_ft=5.0, tarp=True, rate=900, method="mechanised",
         punitive=3116.8, unused_t=158.9, cut3=True, group="COAL"),
    dict(name="COAL (hopper BOBRN)", wagon="hopper", wagons=58, tpw=61.29, overload=0.405,
         private=0.957, freight_t=517.4, base_ft=5.0, tarp=False, rate=900, method="mechanised",
         punitive=3116.8, unused_t=158.9, cut3=True, group="COAL"),
    dict(name="IRON ORE", wagon="open", wagons=58, tpw=68.21, overload=0.037, private=0.738,
         freight_t=807.6, base_ft=5.0, tarp=False, rate=900, method="mechanised",
         punitive=15685.9, unused_t=162.4, cut3=True, group="IRON ORE"),
    dict(name="CLINKER", wagon="open", wagons=58, tpw=68.65, overload=0.214, private=0.963,
         freight_t=1316.9, base_ft=5.0, tarp=False, rate=900, method="mechanised",
         punitive=2385.8, unused_t=47.3, cut3=False, group="CLINKER"),
    dict(name="CEMENT (bagged, BCN)", wagon="covered", wagons=42, tpw=65.66, overload=0.014,
         private=0.005, freight_t=546.9, base_ft=9.0, tarp=False, rate=350, method="manual",
         punitive=4224.1, unused_t=4.2, cut3=False, group="CEMENT"),
    dict(name="FOODGRAINS", wagon="covered", wagons=42, tpw=64.93, overload=0.008, private=0.318,
         freight_t=2032.5, base_ft=9.0, tarp=False, rate=300, method="manual",
         punitive=18909.9, unused_t=0.0, cut3=False, group="FOODGRAINS"),
    dict(name="FERTILISER", wagon="covered", wagons=42, tpw=63.80, overload=0.010, private=0.0,
         freight_t=1171.2, base_ft=9.0, tarp=False, rate=300, method="manual",
         punitive=3095.9, unused_t=37.4, cut3=False, group="FERTILISER"),
    dict(name="IRON & STEEL (flat, crane)", wagon="flat", wagons=58, tpw=63.0, overload=0.053,
         private=0.959, freight_t=740.6, base_ft=7.0, tarp=False, rate=450, method="crane",
         punitive=768.7, unused_t=123.2, cut3=False, group="IRON & STEEL"),
    dict(name="CONTAINERS", wagon="flat", wagons=45, tpw=36.91, overload=0.019, private=0.746,
         freight_t=1715.6, base_ft=3.0, tarp=False, rate=600, method="reach-stacker",
         punitive=8460.5, unused_t=0.0, cut3=False, group="CONTAINERS"),
    dict(name="POL (tank)", wagon="tank", wagons=49, tpw=54.28, overload=0.004, private=0.982,
         freight_t=1174.7, base_ft=8.0, tarp=False, rate=600, method="pumping",
         punitive=3719.8, unused_t=0.0, cut3=False, group="POL"),
]


def refresh_from_field(profiles):
    """Overwrite the data-derived fields with the current field outputs, if present."""
    f1 = os.path.join(FIELD, "F1_commodity_profiles.csv")
    f5 = os.path.join(FIELD, "F5_coal_by_wagon.csv")
    if not os.path.exists(f1):
        return profiles
    p = pd.read_csv(f1).set_index("group")
    cw = pd.read_csv(f5).set_index("wagon_type_filled") if os.path.exists(f5) else None
    for pr in profiles:
        if pr["group"] == "COAL" and cw is not None:
            key = "OPEN WAGON" if pr["wagon"] == "open" else "HOPPER WAGON"
            r = cw.loc[key]
            pr.update(wagons=float(r.wagons), tpw=float(r.t_per_wagon),
                      overload=float(r.overload_incidence), private=float(r.private_siding_share),
                      freight_t=float(r.freight_per_t))
        elif pr["group"] in p.index:
            r = p.loc[pr["group"]]
            pr.update(wagons=float(r.median_wagons_full_rake), tpw=float(r.t_per_wagon_median),
                      overload=float(r.overload_incidence), private=float(r.private_siding_share),
                      freight_t=float(r.freight_per_t_median))
        if pr["group"] in p.index:
            r = p.loc[pr["group"]]
            pr.update(punitive=float(r.punitive_per_overloaded_RR),
                      unused_t=float(r.paid_unused_t_per_full_rake)
                      if not math.isnan(r.paid_unused_t_per_full_rake) else 0.0)
    return profiles


def build(pr, n_reps=N_REPS):
    c = default_config()
    rate = pr["rate"]
    c = replace(c,
                rake=replace(c.rake, wagons=int(round(pr["wagons"])), tonnes_per_wagon=pr["tpw"],
                             load_rate_tph=Dist("logn", mean=rate, sd=0.28 * rate),
                             load_rate_floor=0.33 * rate),
                charges=replace(c.charges, base_free_time_hr=pr["base_ft"],
                                siding_additional_free_time_hr=2.0 if pr["private"] >= 0.5 else 0.0,
                                tarpaulin_applies=pr["tarp"], freight_per_tonne=pr["freight_t"]),
                run=replace(c.run, n_reps=n_reps), label=pr["name"])
    s = default_steps()
    s["M5"] = replace(s["M5"], rework_prob=min(0.9, pr["overload"]))
    return c, s


def leak_per_rake(pr):
    """Money lost per rake that the data shows but the timing model does not:
    expected punitive overloading charge + freight paid on capacity not loaded."""
    return pr["overload"] * pr["punitive"] + pr["unused_t"] * pr["freight_t"]


def levers(pr, c, s):
    L = {
        "G1 terminal 24/7 (M4-M6)": (c, {**s, **{k: replace(s[k], calendar=CAL_24_7)
                                                  for k in ("M4", "M5", "M6")}}),
        "G2 digitalise M6 release reporting": (c, digitalise(["M6"], s)),
        "G3 digitalise M5 weighment": (c, digitalise(["M5"], s)),
        "G4 2nd line + 2nd crew": (replace(c, resources=replace(c.resources, loading_lines=2, crews=2)), s),
        "S1 loading rate +50 % (labour/mechanisation)": (
            replace(c, rake=replace(c.rake, load_rate_tph=Dist(
                "logn", mean=1.5 * c.rake.load_rate_tph.mean, sd=1.5 * c.rake.load_rate_tph.sd))), s),
        "S2 precise loading (no overload)": (c, {**s, "M5": replace(s["M5"], rework_prob=0.0)}),
    }
    if pr["cut3"]:
        L["R1 RISK: free time cut to 3:00 [IR-COMP 2.2(c)]"] = (
            replace(c, charges=replace(c.charges, base_free_time_hr=3.0)), s)
    return L


TORNADO = [   # (id, label, apply(c, s, f))
    ("hours", "terminal working hours (M4-M6) 8 h / 24 h",
     lambda c, s, f: (c, {**s, **{k: replace(s[k], calendar=L5._cal_hours(s[k].calendar, 8.0 if f < 1 else 24.0))
                                    for k in ("M4", "M5", "M6")}})),
    ("load_rate", "loading rate", lambda c, s, f: (replace(c, rake=replace(c.rake, load_rate_tph=Dist(
        "logn", mean=f * c.rake.load_rate_tph.mean, sd=f * c.rake.load_rate_tph.sd))), s)),
    ("M6_mean", "M6 release-reporting time", lambda c, s, f: (c, L5._with_steps(
        s, ["M6"], lambda t: L5._svc(t, mean=f * t.service.mean, sd=f * t.service.sd)))),
    ("M5_mean", "M5 weighment time", lambda c, s, f: (c, L5._with_steps(
        s, ["M5"], lambda t: L5._svc(t, mean=f * t.service.mean, sd=f * t.service.sd)))),
    ("M4_mean", "M4 placement-advice time", lambda c, s, f: (c, L5._with_steps(
        s, ["M4"], lambda t: L5._svc(t, mean=f * t.service.mean, sd=f * t.service.sd)))),
    ("M5_rework", "M5 rework (overload) probability", lambda c, s, f: (c, {**s, "M5": replace(
        s["M5"], rework_prob=min(0.9, f * s["M5"].rework_prob))})),
    ("M6_rework", "M6 rework probability", lambda c, s, f: (c, {**s, "M6": replace(
        s["M6"], rework_prob=min(0.9, f * s["M6"].rework_prob))})),
    ("placement", "placement shunting time", lambda c, s, f: (replace(c, shunting=replace(
        c.shunting, placement=Dist("logn", mean=f * 1.0, sd=f * 0.3))), s)),
    ("removal", "removal shunting time", lambda c, s, f: (replace(c, shunting=replace(
        c.shunting, removal=Dist("logn", mean=f * 1.0, sd=f * 0.3))), s)),
]


def main():
    profs = refresh_from_field([dict(p) for p in PROFILES])
    bases = [build(p) for p in profs]
    base_res = L5.run_points([(c, s, "FCFS") for c, s in bases])

    # ---------------------------------------------------------------- C1
    c1 = []
    for p, (c, s), df in zip(profs, bases, base_res):
        c1.append({"commodity": p["name"], "wagons": int(round(p["wagons"])), "t_per_wagon": p["tpw"],
                   "t_per_rake": p["wagons"] * p["tpw"], "load_method": p["method"],
                   "load_rate_tph_ASSUMED": p["rate"], "loading_h": p["wagons"] * p["tpw"] / p["rate"],
                   "free_time_h": c.charges.free_time_hr, "M5_rework_from_overload": p["overload"],
                   "detention_h": df.detention.mean(), "wait_h": df.wait.mean(),
                   "breach_rate": df.breach.mean(), "demurrage_per_rake": df.demurrage_pr.mean(),
                   "model_cost_per_rake": df.cost_pr.mean(), "data_leak_per_rake": leak_per_rake(p),
                   "freight_per_rake": p["wagons"] * p["tpw"] * p["freight_t"]})
    c1 = pd.DataFrame(c1)
    c1["avoidable_cost_per_rake"] = c1.model_cost_per_rake + c1.data_leak_per_rake
    c1["avoidable_pct_of_freight"] = c1.avoidable_cost_per_rake / c1.freight_per_rake
    print(f"\n>>> C1  BASELINE PER COMMODITY  ({N_REPS} reps x 50 rakes, FCFS)")
    print(c1[["commodity", "t_per_rake", "load_method", "loading_h", "free_time_h",
              "M5_rework_from_overload", "detention_h", "breach_rate", "demurrage_per_rake",
              "data_leak_per_rake", "avoidable_pct_of_freight"]].to_string(
        index=False, float_format=lambda v: f"{v:,.2f}"))

    # ---------------------------------------------------------------- C2
    pts, keys = [], []
    for i, (p, (c, s)) in enumerate(zip(profs, bases)):
        for lab, (cc, ss) in levers(p, c, s).items():
            pts.append((cc, ss, "FCFS")); keys.append((i, lab))
    res = L5.run_points(pts)
    rows = []
    for (i, lab), df in zip(keys, res):
        p, b = profs[i], base_res[i]
        d_det, h_det, sig = L5.paired(b, df, "detention")
        d_cost, h_cost, _ = L5.paired(b, df, "cost_pr")
        leak_saved = leak_per_rake(p) if lab.startswith("S2") else 0.0
        rows.append({"commodity": p["name"], "lever": lab, "d_detention_h": d_det, "ci": h_det,
                     "significant": sig, "d_demurrage_per_rake": df.demurrage_pr.mean() - b.demurrage_pr.mean(),
                     "d_model_cost_per_rake": d_cost, "data_leak_saved_per_rake": leak_saved,
                     "total_saving_per_rake": -d_cost + leak_saved})
    c2 = pd.DataFrame(rows)
    cls = []
    for lab, g in c2.groupby("lever"):
        v = g.d_detention_h
        same_sign = (v <= 0.05).all() or (v >= -0.05).all()
        spread = (v.max() - v.min()) / max(abs(v.mean()), 1e-9)
        cls.append({"lever": lab, "mean_d_detention_h": v.mean(), "min": v.min(), "max": v.max(),
                    "relative_spread": spread, "n_commodities": len(g),
                    "class": ("PRICING (moves money, not time)" if lab.startswith("R")
                              else "GENERAL, uniform" if (same_sign and spread < 0.5 and len(g) == len(profs))
                              else "GENERAL, size depends on material" if (same_sign and spread < 1.5
                                                                           and len(g) == len(profs))
                              else "MATERIAL-SPECIFIC")})
    cls = pd.DataFrame(cls).sort_values("mean_d_detention_h")
    print("\n>>> C2  LEVERS x COMMODITIES  (change in detention, h; paired 95 % CI)")
    piv = c2.pivot(index="lever", columns="commodity", values="d_detention_h")
    print(piv.round(2).to_string())
    print("\n  total saving per rake (Rs) = model cost avoided + data leak avoided")
    print(c2.pivot(index="lever", columns="commodity", values="total_saving_per_rake").round(0).to_string())
    print("\n  classification")
    print(cls.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    # ---------------------------------------------------------------- C3
    pts, keys = [], []
    for i, (c, s) in enumerate(bases):
        for tid, _, fn in TORNADO:
            for f in (0.5, 1.5):
                cc, ss = fn(c, s, f)
                pts.append((cc, ss, "FCFS")); keys.append((i, tid, f))
    res = L5.run_points(pts)
    tor = pd.DataFrame([{"commodity": profs[i]["name"], "param": tid, "factor": f,
                         "detention": df.detention.mean(), "cost_pr": df.cost_pr.mean()}
                        for (i, tid, f), df in zip(keys, res)])
    sw = (tor.groupby(["commodity", "param"])
          .agg(det_lo=("detention", "first"), det_hi=("detention", "last"),
               cost_lo=("cost_pr", "first"), cost_hi=("cost_pr", "last")).reset_index())
    sw["detention_swing_h"] = (sw.det_hi - sw.det_lo).abs()
    sw["cost_swing_per_rake"] = (sw.cost_hi - sw.cost_lo).abs()
    sw["rank_in_commodity"] = sw.groupby("commodity").detention_swing_h.rank(ascending=False).astype(int)
    heat = sw.pivot(index="param", columns="commodity", values="detention_swing_h")
    print("\n>>> C3  SWING IN DETENTION (h) PER PARAMETER (-50 % .. +50 %), PER COMMODITY")
    print(heat.round(2).to_string())
    top3 = (sw.sort_values(["commodity", "rank_in_commodity"]).groupby("commodity")
            .head(3).groupby("commodity").param.apply(lambda x: ", ".join(x)))
    print("\n  top-3 levers per commodity:")
    print(top3.to_string())

    # ---------------------------------------------------------------- C4
    s1 = c2[c2.lever.str.startswith("S1")][["commodity", "d_detention_h", "d_demurrage_per_rake",
                                            "total_saving_per_rake"]].copy()
    # cash-only: demurrage actually billed; the full figure also counts the ASSUMED
    # opportunity cost of rake time (idle_cost_per_hr) and siding charges
    s1["max_spend_cash_only_Rs"] = -s1.d_demurrage_per_rake
    s1 = s1.merge(c1[["commodity", "loading_h", "load_method"]], on="commodity")
    s1["loading_h_saved"] = s1.loading_h / 3.0          # +50 % rate -> one third less loading time
    s1["breakeven_Rs_per_loading_hour_saved"] = s1.total_saving_per_rake / s1.loading_h_saved
    print("\n>>> C4  LABOUR / EQUIPMENT BREAK-EVEN  (spend per rake below this and S1 pays)")
    print(s1.rename(columns={"total_saving_per_rake": "max_spend_per_rake_Rs"}).to_string(
        index=False, float_format=lambda v: f"{v:,.0f}"))

    c1.round(4).to_csv("layer6_C1_commodity_baseline.csv", index=False)
    c2.round(4).to_csv("layer6_C2_levers.csv", index=False)
    cls.round(4).to_csv("layer6_C2_lever_classes.csv", index=False)
    sw.round(4).to_csv("layer6_C3_tornado_by_commodity.csv", index=False)
    s1.round(4).to_csv("layer6_C4_labour_breakeven.csv", index=False)
    chart(c1, c2, heat, s1)
    print("\nSaved: layer6_results.png and five CSVs")


def chart(c1, c2, heat, s1):
    fig, ax = plt.subplots(2, 2, figsize=(18, 13))
    order = c1.sort_values("detention_h").commodity
    a = ax[0, 0]
    c = c1.set_index("commodity").loc[order]
    a.barh(order, c.detention_h, color="#5b7c99", label="detention (model)")
    a.scatter(c.free_time_h, order, color="#c1440e", zorder=5, label="free time (IR rule)")
    a.set_xlabel("hours"); a.legend(); a.set_title("C1  Detention vs the free time each commodity gets")
    a = ax[0, 1]
    piv = c2.pivot(index="lever", columns="commodity", values="d_detention_h").reindex(columns=order)
    im = a.imshow(piv.values, cmap="RdBu_r", vmin=-np.nanmax(abs(piv.values)), vmax=np.nanmax(abs(piv.values)),
                  aspect="auto")
    a.set_xticks(range(len(piv.columns))); a.set_xticklabels(piv.columns, rotation=40, ha="right", fontsize=8)
    a.set_yticks(range(len(piv.index))); a.set_yticklabels(piv.index, fontsize=8)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.values[i, j]
            if not np.isnan(v):
                a.text(j, i, f"{v:+.1f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=a, label="change in detention (h)")
    a.set_title("C2  Levers x commodities (blue = detention falls)")
    a = ax[1, 0]
    h = heat.reindex(columns=order)
    im = a.imshow(h.values, cmap="Oranges", aspect="auto")
    a.set_xticks(range(len(h.columns))); a.set_xticklabels(h.columns, rotation=40, ha="right", fontsize=8)
    a.set_yticks(range(len(h.index))); a.set_yticklabels(h.index, fontsize=8)
    for i in range(h.shape[0]):
        for j in range(h.shape[1]):
            a.text(j, i, f"{h.values[i, j]:.1f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=a, label="detention swing (h), -50 %..+50 %")
    a.set_title("C3  Which parameter dominates in which commodity")
    a = ax[1, 1]
    s = s1.set_index("commodity").reindex(order)
    yy = np.arange(len(s))
    a.barh(yy + .2, s.total_saving_per_rake / 1e3, .4, color="#7a9b76", label="incl. assumed rake idle cost")
    a.barh(yy - .2, s.max_spend_cash_only_Rs / 1e3, .4, color="#c1440e", label="cash only (demurrage)")
    a.set_yticks(yy); a.set_yticklabels(s.index); a.legend()
    a.set_xlabel("Rs '000 per rake")
    a.set_title("C4  Break-even: max extra spend per rake for +50 % loading rate")
    for r in ax:
        for b in r:
            b.set_axisbelow(True)
    fig.suptitle("Layer 6 - multi-commodity analysis | profiles from ER RR register + MoR Compendium | "
                 "loading rates ASSUMED", y=1.0)
    fig.tight_layout()
    fig.savefig("layer6_results.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
