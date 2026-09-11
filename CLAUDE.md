# OpenFOAM GUI

Web GUI for OpenFOAM v2506 (Docker, arm64). Read PLAN.md (architecture, locked
decisions) and ROADMAP.md (milestones, branch strategy) before feature work.

## Commands

```bash
# Backend (Python 3.12 venv, NOT system python)
cd backend && .venv/bin/uvicorn app.main:app --reload   # :8000
cd backend && .venv/bin/pytest                          # tests
cd backend && .venv/bin/ruff check app                  # lint

# Frontend (plain JS + JSX, no TypeScript)
cd frontend && npm run dev      # :5173, proxies /api -> :8000
cd frontend && npm run build    # vite build (must pass before merge)
cd frontend && npm run lint     # eslint
```

## Architecture (the short version)

Pipeline pattern, identical for every domain (aero/turbo/engine):
`Geometry → Mesh → Physics → BCs → Numerics → Validate → Run → Post`

- **Case spec** = one versioned JSON document (`app/models/case.py: CaseSpec`)
  holding all stages. Templates are pre-filled specs. Generators and the
  validation engine both consume it.
- **Generator registry** (`app/services/generators/__init__.py`): `spec["domain"]`
  picks the module (`aero` -> airfoil_case, `turbo` -> axial_fan_case). Every
  generator exposes the same surface — `Params.from_spec`, `derive`,
  `build_case`, `summary`, `mesh_ready`, `mesh_cell_count`, `MESH_LOG` — so the
  case service, run service and validation engine never branch on the domain.
  Add a domain by adding a module + rule set, not by adding `if` statements.
- **Validation engine** (`app/services/validation/engine.py`): rules return
  PASS/WARN/FAIL. FAIL blocks the run. WARN is overridable; overrides are
  logged to the `ValidationOverride` table. Never bypass this gate. Rules are
  registered per domain in `RULES_BY_DOMAIN` (`rules.py` aero, `rules_turbo.py`).
- **Runner protocol** (`app/services/runner/base.py`): API code depends only on
  the protocol. DockerRunner uses image `opencfd/openfoam-run:2506` (same image
  scheme as the user's ~/CFD/openfoam-docker script).
- **Units**: convert at the API boundary (`app/services/units`). Everything
  internal is strict SI. Turbulence inlet values are always computed, never
  hand-typed.
- **Sweeps** (`app/services/sweeps_service.py`): one base case fanned out over
  one parameter (a curve) or two (a grid). For turbo, geometry is derived from
  the operating point, so sweeping RPM or through-flow first *pins* the design
  point (`geometry.parameters.design_rpm` / `design_axial_velocity`) — without
  that the blade is re-cut at every point and the map describes a different fan
  at each mark. Anything that derives geometry from an operating condition must
  do the same.
- **Schema changes**: there is no migration tool. `db.init_db()` adds columns
  missing from existing tables; new columns must therefore be nullable.
- **Post-processing**: PyVista server-side; ship decimated extracts to VTK.js,
  never full volume meshes.

## Conventions

- Branches: `feature/<milestone>` off `develop`; `main` is release-only.
- Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:` ...).
- Before merge to develop: frontend `npm run build` passes, backend
  `python -c "from app.main import app"` passes.
- Frontend is plain JavaScript (`.jsx`/`.js`), no TypeScript. `@/` aliases `src/`.
- OpenFOAM dicts: generate through foamlib/generators, never string-template
  in route handlers.
