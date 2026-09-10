"""Parse force coefficient output written by the forceCoeffs function object.

OpenFOAM v2506 writes postProcessing/forceCoeffs/<startTime>/coefficient.dat
with a header naming the columns (Time Cd Cs Cl CmRoll CmPitch CmYaw ...).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ForceCoeffs:
    time: float
    cl: float
    cd: float
    cm: float | None = None


def _find_dat(case_dir: Path) -> Path | None:
    base = case_dir / "postProcessing" / "forceCoeffs"
    if not base.is_dir():
        return None
    for name in ("coefficient.dat", "forceCoeffs.dat"):
        hits = sorted(base.glob(f"*/{name}"))
        if hits:
            return hits[-1]
    return None


def _columns(path: Path) -> list[str]:
    cols: list[str] = []
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            tokens = line.lstrip("#").split()
            if "Time" in tokens or "time" in [t.lower() for t in tokens]:
                cols = tokens
        else:
            break
    return cols


def history(case_dir: Path) -> list[ForceCoeffs]:
    path = _find_dat(case_dir)
    if path is None:
        return []
    cols = [c.lower() for c in _columns(path)]

    def idx(*names: str) -> int | None:
        for n in names:
            if n in cols:
                return cols.index(n)
        return None

    i_time = idx("time") or 0
    i_cl = idx("cl")
    i_cd = idx("cd")
    i_cm = idx("cmpitch", "cm")

    out: list[ForceCoeffs] = []
    for line in path.read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        vals = line.split()
        try:
            out.append(
                ForceCoeffs(
                    time=float(vals[i_time]),
                    cl=float(vals[i_cl]) if i_cl is not None else float("nan"),
                    cd=float(vals[i_cd]) if i_cd is not None else float("nan"),
                    cm=float(vals[i_cm]) if i_cm is not None else None,
                )
            )
        except (ValueError, IndexError):
            continue
    return out


def latest(case_dir: Path) -> ForceCoeffs | None:
    h = history(case_dir)
    return h[-1] if h else None
