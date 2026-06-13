/** 2D airfoil section preview from coordinate pairs (chord-normalised SVG). */
export function AirfoilPreview({ coordinates }) {
  if (!coordinates || coordinates.length === 0) {
    return (
      <div className="h-40 flex items-center justify-center text-[var(--muted-foreground)] text-sm">
        Generate to preview the section.
      </div>
    );
  }

  const xs = coordinates.map((p) => p[0]);
  const ys = coordinates.map((p) => p[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const chord = maxX - minX || 1;

  const W = 600;
  const H = 200;
  const pad = 20;
  const scale = (W - 2 * pad) / chord;
  const yMid = H / 2;

  const pts = coordinates
    .map(([x, y]) => {
      const px = pad + (x - minX) * scale;
      const py = yMid - y * scale;
      return `${px.toFixed(1)},${py.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 220 }}>
      <line x1={pad} y1={yMid} x2={W - pad} y2={yMid} stroke="var(--border)" strokeDasharray="4 4" />
      <polygon points={pts} fill="var(--primary)" fillOpacity="0.15" stroke="var(--primary)" strokeWidth="1.5" />
      <text x={pad} y={H - 4} fill="var(--muted-foreground)" fontSize="11">
        thickness {(((maxY - minY) / chord) * 100).toFixed(1)}% · {coordinates.length} pts
      </text>
    </svg>
  );
}
