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
    # the point the blade was cut for; unset means "the same as above"
    design_rpm: float | None = None
    design_axial_velocity: float | None = None

    def design(self) -> dict:
        d = self.model_dump(exclude={"design_rpm", "design_axial_velocity"})
        d["rpm"] = self.design_rpm or self.rpm
        d["axial_velocity"] = self.design_axial_velocity or self.axial_velocity
        return d

    def operating(self) -> dict:
        return self.model_dump(exclude={"design_rpm", "design_axial_velocity"})


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

    `sections` is the hub-to-tip twist table of the blade as cut; `cascade` is
    the same blade drawn three times at the blade pitch on an unrolled cylinder
    at mid-span, which is how the passage between blades actually looks.

    When the blade was cut for a different point than the one being run, the
    two differ, and `incidence_profile` is where that shows: the metal angle is
    fixed, the flow arrives from somewhere else, and the gap between them is
    the off-design incidence.
    """
    import math

    try:
        spec = blade.BladeSpec(**body.design())
        op = blade.BladeSpec(**body.operating())
        secs = blade.sections(spec, n=7)
        mid = spec.mean_radius
        outline = blade.section_outline(spec, mid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    pitch = 2 * math.pi * mid / spec.n_blades
    off_design = (spec.rpm, spec.axial_velocity) != (op.rpm, op.axial_velocity)
    return {
        "sector_angle": math.degrees(spec.sector_angle),
        "tip_speed": op.tip_speed,
        "flow_coefficient": op.flow_coefficient,
        "mean_radius": mid,
        "pitch": pitch,
        "off_design": off_design,
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
        "incidence_profile": [
            {
                "radius": s.radius,
                "stagger": s.stagger,
                "relative_angle": (flow := blade.section_at(op, s.radius)).relative_angle,
                "incidence": flow.relative_angle - s.stagger,
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
