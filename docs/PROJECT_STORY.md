# MTP — Project Story: start → mid-term → now → final target

**Title.** *Analysis of operational, commercial and managerial constraints at a freight
terminal, and solutions for quick release of rolling stock.*
**Student:** Ayan Ahmed (22MF3IM04) · **Supervisor:** Prof. Biswajit Mahanty · M.Tech, Industrial & Systems Engineering
**Context:** Indian Railways coal rakes at a **private siding** (Eastern Railway context).
**This file last updated:** 22-Oct-2026. Companion file: `docs/CODEBASE.md` (what each code file does).

> **How to use this file (future sessions / Claude Code).** Read §0 first. It is the
> state of the project in ten lines. §1–§3 are history, so you know *why* things are the way they are.
> §4 is the current work. §5 is the target. §6 is the data plan. §7 holds the numbers to quote,
> and §8 the open questions.

---

## 0. State of the project in ten lines

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
7. Two evaluator asks are pending. (a) Find the **individual effect of each parameter/admin step
   with lower/upper bounds** on an absolute scale. (b) Show **how the variables and constraints
   were selected** from the literature.
8. Post-mid-sem asks (8–9 Oct): capacity scaling ("more ore → what else must grow"), wagon
   condition/commodity-wise needs, a **cost analysis** (labour vs demurrage), qualitative +
   hypothesis/reverse-engineering methods, and multiple commodities.
9. First field dataset received: **ER Inward Freight Register (RR-base), Jan-2022–Aug-2026,
   220,733 RRs**. It has money, volume, wagons and overloading, but **no placement/release timestamps**.
10. Code base consolidated and re-verified on 22-Oct-2026 (this repo). Layers 3, 4 and E11
    reproduce the chat-era numbers exactly. 19/20 result tables are bit-identical between the
    replayed original and this repo; the exception is CP-SAT timing, §7.3. Layers 1–2 regenerate
    slightly differently from the mid-term charts (see §7.2).

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

### 4.2 Honest status against those asks (as of 22-Oct)
| Ask | Status | Where it would live |
|---|---|---|
| Per-parameter bounds (mid-term ask 1) | **Not done.** E1 (remove a step), E2 (digitalise a step), E3 (five interventions on M6) and E12 (ten levers) are *partial* evidence, not bounds over ranges | new `experiments/run_layer5_sensitivity.py` (one-at-a-time ranges + tornado) |
| Selection provenance (mid-term ask 2) | **Partly documented** (`calibration.py`, §3); needs a source → model-element traceability table | doc / thesis chapter |
| Scaling (more ore) | **Not done.** Only the L0 load sweep (STEP 3b) and the L0 line sweep exist | arrival-rate multiplier sweep with bottleneck detection |
| Wagon condition / commodity-wise wagons | **Not modelled** (homogeneous BOXN, no wagon state) | terminal-side: sick-wagon detachment as an extra admin/shunting step; full asset life-cycle is outside terminal scope |
| Cost analysis labour vs demurrage | **Not done as a net cost.** Detention/demurrage effect of "+50% loading rate" and "2nd line + 2nd crew" exists (E12); no labour cost was netted, deliberately (E15 avoids invented capital costs) | break-even on labour cost per crew-hour using E12 deltas |
| Optimisation objective | **Time** (CP-SAT minimises waiting; bound is on waiting). **Money** enters through COST/CNP bids and all accounting. Total cost is *measured*, not *optimised* | `optimiser.py`, `policies.py`, `accounting.py` |
| Multiple commodities | **Not modelled** (one commodity, coal) | commodity as a rake attribute → class-specific wagon type, free time and admin steps |
| Qualitative / reverse engineering | **Done once informally**: admin times were inverse-calibrated to TERI's band. Formal version planned with field aggregates (§6) | `calibration.py` + new calibration script |

### 4.3 Repository consolidation (done 22-Oct-2026)
The chat produced files in many separate replies. The code was **replayed from the chat history
tool call by tool call**, then checked against the chat's last full export: 15 of 16 package files
are byte-identical, and `calibration.py` carries only the later free-time label fix. It was
verified (57/57 checks; Layer 0, Layer 3, Layer 4 and E11 tables bit-identical to the original
export) and organised into this repo (`docs/CODEBASE.md`). Discovery during the replay: **the
mid-term Layer 1–2 charts were produced before two later fixes** (BOXN 58.08 t and entity-keyed
RNG). The final code therefore gives 15.53 h baseline detention instead of 15.70 h (§7.2).

---

## 5. Final outcome we want to achieve

**One sentence:** a field-calibrated, verified decision-support simulation of a private freight
siding that quantifies, for each operational, commercial and managerial factor, *how much* it
drives detention and cost (with bounds). It ranks interventions by **net** benefit (₹ saved −
₹ spent) and says which resources must grow as traffic and commodity mix grow.

### Deliverables
1. **Thesis** with these chapters: problem and IR context → literature and selection logic →
   formulation → model (5 layers) → verification and validation → results → sensitivity/bounds →
   cost–benefit → scaling and multi-commodity → recommendations → limitations/future work.
2. **This code repository** (GitHub), reproducible with `bash run_all.sh`.
3. Remaining presentations, built from `results/` charts.

### Research results the thesis must contain
| # | Result | Method | Status |
|---|---|---|---|
| R1 | Where detention comes from (decomposition) | ablation + valid lower bound (E11) | done, re-verify after recalibration |
| R2 | Procedure vs capital ranking | paired scenario campaign (E12–E15) | done |
| R3 | **Per-factor bounds** (absolute ranges, tornado) | one-at-a-time ranges with CRN, then global (e.g., Morris/Sobol) if time allows | to do |
| R4 | **Net cost–benefit / break-even** (labour, lines, digitalisation, 24/7) | E12 deltas × cost data → break-even cost per lever | to do |
| R5 | **Scaling** (bottleneck migration as volume ×1.0 → ×2.0) | arrival-rate sweep, utilisation per resource | to do |
| R6 | **Multi-commodity** extension | commodity classes from field mix | to do |
| R7 | Validation on field data | inverse calibration to field aggregates + hold-out check | to do (needs data, §6) |
| R8 | Incentive alignment (who causes vs who pays) | attribution (L1) + pricing levers (E13/E14) | done (qualitative policy argument) |

---

## 6. Plan for the new field dataset (plan only, nothing executed beyond the audit)

**Dataset:** ER *Inward Freight Register*, RR-base, paid; 56 monthly FOIS exports, Jan-2022 to
Aug-2026; **220,733 RRs**; 93 columns per file (120 in the union, because charge heads were added
over time). Audit script: `tools/audit_rr_register.py`. Folder layout: `data/README.md`.

**Audit facts (22-Oct-2026):**
- Wagons (8-wheelers) per RR: median 46, IQR 10–58, max 70. Full rakes and piecemeal traffic are mixed.
- RR date minus invoice date: median 0 d, 95th percentile 2 d. This is day-granular only.
- **19.4% of RRs carry overloading** (POL1/POL2 > 0).
- e-RR share is 3–10% per year.
- Top consignees are SAIL, DVC, NTPC, WBPDCL. Top destinations are SSYS, MTPS, DSEY, FSTP, PSPM, DSTP.
- One commodity code (2991323) dominates the tonnage.
- Money: basic freight ₹111,931 cr, other charges ₹13,054 cr, final ₹129,626 cr.
- **No placement/release/removal timestamps, no demurrage/wharfage.** Those are billed at the
  terminal and are not on the RR.

**Plan, in order:**
1. **Decode the schema.** Get the FOIS code masters (commodity codes, station codes,
   "other charge" heads, TRFC TYPE, F/L/I flag) from the PhD students or RailSAHAY. Keep decoded
   meanings in a lookup table. Codes still to confirm: DS (looks like the 5% development surcharge),
   DTC/OTC (look like terminal charges), POL1/POL2/POLA (punitive overloading), DPO, PCLA, ENHC, SD, ST.
2. **Pick the study terminal(s).** Filter `STATION TO` + consignee to one coal-receiving siding
   with full-rake traffic (e.g., a DVC/NTPC/WBPDCL plant). The model's base case is a single private
   siding, so the data must be cut the same way.
3. **Replace ASSUMED → EMPIRICAL where the data allows:**
   | Model parameter (file) | From the data |
   |---|---|
   | arrival process `rake.arrival_gap` (config.py) | rakes/day per terminal → Poisson check, over-dispersion, seasonality |
   | `rake.wagons`, `tonnes_per_wagon` (config.py) | empirical distribution of 8-WHLR and WEIGHT ACTL per rake |
   | M5 rework probability (admin.py) | overloading incidence (19.4% overall; per terminal) |
   | `freight_per_tonne` (config.py) | RATE/T and BASIC FRGT per rake |
   | M7 digitalisation baseline (admin.py) | e-RR / eT-RR uptake |
   | upper bound on M7-type paperwork lag | RR − invoice lag (≤ 2 d at p95) |
   | commodity mix for multi-commodity runs | CMDT CODE shares per terminal |
4. **Ask for what is missing**, as one short, specific request: the terminal's **placement–release
   log** (FOIS/TMS "rake placement & release" or the **Demurrage & Wharfage register**) for the same
   terminal and months. That is the only thing that can *validate* detention.
5. **Cost analysis now (no timestamps needed):** revenue and charges per rake from the RR, the E12
   detention/demurrage deltas from the model, and labour/capital cost assumptions stated explicitly.
   This gives a **break-even table** ("a second crew pays for itself if it costs less than ₹X/month").
6. **Hypothesis + reverse engineering** (supervisor's suggestion, done formally). Treat the unknown
   admin parameters as hypotheses. Search them so the model reproduces the field aggregates
   (monthly rakes handled, wagons/rake, overloading rate) **and** TERI's 14–17 h band. Report the
   accepted parameter region (an ABC/grid style inverse calibration), not one tuned point.
7. **Qualitative layer:** a BPMN swim-lane map of the terminal's real procedure (from PhD-student
   interviews), plus three-point (min/most-likely/max, PERT) estimates for M1–M8 from officials.
   This is standard expert elicitation where no logs exist.
8. Then run **R3 (per-factor bounds)** and **R5 (scaling)** on the recalibrated model, and
   re-run E11/E12 to check the headline survives.

---

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
- **Pending by instruction:** apply mid-term asks 1–2 *only when Ayan says so*.
