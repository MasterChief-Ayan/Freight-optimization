# VARIABLE SELECTION — why these variables and conditions, and why they are enough

Answers the evaluator's question (post mid-sem): *"How did you assume that the conditions and
variables you are taking are sufficient?"* It also closes mid-term ask 2 (*"were the variables
invented or taken from papers, and how was the subset selected?"*).

**Short answer.** A model is *sufficient* when the factors it leaves out would not change
its conclusions. It does not have to contain everything (Robinson 2008, conceptual modelling;
Sargent 2013, verification & validation). Our conclusions are **rankings of interventions**
(procedure beats capital). Four pieces of evidence (§3) support the set:
1. it is complete by construction for the quantity it explains;
2. it agrees with facts it was not tuned to;
3. screening shows most included detail barely matters;
4. a stress test adds the main omitted factors and the ranking survives.

---

## 1. How the variables were selected (four filters)

A candidate factor entered the model only if it passed all four filters:

| Filter | Question asked | Why |
|---|---|---|
| F1 Relevance | Does it act on the interval the KPI measures (placement → release, IR 2.2.2(a)), or gate the start of that interval? | The KPI is fixed by the Railway's own definition. |
| F2 Evidence | Is it named as a delay cause in TERI (2023) Vols I–II, the MoR Compendium (2024), or the dwell-time literature (World Bank, WCO TRS, Guan & Liu 2009, Parmaksizoglou et al. 2025)? | No invented mechanisms. |
| F3 Control | Can one of the four parties (terminal, railway, client, transporter) or a rule change it? | The thesis ranks *actions*. |
| F4 Measurability | Can it be measured, or bounded by a rule or physical limit? | Every parameter is tagged CITED / DERIVED / ASSUMED (`rtsim/calibration.py`). |

The 21 documented IR procedural steps (5 booking, 9 siding, 4 truck/gate, 3 destination) were
compressed to **8 steps (M1–M8)**. A step was kept only if it is on the critical path to
placement or release, has a documented approval or rework loop, and is traceable in IR rules
(`rtsim/admin.py`, header of THE EIGHT STEPS).

---

## 2. Traceability: every candidate factor, where it is, or why it is left out

| # | Candidate factor | Source | In the model as | Status |
|---|---|---|---|---|
| 1 | Rake arrival uncertainty | TERI; supervisor (operational) | exponential arrival gap; lateness, no-show; M1 allotment chain feeds arrivals | IN (arrivals Poisson in field data) |
| 2 | Long loading | TERI; supervisor | loading rate per handling method; Layer 6 per commodity | IN (range from published norms) |
| 3 | Line / platform unavailability | supervisor (operational) | loading lines (queue for a line) | IN |
| 4 | People unavailability | supervisor; TERI (labour stops at sunset) | crews; crew shift window | IN (switch) |
| 5 | Loco / shunting availability | IR practice | shunting locos; placement / removal times | IN |
| 6 | Office working hours | MoR Compendium 4.1 (06–22) | calendars on every step | IN, CITED |
| 7 | Documentation and approvals | IR rules (21 steps); supervisor ask | M1–M8 with service time and rework loop | IN (compressed) |
| 8 | Weighment and overloading | IR weighment rules; field data | M5 + rework = observed overload rate per commodity | IN, field data |
| 9 | Release reporting | TERI (80–85 % of restrictions due to poor release) | M6 | IN |
| 10 | Order / payment processing (commercial) | supervisor (commercial) | M1 allotment chain; M7 RR and payment | IN |
| 11 | Free time, demurrage, penal rules | MoR Compendium 2.2, 3.1, 3.4 | charge model (graded bands) | IN, CITED |
| 12 | Road side (trucks, one-way lane, gate) | supervisor; Guan & Liu 2009 | Layer 2 | IN |
| 13 | Material availability (mineral management) | supervisor (managerial) | relaxation A1 (material always available); A1 off tested (+2.9 h) | IN (switch) |
| 14 | Dealing with officials (managerial) | supervisor (managerial) | through office calendars and rework probabilities, not as its own process | PARTIAL |
| 15 | Wagon examination, sick-wagon detachment, levelling | IR practice | not modelled | OUT → stress-tested (O1) |
| 16 | Commodity-specific paperwork (FCI, POL certificates, sampling) | IR practice | not modelled (one admin chain for all) | OUT → stress-tested (O2) |
| 17 | Traffic growth | supervisor (scaling ask) | arrival-gap range (Layer 5) | stress-tested (O3); full scaling study pending |
| 18 | Weather, monsoon, labour absenteeism | TERI | not modelled | OUT → stress-tested (O4) |
| 19 | Higher error / rejection rates | — | rework probabilities (ASSUMED) | stress-tested (O5) |
| 20 | Contracts, monthly demurrage pooling, waivers | MoR Compendium | not modelled | OUT: these change the bill, not the time (pricing levers move detention by 0 h, Layer 5) |
| 21 | Rake–line length mismatch, split placement | IR practice | not modelled (full-rake line assumed) | OUT: acts like factor 15 (extra time inside free time) |
| 22 | Signalling delay | supervisor | outside the terminal (loaded haul only) | OUT by scope |
| 23 | Wagon condition / life cycle | supervisor ask (8–9 Oct) | wagon *type* per commodity from field data; condition not modelled | OUT (separate study) |

---

## 3. Evidence that the set is sufficient

**(a) Complete by construction.** Every hour between placement and release falls in exactly
one modelled interval: a waiting gate, M4, loading, M5 or M6 (`rtsim/eventlog.py`,
`RAKE_EVENT_ORDER`). Attribution therefore sums to 100 % (terminal 73.5 / client 23.7 /
railway 2.9 %, `results/layer1_attribution.csv`). An omitted factor cannot hide in an
unaccounted interval. It can only make one of the modelled intervals longer, which is exactly
what the stress test in (d) does.

**(b) Agrees with facts it was not tuned to.**
- Arrivals: the field data show Poisson arrivals at the 15 largest sidings (dispersion index
  0.7–1.7), as the model assumes.
- Charges: the field data match the model's charge rules exactly (terminal charge ₹20/t on
  99,818 RRs; busy-season charge 15 %; coal exempt).
- The TERI 14–17 h detention band is a calibration target. It was tuned to, so it is weak
  evidence and is reported as such.

**(c) Screening.** Morris screening of all 39 parameters (`results/layer5_S3_morris.csv`) puts
most of the effect in a handful of factors: terminal working hours, M6 release reporting,
loading rate and M5 weighment. Most of the remaining parameters move detention by less than
0.5 h. More detail of the kind already included would not change the ranking.

**(d) Stress test with the omitted factors (Layer 7).** See §4.

---

## 4. Layer 7 stress test — results

`experiments/run_layer7_sufficiency.py` → `results/layer7_*.csv`, `layer7_results.png`.

**Method.** Each omitted factor from §2 is added at a realistic size, through an existing
mechanism. It is applied *after* the intervention, so no intervention can remove it. The six
E12 interventions are then re-ranked on the calibrated base: 50 rakes, 30 paired replications,
the same random numbers.

| Omitted factor added | Base detention | Ranking vs model as built (Kendall τ) | Top 3 unchanged | Best procedural / best capital (h saved) | 2nd line alone |
|---|---|---|---|---|---|
| none (model as built) | 15.53 h | 1.00 | yes | 8.55 / 1.94 | −0.39 h |
| O1 +1 h physical delay in free time | 17.00 h | 1.00 | yes | 8.94 / 1.86 | −0.83 h |
| O1 +3 h | 19.99 h | 1.00 | yes | 9.76 / 1.83 | −0.81 h |
| O2 +1 h unmodelled paperwork (M4) | 17.24 h | 1.00 | yes | 9.25 / 1.97 | −0.41 h |
| O2 +3 h | 20.68 h | 1.00 | yes | 10.69 / 1.97 | −0.16 h |
| O3 +50 % traffic | 15.87 h | 1.00 | yes | 8.88 / 1.90 | −0.51 h |
| O4 loading disruptions (rate −20 %, variability ×2) | 18.49 h | 1.00 | yes | 8.93 / 2.51 | −0.78 h |
| O5 error rates ×2 | 17.39 h | 1.00 | yes | 10.41 / 2.00 | −0.42 h |
| O6 O1 + O2 (+1 h each), O4, O5 together | 23.07 h | 1.00 | yes | 10.74 / 1.63 | −0.88 h |

**Verdict.**
- The omitted factors change the *level* of detention (15.5 → 23.1 h).
- They do **not** change the *conclusions*. In all 9 cases:
  - the order of the six interventions is identical (τ = 1.00);
  - digitalising all paperwork stays first;
  - procedure beats capital by 3.6–6.6×;
  - a second line without a crew stays counter-productive.
- The omitted factors make the procedural levers look *better*, not worse: they add waiting
  that the office calendars amplify.
- So the variable set is sufficient for the thesis's purpose, which is ranking interventions.
  It is not sufficient for predicting absolute hours at a named siding; that needs the time logs.

---

## 5. What is still open

Sufficiency against reality can only be fully confirmed with placement–release time logs
(requested from the PhD students). Compare the simulated and observed detention
distributions: the residual is the joint effect of everything left out. Until then, claims are
rankings and directions, never absolute hours.
