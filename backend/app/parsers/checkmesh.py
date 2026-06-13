"""Parse checkMesh log output into quality metrics for the validation engine."""

from __future__ import annotations

import re

_NONORTHO = re.compile(r"Max non-orthogonality = ([\d.eE+-]+)")
_SKEW = re.compile(r"Max skewness = ([\d.eE+-]+)")
_ASPECT = re.compile(r"Max aspect ratio = ([\d.eE+-]+)")
_CELLS = re.compile(r"cells:\s+(\d+)")


def parse(log: str) -> dict:
    metrics: dict = {"meshOK": "Mesh OK" in log or "Failed" not in log}
    for key, rx in (
        ("maxNonOrtho", _NONORTHO),
        ("maxSkewness", _SKEW),
        ("maxAspectRatio", _ASPECT),
        ("nCells", _CELLS),
    ):
        m = rx.search(log)
        if m:
            val = m.group(1)
            metrics[key] = int(val) if key == "nCells" else float(val)
    metrics["meshOK"] = "***" not in log and "Failed" not in log
    return metrics
