"""
run_layer7_sufficiency.py  -  are the variables and conditions in the model SUFFICIENT?

    python experiments/run_layer7_sufficiency.py          (~2 min, 2 cores)
    python experiments/run_layer7_sufficiency.py quick

Examiner's question (post mid-sem): "how do you know the conditions / variables you
took are sufficient?"  A simulation model is sufficient for its PURPOSE when adding
the factors it leaves out would not change the conclusions drawn from it
(Robinson 2008, conceptual modelling; Sargent 2013, V&V). The conclusions here are
RANKINGS of interventions (E12: procedure beats capital). So the test is:

    add plausible factors that the model does NOT contain, of realistic size,
    and check whether the ranking of the interventions changes.

Each omitted factor is represented through an existing mechanism and is applied
AFTER the intervention, so no intervention can remove it (the omitted delay persists):

  O1  physical delay inside free time not modelled (wagon examination, sick-wagon
      detachment, levelling, tarpaulin): +1 h / +3 h added to loading time
  O2  paperwork inside free time not modelled (sampling / quality certificate,
      commodity-specific permits): +1 h / +3 h added to M4 (terminal office)
  O3  more traffic than assumed: arrival gap 30 h -> 20 h (+50 % rakes)
  O4  loading disruptions (weather, labour absenteeism): rate -20 %, variability x2
  O5  error rates twice as high: every rejection probability x2
  O6  O1 +1 h, O2 +1 h, O4 and O5 together

Interventions (the E12 set, on the calibrated Layer 1 base, 50 rakes, 30 paired reps):
  digitalise all admin / digitalise M5+M6 / terminal 24/7 / +50 % loading rate /
  2nd line + 2nd crew / 2nd line alone

Outputs: layer7_O1_sufficiency.csv (saving per intervention per omitted factor),
         layer7_O2_rank_stability.csv (Kendall tau vs the model as built, top-3 kept?,
         procedure/capital ratio), layer7_results.png
"""
import _bootstrap  # noqa: F401

import sys
from dataclasses import replace
from itertools import combinations

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
KS = ["M1", "M2", "M3", "M4", "M5", "M6", "M7"]
PROCEDURAL = ["digitalise all admin", "digitalise M5+M6", "terminal 24/7"]
CAPITAL = ["+50% loading rate", "2nd line + 2nd crew", "2nd line alone"]


# ---------------------------------------------------------------- interventions
def interventions(c, s):
    t247 = dict(s)
    for k in ("M4", "M5", "M6"):
        t247[k] = replace(t247[k], calendar=CAL_24_7)
    r = c.rake.load_rate_tph
    return {
        "none": (c, s),
        "digitalise all admin": (c, digitalise(KS, s)),
        "digitalise M5+M6": (c, digitalise(["M5", "M6"], s)),
        "terminal 24/7": (c, t247),
        "+50% loading rate": (replace(c, rake=replace(c.rake, load_rate_tph=Dist(
            "logn", mean=1.5 * r.mean, sd=1.5 * r.sd))), s),
        "2nd line + 2nd crew": (replace(c, resources=replace(c.resources, loading_lines=2, crews=2)), s),
        "2nd line alone": (replace(c, resources=replace(c.resources, loading_lines=2)), s),
    }


# ---------------------------------------------------------------- omitted factors
def _extra_loading(dh):
    """Add dh hours to every rake's loading time: rate' = T / (T / rate + dh), same CV."""
    def f(c, s):
        r = c.rake.load_rate_tph
        T = c.rake.wagons * c.rake.tonnes_per_wagon
        new = T / (T / r.mean + dh)
        return replace(c, rake=replace(c.rake, load_rate_tph=Dist("logn", mean=new, sd=r.sd * new / r.mean),
                                       load_rate_floor=c.rake.load_rate_floor * new / r.mean)), s
    return f


def _extra_m4(dh):
    def f(c, s):
        return c, L5._with_steps(s, ["M4"], lambda t: L5._svc(t, mean=t.service.mean + dh))
    return f


def _demand(gap):
    return lambda c, s: (replace(c, rake=replace(c.rake, arrival_gap=Dist("exp", mean=gap))), s)


def _disrupt(c, s):
    r = c.rake.load_rate_tph
    return replace(c, rake=replace(c.rake, load_rate_tph=Dist("logn", mean=0.8 * r.mean, sd=2 * r.sd),
                                   load_rate_floor=0.8 * c.rake.load_rate_floor)), s


def _errors(c, s):
    return c, {k: replace(v, rework_prob=min(0.9, 2 * v.rework_prob)) for k, v in s.items()}


def _combo(c, s):
    for f in (_extra_loading(1.0), _extra_m4(1.0), _disrupt, _errors):
        c, s = f(c, s)
    return c, s


OMITTED = {
    "model as built": lambda c, s: (c, s),
    "O1 +1 h physical delay in free time": _extra_loading(1.0),
    "O1 +3 h physical delay in free time": _extra_loading(3.0),
    "O2 +1 h unmodelled paperwork (M4)": _extra_m4(1.0),
    "O2 +3 h unmodelled paperwork (M4)": _extra_m4(3.0),
    "O3 +50 % traffic (gap 20 h)": _demand(20.0),
    "O4 loading disruptions (-20 %, sd x2)": _disrupt,
    "O5 error rates x2": _errors,
    "O6 O1+O2 (+1 h each), O4, O5 together": _combo,
}


def kendall_tau(a, b):
    """Kendall tau-a between two rankings of the same items (no scipy needed)."""
    items = list(a.index)
    conc = disc = 0
    for i, j in combinations(items, 2):
        s = np.sign(a[i] - a[j]) * np.sign(b[i] - b[j])
        conc += s > 0
        disc += s < 0
    n = len(items) * (len(items) - 1) / 2
    return (conc - disc) / n


def main():
    c0 = default_config()
    c0 = replace(c0, run=replace(c0.run, n_reps=N_REPS))
    s0 = default_steps()

    pts, keys = [], []
    for o, fo in OMITTED.items():
        for lev, (c, s) in interventions(c0, s0).items():
            cc, ss = fo(c, s)                       # omitted factor applied AFTER the lever
            pts.append((cc, ss, "FCFS")); keys.append((o, lev))
    res = dict(zip(keys, L5.run_points(pts)))

    rows = []
    for o in OMITTED:
        b = res[(o, "none")]
        for lev in list(interventions(c0, s0))[1:]:
            d, h, sig = L5.paired(b, res[(o, lev)], "detention")
            rows.append({"omitted_factor": o, "intervention": lev, "base_detention_h": b.detention.mean(),
                         "saving_h": -d, "ci_h": h, "significant": sig,
                         "type": "procedural" if lev in PROCEDURAL else "capital"})
    o1 = pd.DataFrame(rows)

    ref = o1[o1.omitted_factor == "model as built"].set_index("intervention").saving_h
    top3_ref = list(ref.sort_values(ascending=False).index[:3])
    stab = []
    for o, g in o1.groupby("omitted_factor", sort=False):
        sv = g.set_index("intervention").saving_h
        top3 = list(sv.sort_values(ascending=False).index[:3])
        best_cap = sv[CAPITAL].max()
        stab.append({"omitted_factor": o, "base_detention_h": g.base_detention_h.iloc[0],
                     "kendall_tau_vs_built": kendall_tau(ref, sv),
                     "top3_same_set": set(top3) == set(top3_ref),
                     "best_intervention": sv.idxmax(),
                     "best_procedural_h": sv[PROCEDURAL].max(), "best_capital_h": best_cap,
                     "procedure_over_capital": sv[PROCEDURAL].max() / best_cap if best_cap > 0 else np.inf,
                     "2nd_line_alone_h": sv["2nd line alone"]})
    o2 = pd.DataFrame(stab)

    print(f"\n>>> O1  SAVING IN DETENTION (h) PER INTERVENTION, WITH AND WITHOUT OMITTED FACTORS "
          f"({N_REPS} paired reps x {c0.run.n_rakes} rakes)")
    print(o1.pivot(index="intervention", columns="omitted_factor", values="saving_h")
          .reindex(columns=list(OMITTED)).round(2).to_string())
    print("\n>>> O2  DO THE CONCLUSIONS SURVIVE?")
    print(o2.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    print(f"\n  min Kendall tau = {o2.kendall_tau_vs_built.min():.2f}; top-3 unchanged in "
          f"{o2.top3_same_set.sum()}/{len(o2)}; procedure > capital in "
          f"{(o2.procedure_over_capital > 1).sum()}/{len(o2)}")
    o1.round(4).to_csv("layer7_O1_sufficiency.csv", index=False)
    o2.round(4).to_csv("layer7_O2_rank_stability.csv", index=False)
    chart(o1, o2)
    print("\nSaved: layer7_results.png, layer7_O1_sufficiency.csv, layer7_O2_rank_stability.csv")


def chart(o1, o2):
    fig, ax = plt.subplots(1, 2, figsize=(17, 6.5), gridspec_kw={"width_ratios": [2.2, 1]})
    piv = o1.pivot(index="intervention", columns="omitted_factor", values="saving_h").reindex(columns=list(OMITTED))
    piv = piv.loc[piv["model as built"].sort_values(ascending=False).index]
    a = ax[0]
    im = a.imshow(piv.values, cmap="Blues", aspect="auto")
    a.set_xticks(range(piv.shape[1])); a.set_xticklabels(piv.columns, rotation=35, ha="right", fontsize=8)
    a.set_yticks(range(piv.shape[0])); a.set_yticklabels(piv.index, fontsize=9)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            a.text(j, i, f"{piv.values[i, j]:.1f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=a, label="detention saved (h per rake)")
    a.set_title("O1  Saving per intervention, with each omitted factor added")
    a = ax[1]
    y = np.arange(len(o2))[::-1]
    a.barh(y, o2.kendall_tau_vs_built, color="#5b7c99")
    a.set_yticks(y); a.set_yticklabels(o2.omitted_factor, fontsize=8)
    a.set_xlim(0, 1.05); a.axvline(1.0, color="#888", lw=0.8, ls="--")
    a.set_xlabel("Kendall tau vs model as built (1 = same ranking)")
    a.set_title("O2  Ranking stability")
    fig.suptitle("Layer 7 - sufficiency test: do the conclusions survive factors the model leaves out?", y=1.0)
    fig.tight_layout()
    fig.savefig("layer7_results.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
