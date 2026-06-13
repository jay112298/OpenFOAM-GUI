"""Parse simpleFoam/pimpleFoam log output for residuals and convergence.

Line of interest:
  smoothSolver:  Solving for Ux, Initial residual = 0.0123, Final residual = ...
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_RES = re.compile(
    r"Solving for (\w+),\s*Initial residual = ([\d.eE+-]+),\s*Final residual = ([\d.eE+-]+)"
)
_TIME = re.compile(r"^Time = ([\d.eE+-]+)")


@dataclass
class ResidualPoint:
    field: str
    initial: float
    final: float


def parse_line(line: str) -> ResidualPoint | None:
    m = _RES.search(line)
    if not m:
        return None
    return ResidualPoint(field=m.group(1), initial=float(m.group(2)), final=float(m.group(3)))


def parse_time(line: str) -> float | None:
    m = _TIME.match(line.strip())
    return float(m.group(1)) if m else None


def is_diverged(point: ResidualPoint, threshold: float = 1e6) -> bool:
    """Residual blowing up = diverging."""
    return point.initial > threshold or point.initial != point.initial  # NaN guard
