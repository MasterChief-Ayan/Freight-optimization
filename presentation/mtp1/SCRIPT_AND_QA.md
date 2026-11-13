# MTP-1 presentation: script, Q&A bank and plain-language explanations

Verified on 13-Nov-2026 against the 15 slides, the report and `results/`. Numbers are means of the
simulation; paperwork times are ASSUMED, so rupee and hour figures are directions and sizes.

## A. Speaking script (8 minutes, slides 1-13)
| Slide | Keywords | What to say |
|---|---|---|
| 1 Title (15 s) | paperwork, not machines | "A rake that can be loaded in 5 hours stands for 15. Where do the other 10 hours go?" |
| 2 Problem (40 s) | 14-17 h · <=5 h · 80-85 % · who pays | TERI: 14-17 h detention; loading <=5 h (about 1 h with rapid loading); client pays demurrage, Railway loses wagon time, terminal loses line capacity. Analogy: hospital bed blocked by discharge papers. |
| 3 Question (25 s) | time · cost · capacity | Which constraints hold a rake, by how much, which levers release it; measured as detention, demurrage, rakes a year. |
| 4 Before/after mid-term (45 s) | L0-4 -> L5-9 · 57 -> 107 checks | Before: physical chain, M1-M8 paperwork with office hours and rework, road side, dispatch + CP-SAT bound, nine interventions. After (as asked at mid-term): every factor (39 parameters), ten commodities (220,395 records), stress tests, hours/rupees/who gains, capacity. |
| 5 Model (40 s) | billed window · gates · calendars · rework | Arrive, queue, place, load, weigh, release, remove, depart; billed from placement to release (8 h free, then graded); each step waits for a document, each document for an office that opens and closes and may reject it (max 5 tries per step). |
| 6 Anchors (35 s) | Compendium · 220,395 · 107 checks · 15.5 h | Rules from MoR Compendium; data from 220,395 ER railway receipts (coal 61 % of tonnes, hence coal base case); model 15.5 h inside TERI 14-17 h; physical work only 4.05 h; the 11.5 h gap is paperwork. |
| 7 78 % (35 s) | 78 / 8 / 14 | 78 % of waiting is office hours + rejected documents; best possible order recovers <=8 %; 14 % congestion. Analogy: reordering a bank queue does not help if the counter is closed. |
| 8 Procedure vs capital (35 s) | 15.5x · 8.98 vs 0.58 h | Digitalising paperwork saves 8.98 h/rake (16.1 -> 7.1 h); 2nd line + crew 0.58 h. Each of the THREE paperwork levers beats every capital lever (not "no rework", 1.40 h < faster loading 2.08 h). 2nd loco saves 0. |
| 9 Terminal hours (35 s) | 21 h · 16->18 h = 43 % | Day length of terminal desks M4-M6 (today 16 h): 8 h -> 31.9 h detention, 16 h -> 15.5, 18 h -> 13.5, 24 h -> 10.7. Swing 21.2 h = 31.9 - 10.7; round-the-clock gain 4.8 h; 16->18 h gives 2.1 h = 43 % of it. Morris screening confirms the same top three. |
| 10 Money (35 s) | -44 % time · -78 % money · Rs 2.05 cr | Package A: 17.0 -> 9.5 h but demurrage -78 %, Rs 2.05 cr/yr (demurrage only). Why: the first 8 h are free, so almost every hour saved is a billed hour (billed h 9.6 -> 2.2, -77 %); graded bands add ~1 point. |
| 11 Capacity (45 s) | 292 -> 556 · 710 · 1,262 | "35 h is today's average wait before placement." At that wait: A 556 (+90 %), 2nd line + crew 710, both 1,262 (x4.3). Line is the bottleneck; crew <=34 %, loco <=29 % busy. Procedure for speed, 2nd line for growth. Analogy: one parking bay. |
| 12 Robust + limits (35 s) | 10/10 · 8/8 tau = 1 · 0.91-1.03 | Same levers help all ten commodities; in eight stress tests detention changes but ranking does not (Kendall tau = 1); queue matches theory; limits: calibrated not validated, gross savings, one siding. |
| 13 Conclusion (35 s) | paperwork first, capital second | Close: "Rakes don't wait for machines; they wait for offices." |

## B. Q&A bank (most likely questions)
1. **Where did the constraints come from?** 23 candidates (TERI, IR compendium, dwell-time literature, supervisor) through 4 filters F1 relevance (acts on billed time), F2 evidence (named in literature/rules), F3 control (a party can change it), F4 measurability (Tables 2.2-2.3): 13 in, 1 partial, 5 left out and stress-tested, 4 out of scope.
2. **Are the variables sufficient?** Layer 7: 8 stress tests add left-out factors (+1/+3 h physical delay, +1/+3 h extra paperwork, +50 % traffic, loading disruptions, error rates x2, all together); detention 15.5 -> up to 23.1 h, ranking of 6 interventions unchanged, Kendall tau = 1.00 in all 8 (`results/layer7_O2_rank_stability.csv`, Table 3.8).
3. **Individual effect of each parameter (mid-term ask)?** Layer 5: 39 parameters low -> high (Fig 3.2); terminal hours 21.2 h, M6 release reporting 6.6 h, loading rate 6.6 h, M5 weighment 3.6 h; all operational factors together about 13 h; Morris screening agrees.
4. **How was the model tested?** 107 automated checks (70 model + 37 extensions): every rake leaves, line never double-booked, demurrage reproduces the IR table, Little's law within 5 %, a layer switched off reproduces the layer below exactly, same seed gives identical output, CP-SAT bound never beaten; paired runs on common random numbers; PK queue check.
5. **Validated?** Calibrated (15.5 h inside TERI 14-17 h), not validated: siding time logs requested from the PhD student (Ranit Senapati); Part II.
6. **Assumed paperwork times?** Ranking survives the Layer 5 ranges and all 8 stress tests; the top factor (terminal hours 06-22) is cited from the Compendium.
7. **Why simulation?** Office calendars, rework and the graded tariff prevent a closed form; CP-SAT gives a bound and Pollaczek-Khinchine a check.
8. **78/8/14?** Layer 3 exact split (12 reps x 25 rakes): remove calendars + rework -> admin; CP-SAT best order -> sequencing; rest congestion.
9. **Why a 2nd line does not cut detention?** Detention is billed placement -> release; a 2nd line shortens the queue before placement, not the paperwork inside; it doubles capacity.
10. **15.5x for all capital options?** No: vs 2nd line + crew. Vs the best capital lever (50 % faster loading, 2.08 h) the best paperwork lever saves 4.3x more.
11. **Capacity definition?** Same-service capacity = most rakes/yr with mean wait <= today's 35 h (interpolated from a traffic sweep); ceiling = lines x 8,760 / line hold.
12. **Rs 2 cr is the Railway's loss?** It is a transfer; the Railway gains about 48 wagons a year (about Rs 21 cr fleet value) and more rakes through the siding.
13. **Cost of package A?** No construction (shifts + electronic release; coal already uses e-RR 99.7 %); cost and payback are Part II.
14. **Why coal, one siding?** Coal is 61 % of ER tonnes; 10 commodities in Layer 6; capacity for others is Part II.
15. **Wagon damage?** Optional scenario with assumed rates; detach bad wagons; returning the rake costs the Railway 2.3-2.6x the wagon time.
16. **Novelty?** IR-rule-exact siding model with office calendars as gates; exact cause split; every factor's bounded effect; every hour/rupee/capacity traced to a lever and a party (Shapley); capacity at today's service level; office hours bunch arrivals (PK check).
17. **Busy test case utilisation?** About 0.8 (17.9 h hold / 22 h gap); the report's "0.7" is an erratum.
18. **Part II?** Validate on time logs; implementation cost and payback; capacity for other commodities and staged expansion; M7 recalibration to e-RR; damage and locomotive detail; tighter bound.

## C. Plain-language explanations (asked 12-13 Nov)
- **39 parameters (Layer 5):** 9 operational (arrival gap, loading rate and its spread, placement, removal, wagons per rake, payload, transit, late chance), 24 paperwork (M1-M7 mean, spread, rejection = 21, plus terminal day, terminal office, railway office hours), 6 commercial (free time, penal multiplier, demurrage rate, engine-hour, shunting, idle cost).
- **10 commodities (Layer 6):** one commodity per rake and per run; each is a profile of the same model (wagons, payload, overload rate -> M5 rejection, siding/goods shed, free time by wagon type, tarpaulin for coal, assumed loading rate by handling method); levers tested per commodity.
- **Layer 8:** hours (where each hour goes; billed window split into loading / paperwork / rework / office wait), rupees (demurrage by band, overload and unused-capacity leak, per year, wagons freed), Shapley fair split (package A -7.52 h: terminal hours 4.14 h, digital release 3.38 h), who gains (client Rs 2.05 cr/yr, Railway about 48 wagons, terminal +264 rakes/yr).
- **Layer 9 / how 556 is obtained:** 6 set-ups x traffic 250-1,600 rakes/yr (step 50, plus 292), 200 rakes x 30 runs each; target = today's wait 35.0 h at 292; package A wait 34.3 h at 550 and 40.2 h at 600 -> 550 + (35.0-34.3)/(40.2-34.3) x 50 = 556.
- **Rework:** per document; first try + up to 4 redos = max 5 per step, 5th always accepted; steps independent (not 5^n); e.g. M3 rejected 20 % -> 5th try 0.2^4 = 0.16 %.
- **MoR Compendium:** Ministry of Railways rulebook on demurrage etc. (03.04.2024): free time 5+2+1 = 8 h, Rs 150/wagon-h graded to x3, penal up to x6, terminal hours 06-22.
- **220,395:** railway receipts (official document per consignment) in the ER inward register Jan 2022 - Aug 2026, 508.5 Mt; coal 308.7 Mt = 61 %.
- **107 checks:** automated self-tests; 70 model + 37 extensions.
- **Slide 8 items are interventions (Layer 4, before mid-term), slide 9 items are parameters (Layer 5, after).** Interventions: digitalise all paperwork (all steps 24/7, no rejections, half time); digitalise weighment + release (M5+M6 only; 7.65 h = 85 % of the full 8.98 h); terminal 24/7 (M4-M6 desks round the clock); loading 50 % faster; no rework anywhere; 2nd line + crew; 2nd loco; 2nd line alone.
- **Weighment vs release:** both gate release inside the billed window; release reporting matters more (6.6 h swing vs 3.6 h).
- **Morris screening:** second sensitivity method (20 random trajectories, one factor moved at a time); average effect and interaction; same top three.
- **Packages:** A = H (terminal desks M4-M6 24/7) + D (digital release: M6 24/7, no rejections, half time), no construction; B = A + P precise loading (load exactly to permissible weight -> no overload rework, no penalty, no unused paid capacity); C = B + L (loading 50 % faster).
- **Rs 2.05 cr:** demurrage only: (89,786 - 19,651) x 292. Separate: Rs 4.20 cr/yr leak avoided by precise loading; about 48 wagons (Rs 21 cr fleet value, one-time).
- **35 h:** today's mean wait from arrival to placement at 292 rakes/yr (Layer 9, Table 3.5); not billed.
- **x4.3 not x4:** 1,262/292 = 4.32; A alone x1.90, 2nd line alone x2.43 (two lines share one queue, so more than double at the same wait); ceilings roughly double (458 -> 928, 756 -> 1,507).
- **Bottleneck:** the line is occupied ~19 h per rake; crew works only while loading (<=34 % busy), loco only to place/remove (<=29 %); adding crew or loco alone adds nothing.
- **Kendall tau:** rank similarity (1 identical, 0 unrelated, -1 reversed); all 8 stress tests = 1.00.
- **Calibrated, not validated:** overall average matches TERI; no siding timestamps yet to check step by step.
- **0.91-1.03:** simulated queue wait / Pollaczek-Khinchine formula with offices open and line busy < 80 %; ~1 means the queue behaves as theory; with real office hours 1.04-1.96 (office hours bunch arrivals).
- **Round the clock:** 24 h a day, 7 days, for the terminal desks M4-M6 instead of 06:00-22:00.
- **Paperwork first, capital second:** fix procedure first (cheap, biggest gain); add a line with its crew only for growth beyond about 730 rakes/yr (package C).
