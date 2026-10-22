"""
verify_extensions.py  -  integrity checks for Layer 5, Layer 6 and the field-data decoding.

    python tools/verify_extensions.py          (after run_layer5/6 and analyse_rr_register)

Same contract as rtsim/verify_*.py: every check prints PASS/FAIL with the measured
value. Field checks are skipped (not failed) when data/raw is absent, e.g. on a
fresh clone without the railway files.
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES = os.path.join(ROOT, "results")


class Check:
    def __init__(self, title):
        self.title, self.n, self.ok, self.skip = title, 0, 0, 0
        print("\n" + "=" * 90 + f"\n{title}\n" + "=" * 90)

    def assert_(self, name, cond, detail=""):
        self.n += 1
        self.ok += bool(cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {name:<64} {detail}")

    def skipped(self, name, why):
        self.skip += 1
        print(f"  [SKIP] {name:<64} {why}")

    def report(self):
        print("-" * 90 + f"\n  {self.ok}/{self.n} passed" + (f", {self.skip} skipped" if self.skip else ""))
        return self.ok == self.n


def layer5(c):
    b = pd.read_csv(os.path.join(RES, "layer5_S1_bounds.csv"))
    lv = pd.read_csv(os.path.join(RES, "layer5_S1_oat_levels.csv"))
    l1 = open(os.path.join(RES, "l1.log")).read()
    import re
    m = re.search(r"with admin chain\s*:\s*detention\s+([\d.]+)", l1)
    base_l1 = float(m.group(1))
    base_l5 = lv[(lv.param == "load_rate") & (lv.x == 900.0)].detention.iloc[0]
    c.assert_("Layer 5 base reproduces the Layer 1 calibrated baseline",
              abs(base_l5 - base_l1) < 0.006, f"L5 {base_l5:.2f} h vs L1 {base_l1:.2f} h")
    at_base = []
    for p, g in lv.groupby("param"):
        row = b[b.param == p].iloc[0]
        hit = g[np.isclose(g.x, row.base)]
        if len(hit):
            at_base.append(abs(hit.d_detention.iloc[0]))
    c.assert_("every parameter at its base value reproduces the base exactly",
              max(at_base) < 1e-9, f"max |diff| {max(at_base):.1e} h over {len(at_base)} params")
    com = b[b.group == "commercial"]
    c.assert_("commercial parameters move money but never time",
              (com.detention_swing.abs() < 1e-9).all() and (com.wait_swing.abs() < 1e-9).all(),
              f"{len(com)} params, max detention swing {com.detention_swing.abs().max():.1e} h")
    dm = b[b.param == "demurrage_rate"].iloc[0]
    c.assert_("demurrage is linear in the base rate (x0.5 -> x1.5 = 3x)",
              abs(dm.demurrage_pr_at_high / dm.demurrage_pr_at_low - 3.0) < 1e-6,
              f"ratio {dm.demurrage_pr_at_high / dm.demurrage_pr_at_low:.4f}")
    m7 = b[b.param.str.startswith("M7")]
    c.assert_("M7 (after removal) never touches detention",
              (m7.detention_swing.abs() < 1e-9).all(), f"max swing {m7.detention_swing.abs().max():.1e} h")
    tsh = b[b.param == "hours_terminal_shift"].iloc[0]
    c.assert_("longer terminal hours never increase detention (monotone)",
              lv[lv.param == "hours_terminal_shift"].sort_values("x").detention.is_monotonic_decreasing,
              f"8 h {tsh.detention_at_low:.2f} -> 24 h {tsh.detention_at_high:.2f}")
    env = pd.read_csv(os.path.join(RES, "layer5_S4_envelope.csv")).set_index("case")
    c.assert_("envelope brackets the base (best < base < worst)",
              env.loc["all favourable ends", "detention"] < env.loc["base", "detention"]
              < env.loc["all unfavourable ends", "detention"],
              f"{env.loc['all favourable ends','detention']:.2f} < {env.loc['base','detention']:.2f}"
              f" < {env.loc['all unfavourable ends','detention']:.2f}")
    mor = pd.read_csv(os.path.join(RES, "layer5_S3_morris.csv"))
    top_oat = b[b.group != "commercial"].sort_values("detention_swing", ascending=False).param.head(3)
    c.assert_("Morris and OAT agree on the top-3 factors",
              set(mor.param.head(3)) == set(top_oat), f"Morris {list(mor.param.head(3))}")


def layer6(c):
    c1 = pd.read_csv(os.path.join(RES, "layer6_C1_commodity_baseline.csv")).set_index("commodity")
    c2 = pd.read_csv(os.path.join(RES, "layer6_C2_levers.csv"))
    c.assert_("free time per commodity matches the IR rule built into the profile",
              c1.loc["COAL (open BOXN)", "free_time_h"] == 8.0 and c1.loc["CEMENT (bagged, BCN)", "free_time_h"] == 9.0
              and c1.loc["CONTAINERS", "free_time_h"] == 5.0,
              "coal open 8, cement (goods shed) 9, containers 3+2")
    r1 = c2[c2.lever.str.startswith("R1")]
    c.assert_("free-time cut changes the bill, never the time",
              (r1.d_detention_h.abs() < 1e-9).all() and (r1.d_demurrage_per_rake > 0).all(),
              f"{len(r1)} commodities")
    s2 = c2[c2.lever.str.startswith("S2")].set_index("commodity")
    c.assert_("precise loading helps most where overloading is most frequent",
              s2.d_detention_h.idxmin() == c1.M5_rework_from_overload.idxmax(),
              f"largest gain: {s2.d_detention_h.idxmin()}")
    s1 = c2[c2.lever.str.startswith("S1")].set_index("commodity")
    corr = np.corrcoef(c1.loc[s1.index, "loading_h"], -s1.d_detention_h)[0, 1]
    c.assert_("faster loading helps more where loading takes longer",
              corr > 0.7, f"corr(loading hours, gain) = {corr:.2f}")


def field(c):
    raw = os.path.join(ROOT, "data", "raw", "RR_base_IN_freight_details")
    if not os.path.isdir(raw):
        for n in ("no sub-total rows", "tonnage conserved by group", "terminal charge = Rs 20/t",
                  "busy-season charge = 15 %", "coal exempt from busy-season charge",
                  "commodity groups cover >= 95 % of tonnes"):
            c.skipped(n, "data/raw not present")
        return
    from tools.rr_register import load_register
    d = load_register()
    c.assert_("no sub-total rows remain", not d["STATION FROM"].astype(str).str.contains("TOTAL").any(),
              f"{len(d):,} RRs")
    by = d.groupby("group").tonnes.sum().sum()
    c.assert_("tonnage conserved when grouped", abs(by - d.tonnes.sum()) < 1e-6, f"{by/1e6:,.1f} Mt")
    for h in ("OTC", "DTC"):
        x = d[d[f"OTHER CHARGE {h}"] > 0]
        r = (x[f"OTHER CHARGE {h}"] / x["WEIGHT CHRG"]).median()
        c.assert_(f"{h} is the Rs 20/t terminal charge", abs(r - 20) < 0.01, f"median {r:.3f} Rs/t on {len(x):,} RRs")
    x = d[d["OTHER CHARGE DPO"] > 0]
    r = (x["OTHER CHARGE DPO"] / x["BASIC FRGT"])
    c.assert_("DPO is the 15 % busy-season charge", (abs(r - 0.15) < 0.002).mean() > 0.95,
              f"{(abs(r-0.15)<0.002).mean():.1%} of {len(x):,} RRs within 0.2 pp")
    coal = d[(d.group == "COAL") & (d.rr_date >= "2022-10-01")]
    c.assert_("coal pays no busy-season charge after 01.10.2022 (exemption)",
              (coal["OTHER CHARGE DPO"] == 0).all(), f"{len(coal):,} coal RRs")
    known = d[d.group.ne("OTHER")].tonnes.sum() / d.tonnes.sum()
    c.assert_("commodity groups cover >= 95 % of tonnes", known >= 0.95, f"{known:.1%}")


if __name__ == "__main__":
    c = Check("EXTENSIONS VERIFICATION  -  Layer 5 sensitivity, Layer 6 commodities, field decoding")
    layer5(c)
    layer6(c)
    field(c)
    sys.exit(0 if c.report() else 1)
