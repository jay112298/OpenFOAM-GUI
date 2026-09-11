/**
 * Turbo pipeline stages: one blade passage of an axial fan rotor.
 *
 * Geometry owns the blade *and* the operating point, because RPM and the design
 * through-flow are what twist the blade — change either and the geometry
 * changes. Validate and Run are shared with the aero pipeline.
 */
import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import { Button, Card, Field, Input, Select, Stat } from "@/components/ui";
import { CascadePreview } from "@/components/CascadePreview";
import { FieldViewer } from "@/components/FieldViewer";

function NextBar({ goNext, disabled, label = "Next →" }) {
  return (
    <div className="mt-6">
      <Button onClick={goNext} disabled={disabled}>{label}</Button>
    </div>
  );
}

function bladeParams(field) {
  return {
    designation: field("geometry.parameters.designation") ?? "4412",
    n_blades: field("geometry.parameters.n_blades") ?? 6,
    hub_radius: field("geometry.parameters.hub_radius") ?? 0.06,
    tip_radius: field("geometry.parameters.tip_radius") ?? 0.15,
    chord: field("geometry.parameters.chord") ?? 0.05,
    incidence: field("geometry.parameters.incidence") ?? 4,
    rpm: field("physics.reference.rpm") ?? 3000,
    axial_velocity: field("physics.reference.axial_velocity") ?? 12,
  };
}

/* ---------------- Geometry ---------------- */
export function TurboGeometry({ field, setField, persist, markDone, goNext }) {
  const [blade, setBlade] = useState(null);
  const preview = useMutation({
    mutationFn: () => api.blade(bladeParams(field)),
    onSuccess: (d) => { setBlade(d); markDone("geometry"); },
  });

  const num = (path, label, unit, help, step) => (
    <Field label={label} unit={unit} help={help}>
      <Input type="number" step={step} value={field(path) ?? ""}
        onChange={(e) => setField(path, parseFloat(e.target.value))} />
    </Field>
  );

  const mid = blade?.sections?.[Math.floor((blade.sections.length - 1) / 2)];

  return (
    <div className="max-w-5xl">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <div className="text-sm font-semibold mb-3">Blade row</div>
          <Field label="Blade section" help="NACA 4- or 5-digit code, used at every radius. 4412 is a solid cambered fan section.">
            <Input value={field("geometry.parameters.designation") ?? ""}
              onChange={(e) => setField("geometry.parameters.designation", e.target.value)} />
          </Field>
          {num("geometry.parameters.n_blades", "Number of blades", "", "The passage solved is 360/n degrees wide.")}
          {num("geometry.parameters.hub_radius", "Hub radius", "m", "Hub/tip ratio 0.3–0.7 is the usual band.", "0.005")}
          {num("geometry.parameters.tip_radius", "Tip radius", "m", "Casing radius — with RPM this sets the tip speed.", "0.005")}
          {num("geometry.parameters.chord", "Blade chord", "m", "Aim for solidity (chord/pitch) near 1 at the hub.", "0.005")}
          {num("geometry.parameters.incidence", "Design incidence", "deg", "How far the chord sits below the relative inflow. 2–6° is the design band.")}

          <div className="text-sm font-semibold mb-3 mt-6">Operating point</div>
          <p className="text-xs text-[var(--muted-foreground)] mb-3">
            These live here, not under Physics, because the blade twist is derived from them:
            at every radius the chord is set to meet the relative inflow at the incidence above.
          </p>
          {num("physics.reference.rpm", "Shaft speed", "rpm", "Rotation about the flow axis. Also drives the MRF zone.")}
          {num("physics.reference.axial_velocity", "Design axial velocity", "m/s", "Through-flow at the inlet.")}

          <Button onClick={async () => { await persist(); preview.mutate(); }} disabled={preview.isPending}>
            {preview.isPending ? "Deriving twist…" : "Preview blade + passage"}
          </Button>
          {preview.isError && <p className="text-sm text-[var(--destructive)] mt-3">{preview.error.message}</p>}
        </Card>

        <div>
          <Card className="mb-4">
            <div className="text-sm font-medium mb-2">Blade-to-blade passage (mid-span, unrolled)</div>
            <CascadePreview
              outline={blade?.cascade?.outline}
              pitch={blade?.cascade?.pitch}
              stagger={mid?.stagger}
              relativeAngle={mid?.relative_angle}
            />
            {blade && (
              <div className="grid grid-cols-2 gap-2 mt-3">
                <Stat label="Sector" value={`${blade.sector_angle.toFixed(1)}°`} />
                <Stat label="Tip speed" value={`${blade.tip_speed.toFixed(1)} m/s`} />
                <Stat label="Flow coeff. φ" value={blade.flow_coefficient.toFixed(3)} />
                <Stat label="Pitch (mid)" value={`${(blade.pitch * 1000).toFixed(1)} mm`} />
              </div>
            )}
          </Card>

          {blade && (
            <Card>
              <div className="text-sm font-medium mb-2">Twist derived from the velocity triangle</div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono">
                  <thead className="text-[var(--muted-foreground)]">
                    <tr>
                      <th className="text-left py-1">r [mm]</th>
                      <th className="text-right">U [m/s]</th>
                      <th className="text-right">β₁ [°]</th>
                      <th className="text-right">stagger [°]</th>
                      <th className="text-right">solidity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {blade.sections.map((s) => (
                      <tr key={s.radius} className="border-t border-[var(--border)]">
                        <td className="py-1">{(s.radius * 1000).toFixed(0)}</td>
                        <td className="text-right">{s.blade_speed.toFixed(1)}</td>
                        <td className="text-right">{s.relative_angle.toFixed(1)}</td>
                        <td className="text-right">{s.stagger.toFixed(1)}</td>
                        <td className="text-right">{s.solidity.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-[var(--muted-foreground)] mt-2">
                β₁ = atan(U/V<sub>a</sub>) is where the flow comes from in the rotating frame;
                the blade is set {field("geometry.parameters.incidence") ?? 4}° below it everywhere.
              </p>
            </Card>
          )}
        </div>
      </div>
      <NextBar goNext={goNext} disabled={!blade} />
    </div>
  );
}

/* ---------------- Mesh ---------------- */
export function TurboMesh({ caseId, field, setField, persist, markDone, goNext }) {
  const [yp, setYp] = useState(null);
  const [derived, setDerived] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [meshLog, setMeshLog] = useState([]);

  // the wall the boundary layer sits on is the blade, so size it on the
  // mid-span *relative* speed, not the through-flow
  const calc = useMutation({
    mutationFn: async () => {
      const b = await api.blade(bladeParams(field));
      const mid = b.sections[Math.floor((b.sections.length - 1) / 2)];
      return api.yplus(mid.relative_speed, field("geometry.parameters.chord"),
        field("physics.fluid.name") || "air", field("mesh.parameters.target_yplus"));
    },
    onSuccess: setYp,
  });

  const gen = useMutation({
    mutationFn: async () => { await persist(); return api.generate(caseId); },
    onMutate: () => { setElapsed(0); setMeshLog([]); },
    onSuccess: (d) => { setDerived(d); markDone("mesh"); },
    onSettled: () => { api.meshLog(caseId).then((d) => setMeshLog(d.lines)).catch(() => {}); },
  });

  useEffect(() => {
    if (!gen.isPending) return;
    const t = setInterval(() => setElapsed((e) => e + 1), 1000);
    const p = setInterval(() => {
      api.meshLog(caseId).then((d) => setMeshLog(d.lines)).catch(() => {});
    }, 1000);
    return () => { clearInterval(t); clearInterval(p); };
  }, [gen.isPending, caseId]);

  const num = (path, label, unit, help) => (
    <Field label={label} unit={unit} help={help}>
      <Input type="number" value={field(path) ?? ""}
        onChange={(e) => setField(path, parseFloat(e.target.value))} />
    </Field>
  );

  return (
    <div className="max-w-5xl">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <div className="text-sm font-semibold mb-3">Passage mesh (blockMesh sector + snappyHexMesh)</div>
          <p className="text-xs text-[var(--muted-foreground)] mb-4">
            An annular sector one blade pitch wide, closed by rotational <code>cyclicAMI</code>
            {" "}periodics, with the blade carved out of it.
          </p>
          {num("mesh.parameters.cells_per_chord", "Cells per chord", "", "Background cell size = chord / this. 8–12 is a good start.")}
          {num("mesh.parameters.refinement_level", "Blade refinement level", "", "snappy halves the cell this many times at the blade. 2–3.")}
          {num("mesh.parameters.inlet_length", "Inlet duct", "chords", "≥ 1.5 so the fixed inlet velocity is clear of the blade.")}
          {num("mesh.parameters.outlet_length", "Outlet duct", "chords", "≥ 3 so the swirling wake settles before the outlet.")}
          {num("mesh.parameters.target_yplus", "Target y+", "", "30–100 for the wall-function mesh shipped by default.")}
          {num("numerics.end_time", "Max iterations", "", "1000–2000 is usually enough for one passage.")}
          <Field label="CPU cores" help="Parallel solve via decomposePar + mpirun.">
            <Input type="number" min="1" value={field("numerics.n_procs") ?? 1}
              onChange={(e) => setField("numerics.n_procs", parseInt(e.target.value) || 1)} />
          </Field>
        </Card>

        <div>
          <Card className="mb-4 min-h-[190px]">
            <div className="text-sm font-semibold mb-1">1. y+ calculator</div>
            <p className="text-xs text-[var(--muted-foreground)] mb-3">
              Required before meshing — sizes the near-wall cell from the mid-span relative velocity.
            </p>
            <Button variant="ghost" onClick={() => calc.mutate()} disabled={calc.isPending}>
              {calc.isPending ? "Estimating…" : "Estimate first-cell height"}
            </Button>
            {calc.isError && <p className="text-sm text-[var(--destructive)] mt-2">{calc.error.message}</p>}
            {yp && (
              <div className="grid grid-cols-2 gap-2 mt-3">
                <Stat label="First cell height" value={`${yp.first_cell_height.toExponential(2)} m`} />
                <Stat label="Blade Re" value={yp.reynolds.toExponential(2)} />
              </div>
            )}
          </Card>

          <Card>
            <div className="text-sm font-semibold mb-1">2. Generate + mesh the passage</div>
            <p className="text-xs text-[var(--muted-foreground)] mb-3">
              {yp
                ? "Writes every dict, then meshes inside the OpenFOAM container."
                : "Calculate y+ first to enable."}
            </p>
            <Button onClick={() => gen.mutate()} disabled={gen.isPending || !yp}
              title={!yp ? "Run the y+ calculator first" : ""}>
              {gen.isPending ? `Meshing… ${elapsed}s` : "Generate + mesh passage"}
            </Button>
            {gen.isPending && (
              <p className="text-xs text-[var(--muted-foreground)] mt-2">
                blockMesh → surfaceFeatureExtract → snappyHexMesh → topoSet → checkMesh.
                Typically 10–60 s. Live log below.
              </p>
            )}
            {gen.isError && <p className="text-sm text-[var(--destructive)] mt-2">{gen.error.message}</p>}
            {meshLog.length > 0 && (
              <div className="bg-black/60 rounded-lg p-2 mt-3 h-44 overflow-auto font-mono text-[11px] text-green-400">
                {meshLog.map((l, i) => (
                  <div key={i} className={l.startsWith("[") ? "text-[var(--foreground)] font-semibold" : ""}>{l}</div>
                ))}
              </div>
            )}
            {derived && (
              <div className="grid grid-cols-2 gap-2 mt-3">
                <Stat label="Mesh cells" value={derived.n_cells?.toLocaleString() ?? "—"} />
                <Stat label="Blade Re" value={derived.reynolds.toExponential(2)} />
                <Stat label="Tip Mach" value={derived.mach.toFixed(3)} />
                <Stat label="Design flow" value={`${derived.volumetric_flow?.toFixed(3)} m³/s`} />
              </div>
            )}
          </Card>
        </div>
      </div>
      <NextBar goNext={goNext} disabled={!derived} />
    </div>
  );
}

/* ---------------- Physics ---------------- */
export function TurboPhysics({ field, setField, markDone, goNext }) {
  useEffect(() => { markDone("physics"); }, [markDone]);
  return (
    <div className="max-w-2xl">
      <Card>
        <div className="text-sm font-semibold mb-3">Fluid and turbulence</div>
        <Field label="Fluid">
          <Select options={["air", "water"]} value={field("physics.fluid.name") ?? "air"}
            onChange={(e) => setField("physics.fluid.name", e.target.value)} />
        </Field>
        <Field label="Turbulence intensity" help="Recommended 0.03–0.10 (3–10%) inside a duct. Inlet k and omega are computed from it.">
          <Input type="number" step="0.01" value={field("physics.reference.turbulence_intensity") ?? ""}
            onChange={(e) => setField("physics.reference.turbulence_intensity", parseFloat(e.target.value))} />
        </Field>
        <Field label="Turbulence model" help="kOmegaSST handles the adverse pressure gradient on the blade suction side best.">
          <Select options={["kOmegaSST", "kEpsilon", "realizableKE"]}
            value={field("physics.turbulence_model") ?? "kOmegaSST"}
            onChange={(e) => setField("physics.turbulence_model", e.target.value)} />
        </Field>
        <div className="text-xs text-[var(--muted-foreground)] space-y-2">
          <p>
            The rotor is solved in a <strong>rotating frame</strong>: the mesh never moves, and the
            momentum equation carries the Coriolis and centrifugal terms for a zone spinning at{" "}
            {field("physics.reference.rpm") ?? 3000} rpm. Shaft speed and design through-flow are on
            the Geometry tab, because they set the blade twist.
          </p>
          <p>
            BCs are generated: fixed axial velocity at the inlet, fixed static pressure at the
            outlet, <code>rotatingWallVelocity</code> on the blade and hub, a stationary casing, and
            rotational <code>cyclicAMI</code> on the two passage faces.
          </p>
        </div>
      </Card>
      <NextBar goNext={goNext} />
    </div>
  );
}

/* ---------------- Results ---------------- */
export function TurboResults({ caseId, field }) {
  const load = useQuery({
    queryKey: ["fan", caseId],
    queryFn: () => api.fanPerformance(caseId),
    retry: false,
  });
  const paraview = useMutation({ mutationFn: () => api.openParaview(caseId) });
  const data = load.data;
  const last = data?.latest;
  const tip = field("geometry.parameters.tip_radius") ?? 0.15;

  return (
    <div className="max-w-4xl">
      <div className="flex items-center gap-3 flex-wrap">
        <Button onClick={() => load.refetch()} disabled={load.isFetching}>
          {load.isFetching ? "Loading…" : "Refresh results"}
        </Button>
        <Button variant="ghost" onClick={() => paraview.mutate()} disabled={paraview.isPending}>
          {paraview.isPending ? "Opening…" : "Open in ParaView"}
        </Button>
        {paraview.isError && <span className="text-sm text-[var(--destructive)]">{paraview.error.message}</span>}
        {paraview.isSuccess && <span className="text-sm text-[var(--success)]">Launched ParaView ✓</span>}
      </div>

      {last && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-6">
            <Stat label="Flow rate Q" value={`${last.flow_rate.toFixed(3)} m³/s`} />
            <Stat label="Total pressure rise" value={`${last.total_pressure_rise.toFixed(1)} Pa`} />
            <Stat label="Shaft torque" value={`${last.torque.toFixed(3)} N·m`} />
            <Stat label="Efficiency" value={last.efficiency != null ? `${(last.efficiency * 100).toFixed(1)}%` : "—"} />
            <Stat label="Shaft power" value={`${last.shaft_power.toFixed(1)} W`} />
            <Stat label="Air power" value={`${last.air_power.toFixed(1)} W`} />
            <Stat label="Exit swirl" value={`${last.swirl.toFixed(2)} m/s`} />
            <Stat label="φ / ψ" value={`${last.flow_coefficient.toFixed(3)} / ${last.pressure_coefficient.toFixed(3)}`} />
          </div>
          <p className="text-xs text-[var(--muted-foreground)] mt-3">
            One passage was solved; flow, torque and power are scaled by the blade count.
            Efficiency is total-to-total for the rotor alone — there is no stator recovering the
            exit swirl, so it is lower than a whole stage would be.
          </p>
        </>
      )}
      {data && !last && (
        <p className="text-sm text-[var(--muted-foreground)] mt-4">
          No performance data yet — run the solver first.
        </p>
      )}
      {load.isError && (
        <p className="text-sm text-[var(--destructive)] mt-4">{load.error.message}</p>
      )}

      <div className="mt-4">
        <FieldViewer caseId={caseId} chord={2 * tip} />
      </div>

      {data && data.history.length > 1 && (
        <Card className="mt-4">
          <div className="text-sm font-semibold mb-3">Convergence of the operating point</div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data.history}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="time" stroke="var(--muted-foreground)" fontSize={11} />
              <YAxis yAxisId="p" stroke="var(--muted-foreground)" fontSize={11} />
              <YAxis yAxisId="e" orientation="right" domain={[0, 1]} stroke="var(--muted-foreground)" fontSize={11} />
              <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)" }} />
              <Legend />
              <Line yAxisId="p" name="Δp₀ [Pa]" type="monotone" dataKey="total_pressure_rise"
                stroke="#3b82f6" dot={false} isAnimationActive={false} />
              <Line yAxisId="e" name="efficiency" type="monotone" dataKey="efficiency"
                stroke="#22c55e" dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}
