"""Case database models and the case-spec schema.

A *case spec* is one versioned document describing every pipeline stage:
Geometry -> Mesh -> Physics -> BCs -> Numerics. Templates are pre-filled specs.
The validation engine and the dict generators both consume this document.
"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel
from sqlmodel import JSON, Column, Field, SQLModel


class CaseStatus(str, Enum):
    draft = "draft"
    meshed = "meshed"
    validated = "validated"
    running = "running"
    completed = "completed"
    failed = "failed"


class Case(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    domain: str  # aero | turbo | engine
    template_id: str | None = None
    status: CaseStatus = CaseStatus.draft
    spec: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ValidationOverride(SQLModel, table=True):
    """Audit log of warning overrides (guardrail policy: warnings overridable, logged)."""

    id: int | None = Field(default=None, primary_key=True)
    case_id: str = Field(foreign_key="case.id")
    rule_id: str
    message: str
    overridden_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --- Case spec stage schemas (skeletons, fleshed out per phase) ---


class GeometrySpec(BaseModel):
    kind: str = "naca4"  # naca4 | naca5 | import_stl | import_step | blade | duct
    parameters: dict = {}
    source_file: str | None = None


class MeshSpec(BaseModel):
    strategy: str = "snappy"  # blockmesh | snappy | cfmesh | external
    parameters: dict = {}
    target_yplus: float | None = None


class PhysicsSpec(BaseModel):
    flow_type: str = "incompressible"  # incompressible | compressible | transonic
    time_treatment: str = "steady"  # steady | transient
    turbulence_model: str = "kOmegaSST"
    fluid: dict = {}
    reference: dict = {}  # velocity, length, area, angle_of_attack...


class NumericsSpec(BaseModel):
    solver: str = "simpleFoam"
    end_time: float = 1000
    delta_t: float = 1
    write_interval: float = 100
    schemes: dict = {}
    relaxation: dict = {}


class CaseSpec(BaseModel):
    """Full pipeline document. `boundary_conditions` maps patch -> field -> BC."""

    version: int = 1
    domain: str = "aero"
    geometry: GeometrySpec = GeometrySpec()
    mesh: MeshSpec = MeshSpec()
    physics: PhysicsSpec = PhysicsSpec()
    boundary_conditions: dict = {}
    numerics: NumericsSpec = NumericsSpec()
