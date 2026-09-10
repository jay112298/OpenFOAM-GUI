import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button, Card, Select } from "@/components/ui";

/* ParaView's "cool to warm" diverging ramp — the colours OpenFOAM users read
   pressure in. Used when a field straddles zero; magnitudes get a sequential
   ramp instead, since a diverging map would imply a meaningless midpoint. */
const COOL = [59, 76, 192];
const MID = [221, 221, 221];
const WARM = [180, 4, 38];
const SEQ = [
  [12, 34, 68],
  [30, 96, 140],
  [42, 156, 148],
  [140, 200, 110],
  [248, 230, 110],
];

const lerp = (a, b, t) => a + (b - a) * t;

function diverging(t) {
  const [x, from, to] = t < 0.5 ? [t * 2, COOL, MID] : [(t - 0.5) * 2, MID, WARM];
  return [lerp(from[0], to[0], x), lerp(from[1], to[1], x), lerp(from[2], to[2], x)];
}

function sequential(t) {
  const s = Math.min(Math.max(t, 0), 1) * (SEQ.length - 1);
  const i = Math.min(Math.floor(s), SEQ.length - 2);
  const f = s - i;
  return [0, 1, 2].map((c) => lerp(SEQ[i][c], SEQ[i + 1][c], f));
}

export function FieldViewer({ caseId, chord = 1 }) {
  const canvasRef = useRef(null);
  const [field, setField] = useState(null);
  const [zoom, setZoom] = useState(4); // view width in chords

  const { data: avail } = useQuery({
    queryKey: ["fields", caseId],
    queryFn: () => api.listFields(caseId),
    retry: false,
  });

  const active = field ?? avail?.fields?.[0] ?? null;

  const { data, isFetching, error } = useQuery({
    queryKey: ["field", caseId, active],
    queryFn: () => api.fieldSlice(caseId, active),
    enabled: !!active,
    retry: false,
  });

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    // The canvas can still be 0-wide on first paint (panel laying out), and it
    // reflows with the window — observe it and draw whenever it has a size.
    const observer = new ResizeObserver(() => draw());
    observer.observe(cv);
    draw();
    return () => observer.disconnect();

    function draw() {
    if (!cv || !data || !cv.clientWidth || !cv.clientHeight) return;
    const ctx = cv.getContext("2d");
    const W = (cv.width = cv.clientWidth * devicePixelRatio);
    const H = (cv.height = cv.clientHeight * devicePixelRatio);

    const css = getComputedStyle(document.documentElement);
    ctx.fillStyle = css.getPropertyValue("--secondary").trim() || "#1e1e2a";
    ctx.fillRect(0, 0, W, H);

    // view window centred just behind the leading edge, sized in chords
    const viewW = zoom * chord; // scale is isotropic, so height follows from the aspect
    const cx = 0.4 * chord;
    const cy = 0;
    const sx = W / viewW;
    const X = (x) => (x - cx) * sx + W / 2;
    const Y = (y) => H / 2 - (y - cy) * sx;

    const [lo, hi] = data.range;
    const span = hi - lo || 1;
    const useDiverging = lo < 0 && hi > 0;
    const map = useDiverging ? diverging : sequential;
    // diverging maps stay symmetric about zero so the midpoint means something
    const norm = useDiverging
      ? (v) => 0.5 + v / (2 * Math.max(Math.abs(lo), Math.abs(hi)))
      : (v) => (v - lo) / span;

    const P = data.points;
    const T = data.triangles;
    const V = data.values;
    for (let i = 0; i < T.length; i += 3) {
      const a = T[i], b = T[i + 1], c = T[i + 2];
      const x0 = X(P[a * 2]), y0 = Y(P[a * 2 + 1]);
      const x1 = X(P[b * 2]), y1 = Y(P[b * 2 + 1]);
      const x2 = X(P[c * 2]), y2 = Y(P[c * 2 + 1]);
      // cheap cull: skip triangles fully outside the view
      if ((x0 < 0 && x1 < 0 && x2 < 0) || (x0 > W && x1 > W && x2 > W)) continue;
      if ((y0 < 0 && y1 < 0 && y2 < 0) || (y0 > H && y1 > H && y2 > H)) continue;

      const [r, g, bl] = map(norm((V[a] + V[b] + V[c]) / 3));
      ctx.fillStyle = `rgb(${r | 0},${g | 0},${bl | 0})`;
      ctx.beginPath();
      ctx.moveTo(x0, y0);
      ctx.lineTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.closePath();
      ctx.fill();
    }
    }
  }, [data, zoom, chord]);

  if (avail && !avail.ready) {
    return (
      <Card>
        <div className="text-sm font-semibold mb-1">Field view</div>
        <p className="text-sm text-[var(--muted-foreground)] m-0">
          {avail.error
            ? `Could not read the case: ${avail.error}`
            : "No solution written yet — run the solver, then come back."}
        </p>
      </Card>
    );
  }

  const [lo, hi] = data?.range ?? [0, 1];
  const useDiverging = lo < 0 && hi > 0;
  const ramp = (useDiverging ? diverging : sequential);
  const stops = Array.from({ length: 9 }, (_, i) => {
    const [r, g, b] = ramp(i / 8);
    return `rgb(${r | 0},${g | 0},${b | 0})`;
  });
  const fmt = (v) => (Math.abs(v) >= 1000 || (Math.abs(v) < 0.01 && v !== 0) ? v.toExponential(2) : v.toFixed(3));

  return (
    <Card>
      <div className="flex flex-wrap items-end gap-3 mb-3">
        <label className="block">
          <span className="block text-xs text-[var(--muted-foreground)] mb-1">Field</span>
          <Select
            options={avail?.fields ?? []}
            value={active ?? ""}
            onChange={(e) => setField(e.target.value)}
          />
        </label>
        <div className="flex gap-1">
          {[2, 4, 10, 40].map((z) => (
            <Button key={z} variant={zoom === z ? "primary" : "ghost"} onClick={() => setZoom(z)}>
              {z}c
            </Button>
          ))}
        </div>
        <span className="text-xs text-[var(--muted-foreground)] ml-auto">
          {data ? `${data.n_triangles.toLocaleString()} cells · t = ${data.time}` : ""}
          {isFetching ? " · loading…" : ""}
        </span>
      </div>

      {error && <p className="text-sm text-[var(--destructive)] mb-2">{error.message}</p>}

      <canvas
        ref={canvasRef}
        className="w-full rounded-lg border border-[var(--border)]"
        style={{ height: 340, display: "block" }}
      />

      <div className="flex items-center gap-3 mt-3">
        <span className="text-xs font-mono text-[var(--muted-foreground)]">{fmt(lo)}</span>
        <div
          className="flex-1 h-3 rounded"
          style={{ background: `linear-gradient(to right, ${stops.join(",")})` }}
        />
        <span className="text-xs font-mono text-[var(--muted-foreground)]">{fmt(hi)}</span>
      </div>
      <p className="text-xs text-[var(--muted-foreground)] mt-2 m-0">
        Mid-span slice of the solved field. Pressure is kinematic (p/ρ, m²/s²) as OpenFOAM's
        incompressible solvers report it. Use <span className="font-mono">Open in ParaView</span> for
        3D, streamlines and probing.
      </p>
    </Card>
  );
}
