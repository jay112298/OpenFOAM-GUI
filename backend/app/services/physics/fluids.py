"""Fluid property presets. All SI.

nu = kinematic viscosity [m^2/s], rho = density [kg/m^3],
a = speed of sound [m/s] (for Mach estimates).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fluid:
    name: str
    nu: float
    rho: float
    a: float  # speed of sound; used only for Mach estimate


FLUIDS: dict[str, Fluid] = {
    "air": Fluid(name="air", nu=1.5e-5, rho=1.225, a=340.0),
    "water": Fluid(name="water", nu=1.0e-6, rho=998.0, a=1481.0),
}


def get_fluid(name: str) -> Fluid:
    if name not in FLUIDS:
        raise ValueError(f"Unknown fluid: {name!r}. Known: {list(FLUIDS)}")
    return FLUIDS[name]


def reynolds(velocity: float, length: float, nu: float) -> float:
    return velocity * length / nu


def mach(velocity: float, a: float) -> float:
    return velocity / a
