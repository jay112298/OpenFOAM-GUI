"""Case CRUD. A case wraps a versioned case spec + on-disk OpenFOAM directory."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models.case import Case, CaseSpec

router = APIRouter()


@router.get("/")
async def list_cases(session: Session = Depends(get_session)):
    return session.exec(select(Case)).all()


@router.post("/")
async def create_case(name: str, domain: str = "aero", session: Session = Depends(get_session)):
    case = Case(id=uuid.uuid4().hex[:8], name=name, domain=domain, spec=CaseSpec(domain=domain).model_dump())
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


@router.get("/{case_id}")
async def get_case(case_id: str, session: Session = Depends(get_session)):
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.put("/{case_id}/spec")
async def update_spec(case_id: str, spec: CaseSpec, session: Session = Depends(get_session)):
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    case.spec = spec.model_dump()
    session.add(case)
    session.commit()
    return case


@router.delete("/{case_id}")
async def delete_case(case_id: str, session: Session = Depends(get_session)):
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    session.delete(case)
    session.commit()
    return {"deleted": case_id}
