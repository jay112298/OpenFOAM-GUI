"""Run orchestration: start an OpenFOAM solve in Docker, track the Run record,
and expose a log stream with parsed residuals/forces for the WebSocket.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Session

from app.models.run import Run, RunStatus
from app.services import case_service
from app.services.runner.docker_runner import DockerRunner

_runner = DockerRunner()


def start_run(session: Session, case_id: str) -> Run:
    """Validate (block on FAIL), generate, then launch the Allrun container."""
    from app.models.case import Case, CaseStatus

    case = session.get(Case, case_id)
    if case is None:
        raise ValueError("case not found")

    report = case_service.validate(case)
    if not report["can_run"]:
        raise PermissionError("preflight validation failed; resolve FAIL items first")

    case_service.generate(session, case)
    cdir = case_service.case_dir(case_id)
    handle = _runner.submit(cdir, "./Allrun")

    run = Run(
        id=uuid.uuid4().hex[:8],
        case_id=case_id,
        runner="docker",
        status=RunStatus.running,
        container_id=handle,
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    case.status = CaseStatus.running
    session.add(case)
    session.commit()
    session.refresh(run)
    return run


def run_status(session: Session, run_id: str) -> str:
    run = session.get(Run, run_id)
    if run is None or run.container_id is None:
        return "unknown"
    return _runner.status(run.container_id)


async def stream(run_id: str, session: Session):
    """Yield dict events: {log} and {residual} and {time} for the WebSocket."""
    from app.parsers import residuals

    run = session.get(Run, run_id)
    if run is None or run.container_id is None:
        yield {"error": "run not found"}
        return

    async for line in _runner.alogs(run.container_id):
        line = line.rstrip("\n")
        yield {"log": line}
        t = residuals.parse_time(line)
        if t is not None:
            yield {"time": t}
        pt = residuals.parse_line(line)
        if pt is not None:
            yield {
                "residual": {"field": pt.field, "initial": pt.initial, "final": pt.final},
                "diverged": residuals.is_diverged(pt),
            }
