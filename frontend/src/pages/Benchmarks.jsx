import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import { Card, Field, Select, Stat } from "@/components/ui";

/** Merge reference points with a sweep's polar, matched on angle of attack. */
function mergeSeries(reference, polarPoints) {
  const byAlpha = new Map();
  for (const r of reference) {
    byAlpha.set(Number(r.alpha), { alpha: Number(r.alpha), clRef: r.cl, cdRef: r.cd });
  }
  for (const p of polarPoints || []) {
    if (p.cl == null) continue;
    const a = Number(p.value);
    const row = byAlpha.get(a) || { alpha: a };
    byAlpha.set(a, { ...row, clYours: p.cl, cdYours: p.cd });
  }
  return [...byAlpha.values()].sort((a, b) => a.alpha - b.alpha);
}

export function Benchmarks() {
  const [sweepId, setSweepId] = useState("");

  const { data: naca } = useQuery({
    queryKey: ["benchmark", "naca0012"],
    queryFn: () => api.getBenchmark("naca0012"),
    retry: false,
  });
  const { data: sweeps = [] } = useQuery({
    queryKey: ["sweeps"],
    queryFn: api.listSweeps,
    retry: false,
  });
  const { data: polar } = useQuery({
    queryKey: ["polar", sweepId],
    queryFn: () => api.polar(sweepId),
    enabled: !!sweepId,
    retry: false,
  });

  const rows = naca ? mergeSeries(naca.reference, polar?.points) : [];
  const compared = rows.filter((r) => r.clYours != null && r.clRef != null);
  // mean absolute error against the reference, over the points you actually ran
  const err = (key, refKey) =>
    compared.length
      ? compared.reduce((s, r) => s + Math.abs(r[key] - r[refKey]), 0) / compared.length
      : null;
  const clErr = err("clYours", "clRef");
  const cdErr = err("cdYours", "cdRef");

  return (
    <div className="max-w-3xl">
      <h1 className="text-3xl font-bold m-0 mb-2">Benchmarks</h1>
      <p className="text-[var(--muted-foreground)] mb-8">
        Reference data to verify the toolchain before trusting your own results. Run an AoA
        sweep on the matching airfoil, then overlay it here to see how far off you are.
      </p>

      {naca && (
        <Card>
          <div className="text-sm font-semibold">{naca.name}</div>
          <div className="text-xs text-[var(--muted-foreground)] mb-3">
            Re ≈ {naca.reynolds.toExponential(0)} · {naca.source}
          </div>

          <Field label="Overlay one of your sweeps" help="Only cases that have finished contribute points.">
            <Select
              options={["— none —", ...sweeps.map((s) => `${s.id} — ${s.name}`)]}
              value={sweepId ? `${sweepId} — ${sweeps.find((s) => s.id === sweepId)?.name ?? ""}` : "— none —"}
              onChange={(e) => {
                const v = e.target.value;
                setSweepId(v.startsWith("—") ? "" : v.split(" — ")[0]);
              }}
            />
          </Field>

          {sweepId && (
            <div className="grid grid-cols-3 gap-3 mb-4">
              <Stat label="Points compared" value={String(compared.length)} />
              <Stat label="Mean |ΔCl|" value={clErr == null ? "—" : clErr.toFixed(3)} />
              <Stat label="Mean |ΔCd|" value={cdErr == null ? "—" : cdErr.toFixed(4)} />
            </div>
          )}

          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={rows}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="alpha" stroke="var(--muted-foreground)" fontSize={11} type="number"
                domain={["dataMin", "dataMax"]} minTickGap={16}
                label={{ value: "AoA [deg]", position: "insideBottom", offset: -2, fontSize: 11 }} />
              <YAxis stroke="var(--muted-foreground)" fontSize={11} />
              <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)" }} />
              <Legend />
              <Line type="monotone" dataKey="clRef" name="Cl (reference)" stroke="#3b82f6" dot={false} />
              <Line type="monotone" dataKey="cdRef" name="Cd (reference)" stroke="#ef4444" dot={false} />
              {sweepId && (
                <Line type="monotone" dataKey="clYours" name="Cl (yours)" stroke="#3b82f6"
                  strokeDasharray="5 3" connectNulls />
              )}
              {sweepId && (
                <Line type="monotone" dataKey="cdYours" name="Cd (yours)" stroke="#ef4444"
                  strokeDasharray="5 3" connectNulls />
              )}
            </LineChart>
          </ResponsiveContainer>

          <p className="text-xs text-[var(--muted-foreground)] mt-3">
            Reference Cd is for free transition. A fully-turbulent model (kOmegaSST) sits higher
            (~0.012 at low AoA) — use kOmegaSSTLM with a wall-resolved mesh to compare like for like.
          </p>
        </Card>
      )}
    </div>
  );
}
