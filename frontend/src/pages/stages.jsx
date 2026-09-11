import { useState, useRef, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import { Button, Card, Field, Input, Select, Badge, Stat } from "@/components/ui";
import { AirfoilPreview } from "@/components/AirfoilPreview";
import { FieldViewer } from "@/components/FieldViewer";

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
  const [elapsed, setElapsed] = useState(0);
  const [meshLog, setMeshLog] = useState([]);
  const meshLogEnd = useRef(null);

  const calc = useMutation({
    mutationFn: () => api.yplus(field("physics.reference.velocity"), field("geometry.parameters.chord"),
      field("physics.fluid.name") || "air", field("mesh.parameters.target_yplus")),
    onSuccess: setYp,
  });
  const gen = useMutation({
    mutationFn: async () => { await persist(); return api.generate(caseId); },
    onMutate: () => { setElapsed(0); setMeshLog([]); },
    onSuccess: (d) => { setDerived(d); markDone("mesh"); },
    onSettled: () => { api.meshLog(caseId).then((d) => setMeshLog(d.lines)).catch(() => {}); },
  });

  // while the mesh generates: elapsed ticker + live tail of the Gmsh log
  useEffect(() => {
    if (!gen.isPending) return;
    const t = setInterval(() => setElapsed((e) => e + 1), 1000);
    const p = setInterval(() => {
      api.meshLog(caseId).then((d) => setMeshLog(d.lines)).catch(() => {});
    }, 1000);
    return () => { clearInterval(t); clearInterval(p); };
  }, [gen.isPending, caseId]);
  useEffect(() => { meshLogEnd.current?.scrollIntoView({ block: "nearest" }); }, [meshLog]);

  const num = (path, label, unit, help) => (
    <Field label={label} unit={unit} help={help}>
      <Input type="number" value={field(path) ?? ""} onChange={(e) => setField(path, parseFloat(e.target.value))} />
    </Field>
  );

  return (
    <div className="max-w-4xl">
      <div className="grid grid-cols-2 gap-6">
        <Card>
          <div className="text-sm font-semibold mb-3">Mesh (clean 2D, Gmsh + prism layers)</div>
          {num("mesh.parameters.farfield_radius", "Far-field radius", "chords", "Recommended 25–50. Too small inflates pressure drag.")}
          <label className="flex items-center gap-2 mb-4 cursor-pointer">
            <input type="checkbox" checked={field("mesh.parameters.boundary_layers") ?? false}
              onChange={(e) => setField("mesh.parameters.boundary_layers", e.target.checked)} />
            <span className="text-sm font-medium">Boundary layers</span>
            <span className="text-xs text-[var(--muted-foreground)]">(resolved y+~1 wall — needed for accurate drag)</span>
          </label>
          {(field("mesh.parameters.boundary_layers") ?? false) &&
            num("mesh.parameters.n_layers", "Number of layers", "", "Prism layers on the wall. Recommended 10–20.")}
          {num("mesh.parameters.target_yplus", "Target y+", "", "~1 with boundary layers; 30–100 without.")}
          {num("numerics.end_time", "Max iterations", "", "Recommended 1500–3000 for steady convergence.")}
          <Field label="CPU cores" help="Recommended 2–4 (use physical cores). Parallel via decomposePar + mpirun.">
            <Input type="number" min="1" value={field("numerics.n_procs") ?? 1}
              onChange={(e) => setField("numerics.n_procs", parseInt(e.target.value) || 1)} />
          </Field>
        </Card>
        <div>
          <Card className="mb-4 min-h-[190px]">
            <div className="text-sm font-semibold mb-1">1. y+ calculator</div>
            <p className="text-xs text-[var(--muted-foreground)] mb-3">Required before meshing — sizes the near-wall cell.</p>
            <Button variant="ghost" onClick={() => calc.mutate()} disabled={calc.isPending}>
              {calc.isPending ? "Estimating…" : "Estimate first-cell height"}
            </Button>
            {yp && (
              <div className="grid grid-cols-2 gap-2 mt-3">
                <Stat label="First cell height" value={`${yp.first_cell_height.toExponential(2)} m`} />
                <Stat label="Re" value={yp.reynolds.toExponential(2)} />
              </div>
            )}
          </Card>
          <Card>
            <div className="text-sm font-semibold mb-1">2. Generate case</div>
            <p className="text-xs text-[var(--muted-foreground)] mb-3">
              {yp ? "Writes the 2D Gmsh mesh + all OpenFOAM dicts." : "Calculate y+ first to enable."}
            </p>
            <Button onClick={() => gen.mutate()} disabled={gen.isPending || !yp}
              title={!yp ? "Run the y+ calculator first" : ""}>
              {gen.isPending ? `Generating mesh… ${elapsed}s` : "Generate OpenFOAM case"}
            </Button>
            {gen.isPending && (
              <p className="text-xs text-[var(--muted-foreground)] mt-2">
                Meshing in Gmsh — a {field("mesh.parameters.farfield_radius") ?? 50}c far-field typically takes{" "}
                {(field("mesh.parameters.farfield_radius") ?? 50) >= 40 ? "30–60 s" : "10–30 s"}. Live log below.
              </p>
            )}
            {gen.isError && <p className="text-sm text-[var(--destructive)] mt-2">{gen.error.message}</p>}
            {meshLog.length > 0 && (
              <div className="bg-black/60 rounded-lg p-2 mt-3 h-44 overflow-auto font-mono text-[11px] text-green-400">
                {meshLog.map((l, i) => (
                  <div key={i} className={l.startsWith("[gmsh]") ? "text-[var(--foreground)] font-semibold" : ""}>{l}</div>
                ))}
                <div ref={meshLogEnd} />
              </div>
            )}
            {derived && (
              <div className="grid grid-cols-2 gap-2 mt-3">
                <Stat label="Mesh cells" value={derived.n_cells?.toLocaleString() ?? "—"} />
                <Stat label="Reynolds" value={derived.reynolds.toExponential(2)} />
                <Stat label="Mach" value={derived.mach.toFixed(3)} />
                <Stat label="k inlet" value={derived.k.toFixed(3)} />
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
        <Field label="Freestream speed" unit="m/s" help="Recommended 20–60 for low-speed (keeps Mach < 0.3). Aim for Re ~ 1e6–6e6.">
          <Input type="number" value={field("physics.reference.velocity") ?? ""}
            onChange={(e) => setField("physics.reference.velocity", parseFloat(e.target.value))} />
        </Field>
        <Field label="Angle of attack" unit="deg" help="Recommended 0–10° (attached flow). Steady RANS is unreliable past ~12° (stall).">
          <Input type="number" value={field("physics.reference.angle_of_attack") ?? ""}
            onChange={(e) => setField("physics.reference.angle_of_attack", parseFloat(e.target.value))} />
        </Field>
        <Field label="Turbulence intensity" help="Recommended 0.001–0.01 (0.1–1%) for external aero. 0.01 is a safe default.">
          <Input type="number" step="0.001" value={field("physics.reference.turbulence_intensity") ?? ""}
            onChange={(e) => setField("physics.reference.turbulence_intensity", parseFloat(e.target.value))} />
        </Field>
        <Field label="Turbulence model"
          help="kOmegaSST (robust, fully turbulent) is the default. kOmegaSSTLM predicts laminar–turbulent transition — it needs boundary layers with target y+ ~ 1, and preflight will warn if the mesh isn't wall-resolved.">
          <Select options={["kOmegaSST", "kOmegaSSTLM", "kEpsilon", "realizableKE"]}
            value={field("physics.turbulence_model") ?? "kOmegaSST"}
            onChange={(e) => setField("physics.turbulence_model", e.target.value)} />
        </Field>
        <Field label="Flow type"
          help="Incompressible (simpleFoam) below Mach 0.3. Compressible (rhoSimpleFoam) solves the energy equation and lets density vary — needed above Mach 0.3.">
          <Select options={["incompressible", "compressible"]}
            value={field("physics.flow_type") ?? "incompressible"}
            onChange={(e) => setField("physics.flow_type", e.target.value)} />
        </Field>
        {field("physics.flow_type") === "compressible" ? (
          <>
            <Field label="Freestream temperature" unit="K" help="288.15 K at sea level. Sets the speed of sound, so it sets Mach.">
              <Input type="number" value={field("physics.reference.temperature") ?? 288.15}
                onChange={(e) => setField("physics.reference.temperature", parseFloat(e.target.value))} />
            </Field>
            <Field label="Freestream pressure" unit="Pa" help="101325 Pa at sea level. With temperature this fixes density.">
              <Input type="number" value={field("physics.reference.pressure") ?? 101325}
                onChange={(e) => setField("physics.reference.pressure", parseFloat(e.target.value))} />
            </Field>
          </>
        ) : (
          <Field label="Fluid">
            <Select options={["air", "water"]} value={field("physics.fluid.name") ?? "air"}
              onChange={(e) => setField("physics.fluid.name", e.target.value)} />
          </Field>
        )}
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
export function Run({ caseId, pipe, persist, markDone, goNext }) {
  const qc = useQueryClient();
  const [logs, setLogs] = useState([]);
  const [finalStatus, setFinalStatus] = useState(null);
  const [runId, setRunId] = useState(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [residuals, setResiduals] = useState([]);
  const [fields, setFields] = useState([]);
  const [stage, setStage] = useState(null);
  const [time, setTime] = useState(null);
  const [cont, setCont] = useState(null);
  const [courant, setCourant] = useState(null);
  const [forces, setForces] = useState(null);
  const [layers, setLayers] = useState(null);
  const [finished, setFinished] = useState(false);
  // a previous run exists for this case -> we reattach to it below, so the
  // console/metrics should be visible from first paint
  const [started, setStarted] = useState(() => !!pipe?.latest_run?.container_id);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);
  const logEnd = useRef(null);
  const iter = useRef(0);

  const start = useMutation({
    mutationFn: async () => { setStarted(true); await persist(); return api.startRun(caseId); },
    onSuccess: (run) => openSocket(run.id),
    onError: (e) => setError(e.message),
  });

  const stop = useMutation({
    mutationFn: () => api.stopRun(runId),
    onSuccess: () => { setFinished(true); setFinalStatus("cancelled"); },
    onError: (e) => setError(e.message),
  });

  function openSocket(id) {
    // drop any previous stream first, otherwise an earlier run's replay keeps
    // writing into this run's console/chart
    if (wsRef.current) {
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.close();
    }
    setLogs([]); setResiduals([]); setFields([]); setError(null);
    setFinished(false); setFinalStatus(null); setStage(null);
    setForces(null); setCont(null); setCourant(null); setTime(null);
    iter.current = 0;
    setRunId(id);
    const ws = api.runSocket(id);
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.log) setLogs((l) => [...l.slice(-500), { text: m.log, prep: !!m.prep }]);
      if (m.error) setError(m.error);
      if (m.stage) setStage(m.stage);
      if (m.time != null) setTime(m.time);
      if (m.continuity) setCont(m.continuity);
      if (m.courant) setCourant(m.courant);
      if (m.forces) setForces(m.forces);
      if (m.layers) setLayers(m.layers);
      if (m.done) {
        setFinished(true);
        setFinalStatus(m.status || "completed");
        if (m.status !== "failed") markDone("run");
        // case status changed server-side (completed/failed) -> refresh header + lists
        qc.invalidateQueries({ queryKey: ["case", caseId] });
        qc.invalidateQueries({ queryKey: ["cases"] });
      }
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

  // Reattach to the case's most recent run on mount: Docker replays the whole
  // container log, so the console, chart and metrics rebuild after a tab
  // switch or a page reload instead of showing an empty panel.
  useEffect(() => {
    const last = pipe?.latest_run;
    if (!last || !last.container_id) return;
    openSocket(last.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  useEffect(() => () => wsRef.current?.close(), []);
  useEffect(() => { if (autoScroll) logEnd.current?.scrollIntoView({ block: "nearest" }); }, [logs, autoScroll]);

  const colors = ["#3b82f6", "#22c55e", "#eab308", "#ef4444", "#a855f7", "#06b6d4"];

  return (
    <div className="max-w-4xl">
      <div className="flex items-center gap-3">
        <Button variant="success" onClick={() => start.mutate()}
          disabled={start.isPending || (started && !finished)}>
          {start.isPending ? "Starting…" : started && !finished ? "Running…" : "Start solver"}
        </Button>
        {started && !finished && (
          <Button variant="danger" onClick={() => stop.mutate()} disabled={stop.isPending || !runId}>
            {stop.isPending ? "Stopping…" : "Stop"}
          </Button>
        )}
        {stage && (
          <span className="text-sm text-[var(--muted-foreground)]">
            stage {stage.index}/{stage.total}: <span className="text-[var(--foreground)]">{stage.label}</span>
          </span>
        )}
        {finished && (
          <Badge severity={finalStatus === "completed" ? "pass" : finalStatus ? "fail" : "pass"}>
            {finalStatus || "finished"}
          </Badge>
        )}
      </div>
      {error && <p className="text-sm text-[var(--destructive)] mt-3">{error}</p>}

      {/* stage progress: prep -> [1/N] ... [N/N] -> done */}
      {started && (
        <div className="mt-3">
          <div className="h-1.5 w-full bg-[var(--muted)] rounded overflow-hidden">
            <div
              className="h-full bg-[var(--primary)] transition-all duration-500"
              style={{ width: `${finished ? 100 : stage ? Math.round(((stage.index - 0.5) / stage.total) * 100) : 4}%` }}
            />
          </div>
          <div className="text-[11px] text-[var(--muted-foreground)] mt-1">
            {finished ? "run finished" : stage ? `${stage.index} of ${stage.total} stages` : "preparing case…"}
          </div>
        </div>
      )}

      {/* live metrics — sticky so they stay visible while the console streams */}
      {started && (
        <div className="grid grid-cols-4 gap-3 mt-5 sticky top-0 z-10 bg-[var(--background)] py-2">
          <Stat label="Iteration" value={time ?? "—"} />
          <Stat label="Cl" value={forces ? forces.cl.toFixed(4) : "—"} />
          <Stat label="Cd" value={forces ? forces.cd.toFixed(5) : "—"} />
          <Stat label="Courant max" value={courant ? courant.max.toFixed(2) : "—"} />
          {cont && <Stat label="Continuity (local)" value={cont.local.toExponential(2)} />}
          {layers && <Stat label="Layer coverage" value={`${layers.coverage.toFixed(0)}%`} />}
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

      {started && (
        <Card className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-semibold">Solver / mesh console</div>
            <label className="flex items-center gap-1.5 text-xs text-[var(--muted-foreground)] cursor-pointer">
              <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} />
              auto-scroll
            </label>
          </div>
          <div className="bg-black/60 rounded-lg p-3 h-72 overflow-auto font-mono text-xs text-green-400">
            {logs.length === 0 && !error && (
              <div className="text-[var(--muted-foreground)]">Preparing case and starting container… waiting for output.</div>
            )}
            {logs.map((l, i) => (
              <div key={i} className={l.prep ? "text-[var(--warning)]" : "whitespace-pre-wrap"}>{l.text}</div>
            ))}
            <div ref={logEnd} />
          </div>
        </Card>
      )}

      <NextBar goNext={goNext} disabled={!finished} label="View results →" />
    </div>
  );
}

/* ---------------- Results ---------------- */
export function Results({ caseId, field: specField }) {
  // auto-load on open; the button becomes a refresh
  const load = useQuery({
    queryKey: ["forces", caseId],
    queryFn: () => api.forces(caseId),
    retry: false,
  });
  const paraview = useMutation({ mutationFn: () => api.openParaview(caseId) });
  const data = load.data;
  return (
    <div className="max-w-4xl">
      <div className="flex items-center gap-3">
        <Button onClick={() => load.refetch()} disabled={load.isFetching}>
          {load.isFetching ? "Loading…" : "Refresh results"}
        </Button>
        <Button variant="ghost" onClick={() => paraview.mutate()} disabled={paraview.isPending}>
          {paraview.isPending ? "Opening…" : "Open in ParaView"}
        </Button>
        {paraview.isError && <span className="text-sm text-[var(--destructive)]">{paraview.error.message}</span>}
        {paraview.isSuccess && <span className="text-sm text-[var(--success)]">Launched ParaView ✓</span>}
      </div>
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
      <div className="mt-4">
        <FieldViewer caseId={caseId} chord={specField("geometry.parameters.chord") ?? 1} />
      </div>

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
