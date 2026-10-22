"""
eventlog.py  -  The single source of truth.

Design rule that makes the whole project extensible:

    THE SIMULATION ONLY RECORDS TIMESTAMPED EVENTS.
    EVERY NUMBER IN EVERY RESULT IS DERIVED FROM THIS LOG AFTERWARDS.

Consequences:
  * changing an objective changes only the accounting module, never the model
  * per-party attribution is free: every event already carries its owner
  * verification is possible: the log can be checked for ordering violations
  * when real FOIS/TMS data arrives it has the same shape as this log,
    so the accounting code runs unchanged on real data
"""
from dataclasses import dataclass, asdict
from typing import List, Optional
import pandas as pd


# The four parties. Every event is attributed to exactly one.
PARTY_TERMINAL = "terminal"
PARTY_RAILWAY = "railway"
PARTY_TRANSPORTER = "transporter"
PARTY_CLIENT = "client"
PARTY_SYSTEM = "system"          # model bookkeeping, not a real actor

PARTIES = (PARTY_TERMINAL, PARTY_RAILWAY, PARTY_TRANSPORTER, PARTY_CLIENT)

# Event kinds. 'physical' now; 'admin' arrives in Layer 2.
KIND_PHYSICAL = "physical"
KIND_ADMIN = "admin"
KIND_WAIT = "wait"


@dataclass
class Event:
    t: float                  # simulation clock (hours from t=0)
    entity_type: str          # 'rake', later 'truck'
    entity_id: int
    name: str                 # canonical event name, see EVENTS below
    kind: str                 # physical / admin / wait
    owner: str                # which party is responsible for this step
    resource: Optional[str] = None    # resource seized/released, if any
    detail: str = ""


# Canonical physical event names for a rake at a siding.
# Order matters: verify.py checks the log respects it.
RAKE_EVENT_ORDER = [
    "rake_arrive",        # reaches the serving station
    "queue_start",        # begins waiting for a line + loco
    "placement_start",    # loco couples, movement into the siding begins
    "placed",             # ON the loading line  -> FREE TIME CLOCK STARTS
    "loading_start",
    "loading_end",
    "released",           # release reported     -> FREE TIME CLOCK STOPS
    "removal_start",
    "removed",            # back on the main line, loading line FREED
    "departed",           # RR issued, freight settled, rake leaves the station
]


class EventLog:
    def __init__(self):
        self._rows: List[Event] = []

    def add(self, t, entity_type, entity_id, name, kind, owner,
            resource=None, detail=""):
        self._rows.append(Event(round(float(t), 6), entity_type, int(entity_id),
                                name, kind, owner, resource, detail))

    def to_frame(self) -> pd.DataFrame:
        if not self._rows:
            return pd.DataFrame(columns=[f.name for f in Event.__dataclass_fields__.values()])
        return pd.DataFrame([asdict(r) for r in self._rows])

    def pivot_rakes(self) -> pd.DataFrame:
        """One row per rake, one column per event name, value = timestamp.
        This is the table the accounting layer consumes."""
        df = self.to_frame()
        if df.empty:
            return pd.DataFrame()
        r = df[df.entity_type == "rake"]
        wide = r.pivot_table(index="entity_id", columns="name",
                             values="t", aggfunc="first")
        for c in RAKE_EVENT_ORDER:
            if c not in wide.columns:
                wide[c] = pd.NA
        wide = wide[RAKE_EVENT_ORDER]
        wide.index.name = "rake"
        return wide.reset_index()

    def __len__(self):
        return len(self._rows)
