"""Fan / compressor performance from the passage function-object output.

One passage is solved, so every extensive quantity is scaled by the blade count
to get the whole machine:

    Q       = |sum(phi)|_inlet * n_blades          volumetric flow  [m^3/s]
    dp0     = p0_outlet - p0_inlet                 total pressure rise [Pa]
    torque  = |M_z| on the blade * n_blades        shaft torque [N m]
    P_shaft = omega * torque                       [W]
    P_air   = dp0 * Q                              [W]
    eta     = P_air / P_shaft                      total-to-total efficiency

Also reported are the two non-dimensional numbers a fan curve is plotted in:
the flow coefficient phi = Va / U_tip and the pressure coefficient
psi = dp0 / (rho U_tip^2).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path

_POST = "postProcessing"


@dataclass
class OperatingPoint:
    time: float
    flow_rate: float          # [m^3/s], whole machine
    total_pressure_rise: float  # [Pa]
    torque: float             # [N m], whole machine
    shaft_power: float        # [W]
    air_power: float          # [W]
    efficiency: float | None  # [-] total-to-total
    swirl: float              # mass-flow-free area-average exit swirl [m/s]
    flow_coefficient: float
    pressure_coefficient: float


def _series(case_dir: Path, name: str) -> dict[float, list[float]]:
    """Read a function object's .dat output as {time: [values]}.

    Function objects restarted at a later time write into a new sub-directory;
    later files win, which is what a restarted run should show.
    """
    root = case_dir / _POST / name
    if not root.is_dir():
        return {}
    out: dict[float, list[float]] = {}
    for start in sorted(root.iterdir(), key=lambda p: _as_float(p.name, 0.0)):
        for dat in sorted(start.glob("*.dat")):
            for line in dat.read_text(errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                nums = _numbers(line)
                if len(nums) >= 2:
                    out[nums[0]] = nums[1:]
    return out


def _as_float(text: str, default: float) -> float:
    try:
        return float(text)
    except ValueError:
        return default


def _numbers(line: str) -> list[float]:
    """Every number on the line. Vectors are written as `(x y z)` — the
    parentheses are just separators here."""
    values: list[float] = []
    for token in line.replace("(", " ").replace(")", " ").split():
        try:
            values.append(float(token))
        except ValueError:
            return values if values else []
    return values


def history(case_dir: Path, spec: dict) -> list[OperatingPoint]:
    from app.services.generators.axial_fan_case import AxialFanParams, derive

    params = AxialFanParams.from_spec(spec)
    st = derive(params)
    n = int(params.n_blades)
    rho, omega, u_tip = st.density, st.shaft_omega, st.tip_speed

    flow = _series(case_dir, "flowRate")
    p_in = _series(case_dir, "p0Inlet")
    p_out = _series(case_dir, "p0Outlet")
    u_out = _series(case_dir, "outletU")
    moment = _series(case_dir, "bladeForces")

    points: list[OperatingPoint] = []
    for t in sorted(set(flow) & set(p_in) & set(p_out)):
        q = abs(flow[t][0]) * n
        dp0 = p_out[t][0] - p_in[t][0]
        # moment.dat columns: total_(x y z), pressure_(x y z), viscous_(x y z).
        # The fluid resists rotation, so M_z is negative; the shaft supplies it.
        mz = moment.get(t, [0.0, 0.0, 0.0])
        torque = abs(mz[2] if len(mz) > 2 else 0.0) * n
        shaft = omega * torque
        air = dp0 * q
        swirl = _swirl(u_out.get(t))
        points.append(
            OperatingPoint(
                time=t,
                flow_rate=q,
                total_pressure_rise=dp0,
                torque=torque,
                shaft_power=shaft,
                air_power=air,
                efficiency=(air / shaft) if shaft > 1e-9 else None,
                swirl=swirl,
                flow_coefficient=params.axial_velocity / u_tip if u_tip else 0.0,
                pressure_coefficient=dp0 / (rho * u_tip**2) if u_tip else 0.0,
            )
        )
    return points


def _swirl(u: list[float] | None) -> float:
    """Tangential component of the area-averaged exit velocity.

    The passage is centred on theta = 0, so the tangential direction there is
    +y and the in-plane magnitude is a good proxy for the mean swirl.
    """
    if not u or len(u) < 3:
        return 0.0
    return math.copysign(math.hypot(u[0], u[1]), u[1])


def performance(case_dir: Path, spec: dict) -> dict:
    points = history(case_dir, spec)
    last = points[-1] if points else None
    return {
        "history": [asdict(p) for p in points],
        "latest": asdict(last) if last else None,
    }
