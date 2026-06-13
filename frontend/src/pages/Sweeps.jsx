import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import { Button, Card, Field, Input, Select } from "@/components/ui";

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
  const { data } = useQuery({
    queryKey: ["polar", sweep.id],
    queryFn: () => api.polar(sweep.id),
    retry: false,
  });
  const points = (data?.points || []).map((p) => ({ aoa: p.value, cl: p.cl, cd: p.cd }));
  const haveData = points.some((p) => p.cl != null);

  return (
    <Card className="mb-4">
      <div className="text-sm font-semibold mb-1">{sweep.name}</div>
      <div className="text-xs text-[var(--muted-foreground)] mb-3 font-mono">
        {sweep.parameter} · {sweep.case_ids.length} cases
      </div>
      {haveData ? (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={points}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="aoa" stroke="var(--muted-foreground)" fontSize={11} label={{ value: "AoA [deg]", position: "insideBottom", offset: -2, fontSize: 11 }} />
            <YAxis stroke="var(--muted-foreground)" fontSize={11} />
            <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)" }} />
            <Legend />
            <Line type="monotone" dataKey="cl" name="Cl" stroke="#3b82f6" />
            <Line type="monotone" dataKey="cd" name="Cd" stroke="#ef4444" />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-sm text-[var(--muted-foreground)]">
          No results yet — run the child cases to populate the polar.
        </p>
      )}
    </Card>
  );
}
