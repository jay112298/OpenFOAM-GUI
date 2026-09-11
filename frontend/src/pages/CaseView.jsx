import { useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { api, setSpecPath, getSpecPath } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui";
import { Geometry, Mesh, Physics, Validate, Run, Results } from "./stages";
import { TurboGeometry, TurboMesh, TurboPhysics, TurboResults } from "./stages_turbo";

const STATUS_SEVERITY = {
  draft: "warn",
  running: "warn",
  completed: "pass",
  failed: "fail",
};

// Each stage gates the next: you can't open a stage until the previous is
// complete. The pipeline is the same for every domain — only the Geometry,
// Mesh, Physics and Results panels differ, so each domain supplies its own.
const stagesFor = (domain) => {
  const turbo = domain === "turbo";
  return [
    {
      key: "geometry", label: "Geometry", gate: turbo ? "Preview the blade first" : "Preview the section first",
      Comp: turbo ? TurboGeometry : Geometry,
    },
    { key: "mesh", label: "Mesh", Comp: turbo ? TurboMesh : Mesh, gate: "Generate the mesh first" },
    {
      key: "physics", label: "Physics & BCs", Comp: turbo ? TurboPhysics : Physics,
      gate: "Set flow conditions",
    },
    { key: "validate", label: "Validate", Comp: Validate, gate: "Pass preflight (no FAIL)" },
    { key: "run", label: "Run", Comp: Run, gate: "Finish the solve" },
    { key: "results", label: "Results", Comp: turbo ? TurboResults : Results, gate: "" },
  ];
};

export function CaseView() {
  const { id } = useParams();
  const { data: caseData } = useQuery({
    queryKey: ["case", id],
    queryFn: () => api.getCase(id),
    retry: false,
  });
  // Server-side view of what's already done (mesh on disk, preflight, last run)
  // so a reload doesn't re-lock stages whose work exists.
  const { data: pipe, isLoading: pipeLoading } = useQuery({
    queryKey: ["pipeline-status", id],
    queryFn: () => api.pipelineStatus(id),
    retry: false,
  });
  if (!caseData || pipeLoading) {
    return <div className="text-[var(--muted-foreground)]">Loading case…</div>;
  }
  return <Pipeline key={caseData.id} caseData={caseData} pipe={pipe} />;
}

function seedDone(pipe) {
  if (!pipe) return {};
  const meshed = !!pipe.mesh?.exists;
  const ran = pipe.latest_run?.status === "completed";
  return {
    // a mesh on disk means geometry and mesh were both completed earlier
    geometry: meshed,
    mesh: meshed,
    physics: meshed,
    validate: meshed && !!pipe.validation?.can_run,
    run: ran,
  };
}

function Pipeline({ caseData, pipe }) {
  const id = caseData.id;
  const [active, setActive] = useState("geometry");
  const [spec, setSpec] = useState(caseData.spec);
  const [done, setDone] = useState(() => seedDone(pipe)); // stage key -> bool
  const STAGES = stagesFor(caseData.domain);

  const setField = (path, value) => setSpec((s) => setSpecPath(s, path, value));
  const field = (path) => getSpecPath(spec, path);
  const persist = () => api.updateSpec(id, spec);
  const markDone = useCallback((key, ok = true) => setDone((d) => ({ ...d, [key]: ok })), []);

  // a stage is unlocked if it's the first, or every earlier stage is done
  const unlocked = (idx) => idx === 0 || STAGES.slice(0, idx).every((s) => done[s.key]);

  const activeIdx = STAGES.findIndex((s) => s.key === active);
  const Active = STAGES[activeIdx].Comp;

  return (
    <div>
      <div className="flex items-center gap-3 mb-1">
        <h1 className="text-2xl font-bold m-0">{caseData.name}</h1>
        <Badge severity={STATUS_SEVERITY[caseData.status] || "warn"}>{caseData.status}</Badge>
      </div>
      <p className="text-[var(--muted-foreground)] mt-0 mb-6 font-mono text-xs">
        {id} · {caseData.domain}
      </p>

      {/* scrolls rather than clipping: at narrow widths the later stages were
          unreachable because the tab row simply ran off the edge */}
      <div className="flex gap-1 border-b border-[var(--border)] mb-8 overflow-x-auto">
        {STAGES.map((s, i) => {
          const locked = !unlocked(i);
          return (
            <button
              key={s.key}
              onClick={() => !locked && setActive(s.key)}
              disabled={locked}
              title={locked ? STAGES[i - 1]?.gate : ""}
              className={cn(
                "px-4 py-2.5 text-sm font-medium border-b-2 -mb-px flex items-center gap-1.5 whitespace-nowrap",
                locked ? "cursor-not-allowed text-[var(--muted)]" : "cursor-pointer",
                active === s.key
                  ? "border-[var(--primary)] text-[var(--foreground)]"
                  : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              )}
            >
              {locked && <Lock className="w-3 h-3" />}
              {done[s.key] && !locked && <span className="text-[var(--success)]">✓</span>}
              {s.label}
            </button>
          );
        })}
      </div>

      <Active
        caseId={id}
        spec={spec}
        pipe={pipe}
        field={field}
        setField={setField}
        persist={persist}
        markDone={markDone}
        goNext={() => {
          const next = STAGES[activeIdx + 1];
          if (next) setActive(next.key);
        }}
      />
    </div>
  );
}
