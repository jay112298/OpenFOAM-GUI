"""Unit conversion layer.

The GUI accepts convenient units (mm, in, km/h, RPM, bar, degC). Everything
inside the services is strict SI. Convert once, here, at the API boundary.
"""

from __future__ import annotations

# factor to multiply a value in `unit` by to get SI
_TO_SI: dict[str, float] = {
    # length -> m
    "m": 1.0,
    "mm": 1e-3,
    "cm": 1e-2,
    "in": 0.0254,
    "ft": 0.3048,
    # speed -> m/s
    "m/s": 1.0,
    "km/h": 1.0 / 3.6,
    "mph": 0.44704,
    "kn": 0.514444,
    # pressure -> Pa
    "Pa": 1.0,
    "kPa": 1e3,
    "bar": 1e5,
    "atm": 101325.0,
    # angular velocity -> rad/s
    "rad/s": 1.0,
    "rpm": 2.0 * 3.141592653589793 / 60.0,
    # angle -> rad
    "rad": 1.0,
    "deg": 3.141592653589793 / 180.0,
}


def to_si(value: float, unit: str) -> float:
    """Convert a scalar in `unit` to SI. Temperatures handled separately."""
    if unit in ("degC", "C"):
        return value + 273.15
    if unit in ("K",):
        return value
    try:
        return value * _TO_SI[unit]
    except KeyError as exc:
        raise ValueError(f"Unknown unit: {unit!r}") from exc


def from_si(value: float, unit: str) -> float:
    """Convert an SI scalar back to `unit` for display."""
    if unit in ("degC", "C"):
        return value - 273.15
    if unit in ("K",):
        return value
    try:
        return value / _TO_SI[unit]
    except KeyError as exc:
        raise ValueError(f"Unknown unit: {unit!r}") from exc


def known_units() -> list[str]:
    return [*_TO_SI.keys(), "degC", "K"]
