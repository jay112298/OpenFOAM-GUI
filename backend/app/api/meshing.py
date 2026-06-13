"""Mesh stage: y+ calculator now; mesh generation runs via the runner."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.meshing.yplus import first_cell_height
from app.services.physics.fluids import get_fluid

router = APIRouter()


class YPlusBody(BaseModel):
    velocity: float
    length: float
    fluid: str = "air"
    target_yplus: float = 30.0


@router.post("/yplus")
async def yplus(body: YPlusBody):
    try:
        f = get_fluid(body.fluid)
        est = first_cell_height(body.velocity, body.length, f.nu, f.rho, body.target_yplus)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "first_cell_height": est.first_cell_height,
        "first_cell_centre": est.first_cell_centre,
        "cf": est.cf,
        "u_tau": est.u_tau,
        "reynolds": est.reynolds,
    }
