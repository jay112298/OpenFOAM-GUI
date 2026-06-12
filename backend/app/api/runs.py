"""Run stage: queue solves, stream live logs/residuals over WebSocket."""

from fastapi import APIRouter, WebSocket

router = APIRouter()


@router.post("/{case_id}/start")
async def start_run(case_id: str):
    # TODO(phase-1): preflight gate -> generate dicts -> queue job via runner service
    return {"todo": "phase-1"}


@router.websocket("/ws/{run_id}")
async def run_stream(websocket: WebSocket, run_id: str):
    # TODO(phase-1): stream log lines + parsed residuals/forces
    await websocket.accept()
    await websocket.send_json({"todo": "phase-1"})
    await websocket.close()
