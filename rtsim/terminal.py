"""
terminal.py  -  L0 entities, L1 resources, L2 physical event chain, L3 hook.

The physical chain (source: IR placement/release rules + shunting literature):

    rake_arrive
      -> queue_start            waiting for a loading line
      -> placement_start        seizes LINE, then LOCO
      -> placed                 FREE TIME CLOCK STARTS
      -> loading_start          seizes CREW
      -> loading_end
      -> released               FREE TIME CLOCK STOPS
      -> removal_start          seizes LOCO again
      -> removed                LINE released

Resource-holding discipline (prevents deadlock):
    the LINE is held from placement_start to removed.
    the LOCO is held only during placement, and again during removal.
    the LINE is always acquired BEFORE the LOCO, so a rake waiting for a
    loco always already holds a line; since every loco hold is time-bounded,
    the loco is always eventually released. No circular wait can form.
"""
from typing import Callable, List, Dict, Optional
import simpy

from .config import Config
from .distributions import RandomStreams
from .eventlog import (EventLog, KIND_PHYSICAL, KIND_WAIT,
                       PARTY_TERMINAL, PARTY_RAILWAY, PARTY_CLIENT, PARTY_SYSTEM)


# ----------------------------------------------------------------------
# L0  ENTITY
# ----------------------------------------------------------------------
class Rake:
    """One rake. Attributes fixed at generation time so that every policy
    faces an identical stream of work (common random numbers)."""

    __slots__ = ("id", "booking_time", "transit_hr", "scheduled_arrival",
                 "actual_arrival", "wagons", "tonnes", "load_hr",
                 "place_hr", "remove_hr", "no_show", "lateness")

    def __init__(self, rid, scheduled_arrival, actual_arrival, wagons,
                 tonnes, load_hr, place_hr, remove_hr, no_show=False,
                 booking_time=0.0, transit_hr=0.0):
        self.id = rid
        self.booking_time = booking_time
        self.transit_hr = transit_hr
        self.scheduled_arrival = scheduled_arrival
        self.actual_arrival = actual_arrival
        self.wagons = wagons
        self.tonnes = tonnes
        self.load_hr = load_hr
        self.place_hr = place_hr
        self.remove_hr = remove_hr
        self.no_show = no_show
        self.lateness = max(0.0, actual_arrival - scheduled_arrival)

    def __repr__(self):
        return f"Rake({self.id}, arr={self.actual_arrival:.2f}, load={self.load_hr:.2f}h)"


def generate_rakes(cfg: Config, streams: RandomStreams) -> List[Rake]:
    """Build the whole arrival stream up front.

    Doing this BEFORE the simulation (rather than inside it) is what lets
    every policy - and later the CP-SAT optimiser, which needs to see all
    jobs at once - run on a bit-identical scenario.
    """
    rk, sh = cfg.rake, cfg.shunting
    rakes, t = [], 0.0
    for i in range(1, cfg.run.n_rakes + 1):
        # t is the BOOKING time. Physical arrival = booking + (admin lead
        # time, Layer 1 only) + transit. With admin disabled the two layers
        # produce identical arrival streams - see verify_admin.py.
        t += streams.draw("arrival", rk.arrival_gap)
        transit = streams.draw("transit", rk.transit)

        no_show = streams.draw("noshow", type(rk.arrival_gap)(
            "bernoulli", p=rk.no_show_prob)) > 0.5 if rk.no_show_prob > 0 else False

        actual = t
        if rk.late_prob > 0:
            late = streams.get("lateflag").random() < rk.late_prob
            if late:
                actual = t + streams.draw("latedelay", rk.late_delay)

        tonnes = rk.wagons * rk.tonnes_per_wagon
        rate = max(rk.load_rate_floor, streams.draw("loadrate", rk.load_rate_tph))
        rakes.append(Rake(
            rid=i,
            booking_time=t,
            transit_hr=transit,
            scheduled_arrival=t + transit,
            actual_arrival=actual + transit,
            wagons=rk.wagons,
            tonnes=tonnes,
            load_hr=tonnes / rate,
            place_hr=max(sh.min_duration, streams.draw("placement", sh.placement)),
            remove_hr=max(sh.min_duration, streams.draw("removal", sh.removal)),
            no_show=no_show))
    return rakes


# ----------------------------------------------------------------------
# L3  DECISION HOOK
# ----------------------------------------------------------------------
# A policy is any function (rake, context) -> float. LOWER goes first.
# This is the ONLY place intelligence enters the physical model. Swapping
# FCFS for a priority rule, a CP-SAT schedule, or an agent negotiation
# changes this function and nothing else.
PolicyFn = Callable[[Rake, Dict], float]


# ----------------------------------------------------------------------
# L1  RESOURCES + L2  PROCESS
# ----------------------------------------------------------------------
class Terminal:
    def __init__(self, env: simpy.Environment, cfg: Config,
                 log: EventLog, policy: PolicyFn, admin=None):
        self.env, self.cfg, self.log, self.policy = env, cfg, log, policy
        # Layer 1. When admin is None the model is exactly Layer 0.
        self.admin = admin
        self.pending = {}      # rake_id -> background admin processes
        # L2: fires when a rake's loading begins, so the road side can detect
        # trucks that turned up too late to be useful (hard infeasibility)
        self.loading_started = {}
        self.road = None       # RoadSide, attached in Layer 2
        rc = cfg.resources
        # NOT a PriorityResource. SimPy fixes a request's priority at the
        # moment it is made, which makes any time-dependent bid - ageing,
        # deadline pressure, current queue state - silently constant. The
        # Contract Net protocol requires the opposite: when a line frees, the
        # terminal issues a call for proposals and every waiting rake bids AT
        # THAT MOMENT. So the queue is explicit and the policy is evaluated
        # at dispatch time, not at arrival time.
        self.n_lines = rc.loading_lines
        self.free_lines = rc.loading_lines
        self.waiting = []          # [(rake, simpy.Event)] - the bidders
        self.loco = simpy.Resource(env, capacity=rc.shunting_locos)
        self.crew = simpy.Resource(env, capacity=rc.crews)

        # observability
        self.queue_len_samples: List[tuple] = []   # (t, n_waiting)
        self.line_busy_samples: List[tuple] = []   # (t, n_in_use)
        self._waiting = 0

    # -- helpers --------------------------------------------------------
    def _ev(self, rake: Rake, name, owner, kind=KIND_PHYSICAL,
            resource=None, detail=""):
        self.log.add(self.env.now, "rake", rake.id, name, kind, owner,
                     resource, detail)

    def _sample(self):
        self.queue_len_samples.append((self.env.now, self._waiting))
        self.line_busy_samples.append((self.env.now, self.n_lines - self.free_lines))

    def _dispatch(self):
        """Call for proposals. Evaluate every waiting rake's bid at the
        current clock and award the free line to the lowest bidder.

        Ties break on rake id so the model stays deterministic; without a
        deterministic tie-break two runs with the same seed could diverge.
        """
        while self.free_lines > 0 and self.waiting:
            ctx = {"now": self.env.now, "terminal": self,
                   "waiting": [r for r, _ in self.waiting]}
            winner = min(self.waiting,
                         key=lambda pe: (self.policy(pe[0], ctx), pe[0].id))
            self.waiting.remove(winner)
            self.free_lines -= 1
            self._waiting -= 1
            self._sample()
            winner[1].succeed()

    def _crew_window_delay(self) -> float:
        """If crew shifts are enabled, return the wait until the shift opens."""
        rc = self.cfg.resources
        if not rc.crew_shifts_enabled:
            return 0.0
        hod = self.env.now % 24.0
        if rc.crew_shift_start <= hod < rc.crew_shift_end:
            return 0.0
        if hod < rc.crew_shift_start:
            return rc.crew_shift_start - hod
        return (24.0 - hod) + rc.crew_shift_start

    def _gate(self, rake: Rake, *keys):
        """Block the physical chain until the named admin steps clear.
        No-op in Layer 0. This is the ONLY coupling between the two chains."""
        if self.admin is None:
            return
        for k in keys:
            yield from self.admin.run_step(k, "rake", rake.id)

    # -- the rake lifecycle --------------------------------------------
    def handle(self, rake: Rake):
        if rake.no_show:
            self._ev(rake, "rake_arrive", PARTY_RAILWAY, detail="NO SHOW")
            return

        self._ev(rake, "rake_arrive", PARTY_RAILWAY)

        # GATE: forwarding note must be accepted before the rake can be
        # taken in hand for placement (M3)
        yield from self._gate(rake, "M3")

        self._ev(rake, "queue_start", PARTY_TERMINAL, kind=KIND_WAIT,
                 resource="line")
        self._waiting += 1
        self._sample()

        m7 = None
        awarded = self.env.event()
        self.waiting.append((rake, awarded))
        self._dispatch()
        yield awarded                     # won the call for proposals

        try:
            # --- placement: needs the loco as well -----------------------
            with self.loco.request() as loco_req:
                yield loco_req
                self._ev(rake, "placement_start", PARTY_RAILWAY, resource="loco")
                yield self.env.timeout(rake.place_hr)
            # FREE TIME CLOCK STARTS HERE (IR rule)
            self._ev(rake, "placed", PARTY_RAILWAY, resource="line")

            # GATE: placement acknowledgment (M4) must clear before loading
            # may begin, and stacking permission (M2, started at booking)
            # must have been granted. Both sit INSIDE the free-time window,
            # so any time spent here is chargeable detention.
            yield from self._gate(rake, "M4")
            m2 = self.pending.pop(rake.id, None)
            if m2 is not None:
                yield m2

            # --- loading: needs a crew -----------------------------------
            wait_for_shift = self._crew_window_delay()
            if wait_for_shift > 0:
                yield self.env.timeout(wait_for_shift)
            with self.crew.request() as crew_req:
                yield crew_req
                # L2 material gate. Under assumption A1 the stockyard is
                # never the constraint and this is a no-op; switch A1 off to
                # make loading depend on what the trucks actually delivered.
                if (self.road is not None
                        and not self.cfg.trucks.assume_material_always_available):
                    yield self.road.stockyard.get(rake.tonnes)
                self._ev(rake, "loading_start", PARTY_TERMINAL, resource="crew")
                ev = self.loading_started.get(rake.id)
                if ev is not None and not ev.triggered:
                    ev.succeed()
                yield self.env.timeout(rake.load_hr)
                self._ev(rake, "loading_end", PARTY_TERMINAL, resource="crew")

            # M7 (RR + freight payment) is prepared IN PARALLEL with
            # weighment and release, not after them. Modelling it serially
            # would double-count office time that in reality overlaps.
            m7 = self.admin.start_parallel("M7", "rake", rake.id) \
                if self.admin is not None else None   # joined after removal

            # GATE: weighment and overload adjustment (M5), then release
            # reporting (M6). Both sit between loading_end and released, so
            # every hour here is chargeable detention. TERI attributes
            # 80-85% of terminal restrictions to poor release.
            yield from self._gate(rake, "M5", "M6")

            # FREE TIME CLOCK STOPS HERE (IR rule)
            self._ev(rake, "released", PARTY_TERMINAL)



            # --- removal: needs the loco again ---------------------------
            with self.loco.request() as loco_req2:
                yield loco_req2
                self._ev(rake, "removal_start", PARTY_RAILWAY, resource="loco")
                yield self.env.timeout(rake.remove_hr)
                self._ev(rake, "removed", PARTY_RAILWAY, resource="line")
        finally:
            # release the line and immediately issue the next call for
            # proposals. finally: so a line is never lost if a process is
            # interrupted.
            self.free_lines += 1
            self._dispatch()
        self._sample()

        # The LINE IS NOW FREE. The rake is back at the serving station.
        # Railway Receipt issue and freight settlement (M7) happen here, so
        # they delay the rake's departure and its return to the fleet, but
        # they do NOT occupy terminal capacity. Modelling M7 as holding the
        # loading line drove line occupancy above the arrival rate and made
        # the queue explode - a modelling error, not a real bottleneck.
        if m7 is not None:
            yield m7
        self._ev(rake, "departed", PARTY_CLIENT)



def feed(env: simpy.Environment, terminal: Terminal, rakes: List[Rake]):
    """Release rakes into the model at their arrival times (tandem queue:
    this is the arrival process of the first stage)."""
    prev = 0.0
    for r in sorted(rakes, key=lambda x: x.actual_arrival):
        yield env.timeout(max(0.0, r.actual_arrival - prev))
        prev = r.actual_arrival
        env.process(terminal.handle(r))


def feed_with_admin(env, terminal, rakes, admin):
    """Layer 1 arrival process. The rake is booked, the demand-to-allotment
    chain (M1) runs, and only then is the rake dispatched and does it travel
    to the serving station.

    This is the tandem-queue structure: the OUTPUT of the administrative
    stage is the INPUT (arrival process) of the physical stage. It also means
    M1 does two things at once - it delays each rake, and it smooths the
    arrival stream. The ablation output reports both effects.
    """
    def one(r: Rake):
        yield env.timeout(max(0.0, r.booking_time - env.now))
        # Advance stacking permission (M2) is applied for at booking time and
        # runs in parallel with allotment and transit. It is NOT something the
        # rake waits for while occupying a loading line - modelling it that
        # way inflated line occupancy and was wrong.
        m2 = admin.start_parallel("M2", "rake", r.id)
        terminal.pending[r.id] = m2
        yield from admin.run_step("M1", "rake", r.id)
        yield env.timeout(r.transit_hr)
        # constraint O1: uncertainty in rake availability. The delay is
        # applied here, AFTER allotment, because a rake that is allotted can
        # still fail to turn up on time. In Layer 0 the same delay is already
        # baked into actual_arrival; this branch is the Layer 1+ equivalent.
        if r.lateness > 0:
            yield env.timeout(r.lateness)
        yield from terminal.handle(r)

    for r in sorted(rakes, key=lambda x: x.booking_time):
        env.process(one(r))
    yield env.timeout(0)


def simulate(cfg: Config, policy: PolicyFn, seed: int,
             rakes: Optional[List[Rake]] = None,
             admin_steps: Optional[dict] = None,
             tas_rule: Optional[str] = None):
    """Run one replication.

    admin_steps=None  -> L0, physical model only
    admin_steps=dict  -> L1, administrative chain gates the physical chain
    tas_rule set      -> L2, road side active with that appointment rule

    Returns (log, rakes, terminal). terminal.road holds the road-side state
    and terminal.tas the appointment-allocation summary, when L2 is active.
    """
    from .admin import AdminChain
    from .trucks import RoadSide, generate_trucks, allocate_slots, feed_trucks

    streams = RandomStreams(seed)
    if rakes is None:
        rakes = generate_rakes(cfg, streams)
    env = simpy.Environment()
    log = EventLog()

    admin = AdminChain(env, log, streams, admin_steps) if admin_steps is not None else None
    term = Terminal(env, cfg, log, policy, admin=admin)

    if tas_rule is not None:
        trucks = generate_trucks(cfg, rakes, streams)
        term.tas = allocate_slots(cfg, trucks, tas_rule)
        term.trucks = trucks
        term.road = RoadSide(env, cfg, log, streams, admin=admin)
        for r in rakes:
            term.loading_started[r.id] = env.event()
        env.process(feed_trucks(env, term.road, trucks, term.loading_started))
    else:
        term.tas, term.trucks = None, []

    if admin is None:
        env.process(feed(env, term, rakes))
    else:
        env.process(feed_with_admin(env, term, rakes, admin))
    env.run()
    return log, rakes, term
