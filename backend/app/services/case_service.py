"""Case service: ties the DB record, on-disk OpenFOAM directory, generators,
and the validation engine together. The API layer calls into here.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from sqlmodel import Session

from app.config import settings
from app.models.case import Case, CaseStatus
from app.services.generators.airfoil_case import build_case
from app.services.validation.engine import preflight_report
from app.templates.registry import get_template


def case_dir(case_id: str) -> Path:
    return settings.cases_dir / case_id


def create_case(session: Session, name: str, template_id: str = "airfoil") -> Case:
    template = get_template(template_id)
    if template is None:
        raise ValueError(f"Unknown template: {template_id}")
    case = Case(
        id=uuid.uuid4().hex[:8],
        name=name,
        domain=template["domain"],
        template_id=template_id,
        spec=template["spec"],
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
    d = case_dir(case.id)
    d.mkdir(parents=True, exist_ok=True)
    st = build_case(case.spec, d, force_mesh=force_mesh)
    ncells_file = d / "airfoil.ncells"
    n_cells = int(ncells_file.read_text()) if ncells_file.exists() else None
    return {
        "reynolds": st.reynolds,
        "mach": st.mach,
        "k": st.k,
        "omega": st.omega,
        "first_cell_height": st.first_cell_height,
        "velocity_vector": list(st.velocity_vector),
        "n_cells": n_cells,
        "mesh_reused": st.mesh_reused,
    }


def mesh_log(case_id: str, tail: int = 120) -> dict:
    """Tail of the Gmsh log written while the mesh generates (for live progress)."""
    p = case_dir(case_id) / "log.gmsh"
    if not p.exists():
        return {"lines": [], "done": False}
    lines = p.read_text(errors="replace").splitlines()
    done = any(line.startswith("[gmsh] done") or line.startswith("[gmsh] ERROR") for line in lines)
    return {"lines": lines[-tail:], "done": done}


def validate(case: Case, mesh_metrics: dict | None = None) -> dict:
    return preflight_report(case.spec, mesh_metrics=mesh_metrics)


def delete_case(session: Session, case: Case) -> None:
    shutil.rmtree(case_dir(case.id), ignore_errors=True)
    session.delete(case)
    session.commit()
