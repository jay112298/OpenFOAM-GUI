"""Validation benchmarks: bundled reference data to verify the toolchain.

NACA 0012 lift/drag vs angle of attack. Reference values are representative
of high-Reynolds (Re ~ 6e6) measurements (Abbott & von Doenhoff / NASA TMR
Ladson), used to sanity-check that a GUI-built case reproduces known data.
"""

from __future__ import annotations

# alpha [deg]: (Cl, Cd) — attached-flow region, Re ~ 6e6, NACA 0012
NACA0012_RE6E6 = {
    0.0: (0.0000, 0.0080),
    2.0: (0.2200, 0.0083),
    4.0: (0.4400, 0.0087),
    6.0: (0.6600, 0.0095),
    8.0: (0.8600, 0.0108),
    10.0: (1.0500, 0.0125),
    12.0: (1.2200, 0.0150),
    14.0: (1.3500, 0.0190),
}

BENCHMARKS = {
    "naca0012": {
        "id": "naca0012",
        "name": "NACA 0012 lift/drag polar",
        "reynolds": 6e6,
        "source": "Abbott & von Doenhoff / NASA TMR (Ladson)",
        "reference": [
            {"alpha": a, "cl": cl, "cd": cd} for a, (cl, cd) in sorted(NACA0012_RE6E6.items())
        ],
    }
}


def list_benchmarks() -> list[dict]:
    return [{"id": b["id"], "name": b["name"], "reynolds": b["reynolds"]} for b in BENCHMARKS.values()]


def get_benchmark(benchmark_id: str) -> dict | None:
    return BENCHMARKS.get(benchmark_id)
