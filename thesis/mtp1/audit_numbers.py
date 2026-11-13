"""Audit: every result number quoted in the report is recomputed from the repo's result CSVs.
    python audit_numbers.py <Freight-optimization>/results
"""
import re, sys, glob
import numpy as np, pandas as pd
R = sys.argv[1]
tex = " ".join(open(f).read() for f in ["main.tex"] + sorted(glob.glob("ch*.tex")))
tex = re.sub(r"\s+", " ", tex)
c = lambda n: pd.read_csv(f"{R}/{n}.csv")
chk = []
def add(text, value, label):  # value must equal text, and text must be in the report
    chk.append((text, value, label))
f1, f2, f0 = (lambda x: f"{x:.1f}"), (lambda x: f"{x:.2f}"), (lambda x: f"{x:.0f}")
com = lambda x: f"{x:,.0f}"

# ---- Layer 1 attribution
a = c("layer1_attribution").set_index("segment")
for seg, lab in [("queueing_for_line", "Queueing for the line"), ("rr_and_payment", "Railway receipt and payment (M7)"),
                 ("release_reporting", "Release reporting (M5, M6)"), ("loading", "Loading"),
                 ("waiting_for_crew", "Waiting for the crew"), ("placement_shunting", "Placement shunting"),
                 ("removal_shunting", "Removal shunting")]:
    v = f"{a.loc[seg,'mean_hr']:.2f} & {a.loc[seg,'share_pct']:.1f}"
    add(v, v, "attrib " + seg)
own = a.groupby("owner").share_pct.sum()
add("terminal 73.5\\,\\%, client 23.7\\,\\%, Railway 2.9\\,\\%",
    f"terminal {own.terminal:.1f}\\,\\%, client {own.client:.1f}\\,\\%, Railway {own.railway:.1f}\\,\\%", "owners")
# ---- Layer 5 base, envelope, bounds
env = c("layer5_S4_envelope").set_index("case")
add("15.53 $\\pm$ 0.33", f"{env.loc['base','detention']:.2f} $\\pm$ {env.loc['base','detention_ci']:.2f}", "base")
add("84\\,\\% exceed", f"{env.loc['base','breach']*100:.0f}\\,\\% exceed", "base breach")
add("3.54 to 51.41", f"{env.loc['all favourable ends','detention']:.2f} to {env.loc['all unfavourable ends','detention']:.2f}", "envelope")
add("Rs 75,962 to Rs 4.56 lakh", f"Rs {com(env.loc['base','demurrage_pr'])} to Rs {c('layer5_S1_bounds').set_index('param').loc['penal','demurrage_pr_at_high']/1e5:.2f} lakh", "penal")
b = c("layer5_S1_bounds").set_index("param")
add("from 31.86\\,h (8\\,h a day) to 10.69\\,h", f"from {b.loc['hours_terminal_shift','detention_at_low']:.2f}\\,h (8\\,h a day) to {b.loc['hours_terminal_shift','detention_at_high']:.2f}\\,h", "hours")
add("swing of 21.2", f"swing of {b.loc['hours_terminal_shift','detention_swing']:.1f}", "swing")
add("6.6\\,h each", f"{b.loc['M6_mean','detention_swing']:.1f}\\,h each", "M6 swing"); add("6.6\\,h each", f"{b.loc['load_rate','detention_swing']:.1f}\\,h each", "load swing")
h = c("layer5b_hours_sweep").set_index("terminal_hours_per_day").detention_h
add("(2.07 of 4.84\\,h)", f"({h[16]-h[18]:.2f} of {h[16]-h[24]:.2f}\\,h)", "18h gain"); add("43\\,\\% of the round", f"{(h[16]-h[18])/(h[16]-h[24])*100:.0f}\\,\\% of the round", "43%")
s2 = c("layer5_S2_conditions").set_index("condition")
add("save 6.55\\,h", f"save {-s2.loc['M6_removed','d_detention']:.2f}\\,h", "M6 removed")
add("save only 0.67\\,h of detention but 17.7\\,h of waiting", f"save only {-s2.loc['lines2_crews2','d_detention']:.2f}\\,h of detention but {-s2.loc['lines2_crews2','d_wait']:.1f}\\,h of waiting", "2 lines")
mo = c("layer5_S3_morris").sort_values("mu_star", ascending=False)
add("top3", "top3" if list(mo.param[:3]) == ["hours_terminal_shift", "M6_mean", "load_rate"] and mo.param.iloc[3] == "M5_mean" else "X", "morris order")
add("$\\mu^* < 2$\\,h", "$\\mu^* < 2$\\,h" if (mo.mu_star.iloc[4:] < 2).all() else "X", "morris rest")
# ---- Layer 3
e8 = c("layer3_E8_ladder").set_index("policy"); e10 = c("layer3_E10_fairness").set_index("ageing_weight")
add("worst rake wait 161.2\\,h", f"worst rake wait {e10.loc[0.0,'worst_wait']:.1f}\\,h", "worst no ageing")
add("cuts that to 108.1\\,h ($-33$\\,\\%)", f"cuts that to {e10.loc[0.5,'worst_wait']:.1f}\\,h ($-{(1-e10.loc[0.5,'worst_wait']/e10.loc[0.0,'worst_wait'])*100:.0f}$\\,\\%)", "fairness")
ok = all(abs(e8.loc[p,'mean_wait_hr'] - e8.loc['FCFS','mean_wait_hr']) < e8.loc['FCFS','mean_wait_hr_ci'] for p in ["SPT","COST","CNP"])
add("same mean wait", "same mean wait" if ok else "X", "dispatch n.s.")
d = c("layer3_E11_decomposition").mean()
for txt, val in [("73.3\\,\\%", 1-d.nocal/d.full), ("10.9\\,\\%", 1-d.norw/d.full), ("77.8\\,\\%", 1-d.flat/d.full)]:
    add(txt, f"{val*100:.1f}\\,\\%", "E11")
add("seq8", "seq8" if (d.flat-d.bound)/d.full <= 0.085 and round(d.bound/d.full*100) == 14 else "X", "E11 seq/irr")
# ---- Layer 4
e = c("layer4_E12_interventions").set_index("scenario")
add("saves 8.98\\,h", f"saves {-e.loc['digitalise all admin','d_mean_detention_hr']:.2f}\\,h", "dig all")
add("saves 0.58\\,h", f"saves {-e.loc['2nd line + 2nd crew','d_mean_detention_hr']:.2f}\\,h", "2nd line crew")
add("(16.07\\,h at", f"({e.loc['base (private siding)','mean_detention_hr']:.2f}\\,h at", "E12 base")
add("86.8\\,\\% to 24.5\\,\\%", f"{e.loc['base (private siding)','breach_rate']*100:.1f}\\,\\% to {e.loc['digitalise all admin','breach_rate']*100:.1f}\\,\\%", "breach")
add("about 15.5", f"about {e.loc['digitalise all admin','d_mean_detention_hr']/e.loc['2nd line + 2nd crew','d_mean_detention_hr']:.1f}", "ratio")
add("(+0.28\\,h", f"(+{e.loc['2nd loading line','d_mean_detention_hr']:.2f}\\,h", "2nd line alone")
add("from 44.3 to 17.2\\,h", f"from {e.loc['base (private siding)','mean_wait_hr']:.1f} to {e.loc['2nd line + 2nd crew','mean_wait_hr']:.1f}\\,h", "E12 wait")
# ---- Layer 6
c1 = c("layer6_C1_commodity_baseline")
add("13.4\\,h (containers) to 22.0\\,h (foodgrains)", f"{c1.detention_h.min():.1f}\\,h (containers) to {c1.detention_h.max():.1f}\\,h (foodgrains)", "C1 range")
names = {"COAL (open BOXN)": "Coal (open BOXN)", "COAL (hopper BOBRN)": "Coal (hopper BOBRN)", "IRON ORE": "Iron ore", "CLINKER": "Clinker",
         "CEMENT (bagged, BCN)": "Cement (bagged)", "FOODGRAINS": "Foodgrains", "FERTILISER": "Fertiliser",
         "IRON & STEEL (flat, crane)": "Iron and steel (crane)", "CONTAINERS": "Containers", "POL (tank)": "POL (tank)"}
for _, r in c1.iterrows():
    v = f"{names[r.commodity]} & {r.wagons:.0f} & {r.t_per_wagon:.1f} & {r.load_method} & {r.load_rate_tph_ASSUMED:.0f} & {r.free_time_h:.0f} & {r.M5_rework_from_overload*100:.1f}\\,\\% \\\\"
    add(v, v, "C1 " + r.commodity)
cl = c("layer6_C2_lever_classes").set_index("lever")
for k, t in [("G1 terminal 24/7 (M4-M6)", "$-4.1$ to $-6.1$"), ("G2 digitalise M6 release reporting", "$-3.7$ to $-4.6$"),
             ("S1 loading rate +50 % (labour/mechanisation)", "$-1.4$ to $-3.7$"), ("G3 digitalise M5 weighment", "$-1.4$ to $-3.8$"),
             ("S3 silo / rapid loading system (bulk only)", "$-4.3$ to $-5.0$"), ("S2 precise loading (no overload)", "$0.0$ to $-2.0$"),
             ("G4 2nd line + 2nd crew", "$+0.2$ to $-0.9$")]:
    r = cl.loc[k]; v = f"${r['max']:+.1f}$ to ${r['min']:.1f}$".replace("$+0.0$", "$0.0$").replace("$-0.0$", "$0.0$")
    if r["max"] < 0: v = v.replace(f"${r['max']:+.1f}$", f"${r['max']:.1f}$")
    add(t, v, "C2 " + k)
c5 = c("layer6_C5_labour_vs_demurrage").set_index("commodity")
add("Rs 5.5 per tonne", f"Rs {c5.loc['COAL (open BOXN)','breakeven_Rs_per_t']:.1f} per tonne", "B bulk")
add("about 46\\,\\%", f"about {c5.loc['COAL (open BOXN)','breakeven_pct_of_handling_rate']*100:.0f}\\,\\%", "B % coal")
add("Rs 9 per tonne", f"Rs {c5.loc['CEMENT (bagged, BCN)','breakeven_Rs_per_t']:.0f} per tonne", "B bagged")
# ---- Layer 7
o = c("layer7_O2_rank_stability")
for _, r in o.iterrows():
    v = f"{r.base_detention_h:.2f} & {r.kendall_tau_vs_built:.2f} & {r.procedure_over_capital:.1f}"
    add(v, v, "L7 " + r.omitted_factor)
add("3.6--6.6 times", f"{o.procedure_over_capital.min():.1f}--{o.procedure_over_capital.max():.1f} times", "L7 range")
add("15.5 to 23.1\\,h", f"{o.base_detention_h.iloc[0]:.1f} to {o.base_detention_h.iloc[-1]:.1f}\\,h", "L7 level")
# ---- Layer 8
B1, B2, B3, B8, B4 = c("layer8_B1_time_breakdown"), c("layer8_B2_cause_split"), c("layer8_B3_money"), c("layer8_B8_next_bottleneck"), c("layer8_B4_shapley")
add("Detention per rake (h) $\\downarrow$ & 17.02 & 9.50 & 8.82 & 7.25", "Detention per rake (h) $\\downarrow$ & " + " & ".join(f2(x) for x in B1.detention_billed_window), "B1 det")
add("& 90 & 67 & 59 & 28", "& " + " & ".join(f0(x*100) for x in B1.breach_share), "B1 breach")
add("& 37.4 & 20.2 & 19.4 & 17.9", "& " + " & ".join(f1(x) for x in B1.wait_hr), "B1 wait")
add("& 19.0 & 11.5 & 10.8 & 9.2", "& " + " & ".join(f1(x) for x in B1.line_held_per_rake), "B1 hold")
add("& 89,786 & 19,651 & 14,195 & 6,265", "& " + " & ".join(com(x) for x in B3.demurrage_per_rake), "B3 dem")
add("& -- & 2.05 & 2.21 & 2.44", "& -- & " + " & ".join(f2(x) for x in B3.demurrage_saved_Rs_cr_per_yr[1:]), "B3 saved")
add("& -- & -- & 4.20 & 4.20", "& -- & -- & " + " & ".join(f2(x) for x in B3.leak_saved_Rs_cr_per_yr[2:]), "leak")
w = B8[B8.RR_and_payment_digital == True].reset_index(drop=True)
add("& -- & 47.6 (21.0) & 50.5 (22.3) & 56.4 (24.9)", "& -- & " + " & ".join(f"{a:.1f} ({b:.1f})" for a, b in zip(w.wagons_freed[1:], w.fleet_value_Rs_cr[1:])), "wagons")
wo = B8[B8.RR_and_payment_digital == False].reset_index(drop=True)
add("37.5 wagons (Rs 16.5 crore)", f"{wo.wagons_freed[1]:.1f} wagons (Rs {wo.fleet_value_Rs_cr[1]:.1f} crore)", "wagons M7 office")
add("24.6\\,h less", f"{w.rake_hours_saved_vs_today_same_basis[1]:.1f}\\,h less", "rake h saved")
add("6.5 of the 17.0\\,h (38\\,\\%)", f"{B2.rework_h[0]+B2.waiting_for_office_to_open_h[0]:.1f} of the {B2.detention_h[0]:.1f}\\,h ({(B2.rework_h[0]+B2.waiting_for_office_to_open_h[0])/B2.detention_h[0]*100:.0f}\\,\\%)", "nonprod")
add("5.4\\,h of waiting", f"{B2.waiting_for_office_to_open_h[0]:.1f}\\,h of waiting", "office"); add("1.1\\,h of redoing", f"{B2.rework_h[0]:.1f}\\,h of redoing", "rework")
add("by 44\\,\\% but demurrage by 78\\,\\%", f"by {(1-B1.detention_billed_window[1]/B1.detention_billed_window[0])*100:.0f}\\,\\% but demurrage by {(1-B3.demurrage_per_rake[1]/B3.demurrage_per_rake[0])*100:.0f}\\,\\%", "44/78")
add("Rs 32,262 to Rs 1,900", f"Rs {com(B3.dem_band_6_12h[0])} to Rs {com(B3.dem_band_6_12h[1])}", "band 6-12")
add("Rs 15,152.5 to Rs 209", f"Rs {B3.dem_band_12_24h[0]:,.1f} to Rs {com(B3.dem_band_12_24h[1])}", "band 12-24")
add("Rs 1.44 lakh", f"Rs {B3.data_leak_per_rake[0]/1e5:.2f} lakh", "leak/rake")
s = B4[(B4.package.str.startswith("C")) & (B4.metric == "detention")].set_index("lever")
sm = B4[(B4.package.str.startswith("C")) & (B4.metric == "demurrage_pr")].set_index("lever")
for L, lab in [("H", "H Terminal paperwork 24/7"), ("D", "D Digital release reporting"), ("L", "L Loading 50\\,\\% faster"), ("P", "P Precise loading")]:
    v = f"{lab} & {-s.loc[L,'alone_change']:.2f} & {-s.loc[L,'shapley_change']:.2f} & {s.loc[L,'shapley_change']/s.package_change.iloc[0]*100:.0f}\\,\\% & {com(-sm.loc[L,'shapley_change'])} \\\\"
    add(v, v, "shapley " + L)
add("& 13.51 & 9.77 & 100\\,\\% & 83,521", f"& {-s.sum_of_alone.iloc[0]:.2f} & {-s.package_change.iloc[0]:.2f} & 100\\,\\% & {com(-sm.package_change.iloc[0])}", "shapley tot")
add("71\\,\\% of the saving", f"{(s.loc['H','shapley_change']+s.loc['D','shapley_change'])/s.package_change.iloc[0]*100:.0f}\\,\\% of the saving", "71%")
d7 = c("layer8_B7_damage"); d7 = d7[d7.package == "TODAY"]
for p in (0.005, 0.01, 0.02):
    x = d7[(d7.policy == "detach") & (d7.p_defect_per_wagon == p)].iloc[0]; y = d7[(d7.policy == "return_rake") & (d7.p_defect_per_wagon == p)].iloc[0]
    v = f"+{x.d_detention_h:.2f} & +{x.d_arrival_to_departure_h:.2f} & +{y.d_detention_h:.2f} & +{y.d_arrival_to_departure_h:.2f}"
    add(v, v, f"damage {p}")
# ---- Layer 9
k1, k2, k3 = c("layer9_K1_traffic_sweep"), c("layer9_K2_capacity").set_index("config"), c("layer9_K3_queue_check")
rows = [("TODAY", "Today"), ("A paperwork 24/7 + digital release", "A: paperwork 24/7, digital release"), ("B = A + precise loading", "B: A + precise loading"),
        ("C = B + faster loading", "C: B + faster loading"), ("TODAY + 2nd line + 2nd crew", "Today + second line + second crew"),
        ("A + 2nd line + 2nd crew", "A + second line + second crew")]
for key, lab in rows:
    r = k2.loc[key]
    ext = "-- & --" if key == "TODAY" else f"+{r.extra_rakes_vs_today:.0f} & +{r.extra_pct_vs_today:.0f}"
    v = f"{lab} & {r.line_hold_h_at_292:.1f} & {com(r.ceiling_rakes_per_yr)} & {com(r.same_service_capacity_rakes_per_yr)} & {ext} \\\\"
    add(v, v, "K2 " + key)
add("wait 35.0\\,h", f"wait {k2.loc['TODAY','today_wait_target_h']:.1f}\\,h", "today wait")
add("64\\,\\% line utilisation", f"{k2.loc['TODAY','line_util_at_292']*100:.0f}\\,\\% line utilisation", "util")
t = k1[k1.config == "TODAY"].set_index("offered_rakes_per_yr")
add("wait passes 85\\,h", "wait passes 85\\,h" if 85 < t.loc[400, "wait_h"] < 90 else "X", "400 wait")
add("only 448 a year", f"only {t.loc[550,'throughput_per_yr']:.0f} a year", "throughput 550")
add("4.3 times", f"{k2.loc['A + 2nd line + 2nd crew','same_service_capacity_rakes_per_yr']/292:.1f} times", "4.3x")
add("crew 16\\,\\% and the shunting locomotive 7\\,\\%", f"crew {k2.loc['TODAY','crew_util_at_292']*100:.0f}\\,\\% and the shunting locomotive {k2.loc['TODAY','loco_util_at_292']*100:.0f}\\,\\%", "util 292")
add("below 34\\,\\%", "below 34\\,\\%" if k2.crew_util_at_capacity.max() < 0.34 else "X", "crew max")
add("below 29\\,\\%", "below 29\\,\\%" if k2.loco_util_at_capacity.max() < 0.29 else "X", "loco max")
ta = k1[k1.config == "A paperwork 24/7 + digital release"].set_index("offered_rakes_per_yr")
add("Rs 1.12 crore, against Rs 2.66 crore", f"Rs {ta.loc[550,'demurrage_Rs_cr_per_yr']:.2f} crore, against Rs {t.loc[292,'demurrage_Rs_cr_per_yr']:.2f} crore", "dem traffic")
dr = k1.groupby("config").detention_h.agg(["min", "max"])
add("17.0--17.5\\,h (today) and 9.6\\,h (A)", f"{dr.loc['TODAY','min']:.1f}--{dr.loc['TODAY','max']:.1f}\\,h (today) and {dr.loc['A paperwork 24/7 + digital release','max']:.1f}\\,h (A)", "det vs traffic")
fl = k3[(k3.offices == "all open 24/7") & (k3.line_util < 0.8)]; am = k3[(k3.offices == "as modelled") & (k3.line_util < 0.8)]
add("0.91--1.03 times", f"{fl.sim_over_PK.min():.2f}--{fl.sim_over_PK.max():.2f} times", "PK open")
add("1.04--1.96 times", f"{am.sim_over_PK.min():.2f}--{am.sim_over_PK.max():.2f} times", "PK modelled")
cfg = {"Today": "TODAY", "A": "A paperwork 24/7 + digital release", "C": "C = B + faster loading"}
for lab, off, R_ in [("Today", "all open", 292), ("Today", "all open", 450), ("A", "all open", 292), ("A", "all open", 600),
                     ("Today", "as modelled", 292), ("A", "as modelled", 292), ("C", "as modelled", 292)]:
    r = k3[(k3.config == cfg[lab]) & (k3.offices == ("all open 24/7" if off == "all open" else "as modelled")) & (k3.offered_rakes_per_yr == R_)].iloc[0]
    v = f"{lab} & {off} & {R_} & {r.line_util:.2f} & {r.queue_wait_h:.2f} & {r.sim_over_PK:.2f} \\\\"
    add(v, v, f"K3 {lab} {off} {R_}")
for pk, (det, dem, wag, cap) in {"A": (1, 1, 1, "A paperwork 24/7 + digital release"), "B": (2, 2, 2, "B = A + precise loading"), "C": (3, 3, 3, "C = B + faster loading")}.items():
    v = f"{pk} & {B1.detention_billed_window[det]:.2f} & {B3.demurrage_saved_Rs_cr_per_yr[dem]:.2f} & {w.wagons_freed[wag]:.1f} & {k2.loc[cap,'same_service_capacity_rakes_per_yr']:.0f} \\\\"
    add(v, v, "summary " + pk)

bad = 0
for text, val, lab in chk:
    logic = text in ("top3", "seq8")          # logical checks, not strings in the text
    if not (text == val and (logic or text in tex)):
        bad += 1; print(f"FAIL {lab}: text '{text}' | recomputed '{val}' | in report: {text in tex}")
print(f"{len(chk)-bad}/{len(chk)} checks pass")
