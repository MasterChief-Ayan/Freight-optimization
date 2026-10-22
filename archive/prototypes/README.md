# archive/prototypes — Phase-1 siding models (superseded)

Kept for the record of how the project started (PROJECT_STORY §1.3). **Not used by
`rtsim/` or any experiment.** All rates in them are assumed, and several are wrong by later
standards (65 t/wagon, flat demurrage, 7 h free time).

| File | What it adds | Notes |
|---|---|---|
| `siding_sim.py` | v1: one siding, 30 rakes, FCFS vs SPT, profit per rake | single seed; flat ₹150/wagon/h; 7 h free time |
| `siding_sim_v2.py` | v2: distribution objects, profit-aware dispatch, 50 replications with 95% CI, paired test, warm-up cut | first statistically defensible comparison |
| `siding_sim_v3.py` | v3: OPTIMAL policy with an OR-Tools CP-SAT offline optimum as the ceiling | FCFS profit ₹128.79 M vs OPTIMAL ₹129.18 M; mean wait 33.8 → 28.6 h |

Each runs standalone (`python siding_sim_v3.py`) and writes its CSV/PNG next to itself.
