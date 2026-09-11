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


# --- ideal-gas air, used by the compressible path -------------------------
R_SPECIFIC = 287.058  # J/(kg K) for air
GAMMA = 1.4
# Sutherland's law constants for air, as OpenFOAM expects them
SUTHERLAND_AS = 1.4792e-06
SUTHERLAND_TS = 116.0
CP_AIR = 1004.5  # J/(kg K)
MOL_WEIGHT_AIR = 28.96


@dataclass(frozen=True)
class GasState:
    """Air treated as an ideal gas at a given static pressure and temperature."""

    pressure: float      # [Pa]
    temperature: float   # [K]
    density: float       # [kg/m^3]
    mu: float            # dynamic viscosity [Pa s]
    nu: float            # kinematic viscosity [m^2/s]
    sound_speed: float   # [m/s]


def sutherland_mu(temperature: float) -> float:
    """Dynamic viscosity from Sutherland's law — the same relation OpenFOAM
    evaluates from the As/Ts pair we write into thermophysicalProperties."""
    return SUTHERLAND_AS * temperature**1.5 / (temperature + SUTHERLAND_TS)


def gas_state(pressure: float = 101325.0, temperature: float = 288.15) -> GasState:
    density = pressure / (R_SPECIFIC * temperature)
    mu = sutherland_mu(temperature)
    return GasState(
        pressure=pressure,
        temperature=temperature,
        density=density,
        mu=mu,
        nu=mu / density,
        sound_speed=(GAMMA * R_SPECIFIC * temperature) ** 0.5,
    )
