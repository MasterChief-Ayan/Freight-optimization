"""
analyse_rr_register.py  -  what the Eastern Railway RR register says, per commodity.

    python tools/analyse_rr_register.py

Reads the cleaned, decoded register (tools/rr_register.py) and writes

  results/field/
    F0_code_tables.xlsx            every decoding table, with confidence grades
    F1_commodity_profiles.csv      one row per commodity group (aggregate; safe to share)
    F2_charge_structure.csv        charge heads as % of basic freight, per group
    F3_monthly_tonnes.csv          monthly tonnes per group (seasonality)
    F4_model_parameters.csv        data-derived values for the simulation, per group
    field_results.png              four-panel summary chart
  data/processed/                  (git-ignored cache: terminal- and consignee-level detail)
    terminal_profiles.csv          top receiving terminals
    terminal_arrivals.csv          full-rake arrival process at the top terminals

Unit of analysis: one Railway Receipt (RR) = one consignment; a full rake is an RR
with >= 40 wagons. Day-granular dates only, so arrival processes are measured in
rakes per day, not in hours.
"""
import os
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.rr_register import load_register, code_tables, FREE_TIME_BY_WAGON  # noqa: E402

OUT = os.path.join(ROOT, "results", "field")
PRIV = os.path.join(ROOT, "data", "processed")
os.makedirs(OUT, exist_ok=True)
os.makedirs(PRIV, exist_ok=True)

MAIN = ["COAL", "IRON ORE", "CLINKER", "CEMENT", "FOODGRAINS", "FERTILISER",
        "IRON & STEEL", "SLAG", "STEEL-PLANT FLUX (limestone/dolomite)", "SALT",
        "CONTAINERS", "POL", "RAILWAY MATERIAL", "MANGANESE ORE", "GYPSUM", "OTHER"]


def share(s, v):
    return float((s == v).mean())


def profiles(d):
    rows = []
    for g in MAIN:
        x = d[d.group == g]
        if x.empty:
            continue
        fr = x[x.full_rake]
        wt = x.wagon_type_filled.value_counts(normalize=True)
        dom_wagon = wt.index[0] if len(wt) else None
        months = x.rr_date.dt.to_period("M").nunique()
        basic = x["BASIC FRGT"].sum()
        rows.append({
            "group": g,
            "confidence": x.group_conf.mode().iat[0],
            "RRs": len(x),
            "Mt": x.tonnes.sum() / 1e6,
            "share_tonnes": x.tonnes.sum() / d.tonnes.sum(),
            "full_rakes_per_month_ER": len(fr) / max(1, months),
            "median_wagons": x.wagons.median(),
            "full_rake_share": x.full_rake.mean(),
            "median_wagons_full_rake": fr.wagons.median() if len(fr) else np.nan,
            "t_per_wagon_median": x.t_per_wagon.median(),
            "t_per_wagon_p10": x.t_per_wagon.quantile(.1),
            "t_per_wagon_p90": x.t_per_wagon.quantile(.9),
            "t_per_rake_median_full": fr.tonnes.median() if len(fr) else np.nan,
            "overload_incidence": x.overloaded.mean(),
            "overload_t_per_overloaded_RR": x.loc[x.overloaded, "overload_t"].median()
            if x.overloaded.any() else 0.0,
            # IR charges on permissible carrying capacity, so chargeable >= actual on
            # most RRs; the cost of under-loading is the capacity PAID FOR but not used
            "paid_unused_capacity_pct": float(((x["WEIGHT CHRG"] - x["WEIGHT ACTL"]).clip(lower=0)
                                               / x["WEIGHT CHRG"]).median()),
            "paid_unused_t_per_full_rake": float((fr["WEIGHT CHRG"] - fr["WEIGHT ACTL"]).clip(lower=0).median())
            if len(fr) else np.nan,
            "dominant_wagon": dom_wagon,
            "wagon_mix": "; ".join(f"{k.split()[0].lower()} {v:.0%}" for k, v in wt.head(3).items()),
            "private_siding_share": share(x.siding_type_filled, "PRIVATE SIDING"),
            "goods_shed_share": share(x.siding_type_filled, "GOODS SHED"),
            "rake_share": share(x.rake_type_filled, "RAKE"),
            "mini_or_piecemeal_share": float(x.rake_type_filled.isin(["MINI RAKE", "PIECEMEAL"]).mean()),
            "median_lead_km": x["DISTANCE CHRG"].median(),
            "foreign_share": share(x["F/L/I FLAG"], "F"),
            "freight_per_t_median": (x["FINAL FRGT (incl.SrvcTax/GST)"] / x.tonnes).median(),
            "freight_per_full_rake_median": fr["FINAL FRGT (incl.SrvcTax/GST)"].median() if len(fr) else np.nan,
            "surcharge_pct_basic": x.surcharge.sum() / basic,
            "terminal_pct_basic": x.terminal_chg.sum() / basic,
            "siding_pct_basic": x.siding_chg.sum() / basic,
            "punitive_pct_basic": x.punitive_chg.sum() / basic,
            "levy_pct_basic": x.levy_chg.sum() / basic,
            "rebate_pct_basic": x["REBATE TOTAL"].sum() / basic,
            "punitive_per_overloaded_RR": x.loc[x.overloaded, "punitive_chg"].median()
            if x.overloaded.any() else 0.0,
            "e_RR_share": share(x["RR E-RR"], "Y"),
            "rr_lag_days_p95": x.rr_lag_days.quantile(.95),
            "free_time_rule": FREE_TIME_BY_WAGON.get(dom_wagon, {}).get("note", ""),
        })
    return pd.DataFrame(rows)


def charge_structure(d):
    heads = [c for c in d.columns if c.startswith("OTHER CHARGE ") and c != "OTHER CHARGE TOTAL"]
    out = []
    for g in MAIN:
        x = d[d.group == g]
        if x.empty:
            continue
        basic = x["BASIC FRGT"].sum()
        r = {"group": g}
        for h in heads:
            v = x[h].sum() / basic
            if v > 0.0005:
                r[h.replace("OTHER CHARGE ", "")] = v
        out.append(r)
    return pd.DataFrame(out).fillna(0.0)


def terminals(d, n=15):
    rows, arr = [], []
    full = d[d.full_rake]
    for st_, x in full.groupby("STATION TO"):
        if len(x) < 300:
            continue
        days = pd.date_range(x.rr_date.min(), x.rr_date.max(), freq="D")
        daily = x.groupby(x.rr_date.dt.normalize()).size().reindex(days, fill_value=0)
        rows.append({
            "station_to": st_, "full_rakes": len(x),
            "main_consignee": x["CNSG CODE"].mode().iat[0],
            "main_group": x.group.mode().iat[0],
            "group_mix": "; ".join(f"{k} {v:.0%}" for k, v in x.group.value_counts(normalize=True).head(3).items()),
            "wagon_mix": "; ".join(f"{k.split()[0].lower()} {v:.0%}" for k, v in
                                   x.wagon_type_filled.value_counts(normalize=True).head(2).items()),
            "siding_type": x.siding_type_filled.mode().iat[0] if x.siding_type_filled.notna().any() else "",
            "rakes_per_day_mean": daily.mean(),
            "rakes_per_month_mean": daily.mean() * 30.44,
            "daily_dispersion_index": daily.var() / daily.mean() if daily.mean() > 0 else np.nan,
            "implied_mean_gap_h": 24.0 / daily.mean() if daily.mean() > 0 else np.nan,
            "overload_incidence": x.overloaded.mean(),
        })
        m = x.groupby(x.rr_date.dt.to_period("M")).size()
        arr.append(pd.DataFrame({"station_to": st_, "month": m.index.astype(str), "full_rakes": m.values}))
    t = pd.DataFrame(rows).sort_values("full_rakes", ascending=False).head(n)
    a = pd.concat(arr)
    return t, a[a.station_to.isin(t.station_to)]


def model_parameters(prof, term):
    """Values the simulation can take from the data, per commodity group."""
    out = []
    for _, r in prof.iterrows():
        out.append({
            "group": r.group,
            "rake.wagons (full rake median)": r.median_wagons_full_rake,
            "rake.tonnes_per_wagon (median)": r.t_per_wagon_median,
            "M5 rework_prob (overload incidence)": r.overload_incidence,
            "wagon type -> free time rule": r.dominant_wagon,
            "private siding share (2 h extra free time)": r.private_siding_share,
            "charges.freight_per_tonne (final, median)": r.freight_per_t_median,
            "status": "EMPIRICAL (ER RR register 2022-26)",
        })
    return pd.DataFrame(out)


def chart(prof, cs, monthly, term):
    top = prof[prof.group != "OTHER"].sort_values("Mt", ascending=False).head(10)
    fig, ax = plt.subplots(2, 2, figsize=(16, 11))
    a = ax[0, 0]
    a.barh(top.group, top.Mt, color="#5b7c99")
    a.invert_yaxis(); a.set_xlabel("million tonnes received, Jan-2022 to Aug-2026")
    a.set_title("F1  What Eastern Railway receives (top 10 groups)")
    a = ax[0, 1]
    x = np.arange(len(top))
    a.bar(x - .2, 100 * top.overload_incidence, .4, label="RRs with overloading (punitive)", color="#c1440e")
    a.bar(x + .2, 100 * top.paid_unused_capacity_pct, .4, label="capacity paid for but not loaded (% of chargeable t, median)", color="#8c8c8c")
    a.set_xticks(x); a.set_xticklabels(top.group, rotation=35, ha="right", fontsize=8)
    a.set_ylabel("%"); a.legend(fontsize=8)
    a.set_title("F2  Loading accuracy is commodity-specific (weighment step M5)")
    a = ax[1, 0]
    comp = top.set_index("group")[["surcharge_pct_basic", "terminal_pct_basic", "siding_pct_basic",
                                   "punitive_pct_basic", "levy_pct_basic"]] * 100
    comp.columns = ["surcharges", "terminal", "siding/haulage", "punitive", "levies"]
    comp.plot.bar(stacked=True, ax=a, colormap="tab20c")
    a.set_ylabel("% of basic freight"); a.tick_params(axis="x", labelsize=8, rotation=35)
    a.set_title("F3  Charges on top of basic freight, by commodity")
    a = ax[1, 1]
    mt = monthly.pivot(index="month", columns="group", values="Mt").fillna(0)
    for g in top.group.head(5):
        if g in mt:
            a.plot(range(len(mt)), mt[g], label=g)
    a.set_xticks(range(0, len(mt), 6)); a.set_xticklabels(mt.index[::6], rotation=45, fontsize=8)
    a.set_ylabel("million tonnes / month"); a.legend(fontsize=8)
    a.set_title("F4  Monthly receipts (seasonality drives arrival rate)")
    for r in ax:
        for b in r:
            b.grid(alpha=.25); b.set_axisbelow(True)
    fig.suptitle("Field data - ER Inward Freight Register (RR-base), 220,395 RRs, Jan-2022 to Aug-2026", y=1.0)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "field_results.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def main():
    d = load_register()
    print(f"RRs {len(d):,}  ({d.rr_date.min():%b-%Y} to {d.rr_date.max():%b-%Y}), "
          f"{d.tonnes.sum()/1e6:,.0f} Mt, {d.cmdt.nunique()} commodity codes")
    with pd.ExcelWriter(os.path.join(OUT, "F0_code_tables.xlsx")) as xw:
        for k, v in code_tables().items():
            v.to_excel(xw, sheet_name=k[:31], index=False)
    prof = profiles(d)
    prof.round(4).to_csv(os.path.join(OUT, "F1_commodity_profiles.csv"), index=False)
    cs = charge_structure(d)
    cs.round(5).to_csv(os.path.join(OUT, "F2_charge_structure.csv"), index=False)
    monthly = (d.groupby([d.rr_date.dt.to_period("M").astype(str).rename("month"), "group"])
               .tonnes.sum().div(1e6).rename("Mt").reset_index())
    monthly.round(4).to_csv(os.path.join(OUT, "F3_monthly_tonnes.csv"), index=False)
    term, arr = terminals(d)
    term.round(4).to_csv(os.path.join(PRIV, "terminal_profiles.csv"), index=False)
    arr.to_csv(os.path.join(PRIV, "terminal_arrivals.csv"), index=False)
    # coal split by wagon type: hopper (BOBRN) and open (BOXN) have different
    # free-time rules, so they are separate commodity profiles in the model
    coal = d[(d.group == "COAL") & d.full_rake]
    cw = (coal.groupby("wagon_type_filled")
          .agg(full_rakes=("tonnes", "size"), wagons=("wagons", "median"),
               t_per_wagon=("t_per_wagon", "median"), overload_incidence=("overloaded", "mean"),
               private_siding_share=("siding_type_filled", lambda s: (s == "PRIVATE SIDING").mean()),
               freight_per_t=("FINAL FRGT (incl.SrvcTax/GST)", "sum"), tonnes=("tonnes", "sum"))
          .reset_index())
    cw["freight_per_t"] = cw.freight_per_t / cw.tonnes
    cw.round(4).to_csv(os.path.join(OUT, "F5_coal_by_wagon.csv"), index=False)
    print("\n>>> F1c  COAL FULL RAKES BY WAGON TYPE")
    print(cw.to_string(index=False, float_format=lambda v: f"{v:,.3f}"))
    mp = model_parameters(prof, term)
    mp.round(4).to_csv(os.path.join(OUT, "F4_model_parameters.csv"), index=False)
    chart(prof, cs, monthly, term)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 30)
    cols = ["group", "Mt", "full_rakes_per_month_ER", "median_wagons_full_rake", "t_per_wagon_median",
            "overload_incidence", "paid_unused_capacity_pct", "paid_unused_t_per_full_rake", "dominant_wagon", "private_siding_share",
            "mini_or_piecemeal_share", "median_lead_km", "freight_per_t_median"]
    print("\n>>> F1  COMMODITY PROFILES")
    print(prof[cols].to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    print("\n>>> F1b  CHARGES AS % OF BASIC FREIGHT")
    print(prof[["group", "surcharge_pct_basic", "terminal_pct_basic", "siding_pct_basic",
                "punitive_pct_basic", "levy_pct_basic", "rebate_pct_basic",
                "punitive_per_overloaded_RR"]].to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    print("\n>>> F5  TOP RECEIVING TERMINALS (full rakes)")
    print(term.drop(columns=["group_mix"]).to_string(index=False, float_format=lambda v: f"{v:,.2f}"))


if __name__ == "__main__":
    main()
