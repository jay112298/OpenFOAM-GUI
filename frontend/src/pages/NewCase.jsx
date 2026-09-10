import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Wind } from "lucide-react";
import { api } from "@/lib/api";
import { Button, Card, Field, Input } from "@/components/ui";
import { cn } from "@/lib/utils";

export function NewCase() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [template, setTemplate] = useState("airfoil");

  const { data: templates = [] } = useQuery({
    queryKey: ["templates"],
    queryFn: api.listTemplates,
    retry: false,
  });

  const create = useMutation({
    mutationFn: () => api.createCase(name || "Untitled", template),
    onSuccess: (c) => navigate(`/cases/${c.id}`),
  });

  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-bold m-0 mb-2">New Case</h1>
      <p className="text-[var(--muted-foreground)] mb-8">Pick a template, then walk the pipeline.</p>

      <Card>
        <Field label="Case name">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. NACA0012-baseline" />
        </Field>

        <div className="text-sm font-medium mb-2">Template</div>
        <div className="grid grid-cols-2 gap-3 mb-6">
          {templates.map((t) => (
            <button
              key={t.id}
              onClick={() => setTemplate(t.id)}
              className={cn(
                "p-4 rounded-xl border text-left cursor-pointer transition-all",
                template === t.id
                  ? "border-[var(--primary)] bg-[var(--primary)]/10"
                  : "border-[var(--border)] hover:border-[var(--primary)]/50"
              )}
            >
              <Wind className="w-6 h-6 text-[var(--primary)] mb-2" />
              <div className="font-semibold">{t.name}</div>
              <div className="text-xs text-[var(--muted-foreground)] mt-1">{t.description}</div>
            </button>
          ))}
        </div>

        {create.isError && (
          <p className="text-sm text-[var(--destructive)] mb-3">{create.error.message}</p>
        )}
        <Button onClick={() => create.mutate()} disabled={create.isPending}>
          {create.isPending ? "Creating…" : "Create case"}
        </Button>
      </Card>
    </div>
  );
}
