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
- **Validation engine** (`app/services/validation/engine.py`): rules return
  PASS/WARN/FAIL. FAIL blocks the run. WARN is overridable; overrides are
  logged to the `ValidationOverride` table. Never bypass this gate.
- **Runner protocol** (`app/services/runner/base.py`): API code depends only on
  the protocol. DockerRunner uses image `opencfd/openfoam-run:2506` (same image
  scheme as the user's ~/CFD/openfoam-docker script).
- **Units**: convert at the API boundary (`app/services/units`). Everything
  internal is strict SI. Turbulence inlet values are always computed, never
  hand-typed.
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
