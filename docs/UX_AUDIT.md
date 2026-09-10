# UX / UI Audit — 2026-09-10

Method: walked the full airfoil pipeline in the browser (new case → geometry →
mesh → physics → validate → run → results) plus every top-level page, with the
backend log and browser console open. Findings are ordered by impact.
`[fixed]` = corrected in `feature/ux-audit-run-visibility`; the rest are flagged
for upcoming development.

## P0 — blocks the core "set up → run → see what's happening" loop

| # | Finding | Evidence | Status |
|---|---------|----------|--------|
| 1 | **Run shows nothing for ~50s after Start.** `start_run` regenerated the whole case *including the Gmsh mesh* before returning a run id, so the console sat on "waiting for output" with no feedback. The mesh had just been generated on the Mesh tab. | `POST /runs/start` took ~50s; WebSocket only opened after. | [fixed] mesh reused via signature; Run returns immediately and streams prep stages |
| 2 | **No visibility into mesh generation.** Generate showed only an elapsed timer; Gmsh output was suppressed. Users can't tell if it's working or hung. | "Generating mesh… 12s" with no log | [fixed] Gmsh log captured + tailed live in the Mesh tab |
| 3 | **Case/run status never updates.** Every case shows `running` forever on Dashboard/Cases; case header stays `draft` after a completed solve. | Dashboard listed 3 cases all "running"; header `status: draft` post-run | [fixed] status set to completed/failed when the stream ends; header refetches |
| 4 | **Misleading timing hint.** "Meshing typically 5–15s" — a 50c far-field mesh takes ~50s. | measured 50s | [fixed] hint scales with far-field |

## P1 — real friction, fix next

| # | Finding | Suggested fix |
|---|---------|---------------|
| 5 | **Layout shift on Mesh tab.** y+ results expand their card and push the Generate button down ~40px; a click aimed at it can miss (I did). | Reserve space for y+ results (min-height) or place results inline. [fixed] min-height |
| 6 | **No stage progress bar on Run.** Stages arrive as text only; no sense of 3/6 → 6/6 progress. | Progress bar driven by `[n/N]` stage events. [fixed] |
| 7 | **Metric tiles scroll out of view** during a long solve; you lose Cl/Cd/iteration while watching the log. | Sticky metrics row above the console. |
| 8 | **No way to stop a run.** Divergence or a wrong setting means waiting for the container to finish. | "Stop" button → `runner.cancel(handle)`; mark run cancelled. |
| 9 | **Delete is instant** on Cases (trash icon) — no confirmation, and it removes the on-disk case dir. | Confirm dialog; or soft-delete with undo. |
| 10 | **Sweeps are manual.** Creating a sweep makes N child cases you must open and run one by one. | "Run all" on the sweep with a queue; polar fills as children finish. |
| 11 | **Settings page is a placeholder.** Image tag, data dir, default cores are all hard-coded / env-only. | Real settings form (image, cases dir, default cores, units). |
| 12 | **Solver log auto-scroll can't be paused**; reading earlier output while it streams is impossible. | "Pause scroll" toggle; detach when user scrolls up. |
| 13 | **Run tab state is lost on tab switch** — leaving Run unmounts the WebSocket; coming back shows an empty console even though the solve continues. | Lift run state to the Pipeline/store; reconnect and replay from the log file. |
| 13b | **Stage completion is lost on page reload.** Refreshing a case re-locks every tab; you must re-preview and re-generate (the mesh is on disk and reused, but the UI doesn't know). | Derive completion from server state (mesh file + signature present, last run status) instead of client-only flags. |

## P2 — polish

| # | Finding | Suggested fix |
|---|---------|---------------|
| 14 | Convergence-history chart x-axis labels overlap (every iteration labelled). | Tick interval / `minTickGap`. |
| 15 | Header meta line (`id · domain · status`) is tiny monospace — status is the most important word on the page. | Status badge (colour-coded), id secondary. |
| 16 | Physics tab has no "changed since mesh" indicator; editing velocity after meshing silently changes y+ / Re. | Show "mesh will be regenerated" when mesh-affecting fields change (signature now exists to drive this). |
| 17 | Benchmarks page shows the reference curve only — no overlay of your own sweep. | Pick a sweep → overlay polar on reference. |
| 18 | Results is a single "Load" button; nothing loads automatically after a run. | Auto-load on tab open; show "no results yet" state. |
| 19 | Templates page is a read-only list; no "create case from this" action. | Button → New Case with template preselected. |
| 20 | No empty/loading states on Sweeps (blank while the query loads). | Skeleton or spinner. |
| 21 | Validation WARN "Override" gives no visual confirmation the override was logged. | Toggle to "Overridden ✓" and keep it in the report. |
| 22 | Dark theme only; no light mode. | Theme tokens already exist — add a toggle. |

## Positive findings (keep)

- Gated tabs with lock + reason work well and prevent out-of-order setup.
- Preflight report (pass/warn/fail badges, suggestions) is clear.
- Once streaming, the residual chart + console are exactly what a CFD user wants.
- Results at α=0 gave Cd 0.0098 — matches published ~0.009, good confidence signal.
