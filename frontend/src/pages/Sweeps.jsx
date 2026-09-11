import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import { Badge, Button, Card, Field, Input, Select } from "@/components/ui";

const PARSE = (s) => s.split(",").map((v) => parseFloat(v.trim())).filter((v) => !isNaN(v));
const SERIES_COLORS = ["#3b82f6", "#22c55e", "#eab308", "#a855f7", "#06b6d4", "#f97316"];

export function Sweeps() {
  const qc = useQueryClient();
  const { data: cases = [] } = useQuery({ queryKey: ["cases"], queryFn: api.listCases, retry: false });
  const { data: sweeps = [] } = useQuery({ queryKey: ["sweeps"], queryFn: api.listSweeps, retry: false });

  const [baseCase, setBaseCase] = useState("");
  const [aoa, setAoa] = useState("0, 2, 4, 6, 8, 10");
  const [flows, setFlows] = useState("6, 9, 12, 15, 18");
  const [rpms, setRpms] = useState("2400, 3000");

  const selected = cases.find((c) => c.id === baseCase) ?? cases[0];
  const turbo = selected?.domain === "turbo";

  const create = useMutation({
    mutationFn: () =>
      api.createSweep(
        turbo
          ? {
              base_case_id: selected.id,
              parameter: "physics.reference.axial_velocity",
              values: PARSE(flows),
              parameter2: "physics.reference.rpm",
              values2: PARSE(rpms),
              name: "Fan map",
            }
          : {
              base_case_id: selected.id,
              parameter: "physics.reference.angle_of_attack",
              values: PARSE(aoa),
              name: "AoA sweep",
            }
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sweeps"] }),
  });

  const nCases = turbo ? PARSE(flows).length * PARSE(rpms).length : PARSE(aoa).length;

  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-bold m-0 mb-2">Parameter Sweeps</h1>
      <p className="text-[var(--muted-foreground)] mb-8">
        Fan out one base case across a parameter — angle of attack for a polar, flow rate and
        shaft speed for a fan map.
      </p>

      <Card className="mb-6">
        <div className="text-sm font-semibold mb-3">
          {turbo ? "New fan map" : "New AoA sweep"}
        </div>
        <Field label="Base case" help="The sweep takes its domain from this case.">
          <Select
            options={cases.map((c) => `${c.id} — ${c.name}`)}
            value={selected ? `${selected.id} — ${selected.name}` : ""}
            onChange={(e) => setBaseCase(e.target.value.split(" — ")[0])}
          />
        </Field>

        {turbo ? (
          <>
            <Field label="Axial velocity values" unit="m/s"
              help="Comma-separated. This throttles the fan: each value is one point along a speed line.">
              <Input value={flows} onChange={(e) => setFlows(e.target.value)} />
            </Field>
            <Field label="Shaft speed values" unit="rpm"
              help="Comma-separated. One curve per value — together they make the map.">
              <Input value={rpms} onChange={(e) => setRpms(e.target.value)} />
            </Field>
            <p className="text-xs text-[var(--muted-foreground)] mb-4">
              The blade is <strong>pinned to the base case's operating point</strong> before the
              sweep runs, so the same fan is carried across every point instead of being
              re-twisted at each one. Off-design incidence is reported per case, and preflight
              warns when a point is deep enough into stall to distrust.
            </p>
          </>
        ) : (
          <Field label="Angle of attack values" unit="deg" help="Comma-separated.">
            <Input value={aoa} onChange={(e) => setAoa(e.target.value)} />
          </Field>
        )}

        {create.isError && (
          <p className="text-sm text-[var(--destructive)] mb-3">{create.error.message}</p>
        )}
        <Button onClick={() => create.mutate()} disabled={create.isPending || !selected || !nCases}>
          {create.isPending ? "Creating…" : `Create sweep (${nCases} cases)`}
        </Button>
        <p className="text-xs text-[var(--muted-foreground)] mt-2">
          Creates child cases. “Run all” solves them one after another; the chart fills in as
          results land.
        </p>
      </Card>

      {sweeps.map((s) => <SweepCard key={s.id} sweep={s} />)}
    </div>
  );
}

function SweepCard({ sweep }) {
  const qc = useQueryClient();
  // poll while the queue is running so the chart and per-case rows fill in live.
  // refetchIntervalInBackground: a sweep runs for minutes and the user will not
  // be sitting on this tab the whole time.
  const { data: st } = useQuery({
    queryKey: ["sweep-status", sweep.id],
    queryFn: () => api.sweepStatus(sweep.id),
    retry: false,
    refetchInterval: (q) => (q.state.data?.queue?.running ? 2000 : false),
    refetchIntervalInBackground: true,
  });
  const { data } = useQuery({
    queryKey: ["sweep-results", sweep.id],
    queryFn: () => api.sweepResults(sweep.id),
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

  const turbo = (data?.domain ?? sweep.domain) === "turbo";
  const running = !!st?.queue?.running;
  const sev = { completed: "pass", failed: "fail", running: "warn", draft: "warn" };

  return (
    <Card className="mb-4">
      <div className="flex items-start justify-between gap-3 mb-1 flex-wrap">
        <div>
          <div className="text-sm font-semibold">{sweep.name}</div>
          <div className="text-xs text-[var(--muted-foreground)] font-mono">
            {sweep.parameter}
            {sweep.parameter2 ? ` x ${sweep.parameter2}` : ""} · {sweep.case_ids.length} cases
            {st ? ` · ${st.done}/${st.total} done` : ""}
          </div>
        </div>
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
              <span className="font-mono">{childLabel(c, turbo)}</span>
            </span>
          ))}
        </div>
      )}

      {turbo ? <FanMap points={data?.points} /> : <Polar points={data?.points} />}
    </Card>
  );
}

function childLabel(c, turbo) {
  if (!turbo) {
    return `${c.value}°${c.cl != null ? ` · Cl ${c.cl.toFixed(3)} Cd ${c.cd.toFixed(4)}` : ""}`;
  }
  const head = `${c.value} m/s${c.value2 != null ? ` @ ${c.value2} rpm` : ""}`;
  if (c.total_pressure_rise == null) return head;
  const eta = c.efficiency != null ? ` η ${(c.efficiency * 100).toFixed(0)}%` : "";
  return `${head} · Δp₀ ${c.total_pressure_rise.toFixed(0)} Pa${eta}`;
}

function Empty({ children }) {
  return <p className="text-sm text-[var(--muted-foreground)]">{children}</p>;
}

function Polar({ points = [] }) {
  const rows = points.map((p) => ({ aoa: p.value, cl: p.cl, cd: p.cd }));
  if (!rows.some((r) => r.cl != null)) {
    return <Empty>No results yet — hit “Run all”; the polar fills in as cases finish.</Empty>;
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={rows}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="aoa" stroke="var(--muted-foreground)" fontSize={11}
          label={{ value: "AoA [deg]", position: "insideBottom", offset: -2, fontSize: 11 }} />
        <YAxis stroke="var(--muted-foreground)" fontSize={11} />
        <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)" }} />
        <Legend />
        {/* animation off: Recharts can leave the curve at dasharray "0, len" */}
        <Line type="monotone" dataKey="cl" name="Cl" stroke="#3b82f6" isAnimationActive={false} />
        <Line type="monotone" dataKey="cd" name="Cd" stroke="#ef4444" isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

/**
 * Fan map: flow rate on x, one speed line per RPM. Δp0 and efficiency are two
 * charts rather than two axes on one — a map is read by finding the flow you
 * need on the pressure curve, then reading the efficiency directly below it.
 */
function FanMap({ points = [] }) {
  const { rows, speeds } = useMemo(() => {
    const solved = points.filter((p) => p.total_pressure_rise != null);
    const speedSet = [...new Set(solved.map((p) => p.value2 ?? 0))].sort((a, b) => a - b);
    // one row per flow rate, one column per speed line, so Recharts draws a
    // separate connected curve per RPM from a single dataset
    const byFlow = new Map();
    for (const p of solved) {
      const key = Number(p.flow_rate.toFixed(4));
      const row = byFlow.get(key) ?? { flow: key };
      row[`dp_${p.value2 ?? 0}`] = p.total_pressure_rise;
      row[`eta_${p.value2 ?? 0}`] = p.efficiency != null ? p.efficiency * 100 : null;
      byFlow.set(key, row);
    }
    return {
      rows: [...byFlow.values()].sort((a, b) => a.flow - b.flow),
      speeds: speedSet,
    };
  }, [points]);

  if (!rows.length) {
    return <Empty>No results yet — hit “Run all”; the map fills in as cases finish.</Empty>;
  }

  const axis = (label) => ({
    stroke: "var(--muted-foreground)",
    fontSize: 11,
    label: { value: label, angle: -90, position: "insideLeft", fontSize: 11 },
  });

  return (
    <div className="space-y-4">
      <div>
        <div className="text-xs font-semibold mb-1">Total pressure rise</div>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="flow" type="number" domain={["dataMin", "dataMax"]}
              stroke="var(--muted-foreground)" fontSize={11}
              label={{ value: "Q [m³/s]", position: "insideBottom", offset: -2, fontSize: 11 }} />
            <YAxis {...axis("Δp₀ [Pa]")} />
            <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)" }} />
            <Legend />
            {speeds.map((rpm, i) => (
              <Line key={rpm} type="monotone" dataKey={`dp_${rpm}`} name={`${rpm} rpm`}
                stroke={SERIES_COLORS[i % SERIES_COLORS.length]} connectNulls
                isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div>
        <div className="text-xs font-semibold mb-1">Total-to-total efficiency</div>
        <p className="text-[11px] text-[var(--muted-foreground)] mb-1">
          Only defined where the rotor raises total pressure. Past free delivery (Δp₀ ≤ 0) the
          curve simply stops — the machine is no longer pumping.
        </p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="flow" type="number" domain={["dataMin", "dataMax"]}
              stroke="var(--muted-foreground)" fontSize={11}
              label={{ value: "Q [m³/s]", position: "insideBottom", offset: -2, fontSize: 11 }} />
            <YAxis domain={[0, 100]} {...axis("η [%]")} />
            <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)" }} />
            <Legend />
            {speeds.map((rpm, i) => (
              /* no connectNulls here: bridging an undefined stretch would
                 draw an efficiency the machine never had */
              <Line key={rpm} type="monotone" dataKey={`eta_${rpm}`} name={`${rpm} rpm`}
                stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
                isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
