# CODEBASE — structure, data flow, and where to change what

Companion to `docs/PROJECT_STORY.md`. This file answers four questions:
which file does what, how they connect, how to run and verify, and where a new feature goes.
**Last verified:** 24-Oct-2026. 80/80 integrity checks pass (57 model + 23 extension), and every
result in `results/` regenerates from `bash run_all.sh`.

---

## 1. Repository layout

```
Freight-optimization/
├── README.md                  overview, quick start, headline results
├── run_all.sh                 reproduce everything  (bash run_all.sh | bash run_all.sh quick)
├── requirements.txt           pinned versions used for the verified run
├── .gitignore                 ignores only caches (data/processed, __pycache__)
│
├── rtsim/                     THE MODEL (Python package) - 16 files
│   ├── __init__.py            package docstring
│   ├── config.py          L0  every parameter, as frozen dataclasses; scenario() helper
│   ├── distributions.py   L0  Dist (const/exp/logn/uniform/tri/erlang/bernoulli); RandomStreams (BLAKE2b sub-seeds)
│   ├── eventlog.py        L0  EventLog = single source of truth; parties; RAKE_EVENT_ORDER
│   ├── terminal.py        L0  Rake, generate_rakes(), Terminal (lines/locos/crews, _dispatch, _gate), simulate()
│   ├── accounting.py      L0  rake_table() durations + IR charges + P&L; kpis(); attribution(); graded_demurrage()
│   ├── policies.py        L0/L3 dispatch rules FCFS/SPT/LPT/COST + CNP registry; build(name, cfg)
│   ├── experiment.py      L0  replication helpers: ci95, run_policies, summarise, paired, print_summary
│   ├── admin.py           L1  Calendar, AdminStep, default_steps() M1-M8, AdminChain (calendar work + rework), scenario helpers
│   ├── trucks.py          L2  Truck, generate_trucks, deviation_cost, allocate_slots (NONE/FCFS/MINMAX), RoadSide (gate, lane, stockyard)
│   ├── optimiser.py       L3  CP-SAT optimal_sequence, cpsat_policy, waiting_lower_bound, cnp_policy, captured_gain
│   ├── calibration.py     --  provenance registry (CITED/DERIVED/ASSUMED) -> python -m rtsim.calibration
│   ├── verify.py          --  L0 integrity suite (18 checks)
│   ├── verify_admin.py    --  L1 integrity suite (13 checks, incl. the TERI 14-17 h guard)
│   ├── verify_trucks.py   --  L2 integrity suite (12 checks)
│   └── verify_optimiser.py --  L3 integrity suite (14 checks, incl. bound validity 13-14)
│
├── experiments/               THE EXPERIMENTS (scripts; write into results/)
│   ├── _bootstrap.py          puts repo root on sys.path and chdir's to results/ (no model logic)
│   ├── run_layer0.py      L0  policy comparison, attribution, load sweep, line sweep, free-time sweep
│   ├── run_layer1.py      L1  calibration check, E1 ablation, E2 digitalisation, E3 mechanism, attribution
│   ├── run_layer2.py      L2  E4 lane, E5 appointments vs gates, E6 fairness, E7 admin variance -> road side
│   ├── run_layer3.py      L3  E8a control, E8b ladder, E9 disruption, E10 ageing/fairness
│   ├── run_layer4.py      L4  E12 interventions, E13 terminal type, E14 pricing, E15 break-even
│   ├── decompose.py       L3  E11 waiting-time decomposition with the valid lower bound
│   ├── run_layer5_sensitivity.py  L5  every parameter/condition alone: OAT bounds, conditions, Morris, envelope
│   ├── run_layer6_commodities.py  L6  10 commodity profiles x 8 levers, per-commodity tornado, labour break-even (C4), labour cost (C5)
│   └── run_layer7_sufficiency.py  L7  omitted-factor stress test: does the ranking of interventions survive?
│
├── tools/                     HELPERS (not part of the model)
│   ├── compare_outputs.py     regression check: are two results folders numerically identical?
│   ├── dry_run_two_rakes.py   prints a 2-rake trace with the file/function behind every event
│   ├── make_slide_charts.py   slide_decomposition / slide_calibration / slide_procedural_vs_capital
│   ├── make_prof_charts.py    results/prof/Fig1-4: one-message figures for supervisor updates
│   ├── rr_register.py         FIELD DATA: load + clean + DECODE the FOIS RR register (code tables, confidence grades)
│   ├── analyse_rr_register.py FIELD DATA: commodity profiles, charge structure, terminals, arrivals -> results/field/
│   └── verify_extensions.py   23 integrity checks for Layers 5-7 and the decoding
│
├── results/                   GENERATED - charts (layer*_results.png), CSVs (layer*_E*.csv), logs (l*.log)
│   └── field/                 GENERATED from field data - commodity-level aggregates only (F0-F5, field_results.png)
├── archive/prototypes/        Phase-1 siding_sim v1/v2/v3 (superseded, kept for the record)
├── docs/
│   ├── PROJECT_STORY.md       history, current state, target, data plan, numbers to quote
│   ├── CODEBASE.md            this file
│   └── WORKFLOW.md            saving, branching, tags, session routine
└── data/
    └── README.md              dataset description; raw/ committed, processed/ is a git-ignored cache
```

**Layer → file map:** L0 physical = `config, distributions, eventlog, terminal, accounting,
policies, experiment` · L1 administrative = `admin` · L2 road side = `trucks` · L3 decision =
`optimiser` (+ `policies.cnp`) · L4 scenarios = `experiments/run_layer4.py` only (config changes,
no new model code) · L5 sensitivity and L6 commodities = experiment scripts only (no model change) ·
field data = `tools/rr_register.py`, `tools/analyse_rr_register.py` · cross-cutting = `calibration`,
`verify_*`, `tools/verify_extensions.py`.

---

## 2. How the pieces connect

### 2.1 Import graph (arrows = "imports")
```
config ──► distributions
eventlog
terminal ──► config, distributions, eventlog            (lazily: admin, trucks inside simulate())
accounting ──► config, eventlog
policies ──► config, terminal                           (lazily: optimiser.cnp_policy)
admin ──► distributions, eventlog
trucks ──► distributions, eventlog
optimiser ──► config, terminal  (+ ortools.sat)
experiment ──► config, distributions, terminal, accounting, policies
verify_* ──► the modules they test
experiments/*.py ──► rtsim.*  (nothing imports the experiments)
```
**Rule:** admin, trucks and policies never talk to each other. They only connect through
`terminal.py`. That is why any one of them can be swapped or switched off without touching the others.

### 2.2 One replication: `terminal.simulate(cfg, policy, seed, rakes=None, admin_steps=None, tas_rule=None)`
```
RandomStreams(seed)                                   distributions.py
   └─ generate_rakes(cfg)  -> list[Rake]              terminal.py   (all randomness drawn up front -> CRN)
Terminal(env, cfg, log, policy, admin)                terminal.py
   ├─ admin_steps given  -> AdminChain                admin.py      (Layer 1 on)
   └─ tas_rule given     -> generate_trucks, allocate_slots, RoadSide, feed_trucks   trucks.py (Layer 2 on)
feed(...)  or  feed_with_admin(...)                   terminal.py   (arrival process = output of M1 chain)
env.run()                                             SimPy next-event clock (VTIM)
returns (EventLog, rakes, terminal)
   └─ accounting.rake_table(log, cfg)  -> one row per rake: durations, detention, demurrage, P&L
   └─ accounting.kpis(rt, term, cfg)   -> scalars (mean detention, breaches, utilisation ...)
```

### 2.3 The rake's event chain and where the admin steps gate it
```
booking ─► [M1 allotment] ─► transit (+lateness) ─► rake_arrive
   └─► [M2 stacking permission] runs in PARALLEL from booking ───────────────┐
rake_arrive ─► [M3 forwarding note] ─► queue_start ─► (_dispatch awards a line)
   ─► placement_start ─► placed ═══ FREE-TIME CLOCK STARTS
   ─► [M4 placement advice] ─► join M2 ◄──────────────────────────────────────┘
   ─► loading_start ─► loading_end ─► start [M7 RR+payment] in PARALLEL ──────┐
   ─► [M5 weighment] ─► [M6 release reporting] ─► released ═══ CLOCK STOPS   │
   ─► removal_start ─► removed (line freed, _dispatch re-runs) ─► join M7 ◄───┘ ─► departed
```
Detention = `released − placed` (IR 2.2.2(a)). Dwell = `removed − rake_arrive`. Cycle = `departed − rake_arrive`.
Resource discipline: the LINE is held placement_start → removed; the LOCO is held only during
placement and during removal; the line is always acquired before the loco, so deadlock is impossible.

### 2.4 Where randomness comes from (common random numbers)
`RandomStreams.get(name)` derives an independent `random.Random` per *name* from a BLAKE2b digest
of (seed, name), so it is reproducible across processes. Names are keyed on the **entity**
(`admin_M5#rake17`, `rework_M5#rake17#2`, `gate#t401`). A rake therefore gets identical draws
under every policy and scenario. **Never** draw from a shared stream in execution order. That bug
confounded all paired comparisons once (`verify.py` check 8c guards it).

---

## 3. Module reference (what to look at, what to edit)

| File | Key objects | Edit it when you want to… |
|---|---|---|
| `config.py` | `ResourceConfig` (lines, locos, crews, shifts), `RakeConfig` (wagons 58, t/wagon 58.08, arrival gap exp mean 30 h, load rate logn 900/250, transit, lateness/no-show), `ShuntingConfig`, `TruckConfig`, `ChargeConfig` (free time 5 + 2 + 1, graded bands, penal ×, engine-hour cost, shunting, freight/t, idle cost), `CoordinationConfig` (ageing 0.5), `RunConfig` (n_rakes 50, reps 30, warm-up 5, seed 1000); `scenario(base, label, **{"section.field": v})` | change any number. **No numeric constant may live anywhere else** |
| `distributions.py` | `Dist(kind, mean, sd, …)`, `RandomStreams` | add a distribution type |
| `eventlog.py` | `EventLog.add/to_frame/pivot_rakes`, party and kind constants, `RAKE_EVENT_ORDER` | add an event name or a party |
| `terminal.py` | `Rake`, `generate_rakes`, `Terminal.handle` (lifecycle), `_dispatch` (Contract-Net style call for proposals: lowest bid wins, tie on id), `_gate` (only coupling to admin), `feed`, `feed_with_admin`, `simulate` | change the physical process or where a gate sits |
| `accounting.py` | `graded_demurrage`, `rake_table`, `kpis`, `attribution`, `_time_weighted_mean` | change an objective, a charge, a KPI. The model never reads this file, so the objective can change freely |
| `policies.py` | `fcfs, spt, lpt, cost_priority, cnp`, `REGISTRY`, `build` | add a dispatch rule (return a float; lower = served first) |
| `experiment.py` | `ci95`, `run_policies`, `summarise`, `paired`, `print_summary` | change replication/CI reporting |
| `admin.py` | `Calendar` + `CAL_*`, `AdminStep`, `default_steps()` (M1–M8 table in PROJECT_STORY §3.2), `AdminChain._work` (calendar-bounded work, the dominant mechanism), `run_step` (rework loop), `start_parallel`; helpers `ablate, digitalise, all_disabled, halve_mean, halve_variance, remove_calendar, no_rework` | change a step's duration, calendar or rejection rate; add a step |
| `trucks.py` | `Truck`, `generate_trucks` (ceil(tonnes/35 t) trucks per rake, anchored on the *expected* rake arrival), `deviation_cost` (exp, scaled), `allocate_slots` (NONE/FCFS/MINMAX, gate hours), `RoadSide` (gate servers, lane capacity 1 = one-way blocking, stockyard) | road-side changes |
| `optimiser.py` | `optimal_sequence` (CP-SAT, NoOverlap/Cumulative, integer minutes `SCALE=60`), `cpsat_policy`, `waiting_lower_bound` (reads `BestObjectiveBound` on min-hold durations), `cnp_policy` (bid = demurrage + occupancy − ageing), `captured_gain`; unused draft `time_indexed_bound` (§7) | change the bound or the Contract-Net bid |
| `calibration.py` | `REGISTRY` of `Param(path, value, status, source, note)`, `report()` | **every time** a parameter changes source or value |

---

## 4. Running and verifying

```bash
pip install -r requirements.txt
bash run_all.sh quick          # 57 integrity checks + provenance table  (~1 min)
bash run_all.sh                # everything into results/                (~15 min on 2 cores)
python experiments/run_layer5_sensitivity.py [quick]   # per-parameter bounds (~10 min)
python tools/analyse_rr_register.py                    # field data (needs data/raw)
python experiments/run_layer6_commodities.py [quick]   # multi-commodity (~6 min)
python experiments/run_layer7_sufficiency.py [quick]   # sufficiency stress test (~2 min)
python tools/verify_extensions.py                      # 23 extension checks
python experiments/run_layer1.py   # any single layer (works from any folder)
python tools/dry_run_two_rakes.py  # see one replication event by event
python -m rtsim.calibration        # parameter provenance
```

| Suite | Checks | Guards (examples) |
|---|---|---|
| `verify.py` | 18 | conservation; monotone event chain; no negative durations; line capacity; detention = release − placement; demurrage iff free time exceeded; graded table reproduced; marginal rate non-decreasing; free time = 5 + 2 + 1; Little's Law within 5%; byte-identical log for a seed; process-independent sub-seeds (`substream_seed(1000,'loading')=1948952355`); **physical durations identical across policies**; **admin time schedule-dependent (up to 8 h)**; CRN across runs; policy hook changes outcomes; SPT < LPT; all policies serve the same rakes |
| `verify_admin.py` | 13 | all steps disabled reproduces L0 exactly; calendar truncation (1 h task at 17:30 → 17 h); 24/7 costs exactly 1 h; weekend skip; removing rework reduces detention; ablating M6 cuts detention; M7 changes cycle but not detention/dwell; digitalising M5 + M6 reduces detention; every admin event has an owner; chain monotone with gates; deterministic; non-physical time is the majority of dwell (88.5%); **detention inside TERI 14–17 h** |
| `verify_trucks.py` | 12 | rake chain unchanged when road side added (A1 on); truck conservation; one-way lane never holds two trucks; queued lane allows concurrency; quota respected; appointments flatten the peak (80 → 10); deviation cost convex; MINMAX lowers worst-off company cost at the test point; hard infeasibility measured; more gate servers shorten the queue; A1 off makes material bind; M8 fires for trucks |
| `tools/verify_extensions.py` | 23 | Layer 5 base = Layer 1 baseline; every parameter at base reproduces base; commercial parameters never move time; demurrage linear in rate; M7 never touches detention; terminal hours monotone; envelope brackets base; Morris top-3 = OAT top-3; Layer 6 free time per IR rule; free-time cut moves bill not time; precise loading helps most where overload is highest; loading-rate gain correlates with loading hours; silo lever only for mechanised bulk and beats +50 % rate; C5 consistent with C4; Layer 7 base = Layer 5 base; every omitted factor slows the base; field: no sub-totals, tonnage conserved, OTC/DTC = ₹20/t, DPO = 15 %, coal exempt, groups cover ≥ 95 % (field checks SKIP without data/raw) |
| `verify_optimiser.py` | 14 | CP-SAT returns a valid permutation; no placement before arrival; no line overlap; reproduces SPT when all jobs are at t = 0; offline optimum ≤ every online rule (checks 1–12 run on the physical model, no admin); CNP < FCFS on waiting; CNP bid uses only rake + clock; ageing reduces worst wait; heavy ageing collapses onto FCFS; captured-gain scale anchored; identical rakes/revenue across policies; 60-rake solve within 20 s; **13: lower bound never violated by any policy**; **14: executing the relaxed plan (89.48 h) is worse than the bound (37.59 h), so the bound must be read, not simulated** |

**Regression rule.** Before trusting any change, run the experiments into a fresh folder and run
`python tools/compare_outputs.py <old_results> <new_results>`. A refactor must report `ALL IDENTICAL`.
This repo was itself checked this way against the replayed original code (§7).

---

## 5. Experiment → output map

| Runner | Experiments | Outputs in `results/` |
|---|---|---|
| `run_layer0.py` | policy comparison; attribution; load sweep; line sweep; free-time sweep | `layer0_results.png`, `layer0_policy_summary.csv`, `layer0_attribution.csv`, `layer0_capacity_sweep.csv`, `layer0_freetime_sensitivity.csv`, `layer0_load_sweep.csv`, `l0.log` |
| `run_layer1.py` | calibration; E1 ablation; E2 digitalisation; E3 mechanism (on M6); attribution | `layer1_results.png`, `layer1_E1_ablation.csv`, `layer1_E2_digitalisation.csv`, `layer1_E3_mechanism.csv`, `layer1_attribution.csv`, `l1.log` |
| `run_layer2.py` | E4 lane; E5 appointments × gate servers; E6 fairness; E7 M1 variance → hard infeasibility | `layer2_results.png`, `layer2_E4_lane.csv`, `layer2_E5_appointments.csv`, `layer2_E6_fairness.csv`, `layer2_E7_stochastic_rake.csv`, `l2.log` |
| `run_layer3.py` | E8a control (calendars off); E8b ladder FCFS/SPT/COST/CNP/CP-SAT; E9 disruption; E10 ageing weight | `layer3_results.png`, `layer3_E8_ladder.csv`, `layer3_E9_disruption.csv`, `layer3_E10_fairness.csv`, `l3.log` |
| `decompose.py` | E11 decomposition with the valid lower bound | `layer3_E11_decomposition.csv`, `decompose.log` |
| `run_layer4.py` | E12 ten interventions; E13 terminal type; E14 free time × penal; E15 break-even | `layer4_results.png`, `layer4_E12_interventions.csv`, `layer4_E13_terminal_type.csv`, `layer4_E14_pricing.csv`, `l4.log` |
| `run_layer5_sensitivity.py` | S1 OAT bounds (39 params x 5 levels); S2 27 conditions; S3 Morris (20 trajectories); S4 envelope | `layer5_results.png`, `layer5_tornado_cost.png`, `layer5_S1_oat_levels.csv`, `layer5_S1_bounds.csv`, `layer5_S2_conditions.csv`, `layer5_S3_morris.csv`, `layer5_S4_envelope.csv`, `l5.log` |
| `tools/analyse_rr_register.py` | F0 code tables; F1 commodity profiles; F2 charges; F3 monthly tonnes; F4 model parameters; F5 coal by wagon type | `results/field/*` + `data/processed/terminal_*.csv` (git-ignored) |
| `run_layer6_commodities.py` | C1 baseline per commodity; C2 8 levers x 10 commodities + classes (S3 silo for bulk only); C3 per-commodity tornado; C4 labour break-even; C5 labour cost vs demurrage (published handling rates, two pay models) | `layer6_results.png`, `layer6_C1_..C5_*.csv`, `l6.log` |
| `run_layer7_sufficiency.py` | O1 saving per intervention with each omitted factor; O2 rank stability (Kendall τ, top-3, procedure/capital) | `layer7_results.png`, `layer7_O1_sufficiency.csv`, `layer7_O2_rank_stability.csv`, `l7.log` |
| `tools/make_slide_charts.py` | slide figures | `slide_decomposition.png`, `slide_calibration.png`, `slide_procedural_vs_capital.png` |

Operating points: L0/L1 use the default 50 rakes, 30 reps, arrival gap exp(30 h).
L3, L4 and E11 use 25 rakes, gap 22 h (ρ ≈ 0.7, contended but stable). At 18 h the line saturates (ρ ≈ 1.07).

---

## 6. Recipes: where a new feature goes

| Want to… | Do this | Do NOT |
|---|---|---|
| change a rate or duration | edit `config.py` / `admin.default_steps()`, update `calibration.py` status, re-run `run_all.sh quick` | hard-code a number in a runner |
| add a dispatch rule | write `def myrule(cfg): def f(rake, ctx): return score` in `policies.py`, add to `REGISTRY` | use `simpy.PriorityResource` (freezes bids) |
| add a scenario | in a runner: `scenario(cfg, "label", **{"resources.crews": 2})` or an admin helper (`digitalise([...])`) | copy the model |
| add a parameter to the sensitivity | one `add(...)` line in `catalogue()` of `run_layer5_sensitivity.py` (id, group, label, unit, status, base, 5 levels, apply-function, range basis) | forget to include the base value among the levels (check 2 relies on it) |
| **cost–benefit / labour vs demurrage** | add cost fields (crew cost/h, capital annuities) to `ChargeConfig` tagged ASSUMED; compute net = Δdemurrage + Δidle − Δlabour in `accounting` or the runner; report break-even cost per lever | invent a capital cost without tagging it |
| **scaling (more ore)** | sweep `rake.arrival_gap` mean (×1.0 → ×2.0 volume) × resources; log utilisation of line/loco/crew/gate/stockyard/admin offices; report which saturates first | read "more rakes" as the only change; commodity mix shifts too |
| add / change a commodity | one dict in `PROFILES` of `run_layer6_commodities.py` (data fields refresh from `results/field/` automatically); for a MIXED terminal later: add `commodity` to `Rake` and draw it from the field mix | branch on commodity inside `terminal.handle` with magic numbers |
| **field data** | `tools/rr_register.py` (decode; fix a code by editing its table) → `tools/analyse_rr_register.py` → use `results/field/F4_model_parameters.csv` values in profiles/config with status EMPIRICAL in `calibration.py`; keep the TERI guard until detention data exists | commit raw railway data to GitHub |

---

## 7. Provenance of this repository (how it was rebuilt)

- The original work happened in a claude.ai chat. On 22-Oct-2026 the code was **replayed from
  that chat's tool calls in order** (create-file and patch steps of turns 61–91). It was checked
  at waypoints: detention 15.70 ± 0.31 h after turn 67 and the E11 decomposition after turn 73
  both matched the chat to two decimals.
- The chat's last full export (turn 75, `outputs/rtsim/`) was then recovered and used as the
  authority. **15 of 16 package files are byte-identical to it.** `calibration.py` differs only
  by the later turn-91 label fix ("5:00 + 2:00 + 1:00 = 8:00"). `optimiser.py` is the original
  verbatim, including an **unused draft `time_indexed_bound()`** (see below). The six runners
  differ only by one added line (`import _bootstrap`), which relocates outputs to `results/`.
- Against that export's CSVs: Layer 0, E9, E10, E11 and all Layer 4 tables are **bit-identical**.
  Layer 1–2 tables differ (they predate two later fixes, see below).
- Full re-run of the final code reproduces Layer 3, Layer 4 and E11 **exactly** (E8a 10.37/10.64,
  E10 161.2 → 108.1, the whole E12 table, 41.43/11.07/36.90/9.18/5.84).
- Clean repo vs replayed original, every CSV compared with `tools/compare_outputs.py`:
  **19 of 20 tables bit-identical**. The one exception is the **CP-SAT row of E8b**
  (`layer3_E8_ladder.csv`: 40.38 vs 40.08 h), explained in the next item.

### Known non-determinism (inherited from the original code; not a refactor effect)
`optimal_sequence()` runs CP-SAT with a **wall-clock** limit (`max_time_in_seconds`, 4–6 s in
`run_layer3.py`) and **8 parallel workers**. When the solver stops at FEASIBLE rather than
OPTIMAL, the incumbent depends on machine speed and thread timing. Solving the same instance three
times in one process gave two different schedules. Effects:
- E8b CP-SAT row and E9 CP-SAT values may move slightly between runs and machines. Neither is
  quoted, because with calendars on CP-SAT is *not* a bound (that is the finding).
- `waiting_lower_bound` reads `BestObjectiveBound`, and E8a/E11 solved to OPTIMAL, so the quoted
  bound results are stable.
- If bit-reproducibility of those rows is ever needed: `num_search_workers = 1`, a fixed
  `random_seed`, and `max_deterministic_time` instead of wall time. This changes those rows once,
  so record it as a deliberate change.
- Layers 1–2 regenerate slightly differently from the mid-term charts. Those charts were made
  in turn 67, before the BOXN 58.08 t fix (turn 69) and the entity-keyed RNG fix (turn 71), and
  never refreshed. Use the regenerated `results/` versions (details in PROJECT_STORY §7.2).

### Unused draft in `optimiser.py`
`time_indexed_bound()`, `_hold_if_placed_at()`, `_calendar_elapsed()`, `extract_admin_work()`
and `_work_in_span()` (bottom of the file) are a **draft calendar-aware, time-indexed CP-SAT
model**: an hourly grid, with duration a function of start time via `AddElement`. No experiment
or check calls them, and they are unverified. As written, the function returns a *schedule*
(ranks) rather than a proven bound. It is the natural starting point for the "tight bound"
future work, but needs its own verification checks (bound ≤ every policy; agreement with
`waiting_lower_bound` when calendars are 24/7) before any number from it is quoted.

### Old files you can now discard
`siding_sim*.py` (kept once in `archive/prototypes/`), `siding_rake_log_*.csv`, `summary_v*.csv`,
`reps*_*.csv`, `siding_*comparison.png`, `siding_v3_optimal.png` (pre-rtsim prototype outputs);
every earlier `README.md` / `README (1).md` / `calibration_report.txt` copy (stale counts such as
"13.6 h", "16 CITED, 2 TYPICAL", "Layers 0, 1 and 2"); per-layer zips from the chat. The single
source of truth is this repository.

### Known cosmetic drift (no effect on results)
- `AdminStep.gates` strings for M2 ("loading_start") and M7 ("removal_start") are documentation
  only. The real join points are in `terminal.py` (M2 after M4; M7 after removal → departed).
- `policies.py` docstring says "Layer 4 will add CP-SAT…". These were added in Layer 3 (`optimiser.py`).
- `admin.py` header lacks the calibration note that the chat intended to add (that patch never
  matched). The note is in PROJECT_STORY §0 item 4.
