"""Dry run: two rakes, one line, FCFS, administrative chain on, no trucks.

    python tools/dry_run_two_rakes.py [seed]

Prints every event in time order with the file and function that produced
it, so you can follow one replication through the code by hand. Seed 7 is
the example walked through in the chat (rake 1 books first but its M1 is
rejected once, so rake 2 reaches the terminal first).
"""
import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtsim.config import default_config
from rtsim.terminal import simulate
from rtsim.admin import default_steps
from rtsim import policies

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
cfg = default_config()
cfg = replace(cfg, run=replace(cfg.run, n_rakes=2, warmup_rakes=0))
log, rakes, term = simulate(cfg, policies.build("FCFS", cfg), seed=seed,
                            admin_steps=default_steps())

SOURCE = {
    "rake_arrive": "terminal.py  Terminal.handle()",
    "queue_start": "terminal.py  Terminal.handle()",
    "placement_start": "terminal.py  Terminal.handle()  [after _dispatch() awards a line]",
    "placed": "terminal.py  Terminal.handle()  <- FREE TIME STARTS",
    "loading_start": "terminal.py  Terminal.handle()",
    "loading_end": "terminal.py  Terminal.handle()",
    "released": "terminal.py  Terminal.handle()  <- FREE TIME STOPS",
    "removal_start": "terminal.py  Terminal.handle()",
    "removed": "terminal.py  Terminal.handle()  (line freed, _dispatch() re-runs)",
    "departed": "terminal.py  Terminal.handle()  (after M7 joined)",
}

df = log.to_frame().sort_values("t")
print(f"{'t(h)':>7}  {'entity':<8} {'event':<22} code location")
print("-" * 86)
for _, r in df.iterrows():
    if r["kind"] == "admin":
        loc = f"admin.py  AdminChain.run_step('{r['name'].split('_')[1]}')"
    else:
        loc = SOURCE.get(r["name"], "terminal.py  Terminal.handle()")
    tag = f"[{r.entity_type}{r.entity_id}]"
    print(f"{r['t']:7.2f}  {tag:<8} {r['name']:<22} {loc}")
