"""
calibration.py  -  provenance for every number in the model.

Rule for the thesis: no figure appears in a result without a row here. Each
parameter is tagged with where it came from and how much weight it can bear.

    CITED     taken verbatim from a primary source (Railway Board circular,
              TERI report, peer-reviewed paper). Quotable.
    DERIVED   computed from CITED values plus an explicit rule. Quotable if
              the derivation is stated.
    TYPICAL   an industry-standard value that is widely reported but which I
              have not traced to a primary source. State as approximate.
    ASSUMED   a placeholder. NOT quotable. Sensitivity-test it, and replace
              it when field data arrives.

Primary sources
---------------
[IR-COMP]  Ministry of Railways, "Compendium: Demurrage, Stabling, Wharfage,
           Stacking, Waiver and Write off", as on 03.04.2024, issued under
           Rates Master Circular/Demurrage-Wharfage-Waiver/2016/0 dt 19.05.2016.
[IR-FOIS]  FOIS / RailSAHAY freight services FAQ and policy pages.
[TERI-1]   TERI (2023), Strategies to Increase Railway's Share in Freight
           Transport in India, Vol. I: Terminal Operations and Development.
[GL-09]    Guan & Liu (2009), Transportation Research Record 2100:58-67.
[PBS-25]   Parmaksizoglou, Bombelli & Sharpanskykh (2025), Logistics 9(3):110.
[WAGON]    Khosla, "New Designs of Wagons", Jindal Rail Infrastructure Ltd,
           wagon specification table (payload, tare, wagons per train,
           throughput per rake).
"""
from dataclasses import dataclass
from typing import List
import pandas as pd


@dataclass(frozen=True)
class Param:
    path: str
    value: str
    status: str
    source: str
    note: str = ""


REGISTRY: List[Param] = [
    # ---- IR charge rules, all CITED from the 2024 compendium ----------
    Param("charges.free_time_hr", "5:00 + 2:00 + 1:00 = 8:00",
          "DERIVED", "[IR-COMP] 2.2(a)(i), 2.2.1(a) and 2.7",
          "Open wagons (BOXN etc.), MECHANIZED LOADING at a railway terminal "
          "or private/assisted siding not on Engine-on-Load basis: 5:00. "
          "Plus 2:00 additional free time for a private/assisted siding NOT "
          "notified for through-distance charging. Note the asymmetry: "
          "mechanized UNLOADING of the same wagon is 7:00, manual is 9:00."),

    Param("charges.demurrage_per_wagon_hr", "150",
          "CITED", "[IR-COMP] 3.1",
          "Base rate, Rs per 8-wheeled wagon per hour or PART of an hour."),

    Param("charges.demurrage_grades", "150/165/187.5/225/300/450",
          "CITED", "[IR-COMP] 3.1",
          "Demurrage is GRADED, not flat. Base for the first 6 h of excess, "
          "+10% for 6-12 h, +25% for 12-24 h, +50% for 24-48 h, 2x for "
          "48-72 h, 3x beyond 72 h. Modelling it flat understates the charge "
          "on exactly the long detentions the thesis is about."),

    Param("charges.tarpaulin_free_time_hr", "1:00",
          "CITED", "[IR-COMP] 2.7",
          "One extra hour per rake for covering open wagons with tarpaulins "
          "during loading of loose/bulk commodity for which packing condition "
          "P2(a) applies - the circular names Coal and Coke explicitly."),

    Param("charges.coal_reduced_free_time_hr", "3:00",
          "CITED", "[IR-COMP] 2.2(c)",
          "Zonal Railways may cut mechanized loading free time for coal or "
          "iron-ore rakes to 3:00 where two or more such rakes are loaded "
          "from a single line. A policy scenario worth simulating."),

    Param("charges.penal_demurrage_multiplier", "up to 6x",
          "CITED", "[IR-COMP] 3.4.1",
          "PCCM/PCOM/DRM may raise rates up to six times base during "
          "excessive congestion, after 24 hours' notice."),

    Param("charges.wagon_registration_fee", "50,000 per rake",
          "CITED", "[IR-FOIS]",
          "Collected when the indent is placed; adjustable against freight."),

    Param("charges.wharfage_per_wagon_hr", "150 (Group I)",
          "CITED", "[IR-COMP] Ch.II 4.0, 2.1",
          "Group I = more than 12 rakes/month; II = 7-12; III = fewer than 7. "
          "Not levied for detention in a wagon or at a private siding, so it "
          "does not bind in the base scenario."),

    Param("charges.bunching_allowance_hr", "3:00",
          "CITED", "[IR-COMP] 2.2.3",
          "Private/assisted sidings where the SIDING OWNER's loco does "
          "placement and release. Granted only to rakes arriving bunched in "
          "excess of the siding's handling capacity. Not modelled: the base "
          "case uses railway locos."),

    # ---- calendars ----------------------------------------------------
    Param("admin.CAL_TERMINAL_SHIFT", "06:00-22:00",
          "CITED", "[IR-COMP] 4.1",
          "The working and business hours of all railway terminals are 06:00 "
          "to 22:00. DRM may introduce round-the-clock working case by case - "
          "which makes 24/7 a genuine policy lever, not a fantasy."),

    Param("admin.night_incentive", "not applicable",
          "CITED", "[IR-COMP] 4.3, 4.5",
          "Only 50% of time between 22:00 and 06:00 counts towards free time "
          "as an incentive to release at night - but para 4.5 excludes "
          "private/assisted sidings. Correctly NOT modelled in the base case."),

    Param("accounting.sundays", "counted",
          "CITED", "[IR-COMP] 8.2",
          "Sundays are reckoned for demurrage; they are not dies-non. The "
          "free-time clock therefore runs continuously, which is what the "
          "model does - only OFFICE calendars pause."),

    # ---- TERI benchmarks ---------------------------------------------
    Param("benchmark.detention_hr", "14-17",
          "CITED", "[TERI-1]",
          "Average time a rake spends at a freight terminal. The model's "
          "calibration target."),

    Param("benchmark.rakes_per_month_one_line", "15",
          "CITED", "[TERI-1]",
          "An average one-line terminal handles about 15 rakes per month, "
          "i.e. 180 a year. Sets the plausible arrival rate."),

    Param("benchmark.release_share", "80-85%",
          "CITED", "[TERI-1]",
          "Share of terminal restrictions attributed to poor release and "
          "heavy pipeline. The reason M6 is modelled in detail."),

    # ---- road side ----------------------------------------------------
    Param("trucks.gate_service", "Erlang",
          "CITED", "[GL-09]",
          "Exponential truck inter-arrivals and Erlang gate processing were "
          "the distributions found significant on field gate observations."),

    Param("trucks.deviation_cost", "exponential in periods deviated",
          "CITED", "[PBS-25] Eq. 8",
          "Scaled here by 1/4 in the exponent so the objective stays "
          "numerically meaningful over a 24-period deviation limit."),

    # ---- entities -----------------------------------------------------
    Param("rake.wagons", "58", "CITED", "[WAGON]",
          "58 wagons per BOXN train."),

    Param("rake.tonnes_per_wagon", "58.08", "CITED", "[WAGON]",
          "BOXN payload 58.08 t, tare 23.2 t, gross 81.28 t, axle load "
          "20.32 t. Rake throughput 3368.64 t. Note BOXNHL carries 71.0 t on "
          "a 22.9 t axle load and BOXNS 80.15 t on 25 t - if the siding "
          "handles those instead, this figure changes by up to 38%."),

    # ---- everything below is a placeholder ----------------------------
    Param("charges.engine_hour_cost", "6,000", "ASSUMED", "-",
          "Siding charge = engine hour cost x average trip time. The "
          "All-India engine hour cost is notified separately by the Railway "
          "Board for diesel and electric traction. GET THE CURRENT FIGURE."),
    Param("charges.shunting_charge", "25,000", "ASSUMED", "-", "Placeholder."),
    Param("charges.freight_per_tonne", "1,400", "ASSUMED", "-",
          "Depends on distance slab, commodity classification and any "
          "rationalised-route charging. Take from the actual RR."),
    Param("charges.idle_cost_per_hr", "3,000", "ASSUMED", "-",
          "Opportunity cost of rake time. Not an IR charge. Should be derived "
          "from asset value and utilisation."),
    Param("rake.load_rate_tph", "900 +/- 250", "ASSUMED", "-",
          "Mechanised coal loading rate. Fit to observed loading durations."),
    Param("shunting.placement / removal", "1.0 +/- 0.3 h", "ASSUMED", "-",
          "Time & Motion studies exist for individual sidings; get the local one."),
    Param("admin.M1..M8 service times", "various", "ASSUMED", "-",
          "No published distributions exist for Indian rail administrative "
          "steps. This is the single largest source of uncertainty in the "
          "model. Measure with a WCO Time Release Study."),
    Param("admin.M1..M8 rework_prob", "0.05-0.20", "ASSUMED", "-",
          "Rejection rates are not recorded anywhere. Sensitivity-test."),
    Param("trucks.truck_capacity_t", "35", "ASSUMED", "-", "Placeholder."),
    Param("trucks.slots_per_period", "10", "ASSUMED", "-",
          "This is a DECISION VARIABLE, not a datum - it is what the "
          "appointment system chooses."),
]


def table() -> pd.DataFrame:
    return pd.DataFrame([p.__dict__ for p in REGISTRY])


def summary() -> pd.DataFrame:
    t = table()
    return (t.groupby("status").size().rename("n").reset_index()
            .sort_values("n", ascending=False))


def report():
    t = table()
    print("\n" + "=" * 100)
    print("PARAMETER PROVENANCE")
    print("=" * 100)
    for st in ["CITED", "DERIVED", "TYPICAL", "ASSUMED"]:
        sub = t[t.status == st]
        if sub.empty:
            continue
        print(f"\n--- {st}  ({len(sub)}) ---")
        for _, r in sub.iterrows():
            src = f"  [{r.source}]" if r.source != "-" else ""
            print(f"  {r.path:<38} = {r.value:<28}{src}")
    print("\n" + "-" * 100)
    print("  " + " | ".join(f"{r.status}: {r.n}" for _, r in summary().iterrows()))
    print("  Results that depend only on CITED/DERIVED values are quotable.")
    print("  Anything touching an ASSUMED value must be reported as a")
    print("  DIRECTION or a RANKING, never as an absolute figure.")
    print("=" * 100)


if __name__ == "__main__":
    report()
