"""
damage.py  -  damaged wagons at the siding (optional; OFF by default).

Two moments, each with its own outcome:

(1) EMPTY RAKE, examined after placement (wear and tear from service):
      each wagon is defective with probability p_defect_per_wagon; a defect is
        minor       no effect on loading
        repairable fixed at the siding by one C&W gang, wagon by wagon
        unfit       cannot be fixed at the siding
      If any wagon is unfit:
        unfit_policy = "detach"       the unfit wagons are detached by the loco
                                      (inside the free-time window) and the rake
                                      loads with the remaining wagons
        unfit_policy = "return_rake"  the whole rake is sent back; the line is
                                      freed; a replacement rake arrives after
                                      replacement_lead_hr and queues again
      Repairs and detachment run IN PARALLEL with the placement paperwork (M4)
      and join before loading, the way stacking permission (M2) does: an
      examination happens while the paperwork is done, not after it.

(2) LOADED RAKE, damage caused by the loading equipment (payloader / JCB),
      found at the outgoing examination and repaired before release, in
      parallel with weighment and release reporting (M5, M6).

Field basis (no rates exist, so every probability and duration is ASSUMED):
  [IRIMEE] Indian Railways Institute of Mechanical & Electrical Engineering,
      "Freight train examination": wagons with rejectable defects are marked
      sick; the side wagon is detached and a fit wagon attached.
  [CAG-2014] CAG Report No. 31 of 2014, Management of Goods Trains, ch. 10:
      a sizeable number of wagons found unloadable at examination, largely
      avoidable with punitive action against private siding owners who mishandle
      wagons; repairs delayed in 86 % of wagons sent to sick lines.
  [IR-COMP 2.3(b)] unfit/sick-wagon allowance (12 h) only for the seven old
      steel plants; [IR-COMP 2.1.2] demurrage on the whole group even if one
      wagon is detained.
  [OP-2022] Orissa Post, 2 May 2022: ~10,000 coal wagons damaged (Jan 2022),
      largely by JCB unloading; repair Rs 5-10 lakh per wagon (severe damage).

Random numbers come from streams keyed on the rake (and attempt), so switching
the module on never changes any draw the rest of the model makes (common
random numbers are preserved), and with enabled=False nothing here is called.
"""
from dataclasses import dataclass

from .config import DamageConfig
from .distributions import RandomStreams


@dataclass
class Inspection:
    n_defect: int = 0
    n_minor: int = 0
    n_repairable: int = 0
    n_unfit: int = 0


class DamageModel:
    def __init__(self, cfg: DamageConfig, streams: RandomStreams):
        if cfg.unfit_policy not in ("detach", "return_rake"):
            raise ValueError(f"unknown unfit_policy {cfg.unfit_policy!r}")
        if not 0.0 <= cfg.share_minor + cfg.share_repairable <= 1.0:
            raise ValueError("share_minor + share_repairable must lie in [0, 1]")
        self.cfg, self.streams = cfg, streams

    # -- empty rake ------------------------------------------------------
    def inspect(self, rake_id: int, wagons: int, attempt: int) -> Inspection:
        c = self.cfg
        rng = self.streams.get(f"dmg_inspect#rake{rake_id}#{attempt}")
        out = Inspection()
        for _ in range(wagons):
            if rng.random() < c.p_defect_per_wagon:
                out.n_defect += 1
                u = rng.random()
                if u < c.share_minor:
                    out.n_minor += 1
                elif u < c.share_minor + c.share_repairable:
                    out.n_repairable += 1
                else:
                    out.n_unfit += 1
        return out

    def repair_hours(self, rake_id: int, n: int, attempt: int) -> float:
        return sum(self.streams.draw(f"dmg_repair#rake{rake_id}#{attempt}#{i}", self.cfg.repair_hr_per_wagon)
                   for i in range(n))

    def detach_hours(self, rake_id: int) -> float:
        return self.streams.draw(f"dmg_detach#rake{rake_id}", self.cfg.detach_hr)

    def lead_hours(self, rake_id: int, attempt: int) -> float:
        return self.streams.draw(f"dmg_lead#rake{rake_id}#{attempt}", self.cfg.replacement_lead_hr)

    # -- loaded rake -----------------------------------------------------
    def loading_damage(self, rake_id: int, wagons: int) -> int:
        rng = self.streams.get(f"dmg_loading#rake{rake_id}")
        return sum(rng.random() < self.cfg.p_loading_damage_per_wagon for _ in range(wagons))

    def loading_repair_hours(self, rake_id: int, n: int) -> float:
        return sum(self.streams.draw(f"dmg_lrepair#rake{rake_id}#{i}", self.cfg.loading_repair_hr_per_wagon)
                   for i in range(n))
