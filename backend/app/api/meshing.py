"""Mesh stage: blockMesh/snappyHexMesh wizards, y+ calculator, checkMesh gates."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/yplus")
async def yplus_calculator():
    # TODO(phase-1): target y+ -> first cell height (app/services/meshing/yplus.py)
    return {"todo": "phase-1"}


@router.post("/{case_id}/generate")
async def generate_mesh(case_id: str):
    # TODO(phase-1): render mesh dicts from spec, run mesher in container, parse checkMesh
    return {"todo": "phase-1"}
