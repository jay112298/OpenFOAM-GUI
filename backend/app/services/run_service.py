"""Run orchestration: start an OpenFOAM solve in Docker, track the Run record,
and expose a log stream with parsed residuals/forces for the WebSocket.

Starting a run returns immediately. Preparation (writing dicts, regenerating
the mesh only if geometry/mesh settings changed, launching the container) runs
in a background thread and reports progress through an in-memory queue that
the WebSocket drains — so the console shows what's happening from second one.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session

from app.models.case import Case, CaseStatus
from app.models.run import Run, RunStatus
from app.services import case_service
from app.services.runner.docker_runner import DockerRunner

_runner = DockerRunner()

# run_id -> preparation messages (drained by the WebSocket stream)
_progress: dict[str, list[str]] = {}
_lock = threading.Lock()


def _push(run_id: str, msg: str) -> None:
    with _lock:
        _progress.setdefault(run_id, []).append(msg)


def start_run(session: Session, case_id: str) -> Run:
    """Validate (block on FAIL), record the run, kick off preparation. Fast."""
    case = session.get(Case, case_id)
    if case is None:
        raise ValueError("case not found")

    report = case_service.validate(case)
    if not report["can_run"]:
        raise PermissionError("preflight validation failed; resolve FAIL items first")

    run = Run(id=uuid.uuid4().hex[:8], case_id=case_id, runner="docker", status=RunStatus.queued)
    session.add(run)
    case.status = CaseStatus.running
    session.add(case)
    session.commit()
    session.refresh(run)

    _progress[run.id] = []
    threading.Thread(target=_prepare_and_submit, args=(run.id, case_id), daemon=True).start()
    return run


def _prepare_and_submit(run_id: str, case_id: str) -> None:
    from app.db import engine

    with Session(engine) as s:
        case = s.get(Case, case_id)
        run = s.get(Run, run_id)
        try:
            _push(run_id, "[prep] writing OpenFOAM case files (system/, constant/, 0/)")
            info = case_service.generate(s, case, force_mesh=False)
            if info.get("mesh_reused"):
                _push(run_id, "[prep] mesh unchanged since it was generated — reusing it")
            else:
                _push(run_id, f"[prep] mesh regenerated ({info.get('n_cells') or '?'} cells) — geometry or mesh settings changed")
            _push(run_id, f"[prep] starting OpenFOAM container ({_runner.image})")
            handle = _runner.submit(case_service.case_dir(case_id), "./Allrun")
            run.container_id = handle
            run.status = RunStatus.running
            run.started_at = datetime.now(timezone.utc)
            s.add(run)
            s.commit()
            _push(run_id, f"[prep] container {handle[:12]} started — streaming solver output")
        except Exception as exc:  # noqa: BLE001 - report to the console, mark failed
            _push(run_id, f"[prep] ERROR: {exc}")
            run.status = RunStatus.failed
            run.finished_at = datetime.now(timezone.utc)
            case.status = CaseStatus.failed
            s.add(run)
            s.add(case)
            s.commit()


def reconcile(session: Session, run: Run) -> Run:
    """Sync a run's stored status with its container.

    Runs are normally finalized by the WebSocket stream, but nothing is attached
    when the browser is closed mid-solve — without this a finished run would sit
    at `running` forever (and stopping it would wrongly mark it cancelled).
    """
    if run is None or run.status != RunStatus.running or run.container_id is None:
        return run
    actual = _runner.status(run.container_id)
    if actual in ("completed", "failed"):
        _finalize(session, run)
        session.refresh(run)
    return run


def run_status(session: Session, run_id: str) -> str:
    run = session.get(Run, run_id)
    if run is None:
        return "unknown"
    reconcile(session, run)
    return run.status.value


def latest_run(session: Session, case_id: str) -> Run | None:
    """Most recent run for a case — lets the UI reattach after a reload/tab switch."""
    from sqlmodel import select

    runs = session.exec(select(Run).where(Run.case_id == case_id)).all()
    if not runs:
        return None
    run = max(runs, key=lambda r: r.created_at)
    return reconcile(session, run)


def stop_run(session: Session, run_id: str) -> Run:
    """Stop a running solve: kill the container, mark the run cancelled.

    If the container already finished, record the real outcome instead.
    """
    run = session.get(Run, run_id)
    if run is None:
        raise ValueError("run not found")
    reconcile(session, run)
    if run.status in (RunStatus.completed, RunStatus.failed, RunStatus.cancelled):
        return run
    if run.container_id:
        _runner.cancel(run.container_id)
    run.status = RunStatus.cancelled
    run.finished_at = datetime.now(timezone.utc)
    case = session.get(Case, run.case_id)
    if case is not None:
        case.status = CaseStatus.failed  # not a completed solve
        session.add(case)
    session.add(run)
    session.commit()
    session.refresh(run)
    _progress.pop(run_id, None)
    return run


def _finalize(session: Session, run: Run) -> str:
    # A cancelled run keeps its status (the container was killed deliberately).
    if run.status == RunStatus.cancelled:
        _progress.pop(run.id, None)
        return run.status.value
    status = _runner.status(run.container_id) if run.container_id else "failed"
    run.status = RunStatus.completed if status == "completed" else RunStatus.failed
    run.finished_at = datetime.now(timezone.utc)
    case = session.get(Case, run.case_id)
    if case is not None:
        case.status = CaseStatus.completed if status == "completed" else CaseStatus.failed
        session.add(case)
    session.add(run)
    session.commit()
    _progress.pop(run.id, None)
    return run.status.value


def _tail_new(path: Path, offset: int) -> tuple[list[str], int]:
    """Lines appended to `path` since `offset` (used to relay log.gmsh during prep)."""
    if not path.exists():
        return [], offset
    size = path.stat().st_size
    if size <= offset:
        return [], offset
    with path.open("rb") as f:
        f.seek(offset)
        chunk = f.read(size - offset)
    return chunk.decode("utf-8", errors="replace").splitlines(), size


async def stream(run_id: str, session: Session):
    """Yield dict events for the WebSocket terminal.

    Phase 1 (prep): {log, prep:true} messages + any Gmsh log growth.
    Phase 2 (solve): container log lines plus parsed {stage}, {time}, {residual},
    {continuity}, {courant}, {forces}, {layers}, {diverged}.
    Phase 3: {done, status} after the run/case status is persisted.
    """
    from app.parsers import residuals

    run = session.get(Run, run_id)
    if run is None:
        yield {"error": "run not found", "done": True}
        return

    gmsh_log = case_service.case_dir(run.case_id) / "log.gmsh"
    gmsh_off = gmsh_log.stat().st_size if gmsh_log.exists() else 0
    sent = 0

    # Reattaching to a finished run: replay its container log, then report status.
    # (Docker replays the full log from the start, so the console/chart rebuild.)
    if run.status in (RunStatus.cancelled,) and run.container_id is None:
        yield {"log": "[prep] run was cancelled before it started", "prep": True}
        yield {"done": True, "status": run.status.value}
        return

    # --- phase 1: preparation ---
    while run.container_id is None:
        msgs = _progress.get(run_id, [])
        while sent < len(msgs):
            yield {"log": msgs[sent], "prep": True}
            sent += 1
        new, gmsh_off = _tail_new(gmsh_log, gmsh_off)
        for line in new:
            yield {"log": f"[gmsh] {line}", "prep": True}
        session.expire_all()
        run = session.get(Run, run_id)
        if run.status in (RunStatus.failed, RunStatus.cancelled):
            yield {
                "error": f"run {run.status.value} during preparation",
                "done": True,
                "status": run.status.value,
            }
            return
        await asyncio.sleep(0.3)

    msgs = _progress.get(run_id, [])
    while sent < len(msgs):
        yield {"log": msgs[sent], "prep": True}
        sent += 1

    # --- phase 2: solver ---
    cl = cd = None
    async for line in _runner.alogs(run.container_id):
        line = line.rstrip("\n")
        yield {"log": line}

        stage = residuals.parse_stage(line)
        if stage is not None:
            yield {"stage": stage}

        cov = residuals.parse_layer_coverage(line)
        if cov is not None:
            yield {"layers": {"coverage": cov}}

        t = residuals.parse_time(line)
        if t is not None:
            yield {"time": t}

        pt = residuals.parse_line(line)
        if pt is not None:
            yield {
                "residual": {"field": pt.field, "initial": pt.initial, "final": pt.final},
                "diverged": residuals.is_diverged(pt),
            }

        cont = residuals.parse_continuity(line)
        if cont is not None:
            yield {"continuity": cont}

        cour = residuals.parse_courant(line)
        if cour is not None:
            yield {"courant": cour}

        v = residuals.parse_cl(line)
        if v is not None:
            cl = v
        v = residuals.parse_cd(line)
        if v is not None:
            cd = v
            # Cd is printed last in the forceCoeffs block -> emit the pair
            if cl is not None:
                yield {"forces": {"cl": cl, "cd": cd}}

    # --- phase 3: persist final status ---
    session.expire_all()
    run = session.get(Run, run_id)
    status = _finalize(session, run)
    yield {"done": True, "status": status}
