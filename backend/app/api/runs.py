"""Run stage: queue solves, stream live logs/residuals over WebSocket."""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select

from app.db import engine, get_session
from app.models.run import Run
from app.services import run_service

router = APIRouter()


# sync def -> threadpool: regeneration (Gmsh) + container submit won't block the
# event loop, so the WebSocket stays responsive and start returns promptly.
@router.post("/{case_id}/start")
def start_run(case_id: str, session: Session = Depends(get_session)):
    try:
        return run_service.start_run(session, case_id)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - surface Docker errors
        raise HTTPException(status_code=400, detail=f"Run failed to start: {exc}")


@router.get("/")
async def list_runs(case_id: str | None = None, session: Session = Depends(get_session)):
    q = select(Run)
    if case_id:
        q = q.where(Run.case_id == case_id)
    return session.exec(q).all()


@router.get("/{run_id}/status")
async def status(run_id: str, session: Session = Depends(get_session)):
    return {"run_id": run_id, "status": run_service.run_status(session, run_id)}


@router.websocket("/ws/{run_id}")
async def run_stream(websocket: WebSocket, run_id: str):
    await websocket.accept()
    session = Session(engine)
    try:
        async for event in run_service.stream(run_id, session):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        await websocket.send_json({"error": str(exc)})
    finally:
        session.close()
        await websocket.close()
