"""Parameter sweeps: clone a base case spec across values of one parameter,
creating child cases. Aggregation (e.g. polar curves) reads each child's forces.
"""

from __future__ import annotations

import copy
import uuid

from sqlmodel import Session

from app.models.case import Case, CaseStatus
from app.models.run import Sweep


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
