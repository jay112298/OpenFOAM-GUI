"""Post-processing: forces, Cp, field extracts (slices) for VTK.js, ParaView export."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/{case_id}/forces")
async def forces(case_id: str):
    # TODO(phase-1): parse force coefficient function-object output
    return {"todo": "phase-1"}


@router.get("/{case_id}/slice")
async def field_slice(case_id: str):
    # TODO(phase-1): PyVista slice -> decimated VTP for browser
    return {"todo": "phase-1"}
