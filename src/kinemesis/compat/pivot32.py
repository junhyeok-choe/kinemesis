"""The ``pivot32`` profile: float32 rounding of joint ends, as observed in the upstream reference.

Used only to compare against oracle vectors (see ``fixtures/upstream-oracle``). It is not part of
the engine's semantics, which are float64 throughout.
"""

from __future__ import annotations

import math
import struct


def fround(x: float) -> float:
    """Round a float64 to the nearest float32 (like JavaScript ``Math.fround``)."""
    try:
        return struct.unpack("<f", struct.pack("<f", x))[0]  # type: ignore[no-any-return]
    except OverflowError:
        return math.copysign(math.inf, x)


def shortest_atan2(a: float) -> float:
    """Upstream's angle wrap, ``atan2(sin a, cos a)``: ties at exactly +-pi depend on rounding."""
    return math.atan2(math.sin(a), math.cos(a))
