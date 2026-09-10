"""User-editable settings, persisted next to the case data.

`app.config.settings` holds process configuration (env + defaults). The few
values a user should be able to change from the GUI are stored in
`<data_dir>/settings.json` and layered on top at read time, so a restart keeps
them and nothing has to be set through environment variables.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.config import settings

EDITABLE = {"openfoam_image", "default_n_procs"}
DEFAULTS = {"openfoam_image": settings.openfoam_image, "default_n_procs": 1}


def _file() -> Path:
    return settings.data_dir / "settings.json"


def load() -> dict:
    """Stored overrides merged over the defaults."""
    values = dict(DEFAULTS)
    f = _file()
    if f.exists():
        try:
            stored = json.loads(f.read_text())
            values.update({k: v for k, v in stored.items() if k in EDITABLE})
        except (json.JSONDecodeError, OSError):
            pass  # corrupt file: fall back to defaults rather than break startup
    return values


def save(updates: dict) -> dict:
    values = load()
    values.update({k: v for k, v in updates.items() if k in EDITABLE})
    _file().write_text(json.dumps(values, indent=2))
    # keep the live config in step so runs use the new image immediately
    settings.openfoam_image = values["openfoam_image"]
    return values


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def info() -> dict:
    """Everything the Settings screen shows: values, paths, disk use, tooling."""
    from app.services.runner.docker_runner import docker_status

    values = load()
    cases = settings.cases_dir
    n_cases = len([d for d in cases.iterdir() if d.is_dir()]) if cases.exists() else 0
    return {
        "values": values,
        "editable": sorted(EDITABLE),
        "paths": {
            "data_dir": str(settings.data_dir),
            "cases_dir": str(cases),
            "database": str(settings.db_path),
        },
        "storage": {
            "cases_on_disk": n_cases,
            "cases_bytes": _dir_size(cases),
        },
        "docker": docker_status(),
        "tools": {
            "paraview": shutil.which("paraview") or _paraview_bundle(),
            "gmsh": _gmsh_version(),
        },
        "version": "0.1.0",
    }


def _paraview_bundle() -> str | None:
    for p in Path("/Applications").glob("ParaView*.app/Contents/MacOS/paraview"):
        return str(p)
    return None


def _gmsh_version() -> str | None:
    try:
        import gmsh  # noqa: PLC0415

        return getattr(gmsh, "__version__", "installed")
    except Exception:  # noqa: BLE001
        return None
