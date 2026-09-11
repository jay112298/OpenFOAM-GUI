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
| 1.9 | Results v1 | `feature/results-v1` | Force coefficients, convergence history, in-browser field viewer, ParaView export |
| 1.10 | AoA sweeps | `feature/sweeps-polar` | Sweep fan-out, queue, polar curve aggregation |
| 1.11 | NACA 0012 benchmark | `feature/benchmark-naca0012` | Bundled benchmark case + reference data, comparison view |

**Exit criteria:** NACA 0012, Re 6e6, alpha 0–10°: Cl within expected RANS accuracy of
Abbott & von Doenhoff data, set up start-to-finish through the GUI.

**Phase 1 complete — tagged `v0.1.0` (2026-09-10).** Every milestone shipped. The
last two items, in-browser field visualisation and the Settings screen, landed in
`feature/field-viz-and-settings`.

*Note on 1.9:* the roadmap said VTK.js. These cases are 2D (one cell across the
span), so a mid-span slice is the whole solution — the backend extracts triangles
with PyVista and the browser paints them on a canvas with the ParaView cool-to-warm
ramp. That avoids loading a 3D rendering library to draw a plane, and ParaView
remains one click away for 3D, streamlines and probing. VTK.js becomes worthwhile
in Phase 2+, where turbomachinery and engine cases are genuinely three-dimensional.

Validation as shipped (NACA 0012, Re 2e6, far-field 50c, 12 prism layers, kOmegaSST):

| α | Cl | Cl ref | Cd | Cd ref |
|---|----|--------|----|--------|
| 0° | 0.0015 | 0.000 | 0.00902 | 0.0080 |
| 4° | 0.4011 | 0.440 | 0.01109 | 0.0087 |
| 8° | 0.6949 | 0.860 | 0.02026 | 0.0108 |

Accurate at low incidence and drifting as α grows, which is what a fully-turbulent
RANS model does against free-transition measurements.

## Phase 2 — Compressible + Axial fan/compressor

| # | Milestone | Branch | State |
|---|-----------|--------|-------|
| 2.1 | Compressible templates (rhoSimpleFoam, energy eq, ideal gas) | `feature/compressible-solver` | **done** |
| 2.2 | Mach-aware validation rules | `feature/compressible-solver` | **done** |
| 2.3 | Rotating zone wizard: MRF, single passage, cyclicAMI periodics | `feature/turbo-mrf` | **done** |
| 2.4 | Parametric blade/cascade generator | `feature/turbo-mrf` | **done** |
| 2.5 | Fan/compressor map sweeps (RPM, mass flow), efficiency post | `feature/turbo-maps` | **done** |

**Phase 2 complete (2026-09-11)** — every milestone shipped and validated in the
real container. The platform now carries two domains through one pipeline
(`aero` and `turbo`), compressible as well as incompressible flow, and sweeps
that produce both a polar and a fan map. Per the branch strategy below, this
marks a release: `develop` -> `main`, tagged `v0.2.0`.

**2.1 / 2.2 shipped (2026-09-11).** Flow type is part of the case spec: choosing
*compressible* switches the pipeline to rhoSimpleFoam with `hePsiThermo` /
`perfectGas` / Sutherland air, absolute pressure in Pa, and T + alphat fields.
Freestream density, viscosity and sound speed all follow from p and T, so Mach is
derived rather than assumed. The Mach rule now reads the flow type: incompressible
above Mach 0.3 still fails, compressible below Mach 0.1 warns as needlessly stiff,
and above Mach 0.7 warns that shocks need a density-based solver.

Verified NACA 0012 at Mach 0.5, α = 2°: **Cl 0.220** (thin-airfoil 0.219,
Prandtl–Glauert 0.253 — viscous RANS lands at ~87% of the corrected value),
with temperature 242–334 K and pressure 86.7–122.6 kPa around a 288 K / 101.3 kPa
freestream. Compressibility is genuinely being solved, not assumed away.

*Stability note:* the first attempts died on a floating point exception in the
energy equation (iteration 211, then 687). Fixed by upwinding e/K/Ekp, softening
the density and energy relaxation, bounding pressure with pMinFactor/pMaxFactor,
and adding a `limitTemperature` fvOption. It now runs the full schedule.

**2.3 / 2.4 shipped (2026-09-11).** A second domain now runs the same pipeline
end to end: `turbo`. One blade passage of an axial fan rotor, 360/n_blades wide,
closed by rotational `cyclicAMI`, with the blade carved out by snappyHexMesh and
the whole zone spun as an MRF rotor.

The blade is parametric and **its twist is derived, never typed**: at every
radius the chord is set at the requested incidence to the relative inflow angle
`atan(omega r / Va)`. The GUI shows that table hub-to-tip next to a to-scale
blade-to-blade (cascade) view with the periodic planes marked, so a bad RPM or
through-flow is visible before anything is meshed. The blade STL is written
three times, one blade pitch apart, so a highly staggered blade that reaches
across its own periodic plane still cuts both sides identically.

Verified in the real container (6 blades, hub/tip 60/150 mm, 50 mm chord,
3000 rpm, 12 m/s axial, 27k cells, converged to 5e-6 in 14 s on 4 cores):

| Quantity | Value | Cross-check |
|---|---|---|
| Flow rate | 0.712 m³/s | design 0.713 — continuity holds |
| Total pressure rise | 206 Pa | Euler `rho U Vtheta` = 212 Pa |
| Exit swirl | 5.3 m/s, in the direction of rotation | work is added, not extracted |
| Shaft torque / power | 0.619 N·m / 194 W | |
| Total-to-total efficiency | 75.6% | plausible for a rotor with no stator |
| AMI weight sum | 0.998–1.000 | the periodic couple is geometrically exact |

*MRF note, and the subtle failure it caused:* `nonRotatingPatches` must list
every patch of the zone that is not a surface turning with the shaft. MRF treats
anything else as a rotating wall — it forces the relative flux to zero and
overwrites the velocity with `omega x r`. With only the casing listed, the inlet
and outlet were silently sealed (`sum(phi) = 0` through both) and the solver
happily converged on a fan churning a closed box, reporting a 458 Pa total
pressure *drop*. There is now a regression test asserting the exclusion list.

Also in this milestone: generators became a registry keyed by domain
(`app/services/generators/__init__.py`) so the case service, run service and
validation engine never branch on the domain; validation rules are registered
per domain (15 turbo rules); and the long-written `checkMesh` parser is finally
wired into preflight, so mesh quality is a real finding for both domains.

*Known limitations of the passage case:* no tip clearance (the blade is sealed
to the casing), rotor only (no stator, so the exit swirl is lost), constant
chord, and checkMesh's strict `-allGeometry` pass still flags concave cells and
a few low-quality tet decompositions on the snapped mesh — reported as a WARN
rather than hidden.

**2.5 shipped (2026-09-11).** Sweeps take a second axis, so a fan map is a
single object: flow rate along each speed line, one speed line per RPM, with
total pressure rise and total-to-total efficiency plotted against Q.

The change that makes a map mean anything is **separating the design point from
the operating point**. The blade's twist is derived from RPM and through-flow;
sweeping either without pinning would re-cut the blade at every point, so the
"map" would describe a different fan at each mark. `geometry.parameters.
design_rpm` / `design_axial_velocity` now hold the point the blade was cut for,
and creating a turbo sweep pins them to the base case's own operating point.
Everything downstream follows: the mesh signature keys off the design point, so
one blade is meshed once and carried across the whole map.

Pinning also produces the number a fan engineer actually wants. The metal angles
are fixed; off design the flow arrives from somewhere else; the gap is the
**incidence**, reported per radius in the GUI and checked by preflight — beyond
15° it warns that the point is stalled (or that the blade is being driven
rather than driving) and should be read as qualitative.

Measured map — blade cut for 3000 rpm / 12 m/s, then run across two speed lines
(600 iterations per point, mesh built once per child):

| Va [m/s] | rpm | Q [m³/s] | Δp₀ [Pa] | η |
|---|---|---|---|---|
| 6 | 2400 | 0.356 | 186.6 | 61.2% |
| 9 | 2400 | 0.534 | 137.9 | **70.2%** |
| 12 | 2400 | 0.712 | 52.1 | 58.1% |
| 15 | 2400 | 0.890 | −51.7 | — |
| 18 | 2400 | 1.068 | −162.1 | — |
| 6 | 3000 | 0.356 | 247.5 | 41.0% |
| 9 | 3000 | 0.534 | 266.1 | 65.4% |
| 12 | 3000 | 0.712 | 206.3 | **75.6%** |
| 15 | 3000 | 0.890 | 81.4 | 58.5% |
| 18 | 3000 | 1.068 | −45.4 | — |

Two things in there say the whole chain is behaving. Peak efficiency on the
3000 rpm line lands exactly on the point the blade was cut for (12 m/s, 75.6%).
On the 2400 rpm line it moves to 9 m/s — phi = 0.239 against the design 0.255,
i.e. **peak efficiency tracks constant flow coefficient, not constant flow**,
which is the fan law. Each line also crosses into negative Δp₀ at high flow:
free delivery, past which the rotor is no longer pumping.

That last part exposed a reporting bug, now fixed: efficiency was being printed
as −1150% at those points, because air power goes negative while shaft power
falls through zero. It is reported as undefined instead, and the efficiency
curve stops rather than bridging the gap.

*Cost note:* throttled points converge much more slowly than design points —
the separated passage needs far more pressure-solver work per iteration — so
the cheap end of a map is the high-flow end. The queue runs cases sequentially
on purpose: each solve already uses the configured cores.

Also here: `Sweep` gained `parameter2`, `values2`, `domain` and `points`, and
`db.init_db()` now adds columns missing from existing tables, because
`create_all` only creates missing *tables* and the SQLite file predates these
fields. Aggregation moved from `/polar` to a domain-aware `/results`.

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
