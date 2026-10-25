# Freight-optimization: rake detention at an Indian Railways freight terminal

M.Tech (Industrial & Systems Engineering) thesis project, IIT Kharagpur. Ayan Ahmed (22MF3IM04),
supervised by Prof. Biswajit Mahanty. *Analysis of operational, commercial and managerial
constraints at a freight terminal, and solutions for quick release of rolling stock.*

**Question.** A rake (a train of 50–58 wagons) waits at a private siding much longer than its
loading takes. Where does that time go, who causes it, what does it cost, and which fix pays most?

**Method.** We built a discrete-event simulation (Python + SimPy) of a coal loading siding. It
follows IR rules exactly (MoR Demurrage Compendium, 03.04.2024). It is built in layers, and every
layer is checked before the next is added. It is calibrated on Eastern Railway's inward freight
register: 220,395 consignments, 2022–26.

---

## What we found

| # | Finding | Number | Where |
|---|---|---|---|
| 1 | The model reproduces real detention | **15.53 ± 0.33 h** per rake (TERI benchmark 14–17 h); physical work alone is only 4.05 h | `results/l1.log` |
| 2 | Paperwork is the main cause, not track or equipment | admin **78%** of waiting (office hours 73%, rework 11%), sequencing ≤ 8%, irreducible 14% | `layer3_E11_decomposition.csv` |
| 3 | Procedure beats capital | digitalising admin saves 8.98 h/rake; a 2nd line saves ≈ 0 h (−0.28 h) → **≈ 15×** | `layer4_E12_interventions.csv` |
| 4 | The client pays for others' delay | rake time: terminal 73.5%, client 23.7%, railway 2.9%, yet the client pays the demurrage | `layer1_attribution.csv` |
| 5 | Single biggest factor | terminal hours 8 → 24 h/day: **31.9 → 10.7 h**; each hour from today's 16 h: −1.2 h (diminishing); loading rate over its published range (payloader → silo) 17.7 → 11.1 h; all factors together: 3.5–51.4 h | `layer5_S1_bounds.csv`, `layer5b_hours_sweep.csv` |
| 6 | Pricing changes the bill, not the time | free time / penal rate: ₹1.77 → 3.54 M, detention unchanged (0 h) | `layer4_E14_pricing.csv` |
| 7 | General vs material-specific levers | 24/7 terminal and digital release help **all 10 materials** (−4 to −6 h); precise loading and silo loading (−4.3 to −5.0 h) matter only for bulk | `layer6_C2_levers.csv` |
| 8 | When extra labour pays | 50% faster loading is worth **₹10.5k–35.6k per rake** in demurrage = ₹5.5/t (bulk), ₹9/t (bagged): pays if labour is paid per tonne; per full shift only bulk ≈ breaks even | `layer6_C4_…`, `layer6_C5_labour_vs_demurrage.csv` |
| 9 | Fair dispatch is free | Contract-Net ageing cuts the worst-case wait by 33% (161 → 108 h) at ≈ 0 cost to the mean | `layer3_E10_fairness.csv` |
| 10 | The variable set is sufficient for ranking | adding 9 omitted-factor scenarios (extra delays, +50% traffic, disruptions, errors ×2): ranking of all 6 interventions unchanged (Kendall τ = 1.00) | `layer7_O2_rank_stability.csv`, `docs/VARIABLE_SELECTION.md` |

Rule for quoting: a number that depends only on CITED or DERIVED parameters is a figure. A number
that touches an ASSUMED parameter (admin durations, truck volumes) is a direction or ranking only.
`python -m rtsim.calibration` lists all 29 parameters (18 cited, 1 derived, 10 assumed).

---

## How the code is organised

```
rtsim/          the model (an importable package)
experiments/    one script per layer; each writes its CSVs/PNGs to results/
tools/          field data decoding, figures, checks
data/raw/       ER RR register 2022–26 (56 monthly FOIS exports)
results/        every output, committed so it is viewable on GitHub
docs/           project story, codebase guide, git workflow
archive/        Phase-1 prototypes (history only, not used)
```

### `rtsim/`: the model

| File | Layer | What it does |
|---|---|---|
| `config.py` | 0 | every parameter as frozen dataclasses; `scenario()` builds variants |
| `distributions.py` | 0 | duration distributions; per-entity random streams (common random numbers) |
| `eventlog.py` | 0 | event log: the single source of truth for every timestamp and responsible party |
| `terminal.py` | 0 | rakes, lines, locos, crews; arrive → place → load → release → remove; `simulate()` |
| `accounting.py` | 0 | durations, graded demurrage, IR charges, P&L, attribution, KPIs |
| `policies.py` | 0/3 | dispatch rules: FCFS, SPT, LPT, cost-priority, Contract-Net (`cnp`) |
| `experiment.py` | 0 | replications, paired comparisons, 95% CIs |
| `admin.py` | 1 | paperwork steps M1–M8 with office-hour calendars and rework loops, gating the physical chain |
| `trucks.py` | 2 | road side: trucks, gate, one-way lane, appointment system, M8 |
| `optimiser.py` | 3 | CP-SAT optimal sequence and valid lower bound |
| `calibration.py` | – | provenance table: each parameter's value, source and status |
| `verify*.py` (4 files) | – | 57 integrity checks (18 + 13 + 12 + 14) |

### `experiments/`: one script per question

| Script | Answers |
|---|---|
| `run_layer0.py` | Physical only: capacity, load rate, free-time and dispatch sweeps |
| `run_layer1.py` | Add paperwork: baseline 15.53 h, ablation, digitalisation, attribution |
| `run_layer2.py` | Add trucks: lane, appointments, fairness, stochastic rakes |
| `run_layer3.py` + `decompose.py` | Optimiser ladder, disruption, fairness, waiting decomposition (E11) |
| `run_layer4.py` | Ten interventions, terminal types, pricing levers (E12–E14) |
| `run_layer5b_hours_sweep.py` | Detention for every length of the terminal day, 8–24 h (Fig. 7) |
| `run_layer5_sensitivity.py` | Each of 39 parameters and 27 conditions alone: bounds, Morris screening, envelope |
| `run_layer6_commodities.py` | 10 materials from field data: which levers are general vs material-specific; labour break-even and labour cost (C5) |
| `run_layer7_sufficiency.py` | Are the variables enough? Adds omitted factors and checks whether the ranking of interventions changes |
| `_bootstrap.py` | Path helper (repo root on `sys.path`, output to `results/`) |

### `tools/`: data and figures

| File | What it does |
|---|---|
| `rr_register.py` | Loads, cleans (rules C1–C5) and decodes the FOIS register; code tables graded A/B/C |
| `analyse_rr_register.py` | Per-commodity profiles and model parameters → `results/field/F0–F5` |
| `verify_extensions.py` | 25 checks on Layers 5–7 and the field data |
| `make_slide_charts.py` | Mid-term slide figures |
| `make_prof_charts.py` | Seven supervisor figures (Fig1–Fig7) → `results/prof/` |
| `compare_outputs.py` | Proves a refactor changed no number (`ALL IDENTICAL`) |
| `dry_run_two_rakes.py` | Prints one replication event by event (for understanding/debugging) |

### How the pieces connect

```
config ─► terminal (+admin, +trucks) ─► eventlog ─► accounting ─► experiment ─► experiments/*.py ─► results/
               ▲                                                       ▲
           policies / optimiser                         data/raw ─► rr_register ─► analyse_rr_register ─► Layer 6
```

---

## Run it

```bash
pip install -r requirements.txt
bash run_all.sh quick               # 57 checks + provenance table (~1 min)
bash run_all.sh                     # regenerate everything in results/ (~15 min, 2 cores)
python tools/dry_run_two_rakes.py   # watch one simulation, event by event
```

Integrity: **82/82 checks pass** (57 model + 25 extensions).

## Data

`data/raw/RR_base_IN_freight_details/<year>/<Mon YY>.xls[x]` holds the Eastern Railway inward
freight register (RR base), Jan 2022 – Aug 2026: 56 files, 508.5 Mt. It gives money, volume,
commodity, wagon type and overloading. It has **no** placement or release timestamps, so it cannot
calibrate detention hours; for that we are waiting on terminal time logs. See `data/README.md`.

## Read next

- `docs/PROJECT_STORY.md`: how the project started, the mid-term, current state, next steps, numbers to quote.
- `docs/CODEBASE.md`: every file in detail, event chain, recipes for adding features.
- `docs/VARIABLE_SELECTION.md`: why these variables, where each candidate factor is, and the sufficiency test.
- `docs/WORKFLOW.md`: branches, tags, how to save changes.

Milestone tags: `v1.0-midterm-model` (Layers 0–4) · `v1.1-sensitivity-commodities` (Layers 5–6 + field data).

**Next:** scaling study, unloading side, validation against time logs, LaTeX thesis.
