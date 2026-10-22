"""Waiting-time decomposition using the valid lower bound."""
import _bootstrap  # noqa: F401  repo root on sys.path; outputs go to results/

from dataclasses import replace
import statistics as st, math
import pandas as pd
from rtsim.config import default_config
from rtsim.distributions import Dist, RandomStreams
from rtsim.terminal import simulate, generate_rakes
from rtsim.accounting import rake_table
from rtsim.admin import default_steps, remove_calendar, no_rework
from rtsim.optimiser import waiting_lower_bound
from rtsim import policies

K = ["M1","M2","M3","M4","M5","M6","M7"]
cfg = default_config()
cfg = replace(cfg, rake=replace(cfg.rake, arrival_gap=Dist("exp", mean=22.0)),
              run=replace(cfg.run, n_rakes=25, warmup_rakes=3))
full = default_steps()
flat = no_rework(K, remove_calendar(K, full))
nocal = remove_calendar(K, full)
norw  = no_rework(K, full)

rows = []
for rep in range(12):
    seed = 1000 + rep
    rk = generate_rakes(cfg, RandomStreams(seed))
    def w(steps):
        lg, _, _ = simulate(cfg, policies.build("FCFS", cfg), seed,
                            rakes=rk, admin_steps=steps)
        t = rake_table(lg, cfg); t = t[t.rake > cfg.run.warmup_rakes]
        return t.wait_hr.mean(), (t.removed - t.placement_start).mean()
    w_full, h_full = w(full)
    w_flat, h_flat = w(flat)
    w_nocal, _ = w(nocal)
    w_norw, _  = w(norw)
    pl, _, _ = simulate(cfg, policies.build("FCFS", cfg), seed,
                        rakes=rk, admin_steps=flat)
    pt = rake_table(pl, cfg)
    mh = dict(zip(pt.rake.astype(int), (pt.removed - pt.placement_start).astype(float)))
    mh = {r.id: mh.get(r.id, r.place_hr + r.load_hr + r.remove_hr) for r in rk}
    lb, _ = waiting_lower_bound(cfg, rk, min_hold=mh, time_limit_s=8.0)
    rows.append(dict(full=w_full, flat=w_flat, nocal=w_nocal, norw=w_norw,
                     bound=lb, hold_full=h_full, hold_flat=h_flat))
d = pd.DataFrame(rows)
def ci(v): return st.mean(v), 1.96*st.stdev(v)/math.sqrt(len(v))
print("\n" + "="*78)
print("WAITING-TIME DECOMPOSITION  (12 reps x 25 rakes, gap 22 h, FCFS)")
print("="*78)
for lab, col in [("as modelled (full admin)","full"),
                 ("office hours removed (24/7)","nocal"),
                 ("rework removed","norw"),
                 ("both removed","flat"),
                 ("+ optimal sequencing (LOWER BOUND)","bound")]:
    m,h = ci(d[col].tolist())
    print(f"  {lab:<38} {m:7.2f} +/-{h:5.2f} h")
mf,_ = ci(d.full.tolist()); mb,_ = ci(d.bound.tolist())
mc,_ = ci(d.nocal.tolist()); mr,_ = ci(d.norw.tolist()); mfl,_ = ci(d.flat.tolist())
print("-"*78)
print(f"  office hours alone        {100*(mf-mc)/mf:5.1f}% of all waiting")
print(f"  rework alone              {100*(mf-mr)/mf:5.1f}%")
print(f"  both together             {100*(mf-mfl)/mf:5.1f}%")
print(f"  sequencing, at very best  {100*(mfl-mb)/mf:5.1f}%")
print(f"  irreducible congestion    {100*mb/mf:5.1f}%")
hf,_ = ci(d.hold_full.tolist()); hl,_ = ci(d.hold_flat.tolist())
print(f"\n  line occupancy per rake: {hf:.1f} h as modelled -> {hl:.1f} h flat")
print("="*78)
d.round(3).to_csv("layer3_E11_decomposition.csv", index=False)
