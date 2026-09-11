import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import { Badge, Button, Card, Field, Input, Select } from "@/components/ui";

export function Sweeps() {
  const qc = useQueryClient();
  const { data: cases = [] } = useQuery({ queryKey: ["cases"], queryFn: api.listCases, retry: false });
  const { data: sweeps = [] } = useQuery({ queryKey: ["sweeps"], queryFn: api.listSweeps, retry: false });

  const [baseCase, setBaseCase] = useState("");
  const [values, setValues] = useState("0, 2, 4, 6, 8, 10");

  const create = useMutation({
    mutationFn: () => {
      const vals = values.split(",").map((v) => parseFloat(v.trim())).filter((v) => !isNaN(v));
      return api.createSweep(baseCase || cases[0]?.id, vals, "physics.reference.angle_of_attack", "AoA sweep");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sweeps"] }),
  });

  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-bold m-0 mb-2">Parameter Sweeps</h1>
      <p className="text-[var(--muted-foreground)] mb-8">
        Fan out one base case across a parameter (e.g. angle of attack) → polar curve.
      </p>

      <Card className="mb-6">
        <div className="text-sm font-semibold mb-3">New AoA sweep</div>
        <Field label="Base case">
          <Select
            options={cases.map((c) => `${c.id} — ${c.name}`)}
            value={baseCase ? `${baseCase}` : ""}
            onChange={(e) => setBaseCase(e.target.value.split(" — ")[0])}
          />
        </Field>
        <Field label="Angle of attack values" unit="deg" help="Comma-separated.">
          <Input value={values} onChange={(e) => setValues(e.target.value)} />
        </Field>
        <Button onClick={() => create.mutate()} disabled={create.isPending || cases.length === 0}>
          {create.isPending ? "Creating…" : "Create sweep"}
        </Button>
        <p className="text-xs text-[var(--muted-foreground)] mt-2">
          Creates child cases. Run each from its case page; the polar fills in as results land.
        </p>
      </Card>

      {sweeps.map((s) => <SweepCard key={s.id} sweep={s} />)}
    </div>
  );
}

function SweepCard({ sweep }) {
  const qc = useQueryClient();
  // poll while the queue is running so the polar and per-case rows fill in live
  // refetchIntervalInBackground: the queue must keep updating even when this
  // browser tab isn't focused (a sweep runs for minutes).
  const { data: st } = useQuery({
    queryKey: ["sweep-status", sweep.id],
    queryFn: () => api.sweepStatus(sweep.id),
    retry: false,
    refetchInterval: (q) => (q.state.data?.queue?.running ? 2000 : false),
    refetchIntervalInBackground: true,
  });
  const { data } = useQuery({
    queryKey: ["polar", sweep.id],
    queryFn: () => api.polar(sweep.id),
    retry: false,
    refetchInterval: st?.queue?.running ? 5000 : false,
    refetchIntervalInBackground: true,
  });
  const runAll = useMutation({
    mutationFn: () => api.runSweep(sweep.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sweep-status", sweep.id] }),
  });
  const stopAll = useMutation({
    mutationFn: () => api.stopSweep(sweep.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sweep-status", sweep.id] }),
  });

  const points = (data?.points || []).map((p) => ({ aoa: p.value, cl: p.cl, cd: p.cd }));
  const haveData = points.some((p) => p.cl != null);
  const running = !!st?.queue?.running;
  const sev = { completed: "pass", failed: "fail", running: "warn", draft: "warn" };

  return (
    <Card className="mb-4">
      <div className="flex items-start justify-between gap-3 mb-1">
        <div>
          <div className="text-sm font-semibold">{sweep.name}</div>
          <div className="text-xs text-[var(--muted-foreground)] font-mono">
            {sweep.parameter} · {sweep.case_ids.length} cases
            {st ? ` · ${st.done}/${st.total} done` : ""}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {running ? (
            <Button variant="danger" onClick={() => stopAll.mutate()} disabled={stopAll.isPending}>
              Stop queue
            </Button>
          ) : (
            <Button onClick={() => runAll.mutate()} disabled={runAll.isPending}>
              {runAll.isPending ? "Starting…" : "Run all"}
            </Button>
          )}
        </div>
      </div>

      {st && (
        <div className="mb-3">
          <div className="h-1.5 w-full bg-[var(--muted)] rounded overflow-hidden">
            <div className="h-full bg-[var(--primary)] transition-all duration-500"
              style={{ width: `${st.total ? (st.done / st.total) * 100 : 0}%` }} />
          </div>
          {running && (
            <div className="text-[11px] text-[var(--muted-foreground)] mt-1">{st.queue.message}</div>
          )}
        </div>
      )}

      {st && (
        <div className="flex flex-wrap gap-2 mb-4">
          {st.children.map((c) => (
            <span key={c.case_id}
              className="text-[11px] px-2 py-1 rounded bg-[var(--secondary)] flex items-center gap-1.5">
              <Badge severity={sev[c.status] || "warn"}>{c.status}</Badge>
              <span className="font-mono">
                {c.value}° {c.cl != null ? `· Cl ${c.cl.toFixed(3)} Cd ${c.cd.toFixed(4)}` : ""}
              </span>
            </span>
          ))}
        </div>
      )}

      {haveData ? (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={points}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="aoa" stroke="var(--muted-foreground)" fontSize={11} label={{ value: "AoA [deg]", position: "insideBottom", offset: -2, fontSize: 11 }} />
            <YAxis stroke="var(--muted-foreground)" fontSize={11} />
            <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)" }} />
            <Legend />
            {/* animation off: Recharts can leave the curve at dasharray "0, len" */}
            <Line type="monotone" dataKey="cl" name="Cl" stroke="#3b82f6" isAnimationActive={false} />
            <Line type="monotone" dataKey="cd" name="Cd" stroke="#ef4444" isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-sm text-[var(--muted-foreground)]">
          No results yet — hit “Run all” to solve every case in this sweep; the polar fills in as they finish.
        </p>
      )}
    </Card>
  );
}
