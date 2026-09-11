"""Geometry stage: parametric generators (NACA) + CAD import (Phase 1.3)."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.services import case_service
from app.services.geometry import blade, cad_import, naca

router = APIRouter()


class NacaBody(BaseModel):
    designation: str = "0012"
    chord: float = 1.0
    n: int = 120


class BladeBody(BaseModel):
    designation: str = "4412"
    n_blades: int = 6
    hub_radius: float = 0.06
    tip_radius: float = 0.15
    chord: float = 0.05
    rpm: float = 3000.0
    axial_velocity: float = 12.0
    incidence: float = 4.0


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


@router.post("/blade")
def preview_blade(body: BladeBody):
    """Velocity triangles and section outlines for the axial blade preview.

    `sections` is the hub-to-tip twist table the GUI shows; `cascade` is the
    same blade drawn twice at the blade pitch on an unrolled cylinder at
    mid-span, which is how the passage between two blades actually looks.
    """
    import math

    try:
        spec = blade.BladeSpec(**body.model_dump())
        secs = blade.sections(spec, n=7)
        mid = spec.mean_radius
        outline = blade.section_outline(spec, mid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    pitch = 2 * math.pi * mid / spec.n_blades
    return {
        "sector_angle": math.degrees(spec.sector_angle),
        "tip_speed": spec.tip_speed,
        "flow_coefficient": spec.flow_coefficient,
        "mean_radius": mid,
        "pitch": pitch,
        "cascade": {"outline": outline, "pitch": pitch},
        "sections": [
            {
                "radius": s.radius,
                "blade_speed": s.blade_speed,
                "relative_angle": s.relative_angle,
                "stagger": s.stagger,
                "relative_speed": s.relative_speed,
                "pitch": s.pitch,
                "solidity": s.solidity,
            }
            for s in secs
        ],
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
