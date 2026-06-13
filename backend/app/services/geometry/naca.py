"""NACA 4- and 5-digit airfoil generation.

Produces airfoil coordinates (cosine-spaced, closed trailing edge) and can
extrude them to a thin-span STL solid for snappyHexMesh (2D case: span in z
with empty front/back patches).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# closed trailing edge coefficient (vs -0.1015 for open TE)
_A4_CLOSED = -0.1036


@dataclass
class Airfoil:
    designation: str
    chord: float
    x: np.ndarray  # surface x, ordered upper TE -> LE -> lower TE
    y: np.ndarray

    @property
    def coordinates(self) -> list[list[float]]:
        return [[float(xi), float(yi)] for xi, yi in zip(self.x, self.y)]


def _thickness(x: np.ndarray, t: float) -> np.ndarray:
    return (
        5
        * t
        * (
            0.2969 * np.sqrt(x)
            - 0.1260 * x
            - 0.3516 * x**2
            + 0.2843 * x**3
            + _A4_CLOSED * x**4
        )
    )


def _camber4(x: np.ndarray, m: float, p: float) -> tuple[np.ndarray, np.ndarray]:
    yc = np.zeros_like(x)
    dyc = np.zeros_like(x)
    if m > 0 and p > 0:
        fore = x < p
        aft = ~fore
        yc[fore] = m / p**2 * (2 * p * x[fore] - x[fore] ** 2)
        dyc[fore] = 2 * m / p**2 * (p - x[fore])
        yc[aft] = m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x[aft] - x[aft] ** 2)
        dyc[aft] = 2 * m / (1 - p) ** 2 * (p - x[aft])
    return yc, dyc


def _camber5(x: np.ndarray, cl: float, p: float) -> tuple[np.ndarray, np.ndarray]:
    # Standard (non-reflexed) 5-digit mean line. Tabulated m, k1 by camber pos.
    table = {
        0.05: (0.0580, 361.4),
        0.10: (0.1260, 51.64),
        0.15: (0.2025, 15.957),
        0.20: (0.2900, 6.643),
        0.25: (0.3910, 3.230),
    }
    mm, k1 = min(table.items(), key=lambda kv: abs(kv[0] - p))[1]
    scale = cl / 0.3  # tables are for design Cl = 0.3
    yc = np.zeros_like(x)
    dyc = np.zeros_like(x)
    fore = x < mm
    aft = ~fore
    yc[fore] = k1 / 6 * (x[fore] ** 3 - 3 * mm * x[fore] ** 2 + mm**2 * (3 - mm) * x[fore])
    dyc[fore] = k1 / 6 * (3 * x[fore] ** 2 - 6 * mm * x[fore] + mm**2 * (3 - mm))
    yc[aft] = k1 / 6 * mm**3 * (1 - x[aft])
    dyc[aft] = -k1 / 6 * mm**3
    return yc * scale, dyc * scale


def generate(designation: str, chord: float = 1.0, n: int = 120) -> Airfoil:
    """Generate a NACA 4- or 5-digit airfoil.

    designation  e.g. "0012", "4412", "23012"
    chord        chord length [m]
    n            points per surface
    """
    d = designation.strip().upper().removeprefix("NACA").strip()
    if not d.isdigit() or len(d) not in (4, 5):
        raise ValueError(f"Expected a 4- or 5-digit NACA code, got {designation!r}")

    beta = np.linspace(0.0, math.pi, n)
    xc = 0.5 * (1 - np.cos(beta))  # cosine spacing, dense at LE/TE

    if len(d) == 4:
        m = int(d[0]) / 100.0
        p = int(d[1]) / 10.0
        t = int(d[2:]) / 100.0
        yc, dyc = _camber4(xc, m, p)
    else:
        cl = int(d[0]) * 0.15  # design lift coeff
        p = int(d[1:3]) / 200.0  # position of max camber
        t = int(d[3:]) / 100.0
        yc, dyc = _camber5(xc, cl, p)

    yt = _thickness(xc, t)
    theta = np.arctan(dyc)

    xu = xc - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = xc + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)

    # order: upper TE -> LE, then lower LE -> TE (skip duplicate LE point)
    x = np.concatenate([xu[::-1], xl[1:]]) * chord
    y = np.concatenate([yu[::-1], yl[1:]]) * chord
    return Airfoil(designation=d, chord=chord, x=x, y=y)


def export_stl(airfoil: Airfoil, path: Path, span: float | None = None) -> Path:
    """Extrude the airfoil a small span in z and write a watertight STL solid."""
    import cadquery as cq

    span = span if span is not None else 0.1 * airfoil.chord
    pts = [(float(xi), float(yi)) for xi, yi in zip(airfoil.x, airfoil.y)]
    solid = cq.Workplane("XY").polyline(pts).close().extrude(span)
    path.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(solid, str(path))
    return path
