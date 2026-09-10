"""y+ -> first-cell-height calculator.

Flat-plate turbulent correlation, used to size the first cell so the chosen
wall treatment (wall functions vs low-Re) is in its valid y+ band.

    Re_L = U L / nu
    Cf   = 0.058 * Re_L^-0.2          (turbulent flat plate)
    tau_w = 0.5 * Cf * rho * U^2
    u_tau = sqrt(tau_w / rho)
    y1   = yplus * nu / u_tau         (wall-adjacent cell-centre distance)

For a cell-centred FV mesh the first cell *height* ~ 2 * y1.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class YPlusEstimate:
    first_cell_centre: float  # y1 [m]
    first_cell_height: float  # ~2 * y1 [m]
    cf: float
    u_tau: float
    reynolds: float


def first_cell_height(
    velocity: float, length: float, nu: float, rho: float, yplus_target: float
) -> YPlusEstimate:
    if min(velocity, length, nu, rho, yplus_target) <= 0:
        raise ValueError("all inputs must be > 0")
    re = velocity * length / nu
    cf = 0.058 * re**-0.2
    tau_w = 0.5 * cf * rho * velocity**2
    u_tau = (tau_w / rho) ** 0.5
    y1 = yplus_target * nu / u_tau
    return YPlusEstimate(
        first_cell_centre=y1,
        first_cell_height=2 * y1,
        cf=cf,
        u_tau=u_tau,
        reynolds=re,
    )
