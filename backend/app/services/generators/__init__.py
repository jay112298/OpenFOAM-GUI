"""Generator registry: one module per domain, all with the same surface.

Every generator exposes

    Params.from_spec(spec) -> dataclass
    derive(params)         -> derived state (velocities, Re, turbulence inlet, ...)
    build_case(spec, dir, force_mesh) -> derived state
    mesh_ready(dir)        -> bool
    mesh_cell_count(dir)   -> int | None
    MESH_LOG               -> name of the file the mesh writes progress to

so the case service, the run service and the validation engine never branch on
the domain themselves.
"""

from __future__ import annotations

from types import ModuleType

from app.services.generators import airfoil_case, axial_fan_case

BY_DOMAIN: dict[str, ModuleType] = {
    "aero": airfoil_case,
    "turbo": axial_fan_case,
}

DEFAULT_DOMAIN = "aero"


def for_domain(domain: str | None) -> ModuleType:
    return BY_DOMAIN.get(domain or DEFAULT_DOMAIN, airfoil_case)


def for_spec(spec: dict) -> ModuleType:
    return for_domain(spec.get("domain"))
