# MTP — Project Story: start → mid-term → now → final target

**Title.** *Analysis of operational, commercial and managerial constraints at a freight
terminal, and solutions for quick release of rolling stock.*
**Student:** Ayan Ahmed (22MF3IM04) · **Supervisor:** Prof. Biswajit Mahanty · M.Tech, Industrial & Systems Engineering
**Context:** Indian Railways coal rakes at a **private siding** (Eastern Railway context).
**This file last updated:** 25-Oct-2026. Companion file: `docs/CODEBASE.md` (what each code file does).

> **How to use this file (future sessions / Claude Code).** Read §0 first. It is the
> state of the project in a dozen lines. §1–§3 are history, so you know *why* things are the way they are.
> §4 is the current work. §5 is the target. §6 is the data plan. §7 holds the numbers to quote,
> and §8 the open questions.

---

## 0. State of the project in a dozen lines

1. A discrete-event simulation (Python/SimPy, package `rtsim`) of one private coal siding, built
   in **5 verified layers**: physical → administrative → road-side → decision → scenario campaign.
2. **57 automated integrity checks** pass (18 + 13 + 12 + 14).
3. Charge rules are **CITED** from the MoR Demurrage/Wharfage Compendium (03.04.2024). Free time is
   8 h (5 + 2 + 1), demurrage is graded from ₹150/wagon/h, terminal hours are 06:00–22:00, and the
   rake is BOXN 58 × 58.08 t.
4. Admin step durations and rejection rates are **ASSUMED**. They were tuned so detention lands in
   TERI's 14–17 h band. This is calibration, not validation.
5. **Headline finding:** about 78% of rake waiting is administrative (office hours + rework),
   ≤8% is fixable by optimal sequencing, and about 14% is irreducible congestion.
   Procedural levers beat capital levers by about 15× on detention saved.
6. The mid-term presentation (16-Sep-2026) went well. The supervisor said **"good"**.
7. Mid-term ask (a), **individual effect of every parameter/condition with lower/upper bounds**,
   is **done** (Layer 5, 22-Oct-2026): 39 parameters swept over stated ranges, 27 conditions,
   Morris screening and a best/worst envelope. Ask (b), selection provenance, is **done** (24-Oct-2026):
   `docs/VARIABLE_SELECTION.md` (selection filters, 23-factor traceability table) + Layer 7 sufficiency test.
8. Post-mid-sem asks (8–9 Oct): capacity scaling ("more ore → what else must grow"), wagon
   condition/commodity-wise needs, a **cost analysis** (labour vs demurrage), qualitative +
   hypothesis/reverse-engineering methods, and multiple commodities.
9. First field dataset: **ER Inward Freight Register (RR-base), Jan-2022–Aug-2026, 220,395 RRs,
   508.5 Mt** (after removing 338 sub-total rows). It has money, volume, wagons, wagon type and
   overloading, but **no placement/release timestamps**. It is **decoded** (`tools/rr_register.py`) and
   used for commodity profiles; the multi-commodity analysis (Layer 6) is done.
10. Integrity: **82 checks** pass (57 model + 25 for Layers 5–7 and the data decoding,
    `tools/verify_extensions.py`).
11. Code base consolidated and re-verified on 22-Oct-2026 (this repo). Layers 3, 4 and E11
    reproduce the chat-era numbers exactly. 19/20 result tables are bit-identical between the
    replayed original and this repo; the exception is CP-SAT timing, §7.3. Layers 1–2 regenerate
    slightly differently from the mid-term charts (see §7.2).
12. 24-Oct-2026 (§6E–6G): loading-rate range taken from published norms (payloader ~5 h/rake →
    silo/RLS ~1 h/rake); silo lever added for bulk; labour cost compared with published handling
    rates and the 2026 minimum wage (C5); **sufficiency test (Layer 7): the ranking of all six
    interventions is unchanged under 9 omitted-factor scenarios (Kendall τ = 1.00)**. All 56 months
    of field data verified present, no gaps, no duplicate RRs.
13. 25-Oct-2026 (§6H): detention for every length of the terminal day (8–24 h, Fig. 7). The sweep
    exposed a calendar bug (days longer than 18 h were capped at midnight); fixed and re-run. Only
    the Layer 5 20-h level (13.46 → 12.28 h) and Morris values moved slightly; bounds unchanged.

---

## 1. How the project started (first weeks of the MTP)

### 1.1 The starting brief and the first pivot
- **Initial idea (from a peer):** "agentic AI / multi-agent system" for Rake Turnaround Time
  (RTAT). Assessment: the framing was good, but it conflated LLM-agents with MAS, and RL and Mesa
  were the wrong tools. Recommendation adopted: **SimPy (DES) + OR-Tools CP-SAT + a coordination
  protocol**, with the LLM layer optional/dropped.
- **Tool choice:** Python over AnyLogic. Python hosts the optimiser and statistics in one process,
  has no model-size cap, and survives the thesis. AnyLogic is optional for visuals only.
- **Coordination mechanism:** the supervisor had none in mind, so **Contract Net Protocol** (Smith 1980)
  was chosen as the citable MAS standard. FCFS is the floor and CP-SAT the ceiling.
- **Lifecycle:** six stages were proposed (booking, empty haul, loading, loaded haul, unloading,
  return). Agents are split **by entity** (rake, terminal, network, demand), not by phase.
  Otherwise there is nothing to bid on.

### 1.2 Supervisor's first steer (the objective moved)
- **Objective → profit/cost**, railway side, **siding first** (placement → loading → release → removal).
- **Include the charges** (demurrage, siding/shunting, wharfage).
- Signalling delay matters **only on the loaded haul** (source → destination).
- **Non-pre-emption:** a later, higher-paying booking must not displace an earlier one.
- **Relaxation A1:** coal is always available at the loading point. Only the rake can be late.
- Work **probabilistically**, with confidence intervals.

### 1.3 First prototypes (`siding_sim.py`, now superseded)
| Version | What it did | Result |
|---|---|---|
| v1 | 1 line, 30 rakes, FCFS vs SPT, assumed rates | Single-seed comparison |
| v2 | 50 replications, 95% CI, paired differences, warm-up cut | Statistically defensible comparison |
| v3 | Added PROFIT-greedy and **OPTIMAL (CP-SAT)** policies | Profit FCFS ₹128.79 M → OPTIMAL ₹129.18 M; mean wait 33.8 → 28.6 h |

**Lesson carried forward:** the controller mattered less than the *measurement*. That turned out
to be the seed of the mid-term headline.

### 1.4 Second pivot: the terminal, four parties, administrative steps
- A short detour to the full intermodal chain (factory → truck → terminal → rail → terminal →
  truck → destination) gave the **variable/constraint/objective catalogue** (§3.3).
- **Supervisor narrowed it again: focus on the terminal.** Four parties (terminal, railway,
  client, transporter) and three contracts. **One-way passage** for trucks. Constraint classes:
  - *operational*: rake availability uncertainty, long loading/unloading, platform unavailability,
    people unavailability;
  - *commercial*: contract delays, order/delivery processing;
  - *managerial*: mineral management, handling client/railway officials.
- He then asked for **administrative steps**. In his port example, ~150 steps cause ~50% of the delay.
  21 documented IR steps were traced (5 booking, 9 siding, 4 truck/gate, 3 destination) and
  **compressed to 8 (M1–M8)**. Six are inside the terminal; M1 and M7 are boundary steps modelled
  for their gating effect. A private terminal was confirmed as the base case. PhD students began
  collecting field data.

**Literature pillars at this stage:** TERI (2023) Vols I–II; MoR Compendium (2024); World Bank
dwell-time studies (Refas & Cantens 2011; Kgare et al. 2011; Raballand et al. 2012); WCO Time
Release Study; Guan & Liu (2009) gate appointments; Parmaksizoglou, Bombelli & Sharpanskykh (2025)
rail–road coordination; Smith (1980) Contract Net.

---

## 2. What we did up to the mid-term (presented 16-Sep-2026)

### 2.1 Build principles the supervisor asked for
Modular and upgradeable; **layer by layer with 100% integrity before moving on**; not so specific
it becomes a case study and not so general it says nothing; **VTIM** (next-event) not FTIM;
**tandem queues** (the output of stage *i* is the arrival process of stage *i+1*); a policy
simulation and scenario generator on top.

### 2.2 The five layers (what each added, and the bugs each exposed)
| Layer | Added | Key bugs found and fixed |
|---|---|---|
| **L0 physical** | Rake entity; line/loco/crew resources; event chain arrive → queue → place (clock starts) → load → release (clock stops) → remove; IR accounting; swappable policy hook; replications with CI | — |
| **L1 administrative** | M1–M7 with lognormal service, **office-hour calendars**, Bernoulli **rework loops**, gates on the physical chain; per-party attribution; E1–E3 | M7 holding the line drove ρ > 1 (moved after removal, added `departed`); M2 gating inside the siding (made parallel from booking) |
| *Calibration interlude* | MoR Compendium 2024: **graded demurrage**, free time **5 + 2 + 1 = 8 h**, 06:00–22:00 cited; `calibration.py` provenance registry (CITED/DERIVED/ASSUMED); M5/M6 tuned into TERI's 14–17 h band | Flat demurrage understated long detentions by up to 55%; free time was 7 h, not 8 |
| **L2 road side** | Trucks, gate (Erlang, Guan & Liu), **one-way lane** (blocking) vs queue, **truck appointment system**, rake-dependent time windows, MINMAX fairness, stockyard; M8 active; E4–E7 | Lane occupancy mislogged; MINMAX inverted; exp overflow in deviation cost; **salted `hash()` made runs irreproducible** across processes (replaced by BLAKE2b) |
| *BOXN fix* | Payload 60 → **58.08 t** (58 wagons = 3,368.64 t/rake), CITED | — |
| **L3 decision** | **Explicit Contract-Net dispatcher** (SimPy `PriorityResource` froze bids); CNP with ageing; CP-SAT offline sequence; **valid lower bound**; decomposition E11; E8–E10 | Shared per-step RNG streams confounded every paired comparison (now keyed on the entity); the first CP-SAT "bound" was beaten by online rules, because calendars make durations schedule-dependent. Fixed by **reading the solver objective on relaxed (flat-calendar, no-rework) durations** |
| **L4 scenario campaign** | Config-only: ten interventions (E12), terminal type (E13), pricing levers (E14), break-even framing (E15) | — |

### 2.3 Mathematical formulation (as presented; implemented core)
- **Sets:** rakes *R*, loading lines *K*, admin steps *M* = {M1…M8}, trucks *J*, companies *L*.
- **Parameters:** arrival *a_r* (stochastic, from the M1 chain + transit), physical durations
  *p_r* (placement + loading + removal), free time *F* = 8 h, office calendar *cal_m(t)*,
  rework probability *q_m*, graded demurrage *g(·)*.
- **Decision variables:** *x_{r,k}* ∈ {0,1} (rake → line); *s_r* ≥ *a_r* (placement start).
  The dispatch policy π decides *s_r* online.
- **Objective (scheduling layer):** min Σ_r (s_r − a_r), total waiting.
  **KPI (thesis brief):** detention *D_r* = released_r − placed_r.
- **Constraints:** *s_r* ≥ *a_r*; line non-overlap (≤ |K| rakes on lines at any time);
  non-pre-emption by construction; admin gates at 5 points (M3 → placement, M4 + M2 → loading,
  M5 + M6 → release, M7 → departure).
- **Cost:** demurrage = wagons × *g*(⌈D_r − F⌉⁺). *g* is piecewise linear and convex:
  ₹150/165/187.5/225/300/450 per wagon-hour for bands 0–6/6–12/12–24/24–48/48–72/>72 h,
  times a penal multiplier ≤ 6.
- **Methodological challenge:** a step's wall-clock duration depends on *when* it starts
  (calendars), so line occupancy is schedule-dependent. The classical 1|r_j|ΣC_j bound is invalid.
  The problem is **scheduling with machine-availability constraints (resumable)** (Azem, Aggoune &
  Dauzère-Pérès 2007). A tight bound needs a **time-indexed** formulation (Sousa & Wolsey 1992).
  That is future work.
- **Algorithms:** FCFS/SPT/LPT/COST rules; **Contract Net** (bid = expected demurrage + occupancy
  cost − ageing credit); **CP-SAT** for the offline sequence and the relaxed lower bound.
- **Why waiting is the objective but detention is the KPI** (Q&A answer): dispatch only controls
  the wait *before* placement, and after placement durations are exogenous. That is exactly why
  sequencing can fix at most 8%.

### 2.4 Communication and the mid-term
- Emails: the administrative-layer proposal (8 steps + references), then progress through L3,
  then final outputs incl. L4. The supervisor replied *"good progress"* and asked for the write-up.
- **2-page write-up** (approved, signed). **10-slide deck**, presented **16-Sep-2026, 4:30 pm**
  (8-minute slot). The decomposition was phrased as **78 / 8 / 14** so the three parts sum to 100%.
- **Feedback:** supervisor said **"good"** for the broad overview. Two asks were recorded for later:
  1. **Individual effect of each parameter / admin step** with a **lower bound, upper bound or
     range on an absolute scale**.
  2. Another professor asked whether the constraints/variables were invented or taken from papers,
     and **how the subset was selected**. Answered verbally: from what TERI identifies as essential.
     He asked to **show how individual things affect outcomes**.

---

## 3. Reference material that shaped the model

### 3.1 Parameter provenance (from `rtsim/calibration.py`)
**18 CITED · 1 DERIVED · 10 ASSUMED.**

| CITED source | What it gives the model |
|---|---|
| **[IR-COMP]** MoR Compendium, Demurrage/Wharfage/…, 03.04.2024 | free time 5:00 (2.2(a)(i)) + 2:00 siding (2.2.1(a)) + 1:00 tarpaulin (2.7); graded demurrage (3.1); penal ≤ 6× (3.4.1); terminal hours 06–22 (4.1); night incentive excluded for sidings (4.5); Sundays counted (8.2); coal free time may be cut to 3:00 (2.2(c)) |
| **[TERI-1]** TERI 2023 Vol I | detention benchmark 14–17 h; 15 rakes/month typical one-line terminal; 80–85% of restrictions due to poor release |
| **[WAGON]** BOXN spec | 58 wagons × 58.08 t |
| **[GL-09]** Guan & Liu 2009 | Erlang gate service, exponential truck arrivals |
| **[PBS-25]** Parmaksizoglou et al. 2025 | exponential deviation cost; MINMAX fairness; rake-dependent time windows |
| **[IR-FOIS]** | ₹50,000 wagon registration fee |

**ASSUMED (direction/ranking only, never absolute):** engine-hour cost ₹6,000; shunting ₹25,000;
freight ₹1,400/t; idle cost ₹3,000/h; load rate 900 ± 250 t/h; placement/removal 1.0 ± 0.3 h;
M1–M8 service times; M1–M8 rework 0.05–0.20; truck capacity 35 t; slots/period 10.

### 3.2 The eight administrative steps (`rtsim/admin.py: default_steps()`)
| Step | Owner | Gates | Service (logn mean/sd, h) | Calendar | Rework |
|---|---|---|---|---|---|
| M1 demand → allotment | railway | arrival | 10.0 / 7.0 | railway office 10–17 Mon–Sat | 0.10 |
| M2 stacking permission | railway | loading (parallel from booking) | 2.0 / 1.5 | railway office | 0.15 |
| M3 forwarding note | client | placement | 1.5 / 1.0 | terminal office 9–18 | 0.20 |
| M4 placement advice | terminal | loading (inside free time) | 0.5 / 0.35 | terminal shift 06–22 | 0.05 |
| M5 weighment/overload | terminal | release (inside free time) | 1.8 / 1.4 | terminal shift | 0.18 |
| M6 release reporting | terminal | release (inside free time) | 3.6 / 2.8 | terminal shift | 0.10 |
| M7 RR + freight payment | client | departure (parallel; joins after removal) | 4.0 / 3.0 | railway office | 0.12 |
| M8 truck gate verification | transporter | truck entry (L2) | Erlang 0.25 / 0.12 | 24/7 | 0.08 |

### 3.3 The full formulation catalogue vs what is implemented
| Element | Status |
|---|---|
| Sets: rakes, lines, trucks, companies, crews | implemented |
| Sets: contracts (per-client vs long-term) | not built (extension) |
| Vars: rake → line, placement time, dispatch priority, truck slots | implemented |
| Vars: number of appointment slots (robust stage-1), rake → contract | fixed parameter / not built |
| Objectives tracked: detention, demurrage, deviation cost, MINMAX fairness, throughput, controllable cost, profit | all computed in `accounting.py` (profit = constant revenue − controllable cost) |
| Constraints: line non-overlap, graded free-time/demurrage, truck time windows, crew shift windows (switchable), stockyard capacity, non-pre-emption | implemented |
| Line-length/rake compatibility, multiple-placement penalty, monthly demurrage pooling | not modelled (future work) |

---

## 4. What we are doing now (post mid-sem, Oct 2026)

### 4.1 Supervisor discussion, 8–9 Oct 2026 (verbatim intent)
1. **Scaling:** "if we incorporate more ore, how does each thing change?" (like admitting more
   students needs more hostels and more security). → *capacity planning / bottleneck migration*.
2. **Wagons:** specification, deterioration over time, reuse, cost, when to discard; which wagon
   suits which mineral. Then *"think where your role lies"*.
3. **Each variable's effect** on the overall result, and *"with a bit more money, which factor
   gives the most profit?"* → sensitivity + marginal value of investment.
4. **Costing analysis:** labour increase → cost up, demurrage down → net? (also the PhD student's
   question: more loading workers vs demurrage saved).
5. **Data reality:** we have money/cargo/material/wagon data, not timestamps. Use **qualitative**
   analysis where quantitative is impossible; if confused, **assume a hypothesis model** and
   **reverse-engineer** it against the constraints and aims to see whether it fits.
6. **Multiple materials**, each with its own approvals/formalities and wagon type.
7. Wagon/train information source: FOIS **RailSAHAY** (https://www.fois.indianrail.gov.in/RailSAHAY/Home.jsp).

### 4.2 Status against those asks (updated 24-Oct-2026)
| Ask | Status | Where |
|---|---|---|
| Per-parameter bounds (mid-term ask 1) | **Done** — Layer 5: 39 parameters × 5 levels, 27 conditions, Morris, envelope (§6A) | `experiments/run_layer5_sensitivity.py` |
| Selection provenance (mid-term ask 2) and sufficiency ("are the variables enough?") | **Done** — four selection filters, 23-factor traceability table, four kinds of evidence, Layer 7 stress test (§6G) | `docs/VARIABLE_SELECTION.md`, `experiments/run_layer7_sufficiency.py` |
| Multiple minerals: material-specific vs general features | **Done** — Layer 6: 10 commodity profiles from the field data + IR rules, 7 levers each, per-commodity tornado (§6B) | `experiments/run_layer6_commodities.py` |
| Cost analysis labour vs demurrage | **Done** — break-even per rake (C4), then set against published handling rates (CWC tariff, BCCL SOR) and the 2026 minimum wage under two pay models (C5, §6F) | Layer 6 C4, C5 |
| Loading-rate limits | **Done** — published norms (PIB 2024, bulk-handling sources, IR free times); Layer 5 range now 675–3,370 t/h; silo lever S3 (§6E) | Layer 5, Layer 6 |
| All months in the analysis? | **Verified** — 56/56 months (Jan-2022–Aug-2026), every file 100 % inside its own month, 0 duplicate RRs across files | `tools/rr_register.py` |
| Field data decoding | **Done** — all code columns, 49 charge heads and 15 rebate heads decoded with confidence grades; 16 commodity groups cover 97 % of tonnes (§6C) | `tools/rr_register.py`, `results/field/` |
| Scaling (more ore) | **Not done** (only the L0 load sweep and the L5 arrival-gap range) | arrival-rate multiplier sweep with bottleneck detection |
| Wagon condition / life-cycle | **Not modelled**; wagon *type* per commodity now comes from data | terminal-side: sick-wagon detachment as an extra step |
| Optimisation objective | **Time** (CP-SAT minimises waiting). Money is *measured* and used in COST/CNP bids, not optimised | `optimiser.py`, `accounting.py` |
| Hypothesis / reverse engineering | **Dropped** on Ayan's instruction (too vague) | — |
| Placement–release time logs | **Requested** from the PhD students by Ayan; uncertain. Work proceeds without them | — |

### 4.3 Repository consolidation (done 22-Oct-2026)
The chat produced files in many separate replies. The code was **replayed from the chat history
tool call by tool call**, then checked against the chat's last full export: 15 of 16 package files
are byte-identical, and `calibration.py` carries only the later free-time label fix. It was
verified (57/57 checks; Layer 0, Layer 3, Layer 4 and E11 tables bit-identical to the original
export) and organised into this repo (`docs/CODEBASE.md`). Discovery during the replay: **the
mid-term Layer 1–2 charts were produced before two later fixes** (BOXN 58.08 t and entity-keyed
RNG). The final code therefore gives 15.53 h baseline detention instead of 15.70 h (§7.2).

### 4.4 Where everything lives (from 22-Oct-2026)
- **Code + data + results:** GitHub `MasterChief-Ayan/Freight-optimization` (private), branch
  `main`, tags `v1.0-midterm-model`, `v1.1-sensitivity-commodities`. The raw RR register
  (`data/raw/`, 56 files, 159 MB) is committed (the owner confirmed it is not confidential);
  only the cache `data/processed/` is git-ignored. Branch/tag rules: `docs/WORKFLOW.md`.
- **Context for new chats:** the claude.ai MTP project, in one dated folder per session
  (e.g. `22October2026/MTP_PROJECT_STORY.md`, `22October2026/MTP_CODEBASE.md`). The latest dated
  folder is the current state.

---

## 5. Final outcome we want to achieve

**One sentence:** a field-calibrated, verified decision-support simulation of a private freight
siding that quantifies, for each operational, commercial and managerial factor, *how much* it
drives detention and cost (with bounds). It ranks interventions by **net** benefit (₹ saved −
₹ spent) and says which resources must grow as traffic and commodity mix grow.

### Deliverables
1. **Thesis** (LaTeX/Overleaf; Ayan will supply the reference style/format documents later —
   ask for them before starting) with these chapters: problem and IR context → literature and selection logic →
   formulation → model (5 layers) → verification and validation → results → sensitivity/bounds →
   cost–benefit → scaling and multi-commodity → recommendations → limitations/future work.
2. **This code repository** (GitHub), reproducible with `bash run_all.sh`.
3. Remaining presentations, built from `results/` charts.

### Research results the thesis must contain
| # | Result | Method | Status |
|---|---|---|---|
| R1 | Where detention comes from (decomposition) | ablation + valid lower bound (E11) | done, re-verify after recalibration |
| R2 | Procedure vs capital ranking | paired scenario campaign (E12–E15) | done |
| R3 | **Per-factor bounds** (absolute ranges, tornado) | OAT ranges with CRN + Morris screening + envelope (Layer 5) | **done** |
| R4 | **Net cost–benefit / break-even** (labour, lines, digitalisation, 24/7) | lever savings per rake per commodity = max affordable spend (Layer 6 C2/C4); labour cost from published rates (C5) | **done for labour/loading-rate; capital annuities (silo, 2nd line) still to add** |
| R5 | **Scaling** (bottleneck migration as volume ×1.0 → ×2.0) | arrival-rate sweep, utilisation per resource | to do |
| R6 | **Multi-commodity** extension | 10 commodity profiles from field data + IR free-time rules (Layer 6) | **done** (admin chain still common to all commodities) |
| R7 | Validation on field data | needs placement–release logs (requested); partial: Poisson arrivals confirmed (§6C) | open |
| R8 | Incentive alignment (who causes vs who pays) | attribution (L1) + pricing levers (E13/E14) | done (qualitative policy argument) |
| R9 | **Sufficiency of the variable set** | traceability + omitted-factor stress test (Layer 7) | **done** (rankings robust; absolute hours need time logs) |

---

## 6. Work done after the mid-term (22-Oct-2026): sensitivity, multi-mineral, field data

### 6A. Layer 5 — individual effect of every parameter and condition (mid-term ask 1)
`experiments/run_layer5_sensitivity.py` → `results/layer5_*.csv`, `layer5_results.png`,
`layer5_tornado_cost.png`. Base = calibrated Layer-1 baseline (50 rakes, 30 paired replications,
FCFS, full admin chain): detention **15.53 h**, demurrage ₹75,962 per rake, 84 % of rakes over
free time.

**Ranges.** CITED parameters use the range the rule itself allows: base free time 3–7 h, penal ×1–×6,
terminal hours 8–24 h (06–22 is cited). ASSUMED parameters use a uniform ±50 % stress band, except
the loading rate, whose range comes from published norms since 24-Oct-2026 (§6E): 675 t/h
(payloader, ~5 h/rake) to 3,370 t/h (silo / rapid loading system, ~1 h/rake).
Physical ones use physical limits: wagons 42–59, payload 52–71 t (BOXN → BOXNHL).

**S1 — lower/upper bound of mean detention, each parameter alone** (top of 39; the full table is in `layer5_S1_bounds.csv`)
| Parameter (range) | Detention at low → high end | Swing |
|---|---|---|
| Terminal working hours M4–M6 (8 → 24 h/day) | 31.86 → 10.69 h | **21.17 h** |
| M6 release-reporting mean time (1.8 → 5.4 h) | 12.09 → 18.71 h | 6.63 h |
| Mean loading rate (675 → 3,370 t/h, published range) | 17.68 → 11.09 h | 6.60 h |
| M5 weighment mean time (0.9 → 2.7 h) | 13.66 → 17.25 h | 3.59 h |
| Payload per wagon (52 → 71 t) | 14.82 → 16.79 h | 1.98 h |
| Wagons per rake (42 → 59) | 13.85 → 15.65 h | 1.79 h |
| M5 rejection probability (0 → 0.36) | 14.91 → 16.55 h | 1.64 h |
| M6 rejection probability (0 → 0.20) | 14.86 → 16.28 h | 1.42 h |
| M4 placement-advice mean (0.25 → 0.75 h) | 15.06 → 16.00 h | 0.95 h |
| Loading-rate variability, arrival gap, placement time | — | 0.7–0.8 h each |
| All M1, M2, M3 and variance parameters, lateness | — | < 0.5 h each |
| M7 (all), every commercial parameter | — | **0** (by construction; verified) |

Commercial parameters move money only. Base free time 3 → 7 h: demurrage ₹94,498 → ₹60,329 per
rake. Penal ×1 → ×6: ₹75,962 → ₹455,772 per rake. Detention is unchanged in both.

**S2 — conditions (paired change in detention):** M6 removed −6.55 h; M5 removed −3.59; M6 office
24/7 −2.05; M4 removed −1.41; M4 24/7 −0.75; M5 24/7 −0.70; 2 lines + 2 crews −0.67. Second or
third line **without** crew: **+0.39 / +0.72 h (worse)**. M1/M3 removed: +0.38 / +0.48 h (worse,
because those steps smooth arrivals). Dispatch rule SPT/COST/CNP: ±0.03 h (n.s.). 2 locos, 2 crews
on one line, crew shift 06–22: 0 (the crew shift coincides with the terminal-shift calendar that
already gates loading).

**S3 — Morris screening** (20 trajectories, μ\* = h of detention per full-range move):
terminal hours 20.3 (σ 9.0), M6 mean 7.5, loading rate 5.2, M5 mean 4.2, M5 rework 1.7 (σ/μ\* 0.59),
M6 rework 1.5, M4 mean 1.0, payload 0.9, wagons 0.9. **Morris and OAT agree on the top 3.** Shunting times,
transit and arrival gap have σ > μ\*: their effect is mostly interaction (they matter only together
with other factors).

**S4 — envelope** (all time-affecting factors at their favourable/unfavourable ends together):
**3.54 h ← 15.53 h → 51.41 h**. The unfavourable end saturates the line (wait > 700 h) even with
demand held at base. That is the model's absolute range within the stated bounds.

**Reading for the thesis.** One calendar decision (how many hours a day the terminal's own
paperwork runs) moves detention more than every physical parameter put together. Release
reporting (M6) and loading speed tie for second (6.6 h each).

### 6B. Layer 6 — which lever matters for which mineral (supervisor ask, 8–9 Oct)
`experiments/run_layer6_commodities.py` → `results/layer6_*.csv`, `layer6_results.png`. Ten
commodity profiles of the same model. Wagons, payload, overload rate (→ M5 rework), siding share
and freight come from the field data. Free time comes from the Compendium 2.2 for the dominant wagon type.
Loading rates by handling method are **ASSUMED** (manual 300–350 t/h, crane 450, reach-stacker /
pumping 600, mechanised 900).

**C1 baseline**
| Commodity | t/rake | Loading | Free time | Detention | Overload (data) | Data leak / rake* |
|---|---|---|---|---|---|---|
| Coal, open BOXN | 3,898 | mech. 4.3 h | 8 h | 17.0 h | 30 % | ₹143,914 |
| Coal, hopper BOBRN | 3,555 | mech. 4.0 h | 7 h | 17.2 h | 41 % | ₹83,479 |
| Iron ore | 3,956 | mech. 4.4 h | 7 h | 16.0 h | 4 % | ₹131,743 |
| Clinker | 3,982 | mech. 4.4 h | 7 h | 16.7 h | 21 % | ₹62,801 |
| Cement (bagged, BCN) | 2,758 | manual 7.9 h | 9 h (goods shed) | 20.9 h | 1 % | ₹2,356 |
| Foodgrains | 2,727 | manual 9.1 h | 9 h | 22.0 h | 1 % | ₹153 |
| Fertiliser | 2,680 | manual 8.9 h | 9 h | 21.9 h | 1 % | ₹43,834 |
| Iron & steel (flat, crane) | 3,654 | crane 8.1 h | 9 h | 21.3 h | 5 % | ₹91,279 |
| Containers | 1,661 | 2.8 h | 5 h | 13.4 h | 2 % | ₹162 |
| POL (tank) | 2,660 | 4.4 h | 10 h | 16.0 h | 0 % | ₹15 |
\*expected punitive overloading charge + freight paid on capacity not loaded (medians from the RR register).

**C2 levers (change in detention, h) and class**
| Lever | Range over 10 commodities | Class |
|---|---|---|
| G1 terminal works 24/7 (M4–M6) | −4.1 (containers) … −6.1 (iron & steel) | **GENERAL, uniform** |
| G2 digitalise M6 release reporting | −3.7 … −4.6 | **GENERAL, uniform** |
| S1 loading rate +50 % | −1.4 (containers) … −3.7 (manual/crane cargo) | general, **size depends on material** (corr. with loading hours 0.96) |
| G3 digitalise M5 weighment | −1.4 … −3.8 (coal hopper) | general, **size depends on material** (overload rate) |
| S2 precise loading (no overload) | 0 (bagged, POL) … −2.0 h coal hopper; money: ₹1.67 lakh/rake coal BOXN, ₹1.35 lakh iron ore | **MATERIAL-SPECIFIC** |
| G4 2nd line + 2nd crew | +0.18 (covered cargo) … −0.94 (containers) | **MATERIAL-SPECIFIC** (sign changes) |
| S3 silo / rapid loading system, rake in ~1.25 h (bulk only, added 24-Oct) | −4.3 (coal hopper) … −5.0 (clinker); cash ₹38.9–43.8 k demurrage per rake (₹71.6–78.8 k incl. idle cost) | **MATERIAL-SPECIFIC** (bulk only) |
| R1 free time cut to 3 h (coal, iron ore only) | 0 h, +≈₹20,000 demurrage per rake | **PRICING risk** |

**What to focus on, per material**
- *Coal (both wagon types), clinker, slag, flux:* loading accuracy is the material-specific lever.
  Overloading is 21–41 %, so it shows up as weighment rework (M5) and punitive charges. Coal also
  pays for ~159 t of unused capacity per rake. Fix: weigh-bridge-controlled loading (silo /
  weigh-o-meter).
- *Iron ore:* little overloading (4 %), but ~162 t of paid-but-unused capacity per rake (₹1.3 lakh)
  and the highest surcharge burden (21 % of basic freight: 15 % busy-season charge still applies to
  iron ore). Watch the 3-hour free-time cut risk.
- *Cement, foodgrains, fertiliser (bagged, covered, goods sheds):* loading rate is the dominant
  material-specific lever (manual 8–9 h). Extra labour gangs pay up to ~₹24–25 k per rake in
  demurrage alone. A second line without crew makes them *worse*.
- *Iron & steel (flat, crane):* crane rate. It has the highest demurrage per rake (₹1.21 lakh) and
  the largest cash break-even (₹35.6 k per rake).
- *Containers / POL:* already short; only the general levers matter.
- *Every commodity:* the same three general levers rank first — terminal hours, release
  reporting (M6), weighment (M5). Per-commodity tornado (C3): **hours > loading rate > M6** for 9 of
  10 commodities (containers: hours > M6 > loading rate).

**C4 labour/equipment break-even for +50 % loading rate** (labour cost compared in §6F). Maximum spend
per rake that still pays, **cash only (demurrage)**: containers ₹10.5 k, POL ₹14.6 k, mechanised bulk
₹19.9–22.1 k, bagged ₹24.2–25.3 k, steel ₹35.6 k. Including the ASSUMED rake idle cost: ₹19–85 k.
Per loading-hour saved, ≈ ₹21–31 k in every case. This answers the PhD student's question: hire
the extra crew if it costs less than this per rake.

Limitation: the administrative chain (M1–M7) is common to all commodities. Commodity-specific
paperwork (e.g. FCI documents, POL safety certificates) is not yet modelled.

### 6C. Field data — decoded (`tools/rr_register.py`, `tools/analyse_rr_register.py`)
**Dataset:** ER Inward Freight Register, RR-base, paid traffic; 56 monthly FOIS exports, Jan-2022 to
Aug-2026. **220,395 RRs, 508.5 Mt** after removing 338 sub-total rows (the first audit's 220,733
included them). This is the **receiving** side: it describes the consignments, not the loading
terminal's times.

**Cleaning rules found:** header on row 3; sub-total rows at file ends; commodity column renamed
`CMDT CODE-CODE` from Dec-2024; **WAGON TYPE, RAKE TYPE, SIDING TYPE** columns only from Dec-2024
(back-filled per commodity code where one value covers ≥ 90 %); charge heads added over time
(93 → 120 columns).

**Decoded (grade A = official source + data arithmetic; B = arithmetic/converging evidence;
C = plausible, confirm with FOIS master):**
- **Traffic type:** GC = coal consigned by Coal India subsidiaries (86 % ECL/BCCL/CCL/MCL;
  95 % to DVC/NTPC/WBPDCL/CESC; 75 % hopper). PC = captive/private coal (consignor = the consumer's
  own mine: WBPDCL, SAIL, DVC, NTPC). GG = all non-coal general goods. RM = railway material
  (consignee RAIL on 99.1 %). F/L flag = foreign (other-zone origin, median 418 km) vs local
  (127 km). Payment mode E = e-payment (EPAYMENT ID on 99 %).
- **Charge heads:**
  - OTC/DTC = terminal charge **₹20/t** (exactly, on 99,818 RRs; A).
  - DPO/DPFG/DPCM = busy-season charge **15 %**; DPCN = **10 %** for containers (A/B). The coal
    exemption is visible: no coal RR pays it.
  - PBA = 15 % on iron ore (B). MNRK and TPRO/TPRC = mini-rake and two-point-rake supplementary
    charges, **5 %** (A).
  - POL1/POL2/POLA = punitive overloading (A/B). OTAC/DTAC/TAC = terminal access charge
    ₹2,760/wagon (₹1.6 lakh/rake, B). SD = siding charge (B). DW = demurrage collected on the RR
    (multiples of ₹150, rare, B). DS ≈ 5 % development surcharge (B).
  - Rebates: TEFD 15–20 % (A), STS (A). Remaining heads are graded C in `results/field/F0_code_tables.xlsx`.
- **Commodity codes:** 220 numeric FOIS codes mapped to **16 groups covering 97 % of tonnes**:
  coal 61 %, iron ore 11 %, clinker 6 %, cement 5 %, railway material 3 %, foodgrains 2 %,
  fertiliser 2 %, iron & steel, flux, slag, salt, POL, containers, manganese ore, gypsum. Evidence
  for each group: freight class + wagon type + consignor/consignee + origin.
- **Station codes:** goods sidings (MTPS, FSTP, PSPM, DSEY…) are not in public passenger lists.
  They are identified by consignee and commodity in `data/processed/terminal_profiles.csv` (e.g.
  MTPS = DVC coal, 95 % hopper; DSEY = SAIL iron ore; FSTP = NTPC coal).

**Empirical facts the model uses or is checked against**
- **Arrivals are Poisson.** Daily full-rake counts at the 15 largest receiving sidings have a
  variance/mean ratio of 0.7–1.7 (≈ 1). This supports the model's exponential inter-arrival
  assumption.
- **Rate and wagon type per commodity:** big plants receive 1.4–8.6 rakes/day (several lines).
  Coal is 56 % hopper / 44 % open BOXN by tonnes.
- **Loading accuracy is commodity-specific:** overload incidence is coal 37 %, gypsum 25 %,
  clinker/slag/flux ≈ 21 %, bagged cargo ≈ 1 %. Paid-but-unused capacity per full rake is coal
  159 t, iron ore 162 t, steel 123 t.
- **Charges over basic freight** are 1–3 % for coal but 17–28 % for other cargo (busy-season
  charge + development surcharge + terminal charges).

### 6D. What remains for the data (plan)
1. Confirm the grade-C codes once via the FOIS code master or the PhD students. Edit only the
   tables in `tools/rr_register.py`.
2. If the placement–release logs arrive: fit M4–M6 and the loading time per commodity, replace
   the ASSUMED loading rates, and validate detention (R7).
3. Scaling (R5): sweep demand ×1 → ×2 per commodity mix and report which resource saturates
   first (line, crew, loco, paperwork office).
4. Optional qualitative layer: a BPMN swim-lane map plus three-point (PERT) expert estimates for
   M1–M8 per commodity. This is the honest substitute for commodity-specific paperwork data.

### 6E. Loading rates from published norms (24-Oct-2026)
The RR register has no loading times, so the limits come from published sources:

| Method | Published norm | Implied rate (BOXN rake 3,369 t) | Source |
|---|---|---|---|
| Silo / rapid loading system (RLS) | rake in 1–1.5 h; CCL Karo/Konar: "5 h → 1 h" | 2,250–3,370 t/h | PIB 07.10.2024; bulk-online RLS thread |
| Conventional payloader (mechanised) | ~5 h per rake; IR mechanised free time 5:00 | ~675 t/h | PIB 07.10.2024; MoR Compendium 2.2 |
| Manual, bagged into covered wagons | IR manual free time 9:00 (the time the Railway itself allows) | ~300 t/h for 2,700 t | MoR Compendium 2.2 |

- Model base 900 t/h (mechanised) lies inside 675–3,370 → **no baseline result changes**.
  Layer 6 manual rates (300–350 t/h) give 8–9 h, consistent with the 9:00 norm.
- No public source gives a *measured* manual rate; that stays ASSUMED until the time logs arrive.
- Layer 5 load-rate range: 450–1,350 (±50 %) → **675–3,370 t/h (published)**: 17.68 → 11.09 h.
- New Layer 6 lever **S3 silo/RLS** (bulk only): −4.3 to −5.0 h per rake; ₹38.9–43.8 k demurrage
  per rake (₹71.6–78.8 k incl. idle cost). At one rake a day that is ≈ ₹1.4–1.6 crore a year of
  demurrage, the figure against which a silo's capital cost must be set (annuity not yet added, R4).

### 6F. Labour cost vs demurrage (Layer 6 C5, 24-Oct-2026)
C4 gives the most that faster loading may cost (demurrage saved). C5 sets this against **published**
handling costs, under two bounding pay models for the bigger gang/machine needed for +50 % rate:

- **Piece rate** (paid per tonne, as in CWC and coal-company contracts): the same tonnes are moved
  by more hands in less time, so the bill per rake does not change → extra cost ≈ 0 (only a
  contractor premium) → **pays for every material**.
- **Shift rate, no productivity gain** (upper bound): the 50 % larger gang is paid a full shift
  however short the loading → extra cost = 50 % of the handling bill.

| Material | Break-even (cash) | per tonne | Today's handling rate | Break-even as % of rate | Shift-rate net |
|---|---|---|---|---|---|
| Coal / iron ore / clinker (payloader) | ₹19.9–22.1 k | ₹5.5–5.6/t | ~₹12/t (BCCL SOR 2025, order of magnitude) | 46–47 % | ≈ break-even (−₹7.9 k … +₹4.2 k) |
| Cement / fertiliser (bagged) | ₹24.2–25.3 k | ₹9.0–9.2/t | ₹91/t median (₹50–133), CWC RWC tariff | ≈ 10 % | loses ₹43–158 k |
| Foodgrains (bagged) | ₹24.8 k | ₹9.1/t | ₹100/t median (₹52–136), CWC RWC tariff | ≈ 9 % | loses ₹46–161 k |
| Steel (crane), containers, POL | ₹10.5–35.6 k | ₹5.5–9.8/t | no published rate found | — | not costed |

**Reading.** In labour terms the break-even pays for 24–31 extra labourer-days per rake
(minimum wage ₹827/day, loading & unloading, central sphere Area A, from 01.04.2026). So the answer
to "should we add labour?" depends on **how labour is contracted**, not only on how much is added:
- per tonne → yes, for every material;
- per shift with idle time → only bulk, and only just;
- for bagged cargo, a contractor premium of up to ~10 % of today's rate still pays.

### 6G. Sufficiency of the variable set (Layer 7, 24-Oct-2026)
Evaluator's question: *how do you know the conditions/variables are sufficient?* Answer in
`docs/VARIABLE_SELECTION.md`:
- four selection filters (relevance to the IR detention interval, published evidence,
  controllability, measurability);
- a 23-factor traceability table (IN / PARTIAL / OUT, with reasons);
- four kinds of evidence: complete by construction (attribution sums to 100 %), agreement with
  untuned facts (Poisson arrivals, exact charges), Morris screening, and a stress test.

**Layer 7 stress test** (`experiments/run_layer7_sufficiency.py`):
- *Design:* add plausible omitted factors at realistic size, applied after each intervention so
  none can remove them: +1/+3 h physical delay inside free time, +1/+3 h unmodelled paperwork,
  +50 % traffic, loading disruptions, error rates ×2, and all together.
- *Result:* base detention rises 15.5 → 23.1 h, but the **order of the six interventions is
  identical in 9/9 cases (Kendall τ = 1.00)**. Procedure beats capital by 3.6–6.6×, and a second
  line without crew stays counter-productive.
- *Conclusion:* the set is sufficient for ranking interventions (the thesis's purpose), not for
  predicting absolute hours at a named siding.

### 6H. Detention for every length of the terminal day (Layer 5b, 25-Oct-2026)
`experiments/run_layer5b_hours_sweep.py` → `results/layer5b_hours_sweep.csv`, Fig. 7. Calendar of
M4–M6 set to 8, 9, …, 24 h a day on the calibrated base (30 paired reps × 50 rakes).

| Hours/day | 8 | 10 | 12 | 14 | **16 (today)** | 18 | 20 | 22 | 24 |
|---|---|---|---|---|---|---|---|---|---|
| Detention (h) | 31.86 | 25.86 | 21.87 | 18.35 | **15.53** | 13.46 | 12.28 | 11.36 | 10.69 |
| Demurrage / rake (₹ k) | 258.5 | 184.4 | 139.6 | 103.8 | **76.0** | 55.8 | 44.3 | 35.8 | 29.7 |

- Every extra hour helps, but less each time: 8 → 9 h saves 3.5 h; 16 → 17 h saves 1.2 h;
  23 → 24 h saves 0.3 h.
- From today: +2 h (to 18 h, 06:00–24:00) already gives 43 % of the full 24/7 gain (2.07 of 4.84 h).
- Cutting to 12 h adds 6.3 h per rake and almost doubles demurrage (₹76 k → ₹140 k).
- **Bug found and fixed by this sweep:** a calendar window lives inside one day, so 18–23-hour days
  from 06:00 were silently capped at midnight (all behaved as 18 h). The fix lengthens the day by
  opening earlier (20 h = 04:00–24:00). Two new checks guard it (the sweep reproduces the Layer 5
  levels; every extra hour strictly shortens detention).

## 7. Numbers to quote (and which version they come from)

### 7.1 Exactly reproduced by the final code (safe to quote as model results)
| Result | Value |
|---|---|
| Waiting decomposition, 12 reps × 25 rakes, gap 22 h (E11) | full 41.43 ± 12.37 h; 24/7 11.07; no rework 36.90; both 9.18; + optimal sequencing (bound) 5.84 h |
| Shares | office hours 73.3%, rework 10.9%, both 77.8%, sequencing ≤ 8.1%, irreducible 14.1% (→ **78 / 8 / 14**) |
| Line occupancy | 17.9 h → 12.2 h per rake with calendars and rework removed |
| E8a control (calendars off) | CP-SAT bound 10.37 h ≤ COST 10.64 h (valid) |
| E10 fairness (CNP ageing 0 → 0.5) | worst wait 161.2 ± 66.3 → 108.1 ± 30.6 h (−33%); mean 44.22 → 44.37 h |
| E12 detention saved vs base 16.07 h | digitalise all 8.98 ± 0.56; M5 + M6 7.65 ± 0.69; terminal 24/7 5.28 ± 0.31; +50% load rate 2.08 ± 0.32; no rework 1.40 ± 0.45; 2nd line + crew 0.58 ± 0.22; 2nd loco 0.00; **2nd line alone −0.28 (worse, n.s.)** |
| Procedure vs capital | 8.98 / 0.58 ≈ **15×** |
| Breaches | 87% → 25% under full digitalisation |
| E13/E14 pricing | detention fixed at 16.07 h; demurrage ₹1.77 M (8 h free time) vs ₹2.18 M (6 h); penal ×2 → ₹3.54 M |

### 7.2 Changed slightly when the final code was re-run (use the new values from now on)
The mid-term charts for Layers 1–2 were generated **before** the BOXN 58.08 t fix and the
entity-keyed RNG fix. The original chat never re-ran those two layers afterwards. Directions and
rankings are unchanged.

| Result | Mid-term (slides/write-up) | Final code (this repo) |
|---|---|---|
| Baseline detention (30 reps × 50 rakes) | 15.70 ± 0.31 h | **15.53 ± 0.33 h** (inside 14–17 h) |
| Physical-only detention | ~4.5 h (early README text, pre-calibration) | 4.05 h |
| Attribution terminal / client / railway | 74.5 / 22.2 / 3.3% (~75%) | **73.5 / 23.7 / 2.9%** |
| E2 full digitalisation | −8.57 h | −8.55 h |
| E7 hard infeasibility, M1 sd × 0.25 → × 3 | 1.2% → 12.0% | 1.2% → **14.1%** |
| One-way lane truck turnaround | ~6× | 6.28 h vs 1.06 h (≈ 6×) |

### 7.2b Layers 5–7 (22/24-Oct-2026, this repo)
See §6A–6B, §6E–6G. Headline numbers: terminal-hours swing 21.17 h (31.86 → 10.69 h); envelope
3.54 – 51.41 h (was 4.52 – 52.46 h before the published loading-rate range, 24-Oct); loading rate
over its published range 17.68 → 11.09 h; Morris top 3 = terminal hours, M6 mean, loading rate; per-commodity detention 13.4 h
(containers) – 22.0 h (foodgrains); G1 24/7 −4.1 to −6.1 h for every commodity; precise loading
saves ₹1.67 lakh per coal BOXN rake (data leak + model cost); silo loading −4.3 to −5.0 h per bulk
rake; labour break-even ₹5.5/t (bulk) and ₹9/t (bagged) = 46 % / 10 % of today's handling rates;
Layer 7: ranking unchanged in 9/9 omitted-factor scenarios, procedure > capital by 3.6–6.6×.

### 7.3 Results to report as nulls or open
- E8b/E9: at ρ ≈ 0.7 no online rule beats FCFS significantly. Sequencing pays only above ~50%
  line utilisation (L0 load sweep).
- E6 (truck-company MINMAX fairness): helps only at a loose quota (−4% worst-off cost at quota 20).
  At tight quotas it *raises* the worst-off company's cost (+15.5% at quota 8). Treat it as open.
- L0: a second line without crew raises detention (4.05 → 4.30 h), the same mechanism as E12.
- E8b/E9 **CP-SAT rows are not bit-reproducible**. CP-SAT stops on a wall-clock limit with 8
  threads, so its incumbent schedule varies slightly by machine (40.38 vs 40.08 h observed). They
  are not quoted. The lower-bound results (E8a, E11) are stable (see CODEBASE §7).

---

## 8. Open questions and decisions log
- **Decided:** Python/SimPy; VTIM; private siding base case; non-pre-emption; A1 (coal always
  available); detention = IR definition (placement → release); graded demurrage; CRN with
  entity-keyed streams; read bounds, never execute them.
- **Open:** time-indexed tight bound (an **unused, unverified draft** `time_indexed_bound()` already
  sits at the bottom of `optimiser.py`; see CODEBASE §7); contracts and demurrage pooling; the agentic-AI question from
  the very first brief was never formally closed with the supervisor (worth one line at the next
  meeting); field validation of detention needs the placement–release log.
- **Decided 22-Oct (second session):** hypothesis / reverse-engineering calibration dropped (too
  vague); Layer 5 (per-parameter bounds) and Layer 6 (multi-commodity) built; field data used only
  for what it can measure (no timestamps).
- **Decided 24-Oct:** loading-rate range from published norms (base 900 t/h kept: inside the range,
  so no baseline result changes); labour cost compared only with *published* rates under two
  bounding pay models (no invented labour cost); sufficiency answered by a stress test, not by
  argument alone.
- **Pending:** scaling (R5); capital annuities for silo / 2nd line (R4);
  **LaTeX/Overleaf thesis** — Ayan will provide reference documents for style/format; ask for them
  before starting.
