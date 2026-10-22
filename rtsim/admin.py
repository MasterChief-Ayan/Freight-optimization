"""
admin.py  -  L1. The administrative chain.

Why this layer exists
---------------------
Physical handling is a minority of total dwell time. The World Bank's Douala
study (Refas & Cantens 2011, WPS 5565) decomposed 51,689 shipments into
operational (2-4 days), transactional (2-4 days) and discretionary time, and
found the physical layer was roughly one eighth of the total. The paperwork
is not a footnote to the model; it is most of the model.

Why many SMALL steps produce LARGE delays
-----------------------------------------
Four mechanisms. Only the first is obvious, and it is the least important.

  1. Serial accumulation      n steps x mean m = n*m. Real, but minor.
  2. CALENDAR TRUNCATION      a step finishing at 18:05 waits until 10:00.
                              A five-minute signature costs sixteen hours.
                              This is where the delay actually lives.
  3. REWORK LOOPS             a rejected document does not cost its own
                              service time, it costs a whole office cycle.
                              This is what makes the tail heavy.
  4. Variance compounding     Pollaczek-Khinchine: waiting grows with the
                              VARIANCE of service, not just the mean.

Douala's dwell-time standard deviation was 160% of its mean. The CAG found
Eastern Railway goods-train detention ranging from 2 to 11,936 minutes.
Both are signatures of mechanisms 2 and 3, not of mechanism 1.

Structure
---------
The administrative chain runs ALONGSIDE the physical chain and connects to it
only through GATES. A physical event cannot occur until its gating documents
clear. Formally: the administrative process generates a stochastic release
date for the physical scheduling problem, turning 1|r_j|SumC_j into
1|r_j(stochastic)|SumC_j.

Design contract
---------------
With every step disabled, Layer 1 reproduces Layer 0 byte for byte.
verify_admin.py checks exactly this.
"""
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple
import simpy

from .distributions import Dist, RandomStreams
from .eventlog import (EventLog, KIND_ADMIN, PARTY_TERMINAL, PARTY_RAILWAY,
                       PARTY_CLIENT, PARTY_TRANSPORTER)


# ======================================================================
# CALENDARS  -  mechanism 2, the dominant one
# ======================================================================
@dataclass(frozen=True)
class Calendar:
    """An office. Work progresses only while it is open.

    t = 0 is taken as 00:00 on day 0, and day 0 is a Monday.
    weekdays uses Python convention: 0 = Monday ... 6 = Sunday.
    """
    name: str = "office"
    open_hr: float = 10.0
    close_hr: float = 18.0
    weekdays: Tuple[int, ...] = (0, 1, 2, 3, 4, 5)     # Mon-Sat
    always_on: bool = False                             # 24/7, e.g. after e-RD

    def is_open(self, t: float) -> bool:
        if self.always_on:
            return True
        day = int(t // 24) % 7
        if day not in self.weekdays:
            return False
        hod = t % 24.0
        return self.open_hr <= hod < self.close_hr

    def next_open(self, t: float) -> float:
        """Earliest time >= t at which this office is open."""
        if self.always_on or self.is_open(t):
            return t
        probe = t
        for _ in range(21):                 # at most three weeks ahead
            day = int(probe // 24) % 7
            hod = probe % 24.0
            day_start = probe - hod
            if day in self.weekdays and hod < self.open_hr:
                return day_start + self.open_hr
            probe = day_start + 24.0        # move to start of next day
        raise RuntimeError(f"calendar '{self.name}' never opens")


# Standard calendars. Distinct hours per party is itself a delay source:
# a handoff across two offices with different windows costs the gap.
CAL_24_7 = Calendar("24/7", always_on=True)
CAL_RAILWAY_OFFICE = Calendar("railway office", 10.0, 17.0, (0, 1, 2, 3, 4, 5))
CAL_TERMINAL_OFFICE = Calendar("terminal office", 9.0, 18.0, (0, 1, 2, 3, 4, 5))
CAL_TERMINAL_SHIFT = Calendar("terminal shift", 6.0, 22.0, (0, 1, 2, 3, 4, 5, 6))
CAL_CLIENT_OFFICE = Calendar("client office", 10.0, 18.0, (0, 1, 2, 3, 4))
CAL_BANK = Calendar("bank", 10.0, 16.0, (0, 1, 2, 3, 4))


# ======================================================================
# ONE ADMINISTRATIVE STEP
# ======================================================================
@dataclass(frozen=True)
class AdminStep:
    key: str                    # M1..M8
    name: str
    owner: str                  # which of the four parties is responsible
    service: Dist               # actual working time, hours
    calendar: Calendar          # when that work can happen
    rework_prob: float = 0.0    # probability the submission is rejected
    max_retries: int = 4
    servers: int = 10_000       # office capacity; large = staff not the bottleneck
    enabled: bool = True
    gates: str = ""             # which physical event this blocks (documentation)
    source: str = ""            # provenance in IR rules

    def disabled(self) -> "AdminStep":
        return replace(self, enabled=False)

    def digitalised(self) -> "AdminStep":
        """E2 scenario: the step goes online. 24/7, no rejections,
        and service time cut by the digitalisation factor."""
        return replace(self, calendar=CAL_24_7, rework_prob=0.0,
                       service=Dist(self.service.kind,
                                    mean=self.service.mean * 0.5,
                                    sd=self.service.sd * 0.5))


# ======================================================================
# THE EIGHT STEPS
# ======================================================================
# Selection criteria: on the critical path to placement or release, has a
# documented approval or rework loop, and is traceable in IR rules.
# Durations and rejection probabilities are ASSUMED and must be
# sensitivity-tested until field data arrives.

def default_steps() -> Dict[str, AdminStep]:
    return {
        "M1": AdminStep(
            "M1", "demand registration to wagon allotment", PARTY_RAILWAY,
            Dist("logn", mean=10.0, sd=7.0), CAL_RAILWAY_OFFICE,
            rework_prob=0.10, gates="rake_arrive",
            source="e-RD / Forwarding Note; WRF; demand-cum-priority number; "
                   "allotment by Control (IR Comm. Manual II ch. XIV)"),

        "M2": AdminStep(
            "M2", "advance stacking permission", PARTY_RAILWAY,
            Dist("logn", mean=2.0, sd=1.5), CAL_RAILWAY_OFFICE,
            rework_prob=0.15, gates="loading_start",
            source="Railway Board circular on advance stacking permission"),

        "M3": AdminStep(
            "M3", "forwarding note acceptance", PARTY_CLIENT,
            Dist("logn", mean=1.5, sd=1.0), CAL_TERMINAL_OFFICE,
            rework_prob=0.20, gates="placement_start",
            source="IR Commercial Manual Vol. II ch. XIV; mis-declaration checks"),

        "M4": AdminStep(
            "M4", "placement advice and acknowledgment", PARTY_TERMINAL,
            Dist("logn", mean=0.5, sd=0.35), CAL_TERMINAL_SHIFT,
            rework_prob=0.05, gates="loading_start",
            source="serving station <-> siding placement advice; starts free time"),

        "M5": AdminStep(
            "M5", "weighment and overload adjustment", PARTY_TERMINAL,
            Dist("logn", mean=1.8, sd=1.4), CAL_TERMINAL_SHIFT,
            rework_prob=0.18, gates="released",
            source="nominated weighbridge; alternate if defective; "
                   "load adjustment on overload detection"),

        "M6": AdminStep(
            "M6", "release reporting", PARTY_TERMINAL,
            Dist("logn", mean=3.6, sd=2.8), CAL_TERMINAL_SHIFT,
            rework_prob=0.10, gates="released",
            source="TERI Vol. I: 80-85% of restrictions attributed to poor "
                   "release; human-reported, not system-detected"),

        "M7": AdminStep(
            "M7", "railway receipt and freight payment clearance", PARTY_CLIENT,
            Dist("logn", mean=4.0, sd=3.0), CAL_RAILWAY_OFFICE,
            rework_prob=0.12, gates="removal_start",
            source="PARALLEL: prepared alongside weighment and release, "
                   "joined before removal. eT-RR; electronic payment / Freight Advance Scheme; "
                   "for outward traffic demurrage raised before RR preparation"),

        "M8": AdminStep(
            "M8", "truck gate verification", PARTY_TRANSPORTER,
            Dist("erlang", mean=0.25, sd=0.12), CAL_24_7,
            rework_prob=0.08, enabled=True, gates="truck gate entry",
            source="driver identity check, weighbridge in/out, gate pass, "
                   "e-way bill. ACTIVE from Layer 2."),
    }


# ======================================================================
# THE ENGINE
# ======================================================================
class AdminChain:
    """Executes administrative steps: calendar-bounded work with rework."""

    def __init__(self, env: simpy.Environment, log: EventLog,
                 streams: RandomStreams, steps: Optional[Dict[str, AdminStep]] = None):
        self.env, self.log, self.streams = env, log, streams
        self.steps = steps if steps is not None else default_steps()
        self._offices: Dict[str, simpy.Resource] = {}
        # per-step accumulated time, for the ablation experiment
        self.step_time: Dict[str, float] = {k: 0.0 for k in self.steps}
        self.step_rejections: Dict[str, int] = {k: 0 for k in self.steps}

    def _office(self, step: AdminStep) -> simpy.Resource:
        if step.key not in self._offices:
            self._offices[step.key] = simpy.Resource(self.env, capacity=step.servers)
        return self._offices[step.key]

    # -- calendar-bounded work -----------------------------------------
    def _work(self, cal: Calendar, duration: float):
        """Consume `duration` hours of WORKING time. Idle time outside
        office hours still passes on the simulation clock but does not
        reduce the remaining work. This single routine is mechanism 2."""
        remaining = duration
        guard = 0
        while remaining > 1e-9:
            guard += 1
            if guard > 500:
                raise RuntimeError("calendar work loop did not converge")
            now = self.env.now
            if not cal.is_open(now):
                yield self.env.timeout(cal.next_open(now) - now)
                continue
            if cal.always_on:
                yield self.env.timeout(remaining)
                remaining = 0.0
                continue
            hod = now % 24.0
            until_close = cal.close_hr - hod
            chunk = min(remaining, until_close)
            yield self.env.timeout(chunk)
            remaining -= chunk

    def start_parallel(self, key: str, entity_type: str, entity_id: int):
        """Launch a step as a BACKGROUND process and return it, so the
        physical chain can carry on and join it later. Used where paperwork
        is genuinely prepared alongside physical work rather than after it."""
        step = self.steps[key]
        if not step.enabled:
            return None
        return self.env.process(self.run_step(key, entity_type, entity_id))

    # -- one step, with rework -----------------------------------------
    def run_step(self, key: str, entity_type: str, entity_id: int):
        """Execute step `key` for one entity. Yields until it clears."""
        step = self.steps[key]
        if not step.enabled:
            return
        t0 = self.env.now
        self.log.add(t0, entity_type, entity_id, f"admin_{key}_start",
                     KIND_ADMIN, step.owner, detail=step.name)

        attempts = 0
        with self._office(step).request() as req:
            yield req
            while True:
                attempts += 1
                # Stream keyed on the ENTITY, not just the step. A shared
                # per-step stream is drawn in EXECUTION order, so changing the
                # dispatch sequence hands a different rake each draw - the
                # scenario silently changes with the policy and every paired
                # comparison is confounded. Keying on the entity fixes each
                # rake's administrative durations for good.
                dur = max(0.0, self.streams.draw(
                    f"admin_{key}#{entity_type}{entity_id}", step.service))
                yield from self._work(step.calendar, dur)

                if step.rework_prob <= 0 or attempts > step.max_retries:
                    break
                if self.streams.get(
                        f"rework_{key}#{entity_type}{entity_id}#{attempts}"
                ).random() >= step.rework_prob:
                    break
                # rejected: log it and go round again. The cost is not the
                # service time, it is the next full office cycle.
                self.step_rejections[key] += 1
                self.log.add(self.env.now, entity_type, entity_id,
                             f"admin_{key}_rejected", KIND_ADMIN, step.owner,
                             detail=f"attempt {attempts}")

        elapsed = self.env.now - t0
        self.step_time[key] += elapsed
        self.log.add(self.env.now, entity_type, entity_id, f"admin_{key}_clear",
                     KIND_ADMIN, step.owner,
                     detail=f"{step.name} | {attempts} attempt(s) | {elapsed:.2f}h")


# ======================================================================
# SCENARIO HELPERS  -  E1 ablation, E2 digitalisation, E3 variance
# ======================================================================
def steps_with(modifier, keys: List[str],
               base: Optional[Dict[str, AdminStep]] = None) -> Dict[str, AdminStep]:
    base = base if base is not None else default_steps()
    out = dict(base)
    for k in keys:
        if k in out:
            out[k] = modifier(out[k])
    return out


def ablate(keys: List[str], base=None) -> Dict[str, AdminStep]:
    """E1: remove step(s) entirely to measure their contribution."""
    return steps_with(lambda s: s.disabled(), keys, base)


def digitalise(keys: List[str], base=None) -> Dict[str, AdminStep]:
    """E2: 24/7 working, no rejections, half the processing time.
    Simulates IR's own initiatives: e-RD, eT-RR, TMS, e-payment."""
    return steps_with(lambda s: s.digitalised(), keys, base)


def all_disabled() -> Dict[str, AdminStep]:
    """Layer 1 with everything off must reproduce Layer 0 exactly."""
    return {k: v.disabled() for k, v in default_steps().items()}


def halve_mean(keys: List[str], base=None) -> Dict[str, AdminStep]:
    """E3 arm A: work twice as fast, same variability ratio."""
    return steps_with(
        lambda s: replace(s, service=Dist(s.service.kind,
                                          mean=s.service.mean * 0.5,
                                          sd=s.service.sd * 0.5)),
        keys, base)


def halve_variance(keys: List[str], base=None) -> Dict[str, AdminStep]:
    """E3 arm B: same mean, half the standard deviation.
    Tests the Pollaczek-Khinchine prediction directly."""
    return steps_with(
        lambda s: replace(s, service=Dist(s.service.kind,
                                          mean=s.service.mean,
                                          sd=s.service.sd * 0.5)),
        keys, base)


def remove_calendar(keys: List[str], base=None) -> Dict[str, AdminStep]:
    """E3 arm C: same work, same variance, but no office-hours truncation."""
    return steps_with(lambda s: replace(s, calendar=CAL_24_7), keys, base)


def no_rework(keys: List[str], base=None) -> Dict[str, AdminStep]:
    """E3 arm D: same work and calendar, but nothing is ever rejected."""
    return steps_with(lambda s: replace(s, rework_prob=0.0), keys, base)
