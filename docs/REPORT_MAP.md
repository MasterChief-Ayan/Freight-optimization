# MTP-1 report map: every section, table, figure and equation -> what it says -> where it comes from

Report: `thesis/mtp1/` (41 pages, signed 12-Nov-2026). The MTP-2 thesis reuses this report as it is
and adds Part II on top, so this map is the dot-to-dot reference. Numbers are checked by
`thesis/mtp1/audit_numbers.py` (122 checks) against `results/`. Errata: `thesis/mtp1/README.md`.
PDF page = printed page + 10 (front matter i-x).

## Front matter (`main.tex`)
| Item | Content |
|---|---|
| Title page | "A Thesis (Part I)", Master of Technology in Industrial and Systems Engineering, dated 12 November 2026 |
| Declaration (p. 2), Certificate (p. 3), Acknowledgements (p. 4) | supervisor Prof. Biswajit Mahanty; research scholar Mr. Ranit Senapati (ER register data) |
| Abstract (3 paragraphs) | problem / what was done / what was found (supervisor's required format); erratum: "15.5x more than capital ones" -> vs a 2nd line with crew |
| Lists | Contents, Figures, Tables, Abbreviations |

## Chapter 1 Introduction (`ch1_introduction.tex`)
| Section | What it says | Source |
|---|---|---|
| 1.1 Background | rake, detention, free time, demurrage; TERI 14-17 h, 80-85 % restrictions from poor release; PIB loading <=5 h payloader, ~1 h rapid loading; coal 61 % of ER tonnes | TERI 2023 Vol I; PIB 07.10.2024; `results/field.log` |
| 1.2 Siding and charging rules, **Table 1.1** graded bands | free time 5+2+1 = 8 h; Rs 150/wagon-h x (1, 1.1, 1.25, 1.5, 2, 3) over 0/6/12/24/48/72 h; penal up to x6; 06:00-22:00; clock placement -> release; document chain | MoR Compendium 03.04.2024 (2.2, 2.2.1, 2.7, 3.1, 3.4.1, 4.1) |
| 1.3.1-1.3.5 Literature review | dwell time (Refas, Raballand, WCO TRS, TERI); appointment systems and MAS (Guan & Liu, Parmaksizoglou, Smith CNP); scheduling 1\|r_j\|SumC_j with non-availability (Graham, Azem, Sousa & Wolsey); DES credibility (Robinson, Sargent, Law), sensitivity (Morris, Campolongo, Saltelli), Shapley, Little, Pollaczek-Khinchine (Gross); research gap (4 points) | `references.tex` (29) |
| 1.4 Problem statement | the question + 3 difficulties (coupled causes, four parties, missing time data) | — |
| 1.5 Objectives (6) | model, sources of detention, ranking with bounds, commodities and labour, breakdown + capacity, sufficiency + damage | — |
| 1.6 Scope and assumptions | 1 line, 1 crew, 1 loco, coal BOXN; boundary wagon demand -> departure; A1 coal always available (+2.9 h if relaxed); paperwork times assumed | `results/l2.log` (A1) |
| 1.7 Organisation | chapter guide | — |

## Chapter 2 Modelling (`ch2_modelling.tex`)
| Item | What it says | Source in repo |
|---|---|---|
| 2.1, **Fig 2.1** (TikZ) | layered build L0-L9, each verified before the next | `experiments/`, `rtsim/` |
| 2.2, **Fig 2.2** (TikZ), **Table 2.1** | siding, four parties; M1-M8: owner, calendar (railway office 10-17 Mon-Sat, terminal office 09-18 Mon-Sat, terminal shift 06-22, 24/7), lognormal mean/sd (M8 Erlang), rework 0.05-0.20 (M5 30 % for coal), gate | `rtsim/admin.py` `default_steps()` |
| 2.3, **Tables 2.2-2.3** | 4 filters (relevance, evidence, control, measurability); 23 factors: 13 in, 1 partial, 5 left out (stress-tested), 4 out of scope | `docs/VARIABLE_SELECTION.md` |
| 2.4, **Table 2.4** | ER inward register Jan 2022-Aug 2026: 56 files, 220,395 RRs, 508.5 Mt (338 sub-total rows removed), 220 codes -> 16 groups (97 %), coal 61 %, iron ore 11 %; arrivals Poisson (VMR 0.7-1.7 at 15 largest terminals); ten commodity profiles | `tools/rr_register.py`, `tools/analyse_rr_register.py`, `results/field.log`, `results/layer6_C1_commodity_baseline.csv` |
| 2.5, **Table 2.5** notation | symbols used below | — |
| **Eq 2.1** lognormal LN(m,s) | sigma^2 = ln(1+s^2/m^2), mu = ln m - sigma^2/2; loading L = Q / max(mu_r, mu_min), floor 300 t/h | `rtsim/distributions.py`, `rtsim/terminal.py` |
| **Eq 2.2** calendar operator Phi_k(t,d) | work pauses at closing, resumes at opening; 0.5 h started 15 min before closing ends ~8.5 h later | `rtsim/admin.py` (calendars) |
| **Eq 2.3** rework | truncated geometric, max 5 attempts per step, each attempt through the calendar again | `rtsim/admin.py` (`max_retries = 4`) |
| **Eq 2.4** event recursion | a, s, p, l, e, u, m, delta; M3 gates placement, M4+M2+crew gate loading, M5->M6 gate release, loco gates removal, M7 gates departure; <= K overlapping line holds | `rtsim/terminal.py` (rake process) |
| **Eq 2.5** measures | D = u - p (detention, billed), W = s - a (wait), H = m - s (line hold), Gamma = delta - a (cycle) | `rtsim/accounting.py`, `experiments/run_layer9_capacity.py` |
| **Eq 2.6** graded demurrage | kappa N_w Sum g_b [min(E,U_b) - U_(b-1)]+, E = ceil(D - 8)+; convex | `rtsim/accounting.py` |
| **Eq 2.7** derived | wagons freed (Little's law; Rs 1,140 cr / 2,583 per wagon), data leak (overload penalty + unused paid capacity), labour break-even per tonne | `experiments/run_layer8_breakdown.py`, `run_layer6_commodities.py` |
| **Eqs 2.8-2.10** capacity | ceiling K x 8760 / H; same-service capacity R* = max{R : W(R) <= W_today(292) = 35.0 h} (interpolated); utilisations; Pollaczek-Khinchine W_q = lambda E[S^2] / (2(1 - rho)) | `experiments/run_layer9_capacity.py` |
| **Eqs 2.11-2.13** dispatch | FCFS, SPT, Contract Net bid (expected demurrage + idle cost Rs 3,000/h - ageing 0.5); CP-SAT NoOverlap offline sequence and valid lower bound; waiting split admin / <= sequencing / irreducible | `rtsim/policies.py`, `rtsim/optimiser.py`, `experiments/decompose.py` |
| **Eqs 2.14-2.17** statistics | paired 95 % CI (1.96, common random numbers via BLAKE2b keyed streams); OAT swing and envelope; Morris (4 levels, Delta 2/3, 20 trajectories, mu*, sigma); exact detention split (telescoping); Shapley; Kendall tau_a | `rtsim/experiment.py`, `experiments/run_layer5_sensitivity.py`, `run_layer8_breakdown.py`, `run_layer7_sufficiency.py` |
| 2.5.9 wagon damage | Bin(N_w, p) defects, minor/repair/unfit 0.6/0.3/0.1, detach or return rake, loading damage; assumed rates; off by default | `rtsim/damage.py` |
| 2.6, **Table 2.6** provenance | 18 cited, 1 derived, 10 assumed; calibrated 15.53 h inside TERI 14-17 h | `rtsim/calibration.py` |
| 2.7, **Table 2.7** design | L3/L4: 25 rakes, gap 22 h (rho about 0.8, erratum "0.7"), 10 reps (E11 12 reps); L5-L8: 50 rakes (warm-up 5), 30 reps, gap 30 h = 292 rakes/yr; L9: 200 rakes (warm-up 20), 30 reps, 250-1600 rakes/yr; levers H/D/P/L, packages A = H+D, B = A+P, C = B+L | `experiments/*.py` |
| 2.8, **Table 2.8** implementation | modules and the 107 checks (70 model + 37 extensions) with real check names | `rtsim/verify_*.py`, `tools/verify_extensions.py`, `results/verify_*.log` |

## Chapter 3 Results and Discussion (`ch3_results.tex`)
| Item | Key numbers | Source CSV / script |
|---|---|---|
| 3.1, **Table 3.1** attribution | detention 15.53 h vs 4.05 h physical; queue 51 % of rake time; terminal / client / railway 73.5 / 23.7 / 2.9 % | `layer1_attribution.csv` |
| 3.2 sources of detention | waiting 78 % admin (office hours 73.3 %, rework 10.9 %), <= 8 % sequencing, 14 % irreducible; no online rule beats FCFS significantly; CNP ageing cuts worst wait 33 % | `layer3_E11_decomposition.csv`, `layer3_E8_ladder.csv`, `layer3_E10_fairness.csv` |
| 3.3, **Fig 3.1** interventions | base 16.07 h; digitalise all -8.98, M5+M6 -7.65, terminal 24/7 -5.28, +50 % loading -2.08, no rework -1.40, 2nd line + crew -0.58, 2nd loco 0, 2nd line alone +0.28 (n.s.); 15.5x; breaches 86.8 % -> 24.5 % | `layer4_E12_interventions.csv`; `figures/gen_figs.py` fig_interventions |
| 3.4, **Fig 3.2** (a tornado, b hours curve) | terminal hours swing 21.17 h (31.86 -> 10.69); M6 6.63; loading rate 6.60 (675-3,370 t/h); M5 3.59; 16 -> 18 h = 43 % of the 24/7 gain; envelope 3.54-51.41 h | `layer5_S1_bounds.csv`, `layer5_S4_envelope.csv`, `layer5b_hours_sweep.csv` |
| 3.4, **Fig 3.3** Morris | same top three as OAT | `layer5_S3_morris.csv` |
| 3.5, **Fig 3.4**, **Table 3.2** commodities | G1 24/7 -4.1 to -6.1 h every commodity; G2 -3.7 to -4.6; material-specific: precise loading, silo, 2nd line; labour break-even 46 % (bulk) / 10 % (bagged) of handling rates | `layer6_C2_levers.csv`, `layer6_C2_lever_classes.csv`, `layer6_C5_labour_vs_demurrage.csv` |
| 3.6.1, **Fig 3.5** hours | billed 17.0 h = 4.7 loading + 5.9 paperwork + 1.1 rework + 5.4 office wait; A 9.50, B 8.82, C 7.25 | `layer8_B1_time_breakdown.csv`, `layer8_B2_cause_split.csv` |
| 3.6.2, **Table 3.3** rupees | demurrage/rake 89,786 -> 19,651 (A) -> 14,195 (B) -> 6,265 (C); A saves Rs 2.05 cr/yr (demurrage only); data leak Rs 4.20 cr/yr removed by precise loading; wagons freed ~48 (Rs 21 cr) | `layer8_B3_money.csv` |
| 3.6.3, **Table 3.4** Shapley | package C 9.77 h: 24/7 37 %, digital release 34 %, faster loading 19 %, precise 9 %; A: H 4.14 h, D 3.38 h | `layer8_B4_shapley.csv` |
| 3.6.4 who gains | client demurrage, Railway wagons, terminal capacity | `layer8_B3_money.csv` |
| 3.7, **Fig 3.6**, **Table 3.5** capacity | today 292 (ceiling 458); A 556 (+90 %, ceiling 756); B 613; C 732; 2nd line + crew 710 (928); A + 2nd line 1,262 (1,507, x4.3); line 0.64, crew 0.16, loco 0.07 at 292; crew <= 0.34, loco <= 0.29 at capacity | `layer9_K1_traffic_sweep.csv`, `layer9_K2_capacity.csv` |
| 3.7, **Table 3.6** PK check | offices open, line < 0.8: 0.91-1.03; as modelled 1.04-1.96 (office hours bunch arrivals) | `layer9_K3_queue_check.csv` |
| 3.8, **Table 3.7** damage + loco | return rake costs the Railway 2.3-2.6x the wagon time of detaching; loco never a constraint | `layer8_B7_damage.csv` |
| 3.9, **Table 3.8** sufficiency | 8 stress tests + model as built; detention 15.5 -> 23.1 h; Kendall tau = 1.00 in all; best procedural / best capital 3.6-6.6x | `layer7_O1_sufficiency.csv`, `layer7_O2_rank_stability.csv` |
| 3.10, **Table 3.9** summary | time, cost, capacity per package | Layer 8 + Layer 9 |

## Chapter 4 Conclusion (`ch4_conclusion.tex`)
4.1 seven findings (erratum in finding 4's reason), 4.2 recommendations (terminal, capacity planning,
Railway, client), 4.3 limitations (calibration not validation, gross savings, assumed damage,
M7 vs e-RR 99.7 %, one siding), 4.4 Part II future work (6 items).

## How MTP-2 builds on this
Keep Chapters 1-4 as the Part I core (after fixing the errata); add Part II work as new sections
or chapters: validation on time logs (2.6 / new validation chapter), implementation cost and payback
(3.6 + new), capacity for other commodities and staged expansion (3.7), M7 recalibration, damage and
locomotive detail (3.8). Regenerate every figure with `figures/gen_figs.py` and every number with
the audit after each change.
