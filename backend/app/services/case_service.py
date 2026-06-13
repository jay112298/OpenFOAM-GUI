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


def generate(session: Session, case: Case) -> dict:
    """Write the OpenFOAM case directory from the spec. Returns derived state."""
    d = case_dir(case.id)
    d.mkdir(parents=True, exist_ok=True)
    st = build_case(case.spec, d)
    return {
        "reynolds": st.reynolds,
        "mach": st.mach,
        "k": st.k,
        "omega": st.omega,
        "first_cell_height": st.first_cell_height,
        "velocity_vector": list(st.velocity_vector),
    }


def validate(case: Case, mesh_metrics: dict | None = None) -> dict:
    return preflight_report(case.spec, mesh_metrics=mesh_metrics)


def delete_case(session: Session, case: Case) -> None:
    shutil.rmtree(case_dir(case.id), ignore_errors=True)
    session.delete(case)
    session.commit()
