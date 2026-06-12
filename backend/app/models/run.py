"""Run and sweep database models."""

from datetime import datetime, timezone
from enum import Enum

from sqlmodel import JSON, Column, Field, SQLModel


class RunStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class Run(SQLModel, table=True):
    id: str = Field(primary_key=True)
    case_id: str = Field(foreign_key="case.id")
    runner: str = "docker"  # docker | ssh (future)
    status: RunStatus = RunStatus.queued
    container_id: str | None = None
    exit_code: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Sweep(SQLModel, table=True):
    """Parameter sweep: one base case, one varied parameter, N child cases."""

    id: str = Field(primary_key=True)
    name: str
    base_case_id: str = Field(foreign_key="case.id")
    parameter: str  # e.g. "physics.reference.angle_of_attack"
    values: list = Field(default_factory=list, sa_column=Column(JSON))
    case_ids: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
