"""Geometry stage: parametric generators (NACA, blades, ducts) + STEP/STL import."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/naca")
async def generate_naca():
    # TODO(phase-1): NACA 4/5-digit generator via app/services/geometry
    return {"todo": "phase-1"}


@router.post("/import")
async def import_cad():
    # TODO(phase-1): STL/STEP upload -> tessellate -> preview mesh
    return {"todo": "phase-1"}
