"""Parameter sweeps: AoA -> polar, RPM x flow -> fan map. Child cases fan out
from a base spec across one or two parameters."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models.run import Sweep
from app.services import sweeps_service

router = APIRouter()


class CreateSweepBody(BaseModel):
    base_case_id: str
    parameter: str = "physics.reference.angle_of_attack"
    values: list[float]
    name: str = "AoA sweep"
    # optional second axis — children are the cross product (a fan map)
    parameter2: str | None = None
    values2: list[float] | None = None


@router.get("/")
async def list_sweeps(session: Session = Depends(get_session)):
    return session.exec(select(Sweep)).all()


@router.post("/")
async def create_sweep(body: CreateSweepBody, session: Session = Depends(get_session)):
    try:
        return sweeps_service.create_sweep(
            session, body.base_case_id, body.parameter, body.values, body.name,
            parameter2=body.parameter2, values2=body.values2,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{sweep_id}/run")
def run_all(sweep_id: str, session: Session = Depends(get_session)):
    """Run every child case of the sweep, one after another."""
    try:
        return sweeps_service.run_all(session, sweep_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{sweep_id}/stop")
async def stop_all(sweep_id: str):
    return sweeps_service.stop_all(sweep_id)


@router.get("/{sweep_id}/status")
async def status(sweep_id: str, session: Session = Depends(get_session)):
    try:
        return sweeps_service.status(session, sweep_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{sweep_id}/results")
async def results(sweep_id: str, session: Session = Depends(get_session)):
    """Aggregated curve or map, shaped by the base case's domain."""
    try:
        return sweeps_service.results(session, sweep_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
