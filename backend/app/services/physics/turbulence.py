"""Turbulence inlet value computation.

Locked rule (PLAN.md): turbulence inlet k / omega / epsilon are ALWAYS computed
from turbulence intensity + length scale, never hand-typed. This module is the
single source of those numbers.

Standard relations (k-omega SST / k-epsilon):
    k       = 1.5 * (U * I)^2
    epsilon = C_mu^0.75 * k^1.5 / L
    omega   = k^0.5 / (C_mu^0.25 * L)        [= epsilon / (C_mu * k)]
with C_mu = 0.09.
"""

from __future__ import annotations

from dataclasses import dataclass

C_MU = 0.09


@dataclass(frozen=True)
class TurbulenceInlet:
    k: float
    omega: float
    epsilon: float
    intensity: float
    length_scale: float


TRANSITION_MODELS = {"kOmegaSSTLM"}


def re_theta_t(intensity: float) -> float:
    """Inlet transition momentum-thickness Reynolds number (Langtry–Menter).

    Empirical correlation used to set the ReThetat inlet for kOmegaSSTLM,
    with Tu in percent:
        Tu <= 1.3 :  1173.51 - 589.428*Tu + 0.2196/Tu^2
        Tu >  1.3 :  331.50*(Tu - 0.5658)^-0.671
    The low-Tu branch blows up as Tu -> 0, so Tu is clamped to 0.027%
    (the usual practical floor).
    """
    tu = max(intensity * 100.0, 0.027)
    if tu <= 1.3:
        return 1173.51 - 589.428 * tu + 0.2196 / tu**2
    return 331.50 * (tu - 0.5658) ** -0.671


def turbulence_inlet(velocity: float, intensity: float, length_scale: float) -> TurbulenceInlet:
    """Compute inlet k, omega, epsilon.

    velocity      freestream speed [m/s]
    intensity     turbulence intensity as a fraction (0.05 == 5%)
    length_scale  turbulent length scale [m] (often ~0.07 * char. length, or
                  the boundary-layer / inlet height)
    """
    if velocity <= 0:
        raise ValueError("velocity must be > 0")
    if not (0 < intensity < 1):
        raise ValueError("intensity is a fraction in (0, 1), e.g. 0.05 for 5%")
    if length_scale <= 0:
        raise ValueError("length_scale must be > 0")

    k = 1.5 * (velocity * intensity) ** 2
    epsilon = C_MU**0.75 * k**1.5 / length_scale
    omega = k**0.5 / (C_MU**0.25 * length_scale)
    return TurbulenceInlet(
        k=k, omega=omega, epsilon=epsilon, intensity=intensity, length_scale=length_scale
    )
