"""Validation stage: run the rule engine -> preflight report; log overrides."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models.case import Case, ValidationOverride
from app.services.validation.engine import run_preflight

router = APIRouter()


@router.get("/{case_id}/preflight")
async def preflight(case_id: str):
    return run_preflight(case_id)


class OverrideBody(BaseModel):
    rule_id: str
    message: str


@router.post("/{case_id}/override")
async def override_warning(
    case_id: str, body: OverrideBody, session: Session = Depends(get_session)
):
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    log = ValidationOverride(case_id=case_id, rule_id=body.rule_id, message=body.message)
    session.add(log)
    session.commit()
    return {"logged": True, "rule_id": body.rule_id}


@router.get("/{case_id}/overrides")
async def list_overrides(case_id: str, session: Session = Depends(get_session)):
    return session.exec(
        select(ValidationOverride).where(ValidationOverride.case_id == case_id)
    ).all()
