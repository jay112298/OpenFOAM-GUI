"""Post-processing: force coefficient history; open results in ParaView."""

from fastapi import APIRouter, HTTPException

from app.parsers import forces
from app.services import case_service
from app.services.post import paraview

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


@router.post("/{case_id}/paraview")
def open_paraview(case_id: str):
    """Launch the user's local ParaView on this case."""
    try:
        return paraview.open_in_paraview(case_service.case_dir(case_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not launch ParaView: {exc}")
