import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, setSpecPath, getSpecPath } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Geometry, Mesh, Physics, Validate, Run, Results } from "./stages";

const STAGES = [
  { key: "geometry", label: "Geometry", Comp: Geometry },
  { key: "mesh", label: "Mesh", Comp: Mesh },
  { key: "physics", label: "Physics & BCs", Comp: Physics },
  { key: "validate", label: "Validate", Comp: Validate },
  { key: "run", label: "Run", Comp: Run },
  { key: "results", label: "Results", Comp: Results },
];

export function CaseView() {
  const { id } = useParams();
  const { data: caseData } = useQuery({
    queryKey: ["case", id],
    queryFn: () => api.getCase(id),
    retry: false,
  });

  if (!caseData) {
    return <div className="text-[var(--muted-foreground)]">Loading case…</div>;
  }
  // key by id so the editor remounts (and re-seeds its spec) when the case changes
  return <Pipeline key={caseData.id} caseData={caseData} />;
}

function Pipeline({ caseData }) {
  const id = caseData.id;
  const [active, setActive] = useState("geometry");
  const [spec, setSpec] = useState(caseData.spec);

  const setField = (path, value) => setSpec((s) => setSpecPath(s, path, value));
  const field = (path) => getSpecPath(spec, path);
  const persist = () => api.updateSpec(id, spec);

  const Active = STAGES.find((s) => s.key === active).Comp;

  return (
    <div>
      <h1 className="text-2xl font-bold m-0 mb-1">{caseData.name}</h1>
      <p className="text-[var(--muted-foreground)] mt-0 mb-6 font-mono text-xs">
        {id} · {caseData.domain} · status: {caseData.status}
      </p>

      <div className="flex gap-1 border-b border-[var(--border)] mb-8">
        {STAGES.map((s) => (
          <button
            key={s.key}
            onClick={() => setActive(s.key)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium cursor-pointer border-b-2 -mb-px",
              active === s.key
                ? "border-[var(--primary)] text-[var(--foreground)]"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            )}
          >
            {s.label}
          </button>
        ))}
      </div>

      <Active caseId={id} spec={spec} field={field} setField={setField} persist={persist} />
    </div>
  );
}
