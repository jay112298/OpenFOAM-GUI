import { useParams, NavLink, Routes, Route, Navigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Placeholder } from "@/components/Placeholder";

const stages = [
  { path: "geometry", label: "Geometry" },
  { path: "mesh", label: "Mesh" },
  { path: "physics", label: "Physics & BCs" },
  { path: "validate", label: "Validate" },
  { path: "run", label: "Run" },
  { path: "results", label: "Results" },
];

export function CaseView() {
  const { id } = useParams();

  return (
    <div>
      <h1 className="text-3xl font-bold m-0 mb-1">Case {id}</h1>
      <p className="text-[var(--muted-foreground)] mt-0 mb-6">
        Pipeline: every stage must be green before Run unlocks.
      </p>

      <div className="flex gap-1 border-b border-[var(--border)] mb-8">
        {stages.map((s) => (
          <NavLink
            key={s.path}
            to={s.path}
            className={({ isActive }) =>
              cn(
                "px-4 py-2.5 text-sm font-medium no-underline border-b-2 -mb-px",
                isActive
                  ? "border-[var(--primary)] text-[var(--foreground)]"
                  : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              )
            }
          >
            {s.label}
          </NavLink>
        ))}
      </div>

      <Routes>
        <Route index element={<Navigate to="geometry" replace />} />
        <Route
          path="geometry"
          element={
            <Placeholder
              title="Geometry"
              description="Parametric generators (NACA, blades, ducts) and STEP/STL import with 3D preview."
              phase="Phase 1"
            />
          }
        />
        <Route
          path="mesh"
          element={
            <Placeholder
              title="Mesh"
              description="snappyHexMesh wizard, y+ calculator, boundary layers, checkMesh quality gates."
              phase="Phase 1"
            />
          }
        />
        <Route
          path="physics"
          element={
            <Placeholder
              title="Physics & Boundary Conditions"
              description="Flow regime, turbulence model, fluid presets, patch-by-patch BCs with auto-computed turbulence inlet values."
              phase="Phase 1"
            />
          }
        />
        <Route
          path="validate"
          element={
            <Placeholder
              title="Preflight Validation"
              description="Rule engine report: PASS / WARN (overridable, logged) / FAIL (blocks run)."
              phase="Phase 1"
            />
          }
        />
        <Route
          path="run"
          element={
            <Placeholder
              title="Run"
              description="Job queue, live residuals and force coefficients, divergence auto-detection."
              phase="Phase 1"
            />
          }
        />
        <Route
          path="results"
          element={
            <Placeholder
              title="Results"
              description="Force coefficients, Cp plots, in-browser field slices (VTK.js), ParaView export."
              phase="Phase 1"
            />
          }
        />
      </Routes>
    </div>
  );
}
