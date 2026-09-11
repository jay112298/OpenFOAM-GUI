/**
 * Blade-to-blade (cascade) view: the annulus cut at mid-span and unrolled flat,
 * so the blade row reads as a row of 2D sections one pitch apart. This is the
 * view that shows whether the passage between blades is actually open, and how
 * far the blade is staggered over.
 *
 * Axes: x = axial (flow left to right), y = tangential, rotation upwards.
 * Drawn to scale — a low-solidity fan really is a tall, sparse row, and
 * stretching it to fill the card would misreport the stagger angle. The SVG is
 * sized from its own viewBox and centred instead.
 */
/** One labelled velocity arrow. `deg` is measured from the axial direction
 *  toward -tangential, which is +y once the view is flipped for SVG. */
function Arrow({ x0, y0, deg, len, color, label, up, h, stroke }) {
  const r = ((up ? 90 : deg) * Math.PI) / 180;
  const dx = up ? 0 : len * Math.cos(r);
  const dy = up ? -len : len * Math.sin(r);
  const x1 = x0 + dx;
  const y1 = -y0 + dy;
  const head = h / 55;
  const a = Math.atan2(dy, dx);
  return (
    <g>
      <line x1={x0} y1={-y0} x2={x1} y2={y1} stroke={color} strokeWidth={stroke * 1.6} />
      <polygon
        points={[
          [x1, y1],
          [x1 - head * Math.cos(a - 0.4), y1 - head * Math.sin(a - 0.4)],
          [x1 - head * Math.cos(a + 0.4), y1 - head * Math.sin(a + 0.4)],
        ]
          .map((p) => p.join(","))
          .join(" ")}
        fill={color}
      />
      <text x={x1 + head * 0.6} y={y1} fontSize={h / 26} fill={color} dominantBaseline="middle">
        {label}
      </text>
    </g>
  );
}

export function CascadePreview({ outline, pitch, stagger, relativeAngle }) {
  if (!outline || outline.length < 3 || !pitch) {
    return (
      <div className="h-56 grid place-items-center text-sm text-[var(--muted-foreground)] bg-[var(--secondary)] rounded-lg">
        Preview the blade to see the passage
      </div>
    );
  }

  const xs = outline.map((p) => p[0]);
  const ys = outline.map((p) => p[1]);
  const axial = Math.max(...xs) - Math.min(...xs);
  const marginX = Math.max(0.9 * axial, 0.35 * pitch);
  const minX = Math.min(...xs) - marginX;
  const maxX = Math.max(...xs) + marginX;
  const minY = Math.min(...ys) - pitch - 0.12 * pitch;
  const maxY = Math.max(...ys) + pitch + 0.12 * pitch;
  const w = maxX - minX;
  const h = maxY - minY;
  const stroke = h / 260;

  // SVG y grows downward; tangential (the direction of rotation) reads upward
  const path = (dy) =>
    outline.map((p, i) => `${i ? "L" : "M"}${p[0]} ${-(p[1] + dy)}`).join(" ") + " Z";

  // the two rotational periodic planes: half a pitch either side of the blade
  const midY = (Math.min(...ys) + Math.max(...ys)) / 2;
  const periodic = [midY - pitch / 2, midY + pitch / 2];

  return (
    <div className="bg-[var(--secondary)] rounded-lg p-2">
      <svg
        viewBox={`${minX} ${-maxY} ${w} ${h}`}
        style={{ aspectRatio: `${w} / ${h}`, maxHeight: "20rem" }}
        className="block mx-auto max-w-full"
      >
        {periodic.map((y) => (
          <line
            key={y}
            x1={minX}
            y1={-y}
            x2={maxX}
            y2={-y}
            stroke="var(--primary)"
            strokeWidth={stroke}
            strokeDasharray={`${h / 90} ${h / 90}`}
            opacity={0.7}
          />
        ))}
        {[-1, 0, 1].map((k) => (
          <path
            key={k}
            d={path(k * pitch)}
            fill={k === 0 ? "var(--primary)" : "var(--muted)"}
            fillOpacity={k === 0 ? 0.9 : 0.4}
            stroke="var(--foreground)"
            strokeWidth={stroke}
          />
        ))}
        {relativeAngle != null && (
          <Arrow
            x0={minX + w * 0.04}
            y0={midY + pitch * 0.34}
            deg={relativeAngle}
            len={marginX * 0.85}
            color="var(--success)"
            label="W₁"
            h={h}
            stroke={stroke}
          />
        )}
        <Arrow
          x0={maxX - w * 0.1}
          y0={midY - pitch * 0.42}
          up
          len={pitch * 0.3}
          color="var(--warning)"
          label="U"
          h={h}
          stroke={stroke}
        />
      </svg>
      <div className="flex flex-wrap justify-center gap-x-3 gap-y-0.5 text-[11px] text-[var(--muted-foreground)] mt-1 px-1">
        <span className="whitespace-nowrap">axial flow →</span>
        {stagger != null && (
          <span className="whitespace-nowrap">
            stagger {stagger.toFixed(0)}° · inflow {relativeAngle?.toFixed(0)}°
          </span>
        )}
        <span className="whitespace-nowrap text-[var(--primary)]">- - periodic planes</span>
      </div>
    </div>
  );
}
