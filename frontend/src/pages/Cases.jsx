import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus, Trash2, FolderOpen } from "lucide-react";
import { api } from "@/lib/api";
import { Button, Card, Badge } from "@/components/ui";

const statusSeverity = { draft: "warn", running: "warn", completed: "pass", failed: "fail" };

export function Cases() {
  const qc = useQueryClient();
  const { data: cases = [], isLoading } = useQuery({
    queryKey: ["cases"],
    queryFn: api.listCases,
    retry: false,
  });
  const del = useMutation({
    mutationFn: api.deleteCase,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cases"] }),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold m-0">Cases</h1>
          <p className="text-[var(--muted-foreground)] mt-1 mb-0">All simulation cases</p>
        </div>
        <Link to="/cases/new" className="no-underline">
          <Button>
            <span className="flex items-center gap-2">
              <Plus className="w-4 h-4" /> New Case
            </span>
          </Button>
        </Link>
      </div>

      <Card className="p-0">
        {isLoading ? (
          <div className="p-12 text-center text-[var(--muted-foreground)]">Loading…</div>
        ) : cases.length === 0 ? (
          <div className="p-12 text-center text-[var(--muted-foreground)]">
            <FolderOpen className="w-10 h-10 mx-auto mb-3 opacity-50" />
            <p className="m-0">No cases yet.</p>
          </div>
        ) : (
          <div className="divide-y divide-[var(--border)]">
            {cases.map((c) => (
              <div key={c.id} className="flex items-center justify-between p-4">
                <Link to={`/cases/${c.id}`} className="no-underline flex-1">
                  <div className="font-medium text-[var(--foreground)]">{c.name}</div>
                  <div className="text-xs text-[var(--muted-foreground)] font-mono">
                    {c.id} · {c.domain} · {c.template_id}
                  </div>
                </Link>
                <div className="flex items-center gap-4">
                  <Badge severity={statusSeverity[c.status] || "warn"}>{c.status}</Badge>
                  <button
                    onClick={() => {
                      if (
                        window.confirm(
                          `Delete "${c.name}"?\n\nThis removes the case and its OpenFOAM directory (mesh, logs, results) from disk. This cannot be undone.`
                        )
                      ) {
                        del.mutate(c.id);
                      }
                    }}
                    className="text-[var(--muted-foreground)] hover:text-[var(--destructive)] cursor-pointer"
                    title="Delete case"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
