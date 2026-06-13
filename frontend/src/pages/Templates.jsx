import { useQuery } from "@tanstack/react-query";
import { Wind } from "lucide-react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui";

export function Templates() {
  const { data: templates = [] } = useQuery({
    queryKey: ["templates"],
    queryFn: api.listTemplates,
    retry: false,
  });

  return (
    <div className="max-w-3xl">
      <h1 className="text-3xl font-bold m-0 mb-2">Templates</h1>
      <p className="text-[var(--muted-foreground)] mb-8">
        Pre-filled case specs. More arrive per the roadmap (axial fan, engine port, exhaust duct).
      </p>

      <div className="space-y-4">
        {templates.map((t) => (
          <Card key={t.id}>
            <div className="flex items-start gap-3">
              <Wind className="w-7 h-7 text-[var(--primary)] mt-1" />
              <div>
                <div className="font-semibold">{t.name}</div>
                <div className="text-xs text-[var(--muted-foreground)] font-mono mb-1">
                  {t.id} · {t.domain}
                </div>
                <div className="text-sm text-[var(--muted-foreground)]">{t.description}</div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
