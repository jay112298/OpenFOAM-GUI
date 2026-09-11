"""Parameter sweeps: clone a base case spec across one or two parameters,
creating child cases. Aggregation reads each child's results — a polar for
external aero, a fan/compressor map for turbomachinery.
"""

from __future__ import annotations

import copy
import threading
import time
import uuid
from datetime import datetime, timezone

from sqlmodel import Session

from app.models.case import Case, CaseStatus
from app.models.run import Run, RunStatus, Sweep

# sweep_id -> {"running": bool, "current": case_id | None, "message": str}
_sweep_state: dict[str, dict] = {}

# Sweeping either of these moves the fan's operating point. The blade itself
# must not move with it, or every point of the map would be a different machine.
_TURBO_OPERATING = ("physics.reference.rpm", "physics.reference.axial_velocity")
_DESIGN_PINS = {
    "physics.reference.rpm": "geometry.parameters.design_rpm",
    "physics.reference.axial_velocity": "geometry.parameters.design_axial_velocity",
}


def _set_nested(spec: dict, dotted_key: str, value) -> None:
    keys = dotted_key.split(".")
    node = spec
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value


def _get_nested(spec: dict, dotted_key: str):
    node = spec
    for k in dotted_key.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(k)
    return node


def pin_design_point(spec: dict, parameters: list[str]) -> dict:
    """Freeze the blade before sweeping the point it is run at.

    The blade's twist is derived from RPM and through-flow. Sweep either without
    pinning and the geometry — and so the mesh — changes at every point, which
    is not a fan map but a series of different fans. Pinning records the base
    case's own operating point as the design point, so one blade is carried
    across the whole map and the mesh is built once per child.
    """
    pinned = {}
    for parameter in parameters:
        target = _DESIGN_PINS.get(parameter)
        if target is None or _get_nested(spec, target) is not None:
            continue
        current = _get_nested(spec, parameter)
        if current is not None:
            _set_nested(spec, target, current)
            pinned[target] = current
    return pinned


def _label(parameter: str, value) -> str:
    return f"{parameter.split('.')[-1]}={value:g}" if isinstance(value, float) else \
        f"{parameter.split('.')[-1]}={value}"


def create_sweep(
    session: Session,
    base_case_id: str,
    parameter: str,
    values: list,
    name: str,
    parameter2: str | None = None,
    values2: list | None = None,
) -> Sweep:
    base = session.get(Case, base_case_id)
    if base is None:
        raise ValueError("base case not found")
    if not values:
        raise ValueError("a sweep needs at least one value")

    axes = [parameter] + ([parameter2] if parameter2 else [])
    grid = [(v, None) for v in values] if not parameter2 else [
        (v, v2) for v in values for v2 in (values2 or [])
    ]
    if parameter2 and not values2:
        raise ValueError("second parameter given without values")

    # do this once, on a copy of the base spec, so every child inherits the same
    # frozen blade rather than each pinning its own swept value
    pinned_spec = copy.deepcopy(base.spec)
    if base.domain == "turbo":
        pin_design_point(pinned_spec, [a for a in axes if a in _TURBO_OPERATING])

    child_ids: list[str] = []
    points: list[dict] = []
    for value, value2 in grid:
        spec = copy.deepcopy(pinned_spec)
        _set_nested(spec, parameter, value)
        label = _label(parameter, value)
        if parameter2:
            _set_nested(spec, parameter2, value2)
            label += f", {_label(parameter2, value2)}"
        child = Case(
            id=uuid.uuid4().hex[:8],
            name=f"{name} [{label}]",
            domain=base.domain,
            template_id=base.template_id,
            spec=spec,
            status=CaseStatus.draft,
        )
        session.add(child)
        child_ids.append(child.id)
        points.append({"value": value, "value2": value2})

    sweep = Sweep(
        id=uuid.uuid4().hex[:8],
        name=name,
        base_case_id=base_case_id,
        parameter=parameter,
        values=values,
        parameter2=parameter2,
        values2=values2,
        domain=base.domain,
        points=points,
        case_ids=child_ids,
    )
    session.add(sweep)
    session.commit()
    session.refresh(sweep)
    return sweep


def _points(sweep: Sweep) -> list[dict]:
    """Per-child axis values, tolerating sweeps created before the second axis."""
    if sweep.points:
        return sweep.points
    return [{"value": v, "value2": None} for v in sweep.values]


def run_all(session: Session, sweep_id: str) -> dict:
    """Queue every child case of a sweep and run them one after another.

    Sequential on purpose: each solve already uses the configured cores, so
    running them in parallel would just oversubscribe the machine.
    """
    sweep = session.get(Sweep, sweep_id)
    if sweep is None:
        raise ValueError("sweep not found")
    if _sweep_state.get(sweep_id, {}).get("running"):
        return {"already_running": True, **_sweep_state[sweep_id]}

    _sweep_state[sweep_id] = {"running": True, "current": None, "message": "queued"}
    threading.Thread(target=_worker, args=(sweep_id,), daemon=True).start()
    return {"started": True, "n_cases": len(sweep.case_ids)}


def _worker(sweep_id: str) -> None:
    from app.db import engine
    from app.services import case_service
    from app.services.runner.docker_runner import DockerRunner

    runner = DockerRunner()
    with Session(engine) as s:
        sweep = s.get(Sweep, sweep_id)
        case_ids = list(sweep.case_ids)

    for idx, cid in enumerate(case_ids, start=1):
        state = _sweep_state.get(sweep_id)
        if state is None or not state.get("running"):
            break  # stopped
        try:
            with Session(engine) as s:
                case = s.get(Case, cid)
                if case is None:
                    continue
                _sweep_state[sweep_id] |= {
                    "current": cid,
                    "message": f"{idx}/{len(case_ids)}: preparing {case.name}",
                }
                report = case_service.validate(case)
                if not report["can_run"]:
                    case.status = CaseStatus.failed
                    s.add(case)
                    s.commit()
                    continue
                case_service.generate(s, case, force_mesh=False)
                handle = runner.submit(case_service.case_dir(cid), "./Allrun")
                run = Run(
                    id=uuid.uuid4().hex[:8],
                    case_id=cid,
                    runner="docker",
                    status=RunStatus.running,
                    container_id=handle,
                    started_at=datetime.now(timezone.utc),
                )
                case.status = CaseStatus.running
                s.add(run)
                s.add(case)
                s.commit()
                run_id = run.id

            _sweep_state[sweep_id] |= {"message": f"{idx}/{len(case_ids)}: solving"}
            while runner.status(handle) == "running":
                time.sleep(2)

            with Session(engine) as s:
                run = s.get(Run, run_id)
                case = s.get(Case, cid)
                ok = runner.status(handle) == "completed"
                run.status = RunStatus.completed if ok else RunStatus.failed
                run.finished_at = datetime.now(timezone.utc)
                case.status = CaseStatus.completed if ok else CaseStatus.failed
                s.add(run)
                s.add(case)
                s.commit()
        except Exception as exc:  # noqa: BLE001 - keep the queue going
            _sweep_state[sweep_id] |= {"message": f"{idx}/{len(case_ids)} failed: {exc}"}

    _sweep_state[sweep_id] = {"running": False, "current": None, "message": "finished"}


def stop_all(sweep_id: str) -> dict:
    """Stop after the case currently solving (does not kill the live container)."""
    if sweep_id in _sweep_state:
        _sweep_state[sweep_id]["running"] = False
        _sweep_state[sweep_id]["message"] = "stopping after current case"
    return _sweep_state.get(sweep_id, {"running": False})


def _metrics(case: Case | None, case_dir, domain: str | None) -> dict:
    """The numbers worth plotting for one child, by domain."""
    from app.parsers import forces
    from app.services.post import fan

    if domain == "turbo":
        if case is None:
            return {}
        last = fan.performance(case_dir, case.spec)["latest"]
        if not last:
            return {}
        return {
            "flow_rate": last["flow_rate"],
            "total_pressure_rise": last["total_pressure_rise"],
            "efficiency": last["efficiency"],
            "torque": last["torque"],
            "shaft_power": last["shaft_power"],
            "flow_coefficient": last["flow_coefficient"],
            "pressure_coefficient": last["pressure_coefficient"],
        }
    last = forces.latest(case_dir)
    return {"cl": last.cl, "cd": last.cd} if last else {}


def status(session: Session, sweep_id: str) -> dict:
    """Per-child status + its headline numbers, plus queue progress."""
    from app.services import case_service

    sweep = session.get(Sweep, sweep_id)
    if sweep is None:
        raise ValueError("sweep not found")

    children = []
    for point, cid in zip(_points(sweep), sweep.case_ids):
        case = session.get(Case, cid)
        children.append(
            {
                "case_id": cid,
                **point,
                "name": case.name if case else cid,
                "status": case.status.value if case else "missing",
                **_metrics(case, case_service.case_dir(cid), sweep.domain),
            }
        )
    queue = _sweep_state.get(sweep_id, {"running": False, "current": None, "message": ""})
    done = sum(1 for c in children if c["status"] in ("completed", "failed"))
    return {
        "id": sweep.id,
        "name": sweep.name,
        "domain": sweep.domain,
        "parameter": sweep.parameter,
        "parameter2": sweep.parameter2,
        "children": children,
        "queue": queue,
        "done": done,
        "total": len(children),
    }


def results(session: Session, sweep_id: str) -> dict:
    """Aggregate the children into the curve or map this domain is plotted as.

    aero  -> polar: the swept value against Cl and Cd.
    turbo -> fan map: flow rate against total pressure rise and efficiency,
             grouped into one series per value of the second axis (the RPM).
    """
    from app.services import case_service

    sweep = session.get(Sweep, sweep_id)
    if sweep is None:
        raise ValueError("sweep not found")

    points = []
    for point, cid in zip(_points(sweep), sweep.case_ids):
        case = session.get(Case, cid)
        points.append(
            {
                **point,
                "case_id": cid,
                **_metrics(case, case_service.case_dir(cid), sweep.domain),
            }
        )
    return {
        "domain": sweep.domain,
        "parameter": sweep.parameter,
        "parameter2": sweep.parameter2,
        "points": points,
    }
