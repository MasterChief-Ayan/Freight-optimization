"""rtsim - Rail freight terminal simulation for MTP.

Layer 0 (this release): entities, resources, physical event chain,
decision hook, IR charge accounting, verification, replications.

Later layers slot in without changing anything below them:
  Layer 1  administrative chain (calendars, rework, gating)
  Layer 2  truck / gate side and appointment system
  Layer 3  CP-SAT optimiser and agent coordination
  Layer 4  policy scenarios and comparison study
"""
__version__ = "0.1.0"
