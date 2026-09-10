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

**Drag accuracy — investigated and largely resolved (2026-06-13).** A study of the
NACA0012 Cd over-prediction found the dominant lever was **far-field distance**, not
near-wall layers:

| Far-field | Cl | Cd | note |
|-----------|----|----|------|
| 15c | 0.55 | 0.024 | small domain inflates pressure drag |
| 50c | 0.50 | 0.012 | correct for fully-turbulent RANS |

Published NACA0012 at α=5°, Re 2e6: Cl≈0.54, Cd≈0.009 (free transition) or ≈0.012
(fully turbulent). The shipped default (far-field 50c, kOmegaSST + Spalding wall
function) gives **Cl 0.50, Cd 0.012 — both in the correct fully-turbulent RANS
range.** Remaining ~8% Cl deficit and the gap to free-transition Cd would need a
transition model (kOmegaSSTLM) + mesh-independence study.

**Boundary layers — now reliable (2026-09-10).** The earlier "0% layers added"
failures were snappy silently refusing when the prism stack was thicker than the
surface cell it had to carve them from. Fixed by keeping the surface cell at its
resolution-driven size and capping the layer count to fit (`fitted_n_layers`);
coverage is now ~99% and accuracy is unchanged from the best no-layer config:

| Config (NACA0012, α=5°, Re 2e6, far-field 50c) | Cl | Cd | Layers |
|---|---|---|---|
| fine mesh, no layers | 0.499 | 0.0125 | — |
| coarsened to fit layers (rejected) | 0.472 | 0.0204 | 98% |
| **fine mesh + 12 fitted layers** | **0.499** | **0.0125** | **99.3%** |

**Transition model (kOmegaSSTLM) — implemented, not yet a Cd win.** gammaInt +
ReThetat fields, Langtry–Menter inlet correlation, schemes/solvers, and a preflight
warning when the mesh isn't wall-resolved. On the wall-resolved mesh above it gives
Cl 0.4994 / Cd 0.01253 — indistinguishable from fully turbulent, i.e. the boundary
layer trips almost immediately at this Re with Tu = 1%. Closing the remaining gap to
the free-transition reference (Cd ≈ 0.009, Cl ≈ 0.54) needs a lower inlet turbulence
intensity (~0.05–0.1%, wind-tunnel-like) and a mesh-independence study — follow-up
`feature/transition-tuning`.

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
