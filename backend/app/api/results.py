"""Post-processing: force coefficient history; field extracts (Phase 1.9)."""

from fastapi import APIRouter

from app.parsers import forces
from app.services import case_service

router = APIRouter()


@router.get("/{case_id}/forces")
async def force_history(case_id: str):
    cdir = case_service.case_dir(case_id)
    h = forces.history(cdir)
    last = h[-1] if h else None
    return {
        "history": [{"time": f.time, "cl": f.cl, "cd": f.cd, "cm": f.cm} for f in h],
        "latest": {"cl": last.cl, "cd": last.cd, "cm": last.cm} if last else None,
    }
