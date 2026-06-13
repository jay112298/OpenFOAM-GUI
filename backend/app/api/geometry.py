"""Geometry stage: parametric generators (NACA) + CAD import (Phase 1.3)."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.services import case_service
from app.services.geometry import cad_import, naca

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


@router.post("/{case_id}/import")
async def import_cad(case_id: str, file: UploadFile = File(...)):
    """Upload an STL or STEP surface into the case's triSurface directory."""
    dest = case_service.case_dir(case_id) / "constant" / "triSurface"
    try:
        data = await file.read()
        return cad_import.save_surface(data, file.filename, dest)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
