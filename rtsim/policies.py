"""
policies.py  -  L3. The swappable decision layer.

A policy answers exactly one question in Layer 0:
    of the rakes currently waiting, which is placed next?

It returns a number; LOWER is served first. Nothing else in the model
changes when you swap a policy. Later layers add more hooks (which line,
which truck slot, which crew) but the same pattern applies.

Registered here now:
    FCFS     first come first served - the baseline every result is measured against
    SPT      shortest loading job first - classic, minimises mean flow time
    LPT      longest first - included because it should be WORSE; a policy
             set with no bad member cannot demonstrate that the model is
             sensitive to the decision at all
    COST     minimise the controllable cost this rake will inflict

Layer 4 will add: CP-SAT offline optimum, and agent negotiation.
"""
from .config import Config
from .terminal import Rake


def fcfs(cfg: Config):
    def f(rake: Rake, ctx) -> float:
        return rake.actual_arrival
    f.__name__ = "FCFS"
    return f


def spt(cfg: Config):
    def f(rake: Rake, ctx) -> float:
        return rake.load_hr
    f.__name__ = "SPT"
    return f


def lpt(cfg: Config):
    def f(rake: Rake, ctx) -> float:
        return -rake.load_hr
    f.__name__ = "LPT"
    return f


def cost_priority(cfg: Config):
    """Serve first the rake that will cost least to clear, so the line is
    freed soonest. Uses only information available at decision time."""
    c = cfg.charges

    def f(rake: Rake, ctx) -> float:
        detention = rake.place_hr + rake.load_hr
        excess = max(0.0, detention - c.free_time_hr)
        demurrage = excess * rake.wagons * c.demurrage_per_wagon_hr
        blocking = (detention + rake.remove_hr) * c.idle_cost_per_hr
        return demurrage + blocking
    f.__name__ = "COST"
    return f


def cnp(cfg: Config):
    """Contract Net bidding. Defined in optimiser.py; registered here so it
    is swappable exactly like any other rule."""
    from .optimiser import cnp_policy
    return cnp_policy(cfg)


REGISTRY = {
    "FCFS": fcfs,
    "SPT": spt,
    "LPT": lpt,
    "COST": cost_priority,
    "CNP": cnp,
}


def build(name: str, cfg: Config):
    if name not in REGISTRY:
        raise KeyError(f"unknown policy '{name}'. Available: {list(REGISTRY)}")
    return REGISTRY[name](cfg)
