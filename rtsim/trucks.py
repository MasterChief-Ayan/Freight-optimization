"""
trucks.py  -  L2. The road side: trucks, gate, access lane, appointments.

What this layer adds
--------------------
The terminal is a two-sided system. Rail capacity is useless if the road side
cannot feed it, and road congestion is the professor's one-way-passage point.
Three published mechanisms are implemented here:

  * Truck Appointment System (Guan & Liu 2009, TRR 2100). Validated
    distributions: exponential truck inter-arrivals, Erlang gate processing.
  * Rake-Dependent Time Windows, transposed from the Vessel-Dependent Time
    Windows of Parmaksizoglou, Bombelli & Sharpanskykh (2025), Logistics
    9(3):110. Delivery trucks must arrive before the rake is loaded;
    pickup trucks after it is unloaded.
  * Hard vs soft infeasibility, same source. HARD = the truck's arrival
    cannot align with the rake at all. SOFT = the period quota is exceeded;
    the schedule is still feasible but the gate congests.

Where the novelty sits
----------------------
The source paper assumes vessel arrivals are DETERMINISTIC and does not study
disruption. Here the appointment schedule is built against the rake's
EXPECTED arrival, and then the rake actually arrives stochastically. The
resulting misalignment is measured as hard infeasibility. That gap is the
contribution, and it is exactly the professor's constraint O1.

Access lane
-----------
capacity 1  = one-way passage. A BLOCKING system: while a truck is in the
              lane nothing else may enter, in either direction.
capacity >1 = organised queue, a waiting system.
These are different queueing regimes (Erlang loss vs M/M/c), not the same
model with a different number. The lane experiment compares them directly.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math
import simpy

from .distributions import Dist, RandomStreams
from .eventlog import (EventLog, KIND_PHYSICAL, KIND_WAIT, KIND_ADMIN,
                       PARTY_TRANSPORTER, PARTY_TERMINAL)


# ======================================================================
# ENTITY
# ======================================================================
class Truck:
    __slots__ = ("id", "company", "job", "rake_id", "tonnes",
                 "preferred_period", "assigned_period", "deviation",
                 "hard_infeasible", "service_hr")

    def __init__(self, tid, company, job, rake_id, tonnes,
                 preferred_period, service_hr):
        self.id = tid
        self.company = company
        self.job = job                      # 'deliver' or 'pickup'
        self.rake_id = rake_id
        self.tonnes = tonnes
        self.preferred_period = preferred_period
        self.assigned_period = preferred_period
        self.deviation = 0
        self.hard_infeasible = False
        self.service_hr = service_hr

    def __repr__(self):
        return (f"Truck({self.id}, {self.company}, {self.job}, rake={self.rake_id}, "
                f"pref={self.preferred_period}, assigned={self.assigned_period})")


# ======================================================================
# GENERATION
# ======================================================================
def generate_trucks(cfg, rakes, streams: RandomStreams) -> List[Truck]:
    """One truck per load. Preferred period is drawn around the rake's
    EXPECTED arrival - which is what a terminal planner actually has."""
    tc = cfg.trucks
    out, tid = [], 0
    for r in rakes:
        n = int(math.ceil(r.tonnes / tc.truck_capacity_t))
        # The planner anchors on the EXPECTED arrival: booking time, plus the
        # MEAN administrative lead time, plus transit. It is an unbiased
        # estimate - the planner knows the average, not the realisation.
        # The rake then arrives early or late around it. That misalignment,
        # not the mean, is what the appointment system has to absorb, and
        # studying it is the gap the source paper leaves open (it assumes
        # vessel arrivals are deterministic).
        expected = r.booking_time + tc.planned_admin_lead_hr + r.transit_hr
        anchor = int(expected // tc.period_hr)
        for _ in range(n):
            tid += 1
            comp = streams.get(f"truckcompany#{tid}").randrange(tc.n_companies)
            # deliveries want to be just BEFORE the rake
            off = streams.get(f"truckpref#{tid}").randint(
                -tc.delivery_lead_periods, -1)
            out.append(Truck(
                tid=tid,
                company=f"C{comp+1}",
                job="deliver",
                rake_id=r.id,
                tonnes=tc.truck_capacity_t,
                preferred_period=max(0, anchor + off),
                service_hr=max(0.02, streams.draw(f"truckservice#{tid}",
                                              tc.discharge))))
    return out


# ======================================================================
# APPOINTMENT SYSTEM  (hooks D3 and D4)
# ======================================================================
def deviation_cost(dev: int, aversion: float, scale: float = 4.0) -> float:
    """Parmaksizoglou et al. Eq. 8 in form: exponential in periods deviated,
    scaled by the company's aversion factor. A small reshuffle is cheap;
    a large one is punitive. Non-linear on purpose.

    `scale` divides the exponent. Without it, exp(24) over a 24-period
    deviation limit gives costs of order 1e10 and the objective is numerically
    meaningless. scale=4 keeps the range interpretable while preserving
    strict convexity, which is the property the mechanism actually relies on.
    """
    return aversion * (math.exp(abs(dev) / scale) - 1.0)


def _period_open(cfg, period: int) -> bool:
    """A real appointment system cannot offer a slot when the gate is shut."""
    tc = cfg.trucks
    hod = (period * tc.period_hr) % 24.0
    return tc.gate_open_hr <= hod < tc.gate_close_hr


def allocate_slots(cfg, trucks: List[Truck], rule: str = "FCFS") -> Dict:
    """Stage 2 of the appointment system: assign each truck to a period.

    rule = 'NONE'    no appointment system; everyone shows up when they like
    rule = 'FCFS'    first come first served against the period quota
    rule = 'MINMAX'  fairness. When a deviation must be imposed, impose it on
                     the company whose cumulative deviation cost is lowest
                     (Parmaksizoglou et al.). Protects small operators from
                     absorbing every reschedule.
    """
    tc = cfg.trucks
    quota = tc.slots_per_period
    used: Dict[int, int] = {}
    cum_cost: Dict[str, float] = {}
    aversion = {f"C{i+1}": tc.aversion_base * (1 + 0.4 * i)
                for i in range(tc.n_companies)}

    if rule == "NONE":
        # no appointment system: everyone turns up when they like, and the
        # only thing stopping them is the gate being physically shut
        for t in trucks:
            p = t.preferred_period
            while not _period_open(cfg, p):
                p += 1
            t.assigned_period = p
            t.deviation = 0
        return {"rule": rule, "total_deviation_cost": 0.0,
                "max_company_cost": 0.0, "deviated": 0, "hard_infeasible": 0}

    def assign(t):
        """Place one truck at, or as near as possible to, its preferred
        period, respecting the quota and the gate's operating hours."""
        p0 = t.preferred_period
        for d in range(0, tc.max_deviation + 1):
            for cand in ([p0] if d == 0 else [p0 - d, p0 + d]):
                if cand < 0 or not _period_open(cfg, cand):
                    continue
                if used.get(cand, 0) < quota:
                    used[cand] = used.get(cand, 0) + 1
                    t.assigned_period, t.deviation = cand, cand - p0
                    return
        # SOFT infeasibility: no slot within the deviation limit. The
        # schedule stays feasible but the quota is knowingly breached.
        t.assigned_period, t.deviation = p0, 0
        used[p0] = used.get(p0, 0) + 1

    # group by preferred period and process periods in time order, so no
    # company gains simply by being early in the list
    by_period: Dict[int, List[Truck]] = {}
    for t in trucks:
        by_period.setdefault(t.preferred_period, []).append(t)

    for p in sorted(by_period):
        group = by_period[p]
        if rule == "MINMAX":
            # the scarce on-time slots go to whoever is ALREADY worst off;
            # the company with the lowest cumulative cost absorbs the
            # deviation. This is what minimises the maximum per-company cost.
            group.sort(key=lambda t: -cum_cost.get(t.company, 0.0))
        else:
            group.sort(key=lambda t: t.id)
        for t in group:
            assign(t)
            cum_cost[t.company] = cum_cost.get(t.company, 0.0) + \
                deviation_cost(t.deviation, aversion[t.company],
                               tc.deviation_scale)

    return {"rule": rule,
            "total_deviation_cost": sum(cum_cost.values()),
            "max_company_cost": max(cum_cost.values()) if cum_cost else 0.0,
            "company_costs": dict(cum_cost),
            "deviated": sum(1 for t in trucks if t.deviation != 0),
            "peak_period_load": max(used.values()) if used else 0}


# ======================================================================
# ROAD SIDE RESOURCES + PROCESS
# ======================================================================
class RoadSide:
    def __init__(self, env, cfg, log: EventLog, streams: RandomStreams,
                 admin=None):
        self.env, self.cfg, self.log, self.streams = env, cfg, log, streams
        self.admin = admin
        tc = cfg.trucks
        self.gate = simpy.Resource(env, capacity=tc.gate_servers)
        # capacity 1 => one-way passage (blocking); >1 => organised queue
        self.lane = simpy.Resource(env, capacity=tc.lane_capacity)
        self.stockyard = simpy.Container(env, capacity=tc.stockyard_capacity_t,
                                         init=tc.stockyard_initial_t)
        self.gate_queue_samples: List[Tuple[float, int]] = []
        self._waiting = 0
        self.hard_infeasible = 0
        self.trucks_done = 0
        self.early_deliveries = []   # (rake_id, delivery time)

    def _ev(self, truck, name, owner, kind=KIND_PHYSICAL, resource=None, detail=""):
        self.log.add(self.env.now, "truck", truck.id, name, kind, owner,
                     resource, detail)

    def _sample(self):
        self.gate_queue_samples.append((self.env.now, self._waiting))

    def handle(self, truck: Truck, rake_events: Dict[int, simpy.Event]):
        tc = self.cfg.trucks
        target = truck.assigned_period * tc.period_hr
        if self.env.now < target:
            yield self.env.timeout(target - self.env.now)
        self._ev(truck, "truck_arrive", PARTY_TRANSPORTER,
                 detail=f"{truck.company} dev={truck.deviation}")

        # ---- gate queue -------------------------------------------------
        self._waiting += 1
        self._sample()
        # M8: driver identity, weighbridge, gate pass, e-way bill. Modelled
        # BEFORE the booth is seized - a driver assembling paperwork does not
        # occupy a gate server, and modelling it inside the hold made one
        # late-arriving truck block a booth until the next shift.
        if self.admin is not None:
            yield from self.admin.run_step("M8", "truck", truck.id)
        with self.gate.request() as g:
            yield g
            self._waiting -= 1
            self._sample()
            self._ev(truck, "gate_start", PARTY_TERMINAL, resource="gate")
            yield self.env.timeout(self.streams.draw(f"gate#{truck.id}",
                                                     tc.gate_service))
            self._ev(truck, "gate_end", PARTY_TERMINAL, resource="gate")

        # ---- access lane in --------------------------------------------
        with self.lane.request() as l:
            yield l
            self._ev(truck, "lane_seize", PARTY_TERMINAL, resource="lane")
            yield self.env.timeout(tc.lane_transit_hr)
            self._ev(truck, "lane_free", PARTY_TERMINAL, resource="lane")
        self._ev(truck, "at_stockyard", PARTY_TERMINAL)

        # ---- discharge --------------------------------------------------
        yield self.env.timeout(truck.service_hr)
        yield self.stockyard.put(truck.tonnes)
        self._ev(truck, "discharged", PARTY_TRANSPORTER,
                 detail=f"{truck.tonnes:.0f}t")

        # ---- access lane out (same physical lane if one-way) ------------
        with self.lane.request() as l2:
            yield l2
            self._ev(truck, "lane_seize", PARTY_TERMINAL, resource="lane")
            yield self.env.timeout(tc.lane_transit_hr)
            self._ev(truck, "lane_free", PARTY_TERMINAL, resource="lane")
        self._ev(truck, "truck_exit", PARTY_TRANSPORTER)

        # Two ways the plan and the reality can disagree:
        #   HARD INFEASIBLE - the rake was loaded before this truck delivered.
        #                     Its load is useless to that rake.
        #   EARLY DELIVERY  - the truck delivered well before the rake was
        #                     ready. Not infeasible, but the material occupies
        #                     the stockyard and ties up working capital.
        ev = rake_events.get(truck.rake_id)
        if ev is not None and ev.triggered:
            truck.hard_infeasible = True
            self.hard_infeasible += 1
            self._ev(truck, "hard_infeasible", PARTY_TERMINAL, kind=KIND_WAIT,
                     detail="delivered after its rake had already been loaded")
        else:
            self.early_deliveries.append((truck.rake_id, self.env.now))
        self.trucks_done += 1


def feed_trucks(env, road: RoadSide, trucks: List[Truck], rake_events):
    for t in trucks:
        env.process(road.handle(t, rake_events))
    yield env.timeout(0)
