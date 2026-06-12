"""Parameter sweeps: AoA -> polar, RPM -> map. Child cases fan out from a base spec."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_sweeps():
    # TODO(phase-1): list sweeps with aggregate status
    return []


@router.post("/")
async def create_sweep():
    # TODO(phase-1): clone base case across parameter values, queue runs
    return {"todo": "phase-1"}
