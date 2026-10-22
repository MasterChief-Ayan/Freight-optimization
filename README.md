# rtsim — Rail Freight Terminal Simulation (MTP)

*Analysis of operational, commercial and managerial constraints at a freight terminal, and
solutions for quick release of rolling stock.* Ayan Ahmed (22MF3IM04) · Supervisor
Prof. Biswajit Mahanty.

A discrete-event simulation (Python / SimPy, variable-time increment) of a private coal siding
on Indian Railways. It is built in five layers, each verified before the next. All Indian Railways
charge rules are taken from the MoR Demurrage/Wharfage Compendium (03.04.2024).

| Layer | Adds | Code |
|---|---|---|
| 0 Physical | rakes, lines, locos, crews; arrive → place → load → release → remove; IR accounting | `rtsim/terminal.py`, `accounting.py` |
| 1 Administrative | M1–M7 paperwork with office-hour calendars and rework loops, gating the physical chain | `rtsim/admin.py` |
| 2 Road side | trucks, gate, one-way lane, truck appointment system, fairness, M8 | `rtsim/trucks.py` |
| 3 Decision | Contract-Net dispatch, CP-SAT sequence, valid lower bound, decomposition | `rtsim/optimiser.py` |
| 4 Scenarios | ten interventions, terminal type, pricing levers (config only) | `experiments/run_layer4.py` |
| 5 Sensitivity | every parameter and condition alone: bounds, Morris, envelope | `experiments/run_layer5_sensitivity.py` |
| 6 Commodities | 10 commodity profiles from field data; general vs material-specific levers | `experiments/run_layer6_commodities.py` |
| Field data | ER RR register 2022–26 decoded (220,395 RRs) | `tools/rr_register.py`, `tools/analyse_rr_register.py` |

**Status:** Layers 0–6 complete, **76/76 integrity checks pass**. Next: selection-provenance table,
scaling, validation once placement–release logs arrive, LaTeX thesis (see `docs/PROJECT_STORY.md` §5–8).

## Quick start
```bash
pip install -r requirements.txt
bash run_all.sh quick        # 57 checks + provenance table (~1 min)
bash run_all.sh              # every chart/CSV/log into results/ (~15 min on 2 cores)
python tools/dry_run_two_rakes.py   # watch one replication, event by event
```

## Read next
- `docs/PROJECT_STORY.md`: how the project started, the mid-term, current work, the final target, the field-data plan, and which numbers to quote.
- `docs/CODEBASE.md`: what every file does, how they connect, and where a new feature goes.

## Headline results (final code, `results/`)
| Finding | Number |
|---|---|
| Baseline detention vs TERI benchmark 14–17 h | **15.53 ± 0.33 h** (physical model alone: 4.05 h) |
| Waiting decomposition (E11) | administrative **78%** (office hours 73.3%, rework 10.9%), optimal sequencing ≤ **8%**, irreducible **14%** |
| Best levers (E12, detention saved per rake) | digitalise all admin 8.98 h · digitalise M5 + M6 7.65 h · terminal 24/7 5.28 h · +50% load rate 2.08 h · 2nd line + crew 0.58 h · **2nd line alone −0.28 h** (worse; not significant at n = 10, but the same direction as the significant Layer 0 result 4.05 → 4.30 h) |
| Procedure vs capital | ≈ **15×** |
| Contract-Net ageing (E10) | worst-case wait −33% (161 → 108 h) at ≈ 0 cost to the mean |
| Pricing (E13/E14) | free time / penal rate move the bill (₹1.77 M → ₹3.54 M), not detention (16.07 h) |
| Single biggest factor (L5) | terminal working hours 8 → 24 h/day: detention 31.86 → 10.69 h; all factors together: 4.52–52.46 h |
| Per mineral (L6) | general levers (24/7, release reporting) work for all 10 commodities (−4 to −6 h); loading accuracy matters for coal/clinker (overload 21–41 %), loading rate for bagged cargo |
| Attribution (L1) | of a rake's time from arrival to departure: terminal 73.5%, client 23.7%, railway 2.9%; yet the client pays the demurrage |

Rule for the thesis: results depending only on CITED/DERIVED parameters are quotable as figures.
Anything touching an ASSUMED parameter (admin durations, truck volumes) is a *direction* or
*ranking* until field data replaces it. Run `python -m rtsim.calibration` for the full table
(18 CITED · 1 DERIVED · 10 ASSUMED). The coal 3:00 free-time rule [IR-COMP 2.2(c)] is cited and
used in the pricing sweep (E14), but is not tied to its single-line precondition in code.

## Key references
MoR Compendium on Demurrage, Wharfage, Stacking, Waiver (2024) · TERI (2023) *Strategies to
Increase Railway's Share in Freight*, Vols I–II · Refas & Cantens (2011) WB WPS 5565 · Guan & Liu
(2009) TRR 2100 · Parmaksizoglou, Bombelli & Sharpanskykh (2025) *Logistics* 9(3):110 · Smith (1980)
Contract Net, IEEE Trans. Comput. C-29(12) · Sousa & Wolsey (1992) *Math. Prog.* 54 · Azem, Aggoune
& Dauzère-Pérès (2007).
