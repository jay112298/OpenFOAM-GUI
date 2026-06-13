"""Geometry stage: parametric generators (NACA) + CAD import (Phase 1.3)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.geometry import naca

router = APIRouter()


class NacaBody(BaseModel):
    designation: str = "0012"
    chord: float = 1.0
    n: int = 120


@router.post("/naca")
async def generate_naca(body: NacaBody):
    """Return airfoil coordinates for preview."""
    try:
        af = naca.generate(body.designation, body.chord, body.n)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "designation": af.designation,
        "chord": af.chord,
        "coordinates": af.coordinates,
    }
