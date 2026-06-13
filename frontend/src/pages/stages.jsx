import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import { Button, Card, Field, Input, Select, Badge, Stat } from "@/components/ui";
import { AirfoilPreview } from "@/components/AirfoilPreview";

function NextBar({ goNext, disabled, label = "Next →" }) {
  return (
    <div className="mt-6">
      <Button onClick={goNext} disabled={disabled}>{label}</Button>
    </div>
  );
}

/* ---------------- Geometry ---------------- */
export function Geometry({ field, setField, persist, markDone, goNext }) {
  const [coords, setCoords] = useState(null);
  const preview = useMutation({
    mutationFn: () => api.naca(field("geometry.parameters.designation"), field("geometry.parameters.chord")),
    onSuccess: (d) => { setCoords(d.coordinates); markDone("geometry"); },
  });

  return (
    <div className="max-w-4xl">
      <div className="grid grid-cols-2 gap-6">
        <Card>
          <Field label="NACA designation" help="4- or 5-digit code: 0012, 4412, 23012.">
            <Input value={field("geometry.parameters.designation") ?? ""}
              onChange={(e) => setField("geometry.parameters.designation", e.target.value)} />
          </Field>
          <Field label="Chord" unit="m">
            <Input type="number" value={field("geometry.parameters.chord") ?? 1}
              onChange={(e) => setField("geometry.parameters.chord", parseFloat(e.target.value))} />
          </Field>
          <Button onClick={async () => { await persist(); preview.mutate(); }} disabled={preview.isPending}>
            {preview.isPending ? "Generating…" : "Preview section"}
          </Button>
          {preview.isError && <p className="text-sm text-[var(--destructive)] mt-3">{preview.error.message}</p>}
        </Card>
        <Card>
          <div className="text-sm font-medium mb-2">Section preview</div>
          <AirfoilPreview coordinates={coords} />
        </Card>
      </div>
      <NextBar goNext={goNext} disabled={!coords} />
    </div>
  );
}

/* ---------------- Mesh ---------------- */
export function Mesh({ caseId, field, setField, persist, markDone, goNext }) {
  const [yp, setYp] = useState(null);
  const [derived, setDerived] = useState(null);

  const calc = useMutation({
    mutationFn: () => api.yplus(field("physics.reference.velocity"), field("geometry.parameters.chord"),
      field("physics.fluid.name") || "air", field("mesh.parameters.target_yplus")),
    onSuccess: setYp,
  });
  const gen = useMutation({
    mutationFn: async () => { await persist(); return api.generate(caseId); },
    onSuccess: (d) => { setDerived(d); markDone("mesh"); },
  });

  const num = (path, label, unit) => (
    <Field label={label} unit={unit}>
      <Input type="number" value={field(path) ?? ""} onChange={(e) => setField(path, parseFloat(e.target.value))} />
    </Field>
  );

  return (
    <div className="max-w-4xl">
      <div className="grid grid-cols-2 gap-6">
        <Card>
          <div className="text-sm font-semibold mb-3">Mesh (clean 2D, Gmsh)</div>
          {num("mesh.parameters.farfield_radius", "Far-field radius", "chords")}
          {num("mesh.parameters.target_yplus", "Target y+")}
          {num("numerics.end_time", "Max iterations")}
          <Field label="CPU cores" help="Parallel solve via decomposePar + mpirun.">
            <Input type="number" min="1" value={field("numerics.n_procs") ?? 1}
              onChange={(e) => setField("numerics.n_procs", parseInt(e.target.value) || 1)} />
          </Field>
        </Card>
        <div>
          <Card className="mb-4">
            <div className="text-sm font-semibold mb-3">y+ calculator</div>
            <Button variant="ghost" onClick={() => calc.mutate()} disabled={calc.isPending}>
              Estimate first-cell height
            </Button>
            {yp && (
              <div className="grid grid-cols-2 gap-2 mt-3">
                <Stat label="First cell height" value={`${yp.first_cell_height.toExponential(2)} m`} />
                <Stat label="Re" value={yp.reynolds.toExponential(2)} />
              </div>
            )}
          </Card>
          <Card>
            <div className="text-sm font-semibold mb-3">Generate case</div>
            <Button onClick={() => gen.mutate()} disabled={gen.isPending}>
              {gen.isPending ? "Generating mesh…" : "Generate OpenFOAM case"}
            </Button>
            {gen.isError && <p className="text-sm text-[var(--destructive)] mt-2">{gen.error.message}</p>}
            {derived && (
              <div className="grid grid-cols-2 gap-2 mt-3">
                <Stat label="Reynolds" value={derived.reynolds.toExponential(2)} />
                <Stat label="Mach" value={derived.mach.toFixed(3)} />
                <Stat label="k inlet" value={derived.k.toFixed(3)} />
                <Stat label="omega inlet" value={derived.omega.toFixed(2)} />
              </div>
            )}
          </Card>
        </div>
      </div>
      <NextBar goNext={goNext} disabled={!derived} />
    </div>
  );
}

/* ---------------- Physics & BCs ---------------- */
export function Physics({ field, setField, markDone, goNext }) {
  useEffect(() => { markDone("physics"); }, [markDone]);
  return (
    <div className="max-w-2xl">
      <Card>
        <div className="text-sm font-semibold mb-3">Flow conditions</div>
        <Field label="Freestream speed" unit="m/s">
          <Input type="number" value={field("physics.reference.velocity") ?? ""}
            onChange={(e) => setField("physics.reference.velocity", parseFloat(e.target.value))} />
        </Field>
        <Field label="Angle of attack" unit="deg" help="Applied by rotating the freestream, not the mesh.">
          <Input type="number" value={field("physics.reference.angle_of_attack") ?? ""}
            onChange={(e) => setField("physics.reference.angle_of_attack", parseFloat(e.target.value))} />
        </Field>
        <Field label="Turbulence intensity" help="Fraction: 0.01 = 1%. External aero: 0.1–1%.">
          <Input type="number" step="0.001" value={field("physics.reference.turbulence_intensity") ?? ""}
            onChange={(e) => setField("physics.reference.turbulence_intensity", parseFloat(e.target.value))} />
        </Field>
        <Field label="Turbulence model">
          <Select options={["kOmegaSST", "kOmegaSSTLM", "kEpsilon", "realizableKE"]}
            value={field("physics.turbulence_model") ?? "kOmegaSST"}
            onChange={(e) => setField("physics.turbulence_model", e.target.value)} />
        </Field>
        <Field label="Fluid">
          <Select options={["air", "water"]} value={field("physics.fluid.name") ?? "air"}
            onChange={(e) => setField("physics.fluid.name", e.target.value)} />
        </Field>
        <p className="text-xs text-[var(--muted-foreground)]">
          BCs are generated automatically: <code>freestream</code> on the far field,
          <code> noSlip</code> + wall functions on the airfoil. Turbulence inlet (k, omega) are computed.
        </p>
      </Card>
      <NextBar goNext={goNext} />
    </div>
  );
}

/* ---------------- Validate ---------------- */
export function Validate({ caseId, persist, markDone, goNext }) {
  const [report, setReport] = useState(null);
  const run = useMutation({
    mutationFn: async () => { await persist(); return api.validate(caseId); },
    onSuccess: (r) => { setReport(r); markDone("validate", r.can_run); },
  });
  const override = useMutation({ mutationFn: ({ rule_id, message }) => api.override(caseId, rule_id, message) });

  return (
    <div className="max-w-3xl">
      <Button onClick={() => run.mutate()} disabled={run.isPending}>
        {run.isPending ? "Checking…" : "Run preflight checks"}
      </Button>
      {report && (
        <div className="mt-6">
          <div className="flex gap-3 mb-4 text-sm items-center">
            <Badge severity="pass">{report.summary.pass} pass</Badge>
            <Badge severity="warn">{report.summary.warn} warn</Badge>
            <Badge severity="fail">{report.summary.fail} fail</Badge>
            <span className={report.can_run ? "text-[var(--success)]" : "text-[var(--destructive)]"}>
              {report.can_run ? "✓ ready to run" : "✗ blocked — resolve FAIL items"}
            </span>
          </div>
          <div className="space-y-2">
            {report.findings.map((f) => (
              <Card key={f.rule_id} className="p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge severity={f.severity}>{f.severity}</Badge>
                      <span className="font-mono text-xs text-[var(--muted-foreground)]">{f.rule_id}</span>
                    </div>
                    <div className="text-sm mt-1">{f.message}</div>
                    {f.suggestion && <div className="text-xs text-[var(--muted-foreground)] mt-1">→ {f.suggestion}</div>}
                  </div>
                  {f.severity === "warn" && (
                    <Button variant="ghost" onClick={() => override.mutate({ rule_id: f.rule_id, message: f.message })}>
                      Override
                    </Button>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
      <NextBar goNext={goNext} disabled={!report?.can_run} label="Proceed to Run →" />
    </div>
  );
}

/* ---------------- Run ---------------- */
export function Run({ caseId, persist, markDone, goNext }) {
  const [logs, setLogs] = useState([]);
  const [residuals, setResiduals] = useState([]);
  const [fields, setFields] = useState([]);
  const [stage, setStage] = useState(null);
  const [time, setTime] = useState(null);
  const [cont, setCont] = useState(null);
  const [courant, setCourant] = useState(null);
  const [forces, setForces] = useState(null);
  const [finished, setFinished] = useState(false);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);
  const logEnd = useRef(null);
  const iter = useRef(0);

  const start = useMutation({
    mutationFn: async () => { await persist(); return api.startRun(caseId); },
    onSuccess: (run) => openSocket(run.id),
    onError: (e) => setError(e.message),
  });

  function openSocket(runId) {
    setLogs([]); setResiduals([]); setFields([]); setError(null);
    setFinished(false); iter.current = 0;
    const ws = api.runSocket(runId);
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.log) setLogs((l) => [...l.slice(-500), m.log]);
      if (m.error) setError(m.error);
      if (m.stage) setStage(m.stage);
      if (m.time != null) setTime(m.time);
      if (m.continuity) setCont(m.continuity);
      if (m.courant) setCourant(m.courant);
      if (m.forces) setForces(m.forces);
      if (m.done) { setFinished(true); markDone("run"); }
      if (m.residual) {
        const { field: fld, initial } = m.residual;
        setFields((f) => (f.includes(fld) ? f : [...f, fld]));
        iter.current += 1;
        setResiduals((r) => {
          const last = r[r.length - 1];
          if (last && last._i === iter.current) return [...r.slice(0, -1), { ...last, [fld]: initial }];
          return [...r, { _i: iter.current, n: r.length + 1, [fld]: initial }];
        });
      }
    };
    ws.onerror = () => setError("WebSocket error — is Docker running?");
  }

  useEffect(() => () => wsRef.current?.close(), []);
  useEffect(() => { logEnd.current?.scrollIntoView(); }, [logs]);

  const colors = ["#3b82f6", "#22c55e", "#eab308", "#ef4444", "#a855f7", "#06b6d4"];

  return (
    <div className="max-w-4xl">
      <div className="flex items-center gap-3">
        <Button variant="success" onClick={() => start.mutate()} disabled={start.isPending}>
          {start.isPending ? "Starting…" : "Start solver"}
        </Button>
        {stage && (
          <span className="text-sm text-[var(--muted-foreground)]">
            stage {stage.index}/{stage.total}: <span className="text-[var(--foreground)]">{stage.label}</span>
          </span>
        )}
        {finished && <Badge severity="pass">finished</Badge>}
      </div>
      {error && <p className="text-sm text-[var(--destructive)] mt-3">{error}</p>}

      {/* live metrics */}
      {(time != null || forces || cont || courant) && (
        <div className="grid grid-cols-4 gap-3 mt-5">
          <Stat label="Iteration" value={time ?? "—"} />
          <Stat label="Cl" value={forces ? forces.cl.toFixed(4) : "—"} />
          <Stat label="Cd" value={forces ? forces.cd.toFixed(5) : "—"} />
          <Stat label="Courant max" value={courant ? courant.max.toFixed(2) : "—"} />
          {cont && <Stat label="Continuity (local)" value={cont.local.toExponential(2)} />}
        </div>
      )}

      {residuals.length > 0 && (
        <Card className="mt-4">
          <div className="text-sm font-semibold mb-3">Residuals (log scale)</div>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={residuals}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="n" stroke="var(--muted-foreground)" fontSize={11} />
              <YAxis scale="log" domain={["auto", "auto"]} stroke="var(--muted-foreground)" fontSize={11} />
              <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)" }} />
              <Legend />
              {fields.map((f, i) => (
                <Line key={f} type="monotone" dataKey={f} stroke={colors[i % colors.length]} dot={false} strokeWidth={1.5} isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {logs.length > 0 && (
        <Card className="mt-4">
          <div className="text-sm font-semibold mb-2">Solver / mesh log</div>
          <div className="bg-black/50 rounded-lg p-3 h-64 overflow-auto font-mono text-xs text-green-400">
            {logs.map((l, i) => <div key={i}>{l}</div>)}
            <div ref={logEnd} />
          </div>
        </Card>
      )}

      <NextBar goNext={goNext} disabled={!finished} label="View results →" />
    </div>
  );
}

/* ---------------- Results ---------------- */
export function Results({ caseId }) {
  const load = useMutation({ mutationFn: () => api.forces(caseId) });
  const data = load.data;
  return (
    <div className="max-w-4xl">
      <Button onClick={() => load.mutate()} disabled={load.isPending}>
        {load.isPending ? "Loading…" : "Load force coefficients"}
      </Button>
      {data && data.latest && (
        <div className="grid grid-cols-3 gap-3 mt-6">
          <Stat label="Cl (lift)" value={data.latest.cl?.toFixed(4)} />
          <Stat label="Cd (drag)" value={data.latest.cd?.toFixed(5)} />
          <Stat label="L/D" value={(data.latest.cl / data.latest.cd).toFixed(2)} />
        </div>
      )}
      {data && !data.latest && (
        <p className="text-sm text-[var(--muted-foreground)] mt-4">No force data yet — run the solver first.</p>
      )}
      {data && data.history.length > 1 && (
        <Card className="mt-4">
          <div className="text-sm font-semibold mb-3">Convergence history</div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data.history}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="time" stroke="var(--muted-foreground)" fontSize={11} />
              <YAxis stroke="var(--muted-foreground)" fontSize={11} />
              <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)" }} />
              <Legend />
              <Line type="monotone" dataKey="cl" stroke="#3b82f6" dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="cd" stroke="#ef4444" dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}
