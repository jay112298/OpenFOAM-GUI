# Development Roadmap

Working agreement: every milestone is a feature branch off `develop`, merged back via PR.
`main` only receives release merges from `develop`. See "Branch strategy" at the bottom.

Architecture and locked product decisions live in [PLAN.md](PLAN.md) — read that first.

---

## Phase 1 — Platform core + Airfoil/Wing end-to-end

**Goal:** a non-expert sets up a NACA 0012 case entirely through the GUI and gets a
polar that matches published data. This proves the pipeline pattern every other
domain will reuse.

**Status (2026-06-13): pipeline functional end-to-end; lift validated.** Full chain
(NACA generate → Gmsh 2D mesh → gmshToFoam → checkMesh → simpleFoam → forceCoeffs)
runs in the real `opencfd/openfoam-run:latest` container. The dirty snappy thin-slab
mesh was replaced with a clean 2D Gmsh C-mesh — `checkMesh` now reports **Mesh OK**.
NACA0012 at α=5°, Re 2e6: **Cl = 0.555 vs published ~0.54 (within 3%)**. Multi-core
solve (decomposePar + mpirun) verified. Backend 12 tests pass, ruff clean; frontend
builds, eslint clean.

**Known limitation (open):** drag is over-predicted (Cd ≈ 0.024 vs ~0.009) because
the mesh uses isotropic near-wall cells with wall functions, not anisotropic prism
layers — Gmsh's BoundaryLayer field + OCC structured extrude produced degenerate
cells, so it was dropped for robustness. Recovering benchmark-grade Cd needs stable
anisotropic layers (y+ ~1) — tracked as follow-up `feature/airfoil-bl-layers`.

| # | Milestone | Branch | Deliverable |
|---|-----------|--------|-------------|
| 1.1 | Case spec + storage | `feature/case-spec` | Pydantic CaseSpec stages, SQLite persistence, case CRUD wired to UI |
| 1.2 | NACA geometry service | `feature/geometry-naca` | NACA 4/5-digit generator (CadQuery), STL export, 3D preview in Geometry tab |
| 1.3 | CAD import | `feature/geometry-import` | STL/STEP upload, tessellated preview, surface patch naming |
| 1.4 | Mesh wizard | `feature/mesh-snappy` | blockMesh background + snappyHexMesh config UI, boundary layers, y+ calculator |
| 1.5 | checkMesh gates | `feature/mesh-quality` | checkMesh parser, quality thresholds feed validation engine |
| 1.6 | Physics & BC stage | `feature/physics-bcs` | Flow regime/turbulence selection, patch BC editor, auto turbulence inlet calc, unit layer |
| 1.7 | Validation engine v1 | `feature/validation-engine` | Rule framework + first 8 rules, preflight report UI, override logging |
| 1.8 | Run orchestration | `feature/run-orchestration` | DockerRunner (opencfd/openfoam-run:2506), job queue, WebSocket live residuals/forces, divergence detection |
| 1.9 | Results v1 | `feature/results-v1` | Force coefficients, Cp distribution plot, PyVista slice -> VTK.js viewer, ParaView export |
| 1.10 | AoA sweeps | `feature/sweeps-polar` | Sweep fan-out, queue, polar curve aggregation |
| 1.11 | NACA 0012 benchmark | `feature/benchmark-naca0012` | Bundled benchmark case + reference data, comparison view |

**Exit criteria:** NACA 0012, Re 6e6, alpha 0–10°: Cl within expected RANS accuracy of
Abbott & von Doenhoff data, set up start-to-finish through the GUI.

## Phase 2 — Compressible + Axial fan/compressor

| # | Milestone | Branch |
|---|-----------|--------|
| 2.1 | Compressible templates (rhoSimpleFoam, total p/T BCs, energy eq) | `feature/compressible` |
| 2.2 | Mach-aware validation rules | `feature/validation-mach` |
| 2.3 | Rotating zone wizard: MRF, single passage, cyclicAMI periodics | `feature/turbo-mrf` |
| 2.4 | Parametric blade/cascade generator | `feature/geometry-blade` |
| 2.5 | Fan/compressor map sweeps (RPM, mass flow), efficiency post | `feature/turbo-maps` |

## Phase 3 — Engine ports + Duct acoustics

| # | Milestone | Branch |
|---|-----------|--------|
| 3.1 | STEP import hardening (valve/port geometry), cfMesh option | `feature/mesh-cfmesh` |
| 3.2 | Port flow metrics: flow coefficient, swirl, tumble | `feature/engine-ports` |
| 3.3 | Transient compressible template, waveTransmissive BCs | `feature/transient-compressible` |
| 3.4 | Probe FFT/PSD, transmission loss workflow, spectra UI | `feature/acoustics-duct` |
| 3.5 | External mesh import (Gmsh/Fluent converters) | `feature/mesh-import` |

## Phase 4 — Transonic + transient turbo + remote compute

| # | Milestone | Branch |
|---|-----------|--------|
| 4.1 | rhoCentralFoam templates, shock-aware schemes + validation | `feature/transonic` |
| 4.2 | AMI sliding-mesh transient fan/compressor | `feature/turbo-ami` |
| 4.3 | SSHRunner: remote execution, file sync | `feature/runner-ssh` |

## Phase 5 — In-cylinder (long horizon)

| # | Milestone | Branch |
|---|-----------|--------|
| 5.1 | Cold flow, prescribed piston/valve motion (dynamic mesh) | `feature/engine-coldflow` |
| 5.2 | Combustion: spray + chemistry | `feature/engine-combustion` |

---

## Branch strategy

```
main      ── stable, tagged releases only (v0.1.0, v0.2.0 ...)
develop   ── integration branch, always runnable
feature/* ── one milestone each, branched off develop, PR back into develop
fix/*     ── bug fixes off develop (or main for hotfixes)
```

Rules:
1. Never commit directly to `main`. `develop` -> `main` merge marks a release.
2. One milestone = one `feature/*` branch = one PR. Keep them small enough to review.
3. Commit style: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
4. Frontend must build (`npm run build`) and backend must import (`python -c "from app.main import app"`)
   before any merge to `develop`. CI enforcement comes with milestone 1.1.
5. Tag `main` at every phase exit (Phase 1 done -> `v0.1.0`).
