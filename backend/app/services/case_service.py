"""Case service: ties the DB record, on-disk OpenFOAM directory, generators,
and the validation engine together. The API layer calls into here.
"""

from __future__ import annotations

import copy
import shutil
import uuid
from pathlib import Path

from sqlmodel import Session

from app.config import settings
from app.models.case import Case, CaseStatus
from app.services import generators, settings_service
from app.services.validation.engine import preflight_report
from app.templates.registry import get_template


def case_dir(case_id: str) -> Path:
    return settings.cases_dir / case_id


def create_case(session: Session, name: str, template_id: str = "airfoil") -> Case:
    template = get_template(template_id)
    if template is None:
        raise ValueError(f"Unknown template: {template_id}")
    # deep copy: the template dict is module-level shared state, and an in-place
    # edit of a case spec would otherwise corrupt every later case
    spec = copy.deepcopy(template["spec"])
    spec.setdefault("numerics", {})["n_procs"] = settings_service.load()["default_n_procs"]

    case = Case(
        id=uuid.uuid4().hex[:8],
        name=name,
        domain=template["domain"],
        template_id=template_id,
        spec=spec,
        status=CaseStatus.draft,
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def generate(session: Session, case: Case, force_mesh: bool = True) -> dict:
    """Write the OpenFOAM case directory from the spec. Returns derived state.

    force_mesh=False reuses an existing mesh whose signature still matches.
    """
    gen = generators.for_spec(case.spec)
    d = case_dir(case.id)
    d.mkdir(parents=True, exist_ok=True)
    st = gen.build_case(case.spec, d, force_mesh=force_mesh)
    return {
        **gen.summary(st),
        "n_cells": gen.mesh_cell_count(d),
        "mesh_reused": st.mesh_reused,
        "domain": case.spec.get("domain", generators.DEFAULT_DOMAIN),
    }


def pipeline_status(session: Session, case: Case) -> dict:
    """What the pipeline has already achieved on disk / in the DB.

    The UI seeds its stage gating from this so a page reload doesn't re-lock
    tabs whose work is already done (mesh on disk, preflight passing, run done).
    """
    from app.services import run_service

    gen = generators.for_spec(case.spec)
    d = case_dir(case.id)
    report = validate(case)
    last = run_service.latest_run(session, case.id)
    return {
        "mesh": {
            "exists": gen.mesh_ready(d),
            "n_cells": gen.mesh_cell_count(d),
        },
        "validation": {"can_run": report["can_run"], "summary": report["summary"]},
        "latest_run": (
            {"id": last.id, "status": last.status.value, "container_id": last.container_id}
            if last
            else None
        ),
        "has_results": _has_results(case, d),
    }


def _has_results(case: Case, d: Path) -> bool:
    from app.parsers import forces
    from app.services.post import fan

    if case.spec.get("domain") == "turbo":
        return bool(fan.history(d, case.spec))
    return forces.latest(d) is not None


def mesh_log(case_id: str, tail: int = 120) -> dict:
    """Tail of the mesh log written while the mesh generates (for live progress).

    Which file that is depends on the mesher — Gmsh writes its own log in
    process, the passage mesher tees the container output — so ask the
    generator rather than guessing.
    """
    from sqlmodel import Session

    from app.db import engine as db_engine

    with Session(db_engine) as s:
        case = s.get(Case, case_id)
    gen = generators.for_spec(case.spec if case else {})
    p = case_dir(case_id) / gen.MESH_LOG
    if not p.exists():
        return {"lines": [], "done": False}
    lines = p.read_text(errors="replace").splitlines()
    done = any(_is_terminal(line) for line in lines)
    return {"lines": lines[-tail:], "done": done}


def _is_terminal(line: str) -> bool:
    return line.startswith(("[gmsh] done", "[gmsh] ERROR", "[mesh] done", "[mesh] ERROR"))


def mesh_metrics(case_id: str) -> dict | None:
    """checkMesh quality numbers, once the mesher has run."""
    from app.parsers import checkmesh

    log = case_dir(case_id) / "log.checkMesh"
    if not log.exists():
        return None
    return checkmesh.parse(log.read_text(errors="replace"))


def validate(case: Case, metrics: dict | None = None) -> dict:
    """Preflight report. Mesh quality joins the checks as soon as checkMesh has
    something to say — the rules stay silent until then."""
    return preflight_report(case.spec, mesh_metrics=metrics or mesh_metrics(case.id))


def delete_case(session: Session, case: Case) -> None:
    shutil.rmtree(case_dir(case.id), ignore_errors=True)
    session.delete(case)
    session.commit()
