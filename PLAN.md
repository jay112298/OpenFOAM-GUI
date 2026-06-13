# OpenFOAM GUI — Product & Architecture Plan

Goal: a web GUI that lets a non-expert set up, run, and analyze OpenFOAM cases across
external aerodynamics, turbomachinery, and IC engine flow paths — with a validation
engine that makes it hard to run a physically meaningless case.

Target: OpenFOAM v2506 (openfoam.com) in Docker on macOS (Apple Silicon, arm64 images).
Single user. Local compute now, remote-ready job abstraction.

Development sequencing lives in [ROADMAP.md](ROADMAP.md).

---

## 1. Locked Decisions

| Decision | Choice |
|----------|--------|
| Geometry input | Parametric generators (NACA airfoils, blades, ducts) + CAD import (STEP/STL) |
| IC engine scope | Phased: ports/manifolds → duct acoustics → cold-flow in-cylinder → combustion |
| Post-processing | In-browser 3D (VTK.js) + one-click ParaView export |
| Compute | Local Docker now; Runner abstraction so SSH/cluster/cloud plugs in later |
| First turbo machine | Axial fans/compressors (single passage, MRF first, AMI later) |
| Mach regime | Up to transonic (shock capturing required eventually) |
| Acoustics | Duct acoustics: probe FFT, spectra, transmission loss |
| Meshing | Built-in (blockMesh, snappyHexMesh, cfMesh) + external import (Gmsh, Fluent) |
| First end-to-end module | Airfoil/wing — proves the whole pipeline pattern |
| Guardrails | Errors hard-block; warnings overridable with one click, overrides logged |

## 2. Core Architecture Concept

Every domain module (aero, turbo, engine) implements the same **pipeline**:

```
Geometry → Mesh → Physics → Boundary Conditions → Numerics → Validate → Run → Post
```

- Each stage = a Pydantic schema + validation rules + a UI step.
- A **case spec** is one YAML/JSON document capturing all stages — versioned,
  reproducible, diffable. Templates are pre-filled case specs.
- The **validation engine** runs rules against the full case spec and produces a
  **preflight report**: list of PASS / WARN (overridable) / FAIL (blocking) items,
  each with explanation and suggested fix.

### Validation engine v1 rules
- BC compatibility matrix (inlet/outlet pressure-velocity combinations that are well-posed)
- Solver vs Mach regime (incompressible solver blocked when estimated Ma > 0.3)
- Turbulence wall treatment vs estimated y+ (wall functions vs low-Re mismatch)
- Turbulence inlet values always computed (intensity + length scale → k, omega/epsilon)
- checkMesh quality gates (non-orthogonality, skewness, aspect ratio thresholds)
- Courant number pre-estimate for transient cases
- Scheme/solver compatibility (e.g. steadyState ddt with transient solver)
- Reynolds number sanity vs selected turbulence/transition model
- Divergence auto-detection during run (residual spike → stop + diagnose hint)

### Cross-cutting features
- **Unit layer**: GUI accepts mm, inches, RPM, bar, °C; converts to strict SI for OpenFOAM.
- **Parameter sweeps**: AoA sweep → polar; RPM sweep → fan/compressor map. Job queue
  runs cases sequentially/parallel; results aggregated into curves.
- **Validation library**: bundled benchmark cases with experimental data
  (NACA 0012 polars, pipe friction, ERCOFTAC) to verify the toolchain.
- **Educational layer**: every parameter has physical meaning, sane range, and
  "what happens if wrong" in its tooltip/panel.
- **Run report**: PDF/HTML with setup summary, mesh stats, residuals, results plots.

## 3. Tech Stack

### Frontend
| Concern | Tech |
|---------|------|
| Framework | React 19 + JavaScript (JSX) + Vite |
| Styling | Tailwind CSS v4 |
| State | Zustand |
| Server state | TanStack Query |
| Charts (residuals, polars, spectra) | Recharts |
| Geometry/mesh preview | Three.js + react-three-fiber (added in milestone 1.2) |
| Field post-processing | VTK.js (added in milestone 1.9) |
| Routing | react-router |

### Backend (Python 3.12 + FastAPI, venv at backend/.venv)
| Concern | Tech |
|---------|------|
| API + WebSockets | FastAPI, uvicorn |
| OpenFOAM dict I/O | foamlib + generators |
| Parametric geometry + STEP | CadQuery (OpenCascade kernel) |
| External meshes | Gmsh Python API; OpenFOAM converters (gmshToFoam, fluentMeshToFoam) |
| Post-processing pipeline | PyVista (vtkOpenFOAMReader): extract, decimate, serve VTP to client |
| Signal processing | NumPy/SciPy: FFT, PSD, transmission loss |
| Persistence | SQLite + SQLModel |
| Job execution | Runner protocol: DockerRunner (now) → SSHRunner (later) |
| Containers | docker SDK; image `opencfd/openfoam-run:2506` (same scheme as ~/CFD/openfoam-docker) |

### OpenFOAM solver mapping
| Use case | Solver / approach |
|----------|------------------|
| Airfoil/wing steady incompressible | simpleFoam + kOmegaSST |
| Scale models, low Re (1e4–5e5) | simpleFoam + kOmegaSSTLM (transition) |
| Subsonic compressible steady | rhoSimpleFoam |
| Transonic with shocks | rhoCentralFoam (transient density-based) / rhoSimpleFoam with care |
| Axial fan/compressor steady | simpleFoam or rhoSimpleFoam + MRF, cyclicAMI periodic passage |
| Axial fan transient (later) | pimpleFoam/rhoPimpleFoam + AMI sliding mesh |
| Engine port flow | simpleFoam / rhoSimpleFoam; swirl/tumble/flow-coefficient function objects |
| Duct acoustics | rhoPimpleFoam, waveTransmissive BCs, pressure probes → FFT/TL |
| In-cylinder (future) | engine motion libs, sprayFoam/reactingFoam class |

## 4. Risks / Notes
- Transonic convergence is genuinely hard; defaults + guardrails matter most there.
- snappyHexMesh struggles with thin trailing edges and valve seats — cfMesh and
  external mesh import are the escape hatches.
- VTK.js has browser memory limits — server-side decimation/extracts only, never
  ship full volume meshes to the browser.
- Apple Silicon: arm64 OpenFOAM images (no Rosetta penalty).
- Single-user assumption: no auth; revisit if that changes.
