"""Post-processing: force coefficient history; open results in ParaView."""

from fastapi import APIRouter, HTTPException

from app.parsers import forces
from app.services import case_service
from app.services.post import fan, fields, paraview

router = APIRouter()


@router.get("/{case_id}/fan")
def fan_performance(case_id: str):
    """Flow rate, total pressure rise, torque and efficiency for a turbo case."""
    from sqlmodel import Session

    from app.db import engine
    from app.models.case import Case

    with Session(engine) as session:
        case = session.get(Case, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="case not found")
        spec = case.spec
    return fan.performance(case_service.case_dir(case_id), spec)


@router.get("/{case_id}/fields")
def list_fields(case_id: str):
    """Which solution fields are available to plot, and at which times."""
    return fields.available(case_service.case_dir(case_id))


# sync def -> threadpool: reading + slicing the case is CPU work
@router.get("/{case_id}/field")
def field_slice(case_id: str, name: str, time: float | None = None):
    """Mid-span slice of one field as a triangle soup for the browser canvas."""
    try:
        return fields.slice_field(case_service.case_dir(case_id), name, time)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not read field: {exc}")


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
