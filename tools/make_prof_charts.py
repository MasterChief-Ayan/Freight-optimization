"""Four single-message figures for the supervisor update (post mid-sem work).

    python tools/make_prof_charts.py      (after Layers 5-6 and the field analysis)

Writes results/prof/Fig1..Fig4 *.png. Palette: validated reference categorical
slots (blue #2a78d6, orange #eb6834), blue<->red diverging with gray midpoint.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
OUT = os.path.join(RES, "prof")
os.makedirs(OUT, exist_ok=True)

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK2, MUTED, GRID, AXIS, SURF = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11, "text.color": INK,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.facecolor": SURF, "figure.facecolor": SURF, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
})


def finish(fig, ax, title, sub, name, note=None):
    fig.text(0.01, 0.985, title, fontsize=15, fontweight="bold", va="top", color=INK)
    fig.text(0.01, 0.935, sub, fontsize=10.5, va="top", color=INK2)
    if note:
        fig.text(0.01, 0.01, note, fontsize=8.5, color=MUTED, va="bottom")
    ax.set_axisbelow(True)
    fig.savefig(os.path.join(OUT, name), dpi=200, bbox_inches="tight", facecolor=SURF)
    plt.close(fig)


# ---------------------------------------------------------------- Fig 1
b = pd.read_csv(os.path.join(RES, "layer5_S1_bounds.csv"))
ENV = pd.read_csv(os.path.join(RES, "layer5_S4_envelope.csv")).set_index("case").detention
b = b[b.group != "commercial"].sort_values("detention_swing", ascending=False).head(10).iloc[::-1]
base = 15.53
nice = {
    "hours_terminal_shift": "Terminal working hours (8 → 24 h a day)",
    "load_rate": "Loading rate (675 → 3,370 t/h: payloader → silo)",
    "M6_mean": "Release-reporting time, M6 (1.8 → 5.4 h)",
    "M5_mean": "Weighment time, M5 (0.9 → 2.7 h)",
    "t_per_wagon": "Payload per wagon (52 → 71 t)",
    "wagons": "Wagons per rake (42 → 59)",
    "M5_rework": "Weighment rejection rate, M5 (0 → 36 %)",
    "M6_rework": "Release-report rejection rate, M6 (0 → 20 %)",
    "M4_mean": "Placement-advice time, M4 (0.25 → 0.75 h)",
    "load_rate_sd": "Loading-rate variability (125 → 375 t/h)",
}
fig, ax = plt.subplots(figsize=(10, 6.2))
y = np.arange(len(b))
for i, (_, r) in enumerate(b.iterrows()):
    ax.plot([r.detention_at_low, r.detention_at_high], [i, i], color=AXIS, lw=3, solid_capstyle="round", zorder=1)
ax.scatter(b.detention_at_low, y, s=70, color=BLUE, zorder=3, label="parameter at LOW end of its range",
           edgecolor=SURF, linewidth=2)
ax.scatter(b.detention_at_high, y, s=70, color=ORANGE, zorder=3, label="parameter at HIGH end of its range",
           edgecolor=SURF, linewidth=2)
for i, (_, r) in enumerate(b.iterrows()):
    ax.text(max(r.detention_at_low, r.detention_at_high) + 0.4, i, f"{r.detention_swing:.1f} h",
            va="center", fontsize=9.5, color=INK2)
ax.axvline(base, color=INK2, lw=1, ls="--")
ax.text(base, len(b) - 0.35, f"today {base:.1f} h", ha="center", fontsize=9, color=INK2)
ax.set_yticks(y); ax.set_yticklabels([nice.get(p, p) for p in b.param], fontsize=10)
ax.set_xlabel("average rake detention, placement → release (hours)")
ax.grid(axis="y", visible=False)
ax.legend(loc="lower right", frameon=False, fontsize=9.5)
fig.subplots_adjust(top=0.84, left=0.36)
finish(fig, ax, "Fig. 1  How much each factor alone can move detention",
       "Each factor varied over its range, everything else unchanged; numbers = swing (lower to upper bound)",
       "Fig1_parameter_bounds.png",
       "30 paired replications × 50 rakes. Charges (free time, demurrage rate, penal ×) change the bill only: 0 h. "
       f"All factors together: {ENV['all favourable ends']:.1f} h (best) to {ENV['all unfavourable ends']:.1f} h (worst).")

# ---------------------------------------------------------------- Fig 2
c2 = pd.read_csv(os.path.join(RES, "layer6_C2_levers.csv"))
c2 = c2[~c2.lever.str.startswith("R1")]
lev = {"G1 terminal 24/7 (M4-M6)": "Terminal paperwork 24/7",
       "G2 digitalise M6 release reporting": "Digital release reporting",
       "G3 digitalise M5 weighment": "Digital weighment",
       "S1 loading rate +50 % (labour/mechanisation)": "Loading 50 % faster",
       "S2 precise loading (no overload)": "Precise loading (no overload)",
       "G4 2nd line + 2nd crew": "2nd line + 2nd crew",
       "S3 silo / rapid loading system (bulk only)": "Silo / rapid loading (bulk only)"}
com = ["COAL (open BOXN)", "COAL (hopper BOBRN)", "IRON ORE", "CLINKER", "CEMENT (bagged, BCN)",
       "FOODGRAINS", "FERTILISER", "IRON & STEEL (flat, crane)", "CONTAINERS", "POL (tank)"]
lab = ["Coal\n(BOXN)", "Coal\n(hopper)", "Iron\nore", "Clinker", "Cement\n(bagged)", "Food-\ngrains",
       "Fertil-\niser", "Iron &\nsteel", "Contai-\nners", "POL\n(tank)"]
piv = c2.pivot(index="lever", columns="commodity", values="d_detention_h").reindex(index=list(lev), columns=com)
cmap = LinearSegmentedColormap.from_list("div", ["#1c5cab", "#86b6ef", "#f0efec", "#f2a6a5", "#e34948"])
fig, ax = plt.subplots(figsize=(11.5, 6.0))
cmap.set_bad(SURF)
im = ax.imshow(np.ma.masked_invalid(piv.values), cmap=cmap,
               norm=TwoSlopeNorm(vmin=min(-6.5, np.nanmin(piv.values)), vcenter=0, vmax=1.0), aspect="auto")
for i in range(piv.shape[0]):
    for j in range(piv.shape[1]):
        v = piv.values[i, j]
        if np.isnan(v):
            ax.text(j, i, "n/a", ha="center", va="center", fontsize=8.5, color=MUTED)
            continue
        v = 0.0 if abs(v) < 0.05 else v
        ax.text(j, i, "0.0" if v == 0 else f"{v:+.1f}", ha="center", va="center", fontsize=9.5,
                color="white" if v < -3.5 else INK)
ax.set_xticks(range(len(com))); ax.set_xticklabels(lab, fontsize=9)
ax.set_yticks(range(len(lev))); ax.set_yticklabels(list(lev.values()), fontsize=10)
ax.grid(False)
for sp in ax.spines.values():
    sp.set_visible(False)
ax.axhline(1.5, color=SURF, lw=4); ax.axhline(3.5, color=SURF, lw=4)
fig.subplots_adjust(bottom=0.2)
ax.text(len(com) - 0.45, 0.5, "GENERAL\n(all materials)", fontsize=8.5, color=INK2, va="center")
ax.text(len(com) - 0.45, 2.5, "GENERAL,\nsize varies", fontsize=8.5, color=INK2, va="center")
ax.text(len(com) - 0.45, 5.0, "MATERIAL-\nSPECIFIC", fontsize=8.5, color=INK2, va="center")
cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.13)
cb.set_label("change in detention (h): blue = shorter", color=INK2)
fig.subplots_adjust(top=0.82)
finish(fig, ax, "Fig. 2  Which improvement works for which material",
       "Change in average detention (hours) vs each material's own base; same model, material data from the ER register",
       "Fig2_levers_by_material.png",
       "Material profiles: wagons/rake, payload, overload rate, siding type from the ER RR register (2022–26); "
       "free time from MoR Compendium 2.2; loading rates per method assumed, inside published norms.")

# ---------------------------------------------------------------- Fig 3
p = pd.read_csv(os.path.join(RES, "field", "F1_commodity_profiles.csv"))
keep = ["COAL", "IRON ORE", "CLINKER", "CEMENT", "FOODGRAINS", "FERTILISER", "IRON & STEEL", "SLAG",
        "STEEL-PLANT FLUX (limestone/dolomite)", "SALT"]
p = p.set_index("group").loc[keep]
lab3 = ["Coal", "Iron ore", "Clinker", "Cement", "Foodgrains", "Fertiliser", "Iron & steel", "Slag",
        "Limestone/\ndolomite", "Salt"]
x = np.arange(len(p))
fig, ax = plt.subplots(figsize=(11, 5.4))
w = 0.38
ax.bar(x - w / 2 - 0.01, 100 * p.overload_incidence, w, color=ORANGE, label="consignments overloaded (punitive charge)")
ax.bar(x + w / 2 + 0.01, 100 * p.paid_unused_capacity_pct, w, color=BLUE,
       label="capacity paid for but not loaded (median, % of charged weight)")
for i, (o, u) in enumerate(zip(p.overload_incidence, p.paid_unused_capacity_pct)):
    if o > 0.05:
        ax.text(i - w / 2, 100 * o + 0.6, f"{100*o:.0f}%", ha="center", fontsize=9, color=INK2)
ax.set_xticks(x); ax.set_xticklabels(lab3, fontsize=9.5)
ax.set_ylabel("% of consignments  /  % of weight")
ax.grid(axis="x", visible=False)
ax.legend(frameon=False, fontsize=9.5, loc="upper right")
fig.subplots_adjust(top=0.84)
finish(fig, ax, "Fig. 3  Loading accuracy is a material-specific problem",
       "Eastern Railway inward freight register, 220,395 consignments (Jan 2022 – Aug 2026)",
       "Fig3_loading_accuracy_by_material.png",
       "Bulk open-wagon cargo is often overloaded AND often under-filled; bagged cargo (cement, foodgrains, salt) "
       "is loaded almost exactly.")

# ---------------------------------------------------------------- Fig 4
s1 = pd.read_csv(os.path.join(RES, "layer6_C4_labour_breakeven.csv")).set_index("commodity").loc[com]
lab4 = [l.replace("\n", " ").replace("- ", "") for l in lab]
order = np.argsort(s1.max_spend_cash_only_Rs.values)
fig, ax = plt.subplots(figsize=(10, 5.6))
vals = s1.max_spend_cash_only_Rs.values[order] / 1e3
ax.barh(np.arange(len(vals)), vals, color=BLUE, height=0.62)
for i, v in enumerate(vals):
    ax.text(v + 0.4, i, f"₹{v:,.1f} k", va="center", fontsize=9.5, color=INK2)
ax.set_yticks(range(len(vals))); ax.set_yticklabels([lab4[k] for k in order], fontsize=10)
ax.set_xlabel("maximum extra spend per rake that still pays back (₹ thousand, demurrage saved)")
fig.subplots_adjust(bottom=0.16)
ax.grid(axis="y", visible=False)
fig.subplots_adjust(top=0.84)
finish(fig, ax, "Fig. 4  Extra loading labour or equipment: when does it pay?",
       "Break-even for 50 % faster loading = demurrage saved per rake (no labour cost assumed)",
       "Fig4_labour_breakeven.png",
       "Cash only (billed demurrage). Counting the opportunity cost of idle rake-hours raises these to ₹19–85 k. "
       "About ₹21–31 k per hour of loading saved, for every material.")
# ---------------------------------------------------------------- Fig 5
c5 = pd.read_csv(os.path.join(RES, "layer6_C5_labour_vs_demurrage.csv"))
c5 = c5[c5.handling_Rs_per_t.notna()].set_index("commodity")
c5 = c5.loc[[c for c in com if c in c5.index]]
lab5 = [lab4[com.index(c)] for c in c5.index]
y = np.arange(len(c5))[::-1]
fig, ax = plt.subplots(figsize=(11, 5.8))
h = 0.36
ax.barh(y + h / 2, c5.max_spend_cash_only_Rs / 1e3, h, color=BLUE,
        label="demurrage saved per rake (the most it can cost)")
ax.barh(y - h / 2, c5.extra_cost_shift_rate_Rs / 1e3, h, color=ORANGE,
        label="extra cost if the bigger gang/machine is paid a full shift (upper bound)")
for yi, (_, r) in zip(y, c5.iterrows()):
    ax.text(max(r.max_spend_cash_only_Rs, r.extra_cost_shift_rate_Rs) / 1e3 + 1.5, yi,
            f"break-even ₹{r.breakeven_Rs_per_t:.1f}/t  =  {100 * r.breakeven_pct_of_handling_rate:.0f}% of "
            f"today's ₹{r.handling_Rs_per_t:.0f}/t handling rate",
            va="center", fontsize=9, color=INK2)
ax.set_yticks(y); ax.set_yticklabels(lab5, fontsize=10)
ax.set_xlabel("₹ thousand per rake")
ax.set_xlim(0, c5.extra_cost_shift_rate_Rs.max() / 1e3 * 1.85)
ax.grid(axis="y", visible=False)
ax.legend(frameon=False, fontsize=9.5, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
fig.subplots_adjust(top=0.80, bottom=0.17)
finish(fig, ax, "Fig. 5  Extra labour for 50 % faster loading: does it pay once labour cost is counted?",
       "Paid per tonne (piece rate): extra cost ≈ 0, so it pays for every material.  Paid per full shift: "
       "bulk ≈ breaks even, bagged cargo loses ≈ ₹1 lakh/rake",
       "Fig5_labour_vs_demurrage.png",
       "Handling rates: CWC Railside Warehouse handling tariff (bagged, median of 14 terminals); BCCL Schedule of "
       "Rates 2025 (coal by payloader, order of magnitude).\nMinimum wage ₹827/day (loading & unloading, Area A, "
       "from 01.04.2026): the break-even pays for 24–31 extra labourer-days per rake.")
print("saved:", sorted(os.listdir(OUT)))
