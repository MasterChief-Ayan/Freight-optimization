"""
config.py  -  Every assumption in the model lives here and nowhere else.

RULE: no numeric constant may appear anywhere else in the codebase.
      If you need a number, add a field here.

All rates marked ASSUMED are placeholders to be replaced when field data
arrives. Sources are cited where a value comes from a document.
"""
from dataclasses import dataclass, field, replace
from typing import Dict
from .distributions import Dist


# ----------------------------------------------------------------------
# L1  RESOURCES  -  what can be seized and released
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ResourceConfig:
    loading_lines: int = 1        # discrete berths (BAP structure). K>=2 activates hook D1
    shunting_locos: int = 1       # needed for BOTH placement and removal
    crews: int = 1                # loading gangs / mechanised units

    # Crew shift window (24h clock). Loading cannot proceed outside it.
    # TERI: labour stops before sunset in some regions; unions cap at 20:00.
    crew_shift_start: float = 6.0
    crew_shift_end: float = 22.0
    crew_shifts_enabled: bool = False    # Layer 0 = off; Layer 2 turns it on


# ----------------------------------------------------------------------
# L0  ENTITIES  -  what flows through the system
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class RakeConfig:
    wagons: int = 58                      # BOXN rake, typical
    tonnes_per_wagon: float = 58.08       # BOXN payload; 58 x 58.08 = 3368.64 t/rake
    arrival_gap: Dist = field(default_factory=lambda: Dist("exp", mean=30.0))
    load_rate_tph: Dist = field(default_factory=lambda: Dist("logn", mean=900.0, sd=250.0))
    load_rate_floor: float = 300.0        # guards against absurd draws
    # transit from dispatch to the serving station
    transit: Dist = field(default_factory=lambda: Dist("logn", mean=12.0, sd=4.0))

    # Professor's constraint O1: uncertainty in rake availability.
    # Bernoulli no-show + delay. Layer 0 keeps these off; they switch on later.
    no_show_prob: float = 0.0
    late_prob: float = 0.0
    late_delay: Dist = field(default_factory=lambda: Dist("logn", mean=6.0, sd=4.0))


@dataclass(frozen=True)
class ShuntingConfig:
    """Placement = moving the rake from serving station INTO the siding.
       Removal   = moving it back out. Both need a loco."""
    placement: Dist = field(default_factory=lambda: Dist("logn", mean=1.0, sd=0.3))
    removal: Dist = field(default_factory=lambda: Dist("logn", mean=1.0, sd=0.3))
    min_duration: float = 0.1


@dataclass(frozen=True)
class TruckConfig:
    """L2 road side. Distributions marked (validated) are the ones Guan & Liu
    (2009) found significant on field gate data."""
    enabled: bool = False              # Layer 0/1 leave the road side off

    truck_capacity_t: float = 35.0
    n_companies: int = 4
    period_hr: float = 1.0             # appointment period length
    delivery_lead_periods: int = 24    # trucks prefer to arrive within this
                                       # many periods BEFORE the rake
    # what the planner ASSUMES the administrative lead time will be. The
    # realised lead time varies around it, so the rake arrives early or late
    # relative to the truck appointment schedule.
    planned_admin_lead_hr: float = 26.0

    # gate: multi-server queue, Erlang processing (validated)
    gate_servers: int = 4
    gate_open_hr: float = 6.0          # gate operating window
    gate_close_hr: float = 22.0
    gate_service: Dist = field(default_factory=lambda: Dist("erlang", mean=0.15, sd=0.07))

    # access lane. 1 = ONE-WAY PASSAGE (blocking); >1 = organised queue
    lane_capacity: int = 1
    lane_transit_hr: float = 0.08

    discharge: Dist = field(default_factory=lambda: Dist("logn", mean=0.25, sd=0.10))

    stockyard_capacity_t: float = 200_000.0
    stockyard_initial_t: float = 100_000.0

    # appointment system
    slots_per_period: int = 10
    max_deviation: int = 24
    aversion_base: float = 1.0
    deviation_scale: float = 4.0   # divides the exponent; see deviation_cost

    # A1: coal always available. When True the rake never waits for material,
    # so trucks affect congestion but not availability. Professor's relaxation.
    assume_material_always_available: bool = True


# ----------------------------------------------------------------------
# L4  ACCOUNTING  -  IR charge rules
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ChargeConfig:
    """Indian Railways charge heads. Verify current figures against the
    Railway Board rate circular before using any result externally."""

    # Free time runs PLACEMENT -> RELEASE.
    # [IR-COMP 2.2(a)(i)] open wagons (BOXN etc.), MECHANIZED LOADING at a
    # private/assisted siding not on Engine-on-Load basis .......... 5:00
    # [IR-COMP 2.2.1(a)] additional free time for a private/assisted siding
    # NOT notified for through-distance charging .................... 2:00
    base_free_time_hr: float = 5.0
    siding_additional_free_time_hr: float = 2.0
    # [IR-COMP 2.7] one extra hour per rake for tarpaulin covering of loose
    # bulk commodities; the circular names Coal and Coke explicitly
    tarpaulin_free_time_hr: float = 1.0
    tarpaulin_applies: bool = True                   # coal

    # Excess detention = (release - placement) - free time  [IR-COMP 2.2.2(a)]
    demurrage_per_wagon_hr: float = 150.0            # base rate [IR-COMP 3.1]
    demurrage_part_hour_rounding: bool = True        # part-hours charged full
    # [IR-COMP 3.1] demurrage is GRADED, not flat. (upper bound of the band
    # in hours of excess detention, multiplier on the base rate)
    demurrage_grades: tuple = ((6.0, 1.00), (12.0, 1.10), (24.0, 1.25),
                               (48.0, 1.50), (72.0, 2.00),
                               (float("inf"), 3.00))
    graded_demurrage: bool = True
    # [IR-COMP 3.4.1] up to 6x base during notified congestion
    penal_multiplier: float = 1.0

    @property
    def free_time_hr(self) -> float:
        return (self.base_free_time_hr
                + self.siding_additional_free_time_hr
                + (self.tarpaulin_free_time_hr if self.tarpaulin_applies else 0.0))

    # Siding charge = engine hour cost x average trip time (serving stn <-> siding)
    engine_hour_cost: float = 6000.0                 # ASSUMED Rs/engine-hour
    siding_charge_enabled: bool = True

    # Shunting charge for use of a railway loco
    shunting_charge: float = 25000.0                 # ASSUMED Rs per placement+removal

    # Revenue
    freight_per_tonne: float = 1400.0                # ASSUMED Rs/tonne for the haul

    # Opportunity cost of a rake standing idle (not an IR charge - an
    # economic cost borne by whoever owns the asset's time)
    idle_cost_per_hr: float = 3000.0                 # ASSUMED


@dataclass(frozen=True)
class CoordinationConfig:
    """L3. How the parties agree who gets the line."""
    # weight on how long a rake has already waited, in its own bid. Zero
    # would let short jobs starve long ones indefinitely; too high collapses
    # Contract Net back into first-come-first-served.
    ageing_weight: float = 0.5
    solver_time_limit_s: float = 20.0
    # expected admin time a rake holds the line for (M4 + M2 join + M5 + M6).
    # The offline solver needs this or it sequences against the wrong
    # service times. Estimated from a pilot run, not from clairvoyance.
    expected_admin_hold_hr: float = 9.0


# ----------------------------------------------------------------------
# EXPERIMENT CONTROL
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class RunConfig:
    n_rakes: int = 50
    n_reps: int = 30
    warmup_rakes: int = 5           # discard: siding starts empty, unrepresentative
    base_seed: int = 1000
    policy: str = "FCFS"


# ----------------------------------------------------------------------
# TOP-LEVEL
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Config:
    resources: ResourceConfig = field(default_factory=ResourceConfig)
    rake: RakeConfig = field(default_factory=RakeConfig)
    shunting: ShuntingConfig = field(default_factory=ShuntingConfig)
    trucks: TruckConfig = field(default_factory=TruckConfig)
    coordination: CoordinationConfig = field(default_factory=CoordinationConfig)
    charges: ChargeConfig = field(default_factory=ChargeConfig)
    run: RunConfig = field(default_factory=RunConfig)

    # Scenario metadata - printed on every result table so no chart is
    # ever ambiguous about which assumptions produced it
    label: str = "baseline"
    notes: str = "Layer 0. All rates ASSUMED. Coal always available (A1)."

    def with_(self, **kw) -> "Config":
        """Return a modified copy. Used for scenario generation:
             cfg.with_(label='2 lines', resources=replace(cfg.resources, loading_lines=2))
        """
        return replace(self, **kw)


def default_config() -> Config:
    return Config()


# Convenience for scenario sweeps ---------------------------------------
def scenario(base: Config, label: str, **overrides) -> Config:
    """Build a named variant by dotted-path overrides, e.g.
         scenario(cfg, '2 lines', **{'resources.loading_lines': 2})
    """
    sub: Dict[str, dict] = {}
    for path, val in overrides.items():
        head, _, tail = path.partition(".")
        if not tail:
            raise ValueError(f"override '{path}' must be dotted, e.g. 'resources.loading_lines'")
        sub.setdefault(head, {})[tail] = val
    kw = {k: replace(getattr(base, k), **v) for k, v in sub.items()}
    return replace(base, label=label, **kw)
