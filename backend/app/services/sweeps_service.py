"""Parameter sweeps: clone a base case spec across values of one parameter,
creating child cases. Aggregation (e.g. polar curves) reads each child's forces.
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


def _set_nested(spec: dict, dotted_key: str, value) -> None:
    keys = dotted_key.split(".")
    node = spec
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value


def create_sweep(
    session: Session, base_case_id: str, parameter: str, values: list, name: str
) -> Sweep:
    base = session.get(Case, base_case_id)
    if base is None:
        raise ValueError("base case not found")

    child_ids: list[str] = []
    for v in values:
        spec = copy.deepcopy(base.spec)
        _set_nested(spec, parameter, v)
        child = Case(
            id=uuid.uuid4().hex[:8],
            name=f"{name} [{parameter.split('.')[-1]}={v}]",
            domain=base.domain,
            template_id=base.template_id,
            spec=spec,
            status=CaseStatus.draft,
        )
        session.add(child)
        child_ids.append(child.id)

    sweep = Sweep(
        id=uuid.uuid4().hex[:8],
        name=name,
        base_case_id=base_case_id,
        parameter=parameter,
        values=values,
        case_ids=child_ids,
    )
    session.add(sweep)
    session.commit()
    session.refresh(sweep)
    return sweep


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


def status(session: Session, sweep_id: str) -> dict:
    """Per-child status + coefficients, plus queue progress."""
    from app.parsers import forces
    from app.services import case_service

    sweep = session.get(Sweep, sweep_id)
    if sweep is None:
        raise ValueError("sweep not found")

    children = []
    for value, cid in zip(sweep.values, sweep.case_ids):
        case = session.get(Case, cid)
        last = forces.latest(case_service.case_dir(cid))
        children.append(
            {
                "case_id": cid,
                "value": value,
                "name": case.name if case else cid,
                "status": case.status.value if case else "missing",
                "cl": last.cl if last else None,
                "cd": last.cd if last else None,
            }
        )
    queue = _sweep_state.get(sweep_id, {"running": False, "current": None, "message": ""})
    done = sum(1 for c in children if c["status"] in ("completed", "failed"))
    return {
        "id": sweep.id,
        "name": sweep.name,
        "parameter": sweep.parameter,
        "children": children,
        "queue": queue,
        "done": done,
        "total": len(children),
    }


def polar(session: Session, sweep_id: str) -> dict:
    """Aggregate child-case force coefficients into a polar (value -> Cl, Cd)."""
    from app.parsers import forces
    from app.services import case_service

    sweep = session.get(Sweep, sweep_id)
    if sweep is None:
        raise ValueError("sweep not found")
    points = []
    for value, cid in zip(sweep.values, sweep.case_ids):
        last = forces.latest(case_service.case_dir(cid))
        points.append(
            {"value": value, "case_id": cid,
             "cl": last.cl if last else None, "cd": last.cd if last else None}
        )
    return {"parameter": sweep.parameter, "points": points}
