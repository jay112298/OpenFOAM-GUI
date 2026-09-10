"""Case CRUD + pipeline actions (generate dicts, validate)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models.case import Case
from app.services import case_service

router = APIRouter()


class CreateCaseBody(BaseModel):
    name: str
    template: str = "airfoil"


class UpdateSpecBody(BaseModel):
    spec: dict


@router.get("/")
async def list_cases(session: Session = Depends(get_session)):
    return session.exec(select(Case)).all()


@router.post("/")
async def create_case(body: CreateCaseBody, session: Session = Depends(get_session)):
    try:
        return case_service.create_case(session, body.name, body.template)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _get(session: Session, case_id: str) -> Case:
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.get("/{case_id}")
async def get_case(case_id: str, session: Session = Depends(get_session)):
    return _get(session, case_id)


@router.put("/{case_id}/spec")
async def update_spec(case_id: str, body: UpdateSpecBody, session: Session = Depends(get_session)):
    case = _get(session, case_id)
    case.spec = body.spec
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


# sync def -> FastAPI runs it in a threadpool, so the Gmsh subprocess + build
# don't block the event loop (keeps the run WebSocket responsive).
@router.post("/{case_id}/generate")
def generate(case_id: str, session: Session = Depends(get_session)):
    case = _get(session, case_id)
    try:
        return case_service.generate(session, case)
    except Exception as exc:  # noqa: BLE001 - surface generator errors to UI
        raise HTTPException(status_code=400, detail=f"Generation failed: {exc}")


@router.get("/{case_id}/mesh-log")
async def mesh_log(case_id: str):
    """Live tail of the Gmsh meshing log (polled by the Mesh tab while generating)."""
    return case_service.mesh_log(case_id)


@router.get("/{case_id}/validate")
async def validate(case_id: str, session: Session = Depends(get_session)):
    case = _get(session, case_id)
    return case_service.validate(case)


@router.delete("/{case_id}")
async def delete_case(case_id: str, session: Session = Depends(get_session)):
    case = _get(session, case_id)
    case_service.delete_case(session, case)
    return {"deleted": case_id}
