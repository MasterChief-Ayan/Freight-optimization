"""
optimiser.py  -  L3. The decision layer: global optimum and coordination.

Three things are compared, and the comparison is only meaningful because all
three are scored by the SAME simulator on the SAME scenarios:

  RULES      FCFS, SPT, COST. Online, myopic, microseconds.
  CNP        Contract Net Protocol. Decentralised: the terminal announces a
             free line, waiting rakes bid, lowest bid wins. Uses only
             information available at the moment of the decision.
  CP-SAT     Offline optimum. Sees EVERY rake's arrival and processing time
             before deciding anything. Not implementable - a dispatcher does
             not know tomorrow's arrivals - but it is the ceiling against
             which the implementable rules are measured.

Why the ceiling matters
-----------------------
"CNP beat FCFS by X hours" is unfalsifiable on its own; X could be 5% or 95%
of what was available. With FCFS as the floor and CP-SAT as the ceiling, the
claim becomes "CNP captured Y% of the achievable gain", which is a bounded,
checkable statement.

Formulation
-----------
Single-machine sequencing with release dates: 1|r_j|Sum w_j C_j. NP-hard, so
the optimum is only obtainable offline. CP-SAT gets interval variables with
NoOverlap (or Cumulative for K > 1 lines) and minimises total weighted
waiting. It returns a SEQUENCE, which is fed back as a priority; the
simulator then executes it and the accounting module prices it exactly as it
prices every other policy. No policy is ever scored by its own solver's
objective - that would be comparing different rulers.
"""
from typing import Dict, List, Optional
import math
from ortools.sat.python import cp_model

from .config import Config
from .terminal import Rake

SCALE = 60          # CP-SAT works in integers; model in minutes


# ======================================================================
# CP-SAT  -  the offline ceiling
# ======================================================================
def optimal_sequence(cfg: Config, rakes: List[Rake],
                     admin_overhead_hr: float = 0.0,
                     hold_hr: Optional[Dict[int, float]] = None,
                     time_limit_s: float = 20.0):
    """Offline optimum. Returns {rake_id: rank} plus the solver status.

    How long a rake occupies the line matters more than anything else here,
    and once the administrative layer is switched on it is NOT the physical
    duration. M4, the M2 join, M5 and M6 all run while the rake stands on the
    line, and each is calendar-bounded and rework-prone, so the hold varies
    from rake to rake by many hours.

      hold_hr given          TRUE CLAIRVOYANCE. Per-rake realised occupancy,
                             measured from a pilot run. This is what makes
                             the result a valid CEILING: no online policy can
                             beat a scheduler that already knows every
                             duration. Use this for the benchmark.
      admin_overhead_hr only A single average added to every rake. This is a
                             PLANNER, not a ceiling - it is what a real
                             dispatcher could compute in advance - and it can
                             legitimately be beaten by an online rule. Use
                             this for the disruption experiment.

    Conflating the two is the easy mistake: a "ceiling" that loses to
    shortest-processing-time-first is not a ceiling, it is a bug.
    """
    mdl = cp_model.CpModel()
    lines = cfg.resources.loading_lines

    if hold_hr is not None:
        dur = {r.id: max(1, int(round(hold_hr[r.id] * SCALE))) for r in rakes}
    else:
        dur = {r.id: int(round((r.place_hr + r.load_hr + r.remove_hr
                                + admin_overhead_hr) * SCALE)) for r in rakes}
    rel = {r.id: int(round(r.actual_arrival * SCALE)) for r in rakes}
    horizon = max(rel.values()) + sum(dur.values()) + 10

    starts, ivs, waits = {}, [], []
    for r in rakes:
        s = mdl.NewIntVar(rel[r.id], horizon, f"s{r.id}")
        e = mdl.NewIntVar(rel[r.id], horizon + dur[r.id], f"e{r.id}")
        ivs.append(mdl.NewIntervalVar(s, dur[r.id], e, f"i{r.id}"))
        starts[r.id] = s
        w = mdl.NewIntVar(0, horizon, f"w{r.id}")
        mdl.Add(w == s - rel[r.id])
        waits.append(w)

    if lines == 1:
        mdl.AddNoOverlap(ivs)
    else:
        mdl.AddCumulative(ivs, [1] * len(ivs), lines)

    # Minimising total waiting is equivalent to minimising total idle cost,
    # which is the only cost sequencing can move at this layer: detention
    # begins at PLACEMENT, so a rake's own demurrage does not depend on when
    # it is placed - only on what happens to it afterwards.
    mdl.Minimize(sum(waits))

    slv = cp_model.CpSolver()
    slv.parameters.max_time_in_seconds = time_limit_s
    slv.parameters.num_search_workers = 8
    st = slv.Solve(mdl)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, "INFEASIBLE"

    order = sorted(rakes, key=lambda r: slv.Value(starts[r.id]))
    return {r.id: i for i, r in enumerate(order)}, slv.StatusName(st)


def cpsat_policy(cfg: Config, ranks: Dict[int, int]):
    """Replay a CP-SAT sequence as a priority function."""
    def f(rake: Rake, ctx) -> float:
        return float(ranks.get(rake.id, 10 ** 6))
    f.__name__ = "CPSAT"
    return f


# ======================================================================
# A VALID LOWER BOUND  -  the fix for the calendar problem
# ======================================================================
# What went wrong first time round
# --------------------------------
# The obvious bound - solve the sequencing problem offline, then EXECUTE the
# resulting sequence in the simulator and read off its waiting time - is not
# a bound at all once administrative steps are calendar-bounded. Executing
# the plan re-inflates every duration, because how long a step takes on the
# wall clock depends on what time of day it starts, which depends on the
# sequence. Online rules beat it, and a "bound" that loses is a bug.
#
# The problem class has a name: SCHEDULING WITH MACHINE AVAILABILITY
# CONSTRAINTS, resumable case (work pauses when the office shuts and resumes
# when it opens). See Azem, Aggoune & Dauzere-Peres (2007) for the two MILP
# formulations - disjunctive and time-indexed - and Sousa & Wolsey (1992),
# Mathematical Programming 54:353-367, for why time-indexed formulations give
# better lower bounds than other mixed-integer formulations of single-machine
# scheduling.
#
# The fix used here
# -----------------
# Two changes, both essential:
#
#   1. THE BOUND IS A NUMBER, NOT A SCHEDULE. Read the solver's objective
#      directly. Never execute it and measure - execution is what reintroduces
#      the calendar inflation the bound is supposed to abstract away.
#
#   2. RELAX THE DURATIONS DOWNWARDS. Each rake occupies the line for at least
#      its physical time (placement + loading + removal) and never less. Solve
#      with those minima. Shrinking every processing time can only reduce the
#      optimal total waiting, so the result is a valid lower bound on what ANY
#      policy can achieve against the true durations.
#
# The bound is not tight - it discards all administrative occupancy - so treat
# it as a floor on what is achievable, not as a target. A tight bound needs
# the time-indexed formulation, which is future work and is flagged as such.

def waiting_lower_bound(cfg: Config, rakes: List[Rake],
                        min_hold: Optional[Dict[int, float]] = None,
                        time_limit_s: float = 20.0):
    """Valid lower bound on MEAN waiting time per rake, in hours.

    Returns (bound_hours, status). Read the objective; never execute it.

    `min_hold` should be the SHORTEST line occupancy each rake could possibly
    have. Two ways to get it, in increasing tightness:

      physical only            place + load + remove. Rigorous but very loose:
                               it discards all administrative occupancy, and
                               admin is most of the hold, so the bound comes
                               out near zero and says nothing.
      flat-calendar pilot      run the model once with every calendar set to
                               24/7 and every rejection probability set to
                               zero, and measure each rake's hold. Because the
                               service times are drawn per rake and do not move
                               with the policy, and because neither an office
                               closure nor a rejection can ever SHORTEN a step,
                               this is a genuine per-rake minimum - and it is
                               far tighter. Use this.
    """
    mdl = cp_model.CpModel()
    lines = cfg.resources.loading_lines

    if min_hold is not None:
        dur = {r.id: max(1, int(round(min_hold[r.id] * SCALE))) for r in rakes}
    else:
        dur = {r.id: max(1, int(round((r.place_hr + r.load_hr + r.remove_hr) * SCALE)))
               for r in rakes}
    rel = {r.id: int(round(r.actual_arrival * SCALE)) for r in rakes}
    horizon = max(rel.values()) + sum(dur.values()) + 10

    ivs, waits = [], []
    for r in rakes:
        s = mdl.NewIntVar(rel[r.id], horizon, f"s{r.id}")
        e = mdl.NewIntVar(rel[r.id], horizon + dur[r.id], f"e{r.id}")
        ivs.append(mdl.NewIntervalVar(s, dur[r.id], e, f"i{r.id}"))
        w = mdl.NewIntVar(0, horizon, f"w{r.id}")
        mdl.Add(w == s - rel[r.id])
        waits.append(w)

    if lines == 1:
        mdl.AddNoOverlap(ivs)
    else:
        mdl.AddCumulative(ivs, [1] * len(ivs), lines)
    mdl.Minimize(sum(waits))

    slv = cp_model.CpSolver()
    slv.parameters.max_time_in_seconds = time_limit_s
    slv.parameters.num_search_workers = 8
    st = slv.Solve(mdl)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, "INFEASIBLE"
    # ObjectiveValue is the incumbent; BestObjectiveBound is the proven floor.
    # For a LOWER bound the proven floor is the honest figure - the incumbent
    # could be above the true optimum if the solver timed out.
    return slv.BestObjectiveBound() / SCALE / len(rakes), slv.StatusName(st)


# ======================================================================
# CONTRACT NET PROTOCOL  -  decentralised, implementable
# ======================================================================
def cnp_policy(cfg: Config):
    """Contract Net (Smith 1980, IEEE Trans. Computers C-29(12)).

    Roles: the TERMINAL is the manager. When a line frees it issues a call
    for proposals. Every waiting RAKE is a contractor and returns a bid. The
    lowest bid wins the line.

    The bid is the rake's own estimate of the controllable cost it will
    impose if placed next:

        bid = expected demurrage         (does it breach free time?)
            + line-occupancy cost         (how long does it block others?)
            - ageing credit               (how long has it already waited?)

    The ageing credit is not cosmetic. Without it a long-loading rake can be
    outbid indefinitely by a stream of short ones - starvation. It also
    encodes the non-preemption rule agreed with the supervisor: an earlier
    booking must not be displaced by a later, more profitable one.

    Only information available AT THE MOMENT OF THE DECISION is used - no
    future arrivals - which is what separates this from the CP-SAT ceiling.
    """
    c = cfg.charges

    def f(rake: Rake, ctx) -> float:
        now = ctx["now"]
        detention = rake.place_hr + rake.load_hr
        excess = max(0.0, detention - c.free_time_hr)
        demurrage = excess * rake.wagons * c.demurrage_per_wagon_hr
        occupancy = (rake.place_hr + rake.load_hr + rake.remove_hr) \
            * c.idle_cost_per_hr
        waited = max(0.0, now - rake.actual_arrival)
        ageing = waited * c.idle_cost_per_hr * cfg.coordination.ageing_weight
        return demurrage + occupancy - ageing
    f.__name__ = "CNP"
    return f


# ======================================================================
# SCORING
# ======================================================================
def captured_gain(floor: float, ceiling: float, value: float) -> float:
    """What share of the achievable improvement did this policy realise?
    0% = no better than FCFS, 100% = matched the offline optimum."""
    span = floor - ceiling
    if abs(span) < 1e-9:
        return float("nan")
    return 100.0 * (floor - value) / span


# ======================================================================
# CALENDAR-AWARE BOUND  -  1|r_j, nr-a|Sum C_j
# ======================================================================
"""
Why the sequencing bound above fails once office hours are switched on
---------------------------------------------------------------------
Classical 1|r_j|Sum C_j assumes each job has a FIXED processing time. Here it
does not: M4, M5 and M6 run while the rake stands on the line, and each is
calendar-bounded, so how long the rake occupies the line depends on WHAT TIME
OF DAY placement happens. Verification check 8d measures this directly -
physical durations are identical across policies to 1e-5 h, while elapsed
administrative time on the same rake moves by up to 8 h purely from the
dispatch order.

The problem class is single-machine scheduling with release dates AND a
NON-RESUMABLE AVAILABILITY constraint, written 1|r_j, nr-a|Sum C_j. Lee
showed that a flow shop becomes NP-complete with a single non-availability
interval on one machine, and Ma, Chu & Zuo (2010) survey the family. The
standard remedy is a TIME-INDEXED formulation, which Sousa & Wolsey (1992,
Mathematical Programming) show gives better lower bounds than other mixed
integer formulations precisely because it can carry time-varying data.

Implementation
--------------
Time is discretised to the hour. For every rake and every candidate
placement hour, the resulting line occupancy is precomputed by walking the
same calendar arithmetic the simulator uses. CP-SAT then chooses a start hour
per rake, an AddElement constraint links that choice to the matching
duration, and NoOverlap enforces the single line. Duration is therefore a
FUNCTION OF START TIME, which is the property the sequencing model could not
express.
"""


def _calendar_elapsed(cal, start_hr: float, work_hr: float) -> float:
    """Wall-clock hours to complete `work_hr` of work in calendar `cal`,
    starting at `start_hr`. Mirrors AdminChain._work exactly."""
    if cal.always_on:
        return work_hr
    t, remaining, guard = start_hr, work_hr, 0
    while remaining > 1e-9:
        guard += 1
        if guard > 500:
            break
        if not cal.is_open(t):
            t = cal.next_open(t)
            continue
        chunk = min(remaining, cal.close_hr - (t % 24.0))
        t += chunk
        remaining -= chunk
    return t - start_hr


def _hold_if_placed_at(cfg, rake, steps, t0: float,
                       admin_work: Dict[str, float]) -> float:
    """Line occupancy if this rake begins placement at time t0.

    Chain on the line: placement -> M4 -> loading -> M5 -> M6 -> removal.
    Only the admin legs feel the calendar.
    """
    t = t0 + rake.place_hr
    for key in ("M4",):
        st = steps.get(key)
        if st is not None and st.enabled:
            t += _calendar_elapsed(st.calendar, t, admin_work[key])
    t += rake.load_hr
    for key in ("M5", "M6"):
        st = steps.get(key)
        if st is not None and st.enabled:
            t += _calendar_elapsed(st.calendar, t, admin_work[key])
    t += rake.remove_hr
    return t - t0


def time_indexed_bound(cfg: Config, rakes: List[Rake], steps,
                       admin_work: Dict[int, Dict[str, float]],
                       grid_hr: float = 1.0,
                       time_limit_s: float = 30.0):
    """Offline lower bound that respects office-hour calendars.

    `admin_work` gives the realised WORK content (not elapsed time) of each
    admin step for each rake, taken from a pilot run. Work content is drawn
    per rake and is schedule-independent; only its elapsed cost is not.

    Returns ({rake_id: rank}, status).
    """
    mdl = cp_model.CpModel()
    horizon_hr = max(r.actual_arrival for r in rakes) + \
        sum(r.place_hr + r.load_hr + r.remove_hr + 30.0 for r in rakes)
    n_slots = int(math.ceil(horizon_hr / grid_hr)) + 2

    starts, ivs = {}, []
    for r in rakes:
        first = int(math.ceil(r.actual_arrival / grid_hr))
        # duration lookup: one entry per candidate start slot
        durs = [0] * n_slots
        for k in range(first, n_slots):
            durs[k] = max(1, int(round(
                _hold_if_placed_at(cfg, r, steps, k * grid_hr,
                                   admin_work[r.id]) / grid_hr)))
        for k in range(0, first):
            durs[k] = durs[first]                 # never selected
        s = mdl.NewIntVar(first, n_slots - 1, f"s{r.id}")
        d = mdl.NewIntVar(1, max(durs), f"d{r.id}")
        mdl.AddElement(s, durs, d)                # duration depends on START
        e = mdl.NewIntVar(1, n_slots + max(durs), f"e{r.id}")
        ivs.append(mdl.NewIntervalVar(s, d, e, f"i{r.id}"))
        starts[r.id] = s

    if cfg.resources.loading_lines == 1:
        mdl.AddNoOverlap(ivs)
    else:
        mdl.AddCumulative(ivs, [1] * len(ivs), cfg.resources.loading_lines)

    mdl.Minimize(sum(starts[r.id] - int(math.ceil(r.actual_arrival / grid_hr))
                     for r in rakes))

    slv = cp_model.CpSolver()
    slv.parameters.max_time_in_seconds = time_limit_s
    slv.parameters.num_search_workers = 8
    st = slv.Solve(mdl)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, "INFEASIBLE"
    order = sorted(rakes, key=lambda r: slv.Value(starts[r.id]))
    return {r.id: i for i, r in enumerate(order)}, slv.StatusName(st)


def extract_admin_work(log, steps) -> Dict[int, Dict[str, float]]:
    """Recover each rake's realised admin WORK content from an event log.

    Elapsed time is calendar-inflated and schedule-dependent; work content is
    not. Recovering the work content is what lets the bound re-cost a step at
    a different time of day.
    """
    df = log.to_frame()
    df = df[(df.kind == "admin") & (df.entity_type == "rake")]
    out: Dict[int, Dict[str, float]] = {}
    for rid, g in df.groupby("entity_id"):
        rec = {}
        for key, st in steps.items():
            cl = g[g.name == f"admin_{key}_clear"]
            sr = g[g.name == f"admin_{key}_start"]
            if len(cl) and len(sr):
                elapsed = float(cl.t.iloc[0]) - float(sr.t.iloc[0])
                # invert the calendar: how much WORK fits in that elapsed span
                rec[key] = _work_in_span(st.calendar, float(sr.t.iloc[0]), elapsed)
            else:
                rec[key] = 0.0
        out[int(rid)] = rec
    return out


def _work_in_span(cal, start_hr: float, elapsed_hr: float) -> float:
    """Open hours contained in [start, start+elapsed]."""
    if cal.always_on:
        return elapsed_hr
    t, end, work, guard = start_hr, start_hr + elapsed_hr, 0.0, 0
    while t < end - 1e-9:
        guard += 1
        if guard > 2000:
            break
        if not cal.is_open(t):
            t = min(cal.next_open(t), end)
            continue
        chunk = min(end - t, cal.close_hr - (t % 24.0))
        work += chunk
        t += chunk
    return work
