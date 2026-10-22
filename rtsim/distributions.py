"""
distributions.py  -  All randomness enters the model through here.

Two rules that make results reproducible and comparisons fair:

  1. NOTHING calls random.* directly. Everything draws from a Dist.
  2. Each source of randomness gets its OWN stream (common random numbers).
     Then when you change a policy, the arrival times and loading rates are
     bit-for-bit identical, so any difference in the result is caused by the
     policy and not by luck. This is what makes the paired comparison valid.
"""
from dataclasses import dataclass
from typing import Dict
import hashlib
import math
import random


@dataclass(frozen=True)
class Dist:
    """A named distribution. Parameters are given on the REAL scale
    (a lognormal is specified by the mean and sd you actually want to see,
    not by mu and sigma of the underlying normal)."""
    kind: str
    mean: float = 0.0
    sd: float = 0.0
    value: float = 0.0
    low: float = 0.0
    high: float = 0.0
    p: float = 0.0

    def draw(self, rng: random.Random) -> float:
        k = self.kind
        if k == "const":
            return self.value
        if k == "exp":
            return rng.expovariate(1.0 / self.mean)
        if k == "logn":
            # right-skewed, strictly positive: the standard choice for
            # service durations. Cannot produce a negative time, unlike normal.
            m, s = self.mean, self.sd
            if s <= 0:
                return m
            mu = math.log(m * m / math.sqrt(s * s + m * m))
            sg = math.sqrt(math.log(1.0 + (s / m) ** 2))
            return rng.lognormvariate(mu, sg)
        if k == "uniform":
            return rng.uniform(self.low, self.high)
        if k == "tri":
            return rng.triangular(self.low, self.high, self.mean)
        if k == "erlang":
            # sum of k exponentials; k = (mean/sd)^2. Used for gate processing.
            kk = max(1, int(round((self.mean / self.sd) ** 2))) if self.sd > 0 else 1
            return sum(rng.expovariate(kk / self.mean) for _ in range(kk))
        if k == "bernoulli":
            return 1.0 if rng.random() < self.p else 0.0
        raise ValueError(f"unknown distribution kind: {k}")


class RandomStreams:
    """One independent RNG per named purpose, all derived from a single
    replication seed. Adding a new stream later does not disturb existing
    ones, so results stay comparable across code versions."""

    def __init__(self, seed: int):
        self.seed = seed
        self._streams: Dict[str, random.Random] = {}

    @staticmethod
    def substream_seed(seed: int, name: str) -> int:
        """Deterministic sub-seed from (seed, name).

        NOTE: Python's built-in hash() is salted per process for strings, so
        using it here made results irreproducible ACROSS runs while looking
        perfectly deterministic WITHIN a run. Every number in a thesis must
        reproduce on someone else's machine, so the digest is explicit.
        """
        h = hashlib.blake2b(f"{seed}:{name}".encode(), digest_size=8).digest()
        return int.from_bytes(h, "big") % (2 ** 31)

    def get(self, name: str) -> random.Random:
        if name not in self._streams:
            # a stable sub-seed per purpose, so the 'loading' stream is
            # always the same regardless of call order or of which other
            # streams exist. Adding a new stream later disturbs nothing.
            self._streams[name] = random.Random(
                self.substream_seed(self.seed, name))
        return self._streams[name]

    def draw(self, name: str, dist: Dist) -> float:
        return dist.draw(self.get(name))
