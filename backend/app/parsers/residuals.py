"""Parse simpleFoam/pimpleFoam log output for residuals, continuity, Courant,
live force coefficients, and pipeline stage banners (for the GUI terminal).

Lines of interest:
  smoothSolver:  Solving for Ux, Initial residual = 0.0123, Final residual = ...
  time step continuity errors : sum local = 1e-5, global = -2e-7, cumulative = ...
  Courant Number mean: 0.2 max: 4.1
  Cd    = 0.0123        (forceCoeffs function object)
  Cl    = 0.45
  [3/5] checkMesh       (our Allrun banners)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_RES = re.compile(
    r"Solving for (\w+),\s*Initial residual = ([\d.eE+-]+),\s*Final residual = ([\d.eE+-]+)"
)
_TIME = re.compile(r"^Time = ([\d.eE+-]+)")
_CONT = re.compile(r"continuity errors : sum local = ([\d.eE+-]+), global = ([\d.eE+-]+)")
_COURANT = re.compile(r"Courant Number mean: ([\d.eE+-]+) max: ([\d.eE+-]+)")
_CL = re.compile(r"^\s*Cl\s*=\s*([\d.eE+-]+)")
_CD = re.compile(r"^\s*Cd\s*=\s*([\d.eE+-]+)")
_STAGE = re.compile(r"^\[(\d+)/(\d+)\]\s*(.+)")


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


def parse_continuity(line: str) -> dict | None:
    m = _CONT.search(line)
    if not m:
        return None
    return {"local": float(m.group(1)), "global": float(m.group(2))}


def parse_courant(line: str) -> dict | None:
    m = _COURANT.search(line)
    if not m:
        return None
    return {"mean": float(m.group(1)), "max": float(m.group(2))}


def parse_cl(line: str) -> float | None:
    m = _CL.match(line)
    return float(m.group(1)) if m else None


def parse_cd(line: str) -> float | None:
    m = _CD.match(line)
    return float(m.group(1)) if m else None


def parse_stage(line: str) -> dict | None:
    m = _STAGE.match(line.strip())
    if not m:
        return None
    return {"index": int(m.group(1)), "total": int(m.group(2)), "label": m.group(3).strip()}


def is_diverged(point: ResidualPoint, threshold: float = 1e6) -> bool:
    """Residual blowing up = diverging."""
    return point.initial > threshold or point.initial != point.initial  # NaN guard
