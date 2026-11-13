"""Generate the data figures of the MTP-1 report from the committed result tables.

    python gen_figs.py <repo>/results      ->  fig_*.pdf + fig_*.png next to this script

Every number is read from the CSVs written by run_all.sh; nothing is typed in by hand.
Style: serif (Times-metric) to match the report, Okabe-Ito colours, markers/hatches so the
figures also read in grayscale.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RES = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(__file__))

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "TeX Gyre Termes", "Liberation Serif", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 9.5, "axes.titleweight": "bold",
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8, "legend.frameon": False,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": "--", "grid.linewidth": 0.5,
    "savefig.dpi": 300, "savefig.bbox": "tight", "pdf.fonttype": 42,
})
BLUE, ORANGE, GREEN, VERM, SKY, PINK, YELLOW = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7", "#F0E442"
GRAY, INK = "#8C8C8C", "#333333"
W = 6.2  # in, = \textwidth of the report (A4, 1 in margins)


def rd(name):
    return pd.read_csv(os.path.join(RES, name + ".csv"))


def save(fig, name):
    fig.savefig(os.path.join(OUT, name + ".pdf"))
    fig.savefig(os.path.join(OUT, name + ".png"))
    plt.close(fig)
    print("wrote", name)


def panel(ax, tag):
    ax.set_title(tag, loc="left")


# ------------------------------------------------------------------ Fig. interventions
e = rd("layer4_E12_interventions").set_index("scenario")
rows = [  # (scenario in csv, label, kind)
    ("digitalise all admin", "Digitalise all paperwork (M1-M8)", "proc"),
    ("digitalise M5+M6", "Digitalise weighment + release (M5, M6)", "proc"),
    ("terminal works 24/7", "Terminal paperwork 24/7 (M4-M6)", "proc"),
    ("+50% loading rate", "Loading rate +50 %", "cap"),
    ("no rework anywhere", "No rejected paperwork (rework = 0)", "proc"),
    ("2nd line + 2nd crew", "Second line + second crew", "cap"),
    ("2nd shunting loco", "Second shunting loco", "cap"),
    ("2nd loading line", "Second loading line alone", "cap"),
]
fig, ax = plt.subplots(figsize=(W, 2.15))
y = np.arange(len(rows))[::-1]
for yi, (key, lab, kind) in zip(y, rows):
    saved = round(-e.loc[key, "d_mean_detention_hr"], 3) + 0.0
    ci = e.loc[key, "d_mean_detention_hr_ci"]
    col = BLUE if kind == "proc" else ORANGE
    hatch = None if kind == "proc" else "///"
    if saved < 0:
        col, hatch = VERM, "xx"
    ax.barh(yi, saved, height=0.62, color=col, hatch=hatch, edgecolor="white", linewidth=0.4)
    ax.errorbar(saved, yi, xerr=ci, fmt="none", ecolor=INK, elinewidth=0.8, capsize=2)
    txt = f"{saved:+.2f} h" if saved < 0 else f"{saved:.2f} h"
    xpos = max(saved, 0) + ci + 0.15
    ax.text(xpos, yi, txt, va="center", fontsize=7.5, color=INK)
ax.set_yticks(y)
ax.set_yticklabels([r[1] for r in rows])
ax.axvline(0, color=INK, lw=0.7)
ax.set_xlabel("Detention saved per rake (h), paired 95 %% CI; base %.2f h" % e.loc["base (private siding)", "mean_detention_hr"])
ax.set_xlim(-1.0, 10.6)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(facecolor=BLUE, label="procedural (paperwork, hours)"),
                   Patch(facecolor=ORANGE, hatch="///", edgecolor="white", label="capital / physical"),
                   Patch(facecolor=VERM, hatch="xx", edgecolor="white", label="makes it worse")],
          loc="lower right")
ax.grid(axis="y", visible=False)
save(fig, "fig_interventions")

# ------------------------------------------------------------------ Fig. sensitivity (tornado + hours)
b = rd("layer5_S1_bounds")
base = rd("layer5_S4_envelope").set_index("case").loc["base", "detention"]
nice = {
    "hours_terminal_shift": "Terminal hours/day (8-24)",
    "M6_mean": "Release reporting M6 (1.8-5.4 h)",
    "load_rate": "Loading rate (675-3,370 t/h)",
    "M5_mean": "Weighment M5 (0.9-2.7 h)",
    "t_per_wagon": "Payload per wagon (52-71 t)",
    "wagons": "Wagons per rake (42-59)",
    "M5_rework": "M5 rejection rate (0-36 %)",
    "M6_rework": "M6 rejection rate (0-20 %)",
}
t = b[b.param.isin(nice)].sort_values("detention_swing", ascending=True)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(W, 2.35), gridspec_kw={"width_ratios": [1.25, 1]})
yy = np.arange(len(t))
for yi, (_, r) in zip(yy, t.iterrows()):
    lo, hi = r.detention_at_low, r.detention_at_high
    a1.barh(yi, lo - base, left=base, height=0.6, color=SKY, edgecolor="white")
    a1.barh(yi, hi - base, left=base, height=0.6, color=BLUE, hatch="///", edgecolor="white")
    a1.text(max(lo, hi) + 0.4, yi, f"{r.detention_swing:.1f}", va="center", fontsize=7.5, color=INK)
a1.axvline(base, color=INK, lw=0.8)
a1.set_yticks(yy)
a1.set_yticklabels([nice[p] for p in t.param])
a1.set_xlabel("Mean detention (h); base %.2f h" % base)
a1.set_xlim(8, 37)
a1.legend(handles=[Patch(facecolor=SKY, label="low end of range"),
                   Patch(facecolor=BLUE, hatch="///", edgecolor="white", label="high end of range")],
          loc="lower right")
a1.grid(axis="y", visible=False)
panel(a1, "(a) One factor at a time (swing, h)")
h = rd("layer5b_hours_sweep")
a2.fill_between(h.terminal_hours_per_day, h.detention_h - h.detention_ci95, h.detention_h + h.detention_ci95,
                color=BLUE, alpha=0.18, lw=0)
a2.plot(h.terminal_hours_per_day, h.detention_h, color=BLUE, marker="o", markersize=3.2)
today = h[h.terminal_hours_per_day == 16].iloc[0]
a2.plot([16], [today.detention_h], marker="D", color=VERM, markersize=6, zorder=5)
a2.annotate(f"today, 16 h: {today.detention_h:.2f} h", (16, today.detention_h), xytext=(16.6, 21.5),
            fontsize=7.5, arrowprops=dict(arrowstyle="-", color=INK, lw=0.6))
a2.axhline(8, color=GRAY, ls=":", lw=0.9)
a2.text(8.2, 8.5, "free time 8 h", fontsize=7, color=GRAY)
a2.set_xlabel("Terminal paperwork hours per day (M4-M6)")
a2.set_ylabel("Mean detention (h)")
a2.set_xticks([8, 12, 16, 20, 24])
a2.set_ylim(5, 34)
panel(a2, "(b) Length of the terminal day")
fig.tight_layout(w_pad=1.2)
save(fig, "fig_sensitivity")

# ------------------------------------------------------------------ Fig. breakdown (time causes + money bands)
c = rd("layer8_B2_cause_split")
m = rd("layer8_B3_money")
pk = ["Today", "A", "B", "C"]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(W, 2.35))
parts = [("loading_physical_h", "loading (physical)", GREEN, None),
         ("paperwork_working_time_h", "paperwork working time", BLUE, None),
         ("rework_h", "rework (rejected papers)", ORANGE, "///"),
         ("waiting_for_office_to_open_h", "waiting for office to open", VERM, "xx")]
x = np.arange(4)
bottom = np.zeros(4)
for col, lab, colr, ht in parts:
    v = c[col].to_numpy()
    a1.bar(x, v, 0.6, bottom=bottom, color=colr, hatch=ht, edgecolor="white", linewidth=0.4, label=lab)
    bottom += v
for xi, tot in zip(x, c.detention_h):
    a1.text(xi, tot + 0.3, f"{tot:.2f}", ha="center", fontsize=7.5, color=INK,
            bbox=dict(facecolor="white", edgecolor="none", pad=0.6))
a1.axhline(8, color=INK, ls=":", lw=0.9)
a1.set_xlim(-0.5, 4.6)
a1.text(4.58, 8.3, "free time 8 h", fontsize=7, ha="right", va="bottom", color=INK)
a1.set_xticks(x)
a1.set_xticklabels(pk)
a1.set_ylabel("Billed detention per rake (h)")
a1.set_ylim(0, 21)
a1.legend(loc="upper right", fontsize=7)
a1.grid(axis="x", visible=False)
panel(a1, "(a) Why the billed window is long")
bands = [("dem_band_0_6h", "0-6 h  (Rs 150)", SKY, None), ("dem_band_6_12h", "6-12 h (Rs 165)", BLUE, "///"),
         ("dem_band_12_24h", "12-24 h (Rs 187.5)", ORANGE, None), ("dem_band_24_48h", "24-48 h (Rs 225)", VERM, "xx")]
bottom = np.zeros(4)
for col, lab, colr, ht in bands:
    v = m[col].to_numpy() / 1000
    a2.bar(x, v, 0.6, bottom=bottom, color=colr, hatch=ht, edgecolor="white", linewidth=0.4, label=lab)
    bottom += v
for xi, tot in zip(x, m.demurrage_per_rake / 1000):
    a2.text(xi, tot + 1.5, f"{tot:.1f}", ha="center", fontsize=7.5, color=INK)
a2.set_xticks(x)
a2.set_xticklabels(pk)
a2.set_ylabel("Demurrage per rake (Rs thousand)")
a2.set_ylim(0, 100)
a2.legend(title="hours beyond free time (rate per wagon-h)", title_fontsize=7, loc="upper right", fontsize=7)
a2.grid(axis="x", visible=False)
panel(a2, "(b) Where the rupees fall (IR bands)")
fig.tight_layout(w_pad=1.5)
save(fig, "fig_breakdown")

# ------------------------------------------------------------------ Fig. capacity (Layer 9)
k1 = rd("layer9_K1_traffic_sweep")
k2 = rd("layer9_K2_capacity").set_index("config")
cfgs = [("TODAY", "Today", GRAY, "o", "-"),
        ("A paperwork 24/7 + digital release", "A", BLUE, "s", "-"),
        ("B = A + precise loading", "B", SKY, "^", "-"),
        ("C = B + faster loading", "C", GREEN, "D", "-"),
        ("TODAY + 2nd line + 2nd crew", "Today + 2nd line", ORANGE, "v", "--"),
        ("A + 2nd line + 2nd crew", "A + 2nd line", VERM, "P", "--")]
w_today = k2.today_wait_target_h.iloc[0]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(W, 3.1), gridspec_kw={"width_ratios": [1.25, 1]})
for key, lab, col, mk, ls in cfgs:
    t = k1[k1.config == key].sort_values("offered_rakes_per_yr")
    t = t[t.wait_h <= 400]
    a1.plot(t.offered_rakes_per_yr, t.wait_h, color=col, marker=mk, markersize=3, ls=ls, lw=1.4, label=lab, markevery=2)
a1.axhline(w_today, color=INK, ls=":", lw=0.9)
a1.text(1290, w_today / 1.12, f"today's wait {w_today:.0f} h", fontsize=7, ha="left", va="top", color=INK)
a1.axvline(292, color=INK, ls=":", lw=0.7)
a1.text(305, 3.0, "today 292/yr", fontsize=7, color=INK, va="bottom")
a1.set_yscale("log")
a1.set_ylim(2.5, 420)
a1.set_xlim(240, 1620)
a1.set_xlabel("Rakes offered per year")
a1.set_ylabel("Mean wait before placement (h, log)")
a1.legend(fontsize=6.8, loc="lower right", ncol=2)
panel(a1, "(a) Queue as traffic grows")
yy = np.arange(len(cfgs))[::-1]
for yi, (key, lab, col, mk, ls) in zip(yy, cfgs):
    ss, ce = k2.loc[key, "same_service_capacity_rakes_per_yr"], k2.loc[key, "ceiling_rakes_per_yr"]
    a2.barh(yi, ce, height=0.62, color="white", edgecolor=col, hatch="////", linewidth=0.8)
    a2.barh(yi, ss, height=0.62, color=col, edgecolor="white")
    a2.text(ce + 25, yi, f"{ss:.0f} / {ce:.0f}", va="center", fontsize=7, color=INK)
a2.axvline(292, color=INK, ls=":", lw=0.7)
a2.set_yticks(yy)
a2.set_yticklabels([c[1] for c in cfgs])
a2.set_xlim(0, 1950)
a2.set_xlabel("Rakes per year")
a2.grid(axis="y", visible=False)
a2.legend(handles=[Patch(facecolor=GRAY, label="same-service capacity"),
                   Patch(facecolor="white", edgecolor=GRAY, hatch="////", label="ceiling (line 100 % busy)")],
          fontsize=6.8, loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=2)
panel(a2, "(b) Rakes a year the siding can take")
fig.tight_layout(w_pad=1.2)
save(fig, "fig_capacity")

# ------------------------------------------------------------------ Fig. Morris screening (Layer 5)
mo = rd("layer5_S3_morris").sort_values("mu_star", ascending=False)
top = mo.head(8)
fig, ax = plt.subplots(figsize=(W * 0.62, 2.6))
grp_col = {"administrative": BLUE, "operational": ORANGE}
for _, r in mo.iterrows():
    ax.scatter(r.mu_star, r.sigma, s=16, color=grp_col.get(r.group, GRAY),
               marker="o" if r.group == "administrative" else "s", edgecolor="white", linewidth=0.4, zorder=3)
lab = {"hours_terminal_shift": ("terminal hours (M4-M6)", -6.5, 0.2), "M6_mean": ("M6 release time", 0.4, 0.15),
       "load_rate": ("loading rate", 0.4, -0.6), "M5_mean": ("M5 weighment time", 0.4, -0.25)}
for _, r in top.iterrows():
    if r.param in lab:
        t, dx, dy = lab[r.param]
        ax.annotate(t, (r.mu_star, r.sigma), xytext=(r.mu_star + dx, r.sigma + dy), fontsize=7)
ax.annotate("rejection rates, M4, payload,\nwagons, shunting: all small", (1.2, 0.8), xytext=(6.5, 5.4), fontsize=7,
            arrowprops=dict(arrowstyle="-", color=INK, lw=0.5))
ax.set_xlabel(r"$\mu^*$ (mean |elementary effect|, h)")
ax.set_ylabel(r"$\sigma$ (h)")
ax.set_xlim(-0.5, 23.5)
ax.legend(handles=[plt.Line2D([], [], marker="o", ls="", color=BLUE, label="administrative"),
                   plt.Line2D([], [], marker="s", ls="", color=ORANGE, label="operational")], loc="upper left")
fig.tight_layout()
save(fig, "fig_morris")

# ------------------------------------------------------------------ Fig. levers by commodity (Layer 6)
c2 = rd("layer6_C2_levers")
c2 = c2[~c2.lever.str.startswith("R1")]
lev_short = {"G1 terminal 24/7 (M4-M6)": "Terminal\n24/7", "G2 digitalise M6 release reporting": "Digital\nrelease",
             "G3 digitalise M5 weighment": "Digital\nweighment", "G4 2nd line + 2nd crew": "2nd line\n+ crew",
             "S1 loading rate +50 % (labour/mechanisation)": "Loading\n+50 %",
             "S2 precise loading (no overload)": "Precise\nloading", "S3 silo / rapid loading system (bulk only)": "Silo\n(bulk)"}
com_short = {"COAL (open BOXN)": "Coal (open)", "COAL (hopper BOBRN)": "Coal (hopper)", "IRON ORE": "Iron ore",
             "CLINKER": "Clinker", "CEMENT (bagged, BCN)": "Cement (bags)", "FOODGRAINS": "Foodgrains",
             "FERTILISER": "Fertiliser", "IRON & STEEL (flat, crane)": "Iron & steel", "CONTAINERS": "Containers",
             "POL (tank)": "POL (tank)"}
piv = c2.pivot_table(index="commodity", columns="lever", values="d_detention_h", sort=False)
piv = piv.reindex(index=list(com_short), columns=list(lev_short))
fig, ax = plt.subplots(figsize=(W, 3.0))
im = ax.imshow(-piv.values, cmap="Blues", vmin=0, vmax=7, aspect="auto")
for i in range(piv.shape[0]):
    for j in range(piv.shape[1]):
        v = piv.values[i, j]
        if np.isnan(v):
            ax.text(j, i, "n/a", ha="center", va="center", fontsize=7, color=GRAY)
        else:
            v = 0.0 if abs(v) < 0.05 else v
            ax.text(j, i, f"{v:+.1f}" if v else "0.0", ha="center", va="center", fontsize=7.2,
                    color="white" if -v > 4 else INK)
ax.set_xticks(range(piv.shape[1]))
ax.set_xticklabels(list(lev_short.values()), fontsize=7.5)
ax.set_yticks(range(piv.shape[0]))
ax.set_yticklabels([com_short[c] for c in piv.index], fontsize=7.5)
ax.grid(False)
for sp in ax.spines.values():
    sp.set_visible(False)
cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
cb.set_label("detention saved (h)", fontsize=7.5)
cb.ax.tick_params(labelsize=7)
fig.tight_layout()
save(fig, "fig_commodity")
