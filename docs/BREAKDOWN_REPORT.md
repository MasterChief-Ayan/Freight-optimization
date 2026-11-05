# BREAKDOWN REPORT — where the hours and the rupees come from (Layer 8)

Supervisor's three points (4-Nov-2026):
1. **Breakdown.** Show how every saving arises, not only the final figure.
2. **Wagon damage.** What a damaged wagon does to the rake, the time and the money.
3. **Engine (locomotive).** Types, origins and capacities of locos.

Code: `experiments/run_layer8_breakdown.py`, `rtsim/damage.py`. Results: `results/layer8_B0…B8*.csv`,
`results/prof/Fig8–Fig10`. Checks: 100/100 (70 model + 30 extension).

---

## 1. Set-up (what was simulated, and how numbers are converted)

**Base: coal in open BOXN wagons, the dominant real case.**
- 58 wagons and 3,898 t per rake, overloading 30 %, private-siding share and freight per tonne all
  come from the ER RR register. Free time is 5 + 2 + 1 = 8 h [IR Compendium 2.2, 2.2.1, 2.7].
- Run size: 50 rakes × 30 paired replications, FCFS dispatch, full paperwork chain M1–M7.
- Traffic is one rake per 30 h on average, i.e. **292 rakes a year**.

**Levers** (the same as in the 2-Nov note):

| Code | Lever | Note |
|---|---|---|
| H | terminal paperwork 24/7 (M4, M5, M6) | |
| D | digital release reporting (M6) | |
| P | precise loading (no overload) | |
| L | 50 % faster loading | |
| Y | yard clutter | scenario |

Packages: **TODAY**; **A = H + D** (no construction); **B = A + P**; **C = B + L**.

**Conversions.** Every rupee can be traced through these:

| Quantity | Formula |
|---|---|
| per year | per-rake value × 292 rakes |
| demurrage | hours beyond 8 h × 58 wagons × graded IR rate: ₹150 / 165 / 187.5 / 225 / 300 / 450 per wagon-hour in bands 0–6 / 6–12 / 12–24 / 24–48 / 48–72 / > 72 h [IR-COMP 3.1] |
| data leak per rake | overload incidence × punitive charge + unused paid tonnes × freight per tonne (ER register medians) = **₹143,914 per coal BOXN rake** |
| wagons freed | rake-hours saved per rake × 58 wagons × 292 ÷ 8,760 h |
| fleet value | wagons freed × ₹44.1 lakh (₹1,140 crore ÷ 2,583 BOXNHL/BOXNS wagons, MoR order, Oct 2026) |
| line capacity | 8,760 h ÷ hours a rake holds the line (placement start → removal). A theoretical ceiling. |

---

## 2. Breakdown of TIME

### 2.1 A rake's whole stay, arrival → departure (h per rake, `layer8_B1`)

| Segment | Inside IR free-time window? | TODAY | A | B | C |
|---|---|---|---|---|---|
| Waiting before placement (queue for the line) | no | 37.43 | 20.23 | 19.37 | 17.93 |
| Placement shunting | no | 0.99 | 0.99 | 0.99 | 0.99 |
| Placed → loading starts (M4 advice, M2, crew) | **yes** | 1.35 | 0.55 | 0.55 | 0.55 |
| Loading | **yes** | 4.69 | 4.69 | 4.69 | 3.13 |
| Loading ends → released (M5 weighment, M6 release) | **yes** | 10.97 | 4.26 | 3.57 | 3.57 |
| Removal shunting | no | 1.00 | 1.00 | 1.00 | 1.00 |
| Removed → departs (M7: RR + payment) | no | 14.05 | 19.40 | 20.12 | 18.85 |
| **Detention (billed window)** | | **17.02** | **9.50** | **8.82** | **7.25** |
| **Arrival → departure** | | **70.50** | **51.12** | **50.30** | **46.02** |
| Line held per rake | | 19.01 | 11.50 | 10.81 | 9.25 |
| Rakes over free time | | 90 % | 67 % | 59 % | 28 % |

Reading:
- The billed window is only a quarter of a rake's stay. The largest single block is the
  queue *before* placement, which is not billed but ties up the Railway's wagons.
- That queue is long *because* each rake holds the line ~19 h. So shortening the billed window
  also shortens everyone's queue: 37.4 → 17.9 h.

### 2.2 Why the billed window is that long (h per rake, `layer8_B2`, Fig. 8)

Method: three counterfactual runs (office hours removed; rework removed; both). The split is
exact, i.e. the parts add up to the detention.

| Package | Detention | Loading (physical) | Paperwork working time | Rework | Waiting for the office to open |
|---|---|---|---|---|---|
| TODAY | 17.02 | 4.69 | 5.87 | 1.08 | **5.38** |
| A | 9.50 | 4.69 | 4.08 | 0.71 | 0.02 |
| B | 8.82 | 4.69 | 4.08 | 0.02 | 0.02 |
| C | 7.25 | 3.13 | 4.08 | 0.02 | 0.02 |

Reading:
- **Today, 6.5 of 17.0 h (38 %) are not productive work:** 5.4 h of waiting for the office to
  open, plus 1.1 h of redoing rejected paperwork.
- Package A removes the office wait completely and makes release reporting faster.
- Precise loading removes the remaining rework (no overloading means no re-weighment).
- Faster loading then cuts the physical part.

---

## 3. Breakdown of MONEY

### 3.1 Demurrage per rake by IR band (₹, `layer8_B3`)

| Band (hours beyond free time) | TODAY | A | B | C |
|---|---|---|---|---|
| 0–6 h (₹150/wagon-h) | 40,613 | 17,503 | 13,282 | 5,819 |
| 6–12 h (₹165) | 32,262 | 1,900 | 737 | 298 |
| 12–24 h (₹187.5) | 15,153 | 209 | 137 | 129 |
| 24–48 h (₹225) | 1,759 | 39 | 39 | 19 |
| **Total per rake** | **89,786** | **19,651** | **14,195** | **6,265** |

**How each rake's demurrage is computed (intermediate step).** Rake by rake:
1. excess = detention − 8 h free time;
2. part-hours are charged as full hours (model setting `demurrage_part_hour_rounding`);
3. each band's hours × that band's rate × 58 wagons;
4. the sum is that rake's demurrage; the table shows the average over rakes.

Worked example for one rake at the average detention of 17.02 h:
- excess 9.02 h → 10 charged hours;
- 6 h × ₹150 + 4 h × ₹165 = ₹1,560 per wagon;
- × 58 wagons = **₹90,480**.

This is close to, but not equal to, the table's ₹89,786. The table averages each rake's own
charge, and rakes differ.

**Why money falls faster than time.** Package A cuts detention by 44 % but demurrage by 78 %. Two
reasons:
- every hour removed lies *above* the 8 h free time;
- the most expensive bands (6 h and beyond, ₹165–225) empty first.

### 3.2 Cost to the client per rake, and per year (292 rakes)

| | TODAY | A | B | C |
|---|---|---|---|---|
| Demurrage per rake | ₹89,786 | ₹19,651 | ₹14,195 | ₹6,265 |
| Data leak per rake = overload penalty ₹949 + paid-unused capacity ₹142,965 | ₹143,914 | ₹143,914 | 0 | 0 |
| **Client's avoidable cost per rake** | **₹233,701** | ₹163,566 | ₹14,195 | ₹6,265 |
| Demurrage avoided per year | — | ₹2.05 crore | ₹2.21 crore | ₹2.44 crore |
| Penalties + paid-unused capacity avoided per year | — | 0 | **₹4.20 crore** | **₹4.20 crore** |

**How the data leak is built, and how to read it.** Inputs are ER-register values for coal BOXN
full rakes (Layer 6 profile).

- **Overload penalty: ₹949 per rake** = 30.4 % overload incidence × ₹3,117 median punitive charge
  per overloaded consignment.
  - *This is conservative.* In the register, 44 % of coal full rakes pay some punitive charge, and
    the mean is ₹28,125 per penalised rake (median ₹3,896; skewed).
  - That gives an average of **₹12,393 per coal full rake**, about 13× the model's ₹949, or
    **≈ ₹36 lakh a year** at 292 rakes.
- **Paid-but-unused capacity: ₹142,965 per rake** = 158.9 t × ₹899.7 per tonne (medians).
  - This is freight already paid for capacity left empty, not a cash penalty.
  - Precise, weigh-controlled loading turns it into **~159 t more coal per rake for the same
    freight bill**. That is ₹4.2 crore a year of carrying value, *assuming* wagons can be filled
    to the permissible limit.
  - Read it as a capacity gain, not as cash saved.

### 3.3 Fair split of the saving between levers (Shapley, `layer8_B4`, Fig. 9)

The levers overlap: some fix the same delay, so their savings cannot be added. The Shapley
value gives each lever its average marginal saving over every order in which the levers could
be introduced, and the shares add up exactly to the package's saving.

| Package C | Saving if done alone | Fair share of the 9.77 h | Fair share of the ₹83,521 demurrage saved per rake |
|---|---|---|---|
| Terminal paperwork 24/7 | 5.35 h | **3.66 h (37 %)** | ₹33,613 (40 %) |
| Digital release reporting | 4.59 h | **3.30 h (34 %)** | ₹28,265 (34 %) |
| Loading 50 % faster | 2.39 h | **1.89 h (19 %)** | ₹13,955 (17 %) |
| Precise loading | 1.18 h | **0.91 h (9 %)** | ₹7,689 (9 %) |
| Sum | 13.51 h | **9.77 h** | ₹83,521 |

### 3.4 Who gains what, per siding per year (`layer8_B6`, `layer8_B8`)

**Client / siding owner:**
- demurrage avoided: ₹2.05 crore (A) to ₹2.44 crore (C);
- penalties and paid-unused capacity avoided: ₹4.20 crore (B, C);
- line capacity: 461 → 762 (A) → 947 (C) rakes a year ceiling (×1.65 to ×2.06), with no new line.

**Railway: how the wagon figure is built.** Arrival → departure per rake, with RR + payment
electronic (`layer8_B8`):

| | TODAY | A | B | C |
|---|---|---|---|---|
| Arrival → departure | 56.50 h | 31.87 h | 30.37 h | 27.35 h |
| Rake-hours saved | — | 24.64 h | 26.13 h | 29.15 h |
| Wagons freed = saved h × 58 × 292 ÷ 8,760 | — | 47.6 | 50.5 | 56.4 |
| Fleet value at ₹44.1 lakh per wagon | — | ₹21.0 crore | ₹22.3 crore | ₹24.9 crore |

The equivalent rows with RR waiting for office hours start from §2.1 (70.50 → 51.12 / 50.30 /
46.02 h).

- wagon time back, with RR + payment electronic, as the ER data show for coal (eT-RR 99.7 %,
  e-payment 87 %, on-account 13 %): **47.6 wagons (₹21.0 crore of fleet) with A, 56.4 wagons
  (₹24.9 crore) with C**;
- if RR issue instead waited for office hours (the model's M7 assumption), the same packages give
  37.5–47.3 wagons (₹16.5–20.9 crore), because rakes then wait longer at the station for the RR;
- demurrage income forgone: −₹2.05 to −₹2.44 crore a year. This is a transfer from client to
  Railway, not a loss to the economy, so it is never added to wagon value.

---

## 4. Relations: what the breakdown shows that single results could not

1. **Savings overlap.** Alone the levers promise 13.5 h; together they deliver 9.8 h. Plans must
   be built from simulated packages (§3.3).
2. **Money falls faster than time,** because of the free-time threshold and the graded bands (§3.1).
3. **The billed window drives the unbilled queue.** Cutting 7.5 h from detention cuts the
   pre-placement wait by 17.2 h (§2.1). This is the "virtual second line": capacity ×1.65–2.06.
4. **The bottleneck moves.**
   - office hours → paperwork working time → loading speed (§2.2);
   - after the siding is fixed, RR + payment (M7) decides when the rake actually leaves (§3.4).
     In reality this is largely solved for coal (eT-RR 99.7 %).
5. **Yard clutter (scenario: loading 20 % slower).**
   - It adds +1.48 h per rake today (+8.7 %, +₹14,233 demurrage);
   - +1.17 h after package A, a *larger share* (+12.3 %);
   - +0.78 h after C (+10.8 %).
   - Source: `layer8_B5_factorial.csv`.
6. **Batch clearance is the common root.** Office calendars (daily batches), shift-paid gangs and
   monthly scrap auctions all create idle occupancy (2-Nov direction note).

---

## 5. Wagon damage (`rtsim/damage.py`, `layer8_B7`, Fig. 10)

### 5.1 Rules and facts used

| Fact | Source |
|---|---|
| Wagons with rejectable defects are marked sick; the usual practice is to detach them and attach a fit wagon | IRIMEE, Freight train examination |
| A sizeable number of wagons are found unloadable at examination, largely avoidable with action against private sidings that mishandle wagons; repairs delayed in 86 % of wagons sent to sick lines | CAG Report No. 31 of 2014, ch. 10 |
| The unfit/sick-wagon free-time allowance (12 h) exists **only for the seven old steel plants**; elsewhere the time stays inside the free-time window | IR Compendium 2.3(b) |
| Demurrage applies to the **whole group** even if one wagon is detained | IR Compendium 2.1.2 |
| ~10,000 coal wagons were damaged in Jan 2022, mostly by JCB unloading; repairs cost ₹5–10 lakh per wagon | Orissa Post, 2-May-2022 |

**No published rate of damage per wagon at loading sidings exists.** All probabilities and
durations are scenario inputs (ASSUMED).

### 5.2 Model (optional module; off by default, so all earlier results are unchanged)

The empty rake is examined after placement. Each wagon is defective with probability p:
- 60 % of defects are **minor** (no effect);
- 30 % are **repairable at the siding** (≈ 1.5 h per wagon, one gang), done in parallel with the
  placement paperwork (M4);
- 10 % are **unfit**. Two policies:
  - **detach** them (loco, ≈ 1.5 h, inside the billed window) and load the rest;
  - **send the whole rake back** (outside the billed window). The line is freed and a
    replacement arrives after ≈ 24 h.

Separately, wagons damaged by loading equipment are repaired before release, in parallel with
weighment and release reporting (M5, M6).

### 5.3 Results: TODAY, change against the same package without damage

| Defective wagons | Policy | Extra detention (billed) | Extra waiting | Extra arrival → departure | Extra demurrage per year | Wagons tied up |
|---|---|---|---|---|---|---|
| 0.5 % | detach | +0.11 h | +0.49 h | +0.47 h | ₹2.8 lakh | 0.9 |
| 0.5 % | return rake | +0.09 h | +1.39 h | +1.24 h | ₹2.5 lakh | 2.4 |
| 1 % | detach | +0.28 h | +1.04 h | +1.13 h | ₹7.7 lakh | 2.2 |
| 1 % | return rake (6 % of rakes rejected) | +0.17 h | +3.11 h | +2.99 h | ₹4.7 lakh | 5.8 |
| 2 % | detach | +0.58 h | +2.12 h | +2.57 h | ₹16.1 lakh | 5.0 |
| 2 % | return rake (12 % rejected) | +0.41 h | +5.98 h | +5.99 h | ₹11.1 lakh | 11.6 |

**Verdicts:**
- **Sending the whole rake back costs the Railway 2.3–2.6× more wagon time than detaching the bad
  wagon.** The client's demurrage barely moves, because the rejected visit is outside the free-time
  clock.
  - So the "return the rake" practice the supervisor described is the expensive one.
  - Detaching at the siding, which needs a short spur or sick line and a C&W gang, is the
    better rule.
- **Detaching** puts the delay inside the billed window, so the client pays slightly more
  demurrage. It also loses about 4.3 t of coal per rake at 1 % (one wagon left out).
- **After package C** the same damage costs less (at 1 %: 1.3 wagons with detach, 4.3 with
  return), because the siding recovers faster.
- **Loading damage** costs about 0 h today: its repair is hidden behind slow weighment and release
  paperwork. It starts to cost time (+0.02 h at 1 %) only once the paperwork is fixed. This is the
  same "bottleneck moves" relation.
- The cost of repairing damaged wagons themselves (₹5–10 lakh per severely damaged wagon) is not
  added here, because it depends on how severe the damage is.

---

## 6. Engine (locomotive): assessment

**What the model already has:**
- shunting locos as a resource, needed for placement, removal and detaching;
- placement and removal times as distributions.

**Results already on record:**
- a second loco changes detention by 0 h (E12, Layer 5 S2);
- placement time over its range moves detention by 0.68 h (Layer 5 S1);
- by the IR definition, placement happens *before* the free-time clock starts and removal
  *after* it stops. So loco delays fall **outside the billed window**: they lengthen the queue,
  the wagons' stay and line occupancy, not demurrage.

**What the supervisor raised:**
- diesel vs electric (an electric loco cannot work a non-electrified siding, so a diesel shunter
  is needed);
- where the loco comes from (availability lag);
- loco capacity (haulage; a line-haul matter, not a siding one).

**Feasible light version** (same safe pattern as damage; off by default):
- a "loco availability lag" before placement and before removal;
- a traction mix (share of rakes needing a diesel shunter) adding an extra lag.

The removal lag matters most: it keeps a *released* rake on the line, so it cuts line capacity
without appearing in demurrage.

**Data:** the RR register has no loco information, so the lags would be pure scenarios until
siding time logs arrive.

**Recommendation:** leave the engine for now, as you suggested. If the supervisor wants it,
build the light version above; it is a contained change in the same pattern as the damage module. The billed-window results will not change by
definition; only queue, wagon time and capacity will.

---

## 7. Verification and safety

- Repo checkpoint before any change: `main` at `a3fe0df`, plus a result snapshot. Work on branch
  `feat/breakdown-damage`.
- Damage module off: Layer 0–1 outputs byte-identical. Switched on with p = 0: identical
  (checks 1–2 of `verify_damage`).
- The full pipeline was re-run and compared with the snapshot (`tools/compare_outputs.py`); the
  outcome is recorded in `docs/PROJECT_STORY.md` §6I.
- Layer 8 reproduces the 2-Nov pilot to < 0.0001 h and ₹.
- Exact-sum checks: billed hours split, demurrage bands, Shapley shares.
- **100/100 checks pass.**

## 8. Limits (state these with every number)

- Paperwork durations (M1–M7) and rejection rates are ASSUMED. Rupee figures are orders of
  magnitude; rankings and relations are the robust part (Layer 7: ranking stable in 9/9 stress
  tests).
- Damage rates, repair, detach and replacement times are ASSUMED scenarios.
- Line capacity is a theoretical ceiling.
- The model's M7 assumption (RR on office hours) conflicts with the ER data (eT-RR 99.7 %).
  - It does not affect detention or demurrage.
  - It does affect arrival → departure, wagon time and Layer 1 attribution ("client 23.7 %").
  - Recalibrating M7 is listed as pending (PROJECT_STORY §8).

---

## 9. Traceability: every number in the 2-Nov email, and where it comes from

| Email statement | Value | How it is obtained | Source |
|---|---|---|---|
| Detention today → A → C | 17.0 → 9.5 → 7.3 h (−44 %, −57 %) | simulated mean, coal BOXN, 30 reps × 50 rakes | §2.1; `layer8_B1` |
| Demurrage per rake today → A → C | ₹89,800 → ₹19,700 → ₹6,300 (−78 %, −93 %) | rake by rake (§3.1), averaged | §3.1; `layer8_B3` |
| Demurrage avoided per year | ₹2.05 / ₹2.44 crore | (₹89,786 − ₹19,651) × 292 = ₹2.05 cr; (₹89,786 − ₹6,265) × 292 = ₹2.44 cr | §3.2 |
| Line capacity | +65 % (A), ×2 (C) | 8,760 ÷ line-held hours: 8,760/19.01 = 461 → 8,760/11.50 = 762 → 8,760/9.25 = 947 rakes/yr | §2.1, §3.4 |
| Wagons freed (fleet value) | 48 / 57 wagons (₹21 / ₹25 crore) | §3.4 table, RR + payment electronic as the data show | §3.4; `layer8_B8` |
| Line held ~19 h vs ~6–7 h physical work | 19.01 h vs 0.99 + 4.69 + 1.00 = 6.68 h | placement + loading + removal | §2.1 |
| "Office hours cause ~73 % of all waiting" | 73.3 % | **different measure:** E11 decomposition of total *waiting* in the base model (25 rakes, arrival every 22 h), not of the coal billed window. In the coal billed window, office waiting is 5.4 of 17.0 h (32 %). | `layer3_E11_decomposition.csv` |
| Savings don't add up | 13.5 h alone vs 9.8 h together | four single-lever runs vs package C | §3.3; `layer8_B4` |
| Yard clutter share 8.7 % → 12.3 % | +1.48 h today, +1.17 h after A | factorial, Y on/off | §4; `layer8_B5` |
| A second line alone doesn't reduce detention | −0.28 h (E12), −0.39 h (Layer 7) | earlier experiments | `layer4_E12_interventions.csv`, `layer7_O1_sufficiency.csv` |
| Scrap: 10–50 days to pay, 40–50 (+15) days to lift; ₹6,814 crore scrap sales FY26 | — | cited documents | 2-Nov direction note (project) |
| Coal 17,200 rakes/yr (62 Mt), 5.6× iron ore; penalties ₹24 crore/yr (coal), ₹14 crore/yr (iron ore); 160 t unused per rake | — | ER register, full rakes arriving in ER, 4.66 years | `tools/rr_register.py`; PROJECT_STORY §6C |
| Copper not among the 16 groups (97 % of tonnage) | — | ER register | `results/field/F1_commodity_profiles.csv` |
| Wagon value ₹44 lakh | ₹1,140 crore ÷ 2,583 | MoR order, Oct 2026 | ThePrint, 29-Oct-2026 |

---

## 10. NOT included in any number above (and stated as such)

| Not included | Effect on the numbers | Status |
|---|---|---|
| **Cost of implementing the packages** (24/7 staff, digital release system, weigh-controlled loading, extra labour or loaders) | All savings are **gross**. Net benefit = saving − these costs. | Next step (payback; R4). Labour vs demurrage is covered separately (Layer 6 C5). |
| Repair cost of damaged wagons | Damage effects are counted only as time, demurrage and wagon time | Only a cited range for severe damage (₹5–10 lakh per wagon) exists |
| Damage rates by wagon type and material | Damage modelled for coal BOXN only; rates ASSUMED | Needs siding damage or sick-marking records |
| Engines (types, origin, capacity) | Outside the billed window by definition | Assessed; light version ready (§6) |
| RR + payment (M7) on office hours | The model's base assumption conflicts with the data | Both bases reported (§3.4); recalibration pending |
| Overload penalty at its mean | Model uses the median-based ₹949 per rake; the data mean is ₹12,393 | Conservative (§3.2) |
| Paperwork step durations from real logs | Rupee figures are orders of magnitude | Time logs requested |
| Demurrage pooling, waivers, monthly settlement | Not modelled; they change the bill, not the time | Out of scope |
| Discounting / inflation | All values in 2026 rupees, per year, undiscounted | — |
| Traffic other than one rake per 30 h | Per-year values scale with traffic; the queue grows faster than linearly | Scaling study pending (R5) |
