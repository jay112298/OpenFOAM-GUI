# OpenFOAM GUI

Web GUI that makes OpenFOAM usable for non-experts — external aerodynamics,
turbomachinery, and IC engine flow paths — with a validation engine that makes it
hard to run a physically meaningless case.

- **[PLAN.md](PLAN.md)** — product scope, architecture, tech stack
- **[ROADMAP.md](ROADMAP.md)** — phased milestones + branch strategy

## Requirements

- macOS (Apple Silicon), Docker Desktop
- OpenFOAM v2506 image: `docker pull opencfd/openfoam-run:2506`
- Python 3.12, Node 20+

## Development setup

### Backend

```bash
cd backend
python3.12 -m venv .venv          # once
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload   # http://localhost:8000  (docs at /docs)
```

### Frontend

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173 (proxies /api to backend)
```

## Repository layout

```
backend/app/
  api/         FastAPI routers (system, cases, templates, geometry, meshing,
               validation, runs, results, sweeps)
  models/      SQLModel tables + CaseSpec pipeline schema
  services/    geometry | meshing | validation | runner | post | units
  templates/   pre-filled case specs per domain
  parsers/     solver log parsing (residuals, forces)

frontend/src/
  components/  Layout, shared UI
  pages/       Dashboard, Cases, NewCase, CaseView (stage tabs), Sweeps,
               Templates, Benchmarks, Settings
  stores/      Zustand state
  lib/         API client, utilities
```

## Branching

`main` = releases only. `develop` = integration. Work happens on `feature/*`
branches, one roadmap milestone each. Details in [ROADMAP.md](ROADMAP.md).
