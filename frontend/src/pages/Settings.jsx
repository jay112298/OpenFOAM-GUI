import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Badge, Button, Card, Field, Input, Stat } from "@/components/ui";

const mb = (bytes) =>
  bytes > 1024 ** 3
    ? `${(bytes / 1024 ** 3).toFixed(2)} GB`
    : `${Math.round(bytes / 1024 ** 2)} MB`;

export function Settings() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: api.getSettings,
    retry: false,
  });
  const [draft, setDraft] = useState(null);
  const values = draft ?? data?.values ?? {};

  const save = useMutation({
    mutationFn: () => api.saveSettings(values),
    onSuccess: (fresh) => {
      setDraft(null);
      qc.setQueryData(["settings"], fresh);
      qc.invalidateQueries({ queryKey: ["docker-status"] });
    },
  });

  const set = (k, v) => setDraft({ ...values, [k]: v });
  const dirty = draft !== null && data && JSON.stringify(draft) !== JSON.stringify(data.values);

  if (isLoading) return <div className="text-[var(--muted-foreground)]">Loading settings…</div>;
  if (!data) return <div className="text-[var(--destructive)]">Settings unavailable — is the backend running?</div>;

  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-bold m-0 mb-2">Settings</h1>
      <p className="text-[var(--muted-foreground)] mb-8">
        Where your cases live and which OpenFOAM build runs them.
      </p>

      <Card className="mb-6">
        <div className="text-sm font-semibold mb-3">Solver</div>
        <Field
          label="OpenFOAM Docker image"
          help={
            data.docker.connected
              ? data.docker.image?.available
                ? "Image is present locally."
                : "Not pulled yet — the first run will have to download it."
              : "Docker isn't reachable, so the image can't be checked."
          }
        >
          <Input
            value={values.openfoam_image ?? ""}
            onChange={(e) => set("openfoam_image", e.target.value)}
            spellCheck="false"
          />
        </Field>
        <Field label="Default CPU cores for new cases" help="Recommended 2–4 (physical cores). Each case can still override this.">
          <Input
            type="number"
            min="1"
            value={values.default_n_procs ?? 1}
            onChange={(e) => set("default_n_procs", parseInt(e.target.value) || 1)}
          />
        </Field>
        <div className="flex items-center gap-3">
          <Button onClick={() => save.mutate()} disabled={!dirty || save.isPending}>
            {save.isPending ? "Saving…" : "Save changes"}
          </Button>
          {dirty && <span className="text-xs text-[var(--warning)]">unsaved changes</span>}
          {save.isSuccess && !dirty && <span className="text-xs text-[var(--success)]">Saved ✓</span>}
          {save.isError && <span className="text-sm text-[var(--destructive)]">{save.error.message}</span>}
        </div>
      </Card>

      <Card className="mb-6">
        <div className="text-sm font-semibold mb-3">Storage</div>
        <div className="grid grid-cols-2 gap-3 mb-4">
          <Stat label="Cases on disk" value={String(data.storage.cases_on_disk)} />
          <Stat label="Space used" value={mb(data.storage.cases_bytes)} />
        </div>
        <dl className="text-xs font-mono grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 m-0">
          {Object.entries(data.paths).map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-[var(--muted-foreground)]">{k.replace(/_/g, " ")}</dt>
              <dd className="m-0 break-all">{v}</dd>
            </div>
          ))}
        </dl>
        <p className="text-xs text-[var(--muted-foreground)] mt-3 m-0">
          Deleting a case removes its directory here permanently. Copy a case folder elsewhere
          before experimenting if you want a snapshot.
        </p>
      </Card>

      <Card>
        <div className="text-sm font-semibold mb-3">Environment</div>
        <div className="flex flex-col gap-2 text-sm">
          <Row label="Docker daemon">
            <Badge severity={data.docker.connected ? "pass" : "fail"}>
              {data.docker.connected ? "connected" : "offline"}
            </Badge>
          </Row>
          <Row label="OpenFOAM image">
            <Badge severity={data.docker.image?.available ? "pass" : "warn"}>
              {data.docker.image?.available ? "available" : "not pulled"}
            </Badge>
          </Row>
          <Row label="ParaView">
            <span className="font-mono text-xs text-[var(--muted-foreground)]">
              {data.tools.paraview ?? "not found"}
            </span>
          </Row>
          <Row label="Gmsh">
            <span className="font-mono text-xs text-[var(--muted-foreground)]">
              {data.tools.gmsh ?? "not found"}
            </span>
          </Row>
          <Row label="GUI version">
            <span className="font-mono text-xs text-[var(--muted-foreground)]">{data.version}</span>
          </Row>
        </div>
      </Card>
    </div>
  );
}

function Row({ label, children }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1 border-b border-[var(--border)] last:border-0">
      <span className="text-[var(--muted-foreground)]">{label}</span>
      {children}
    </div>
  );
}
