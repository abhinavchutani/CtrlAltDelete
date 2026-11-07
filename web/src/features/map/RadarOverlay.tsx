// Decorative radar reticle over the map centre: rings, crosshair ticks and a slow sweep. Never intercepts clicks.
export function RadarOverlay() {
  return (
    <div className="radar" aria-hidden="true">
      <svg viewBox="-500 -500 1000 1000" preserveAspectRatio="xMidYMid meet">
        {[90, 200, 330, 460].map((r) => <circle key={r} r={r} className="radar-ring" />)}
        {[0, 90, 180, 270].map((a) => (
          <g key={a} transform={`rotate(${a})`}>
            <line className="radar-tick" x1={0} y1={-490} x2={0} y2={-440} />
            <line className="radar-tick" x1={0} y1={-215} x2={0} y2={-185} />
          </g>
        ))}
        <circle r={4} className="radar-dot" />
      </svg>
      <div className="radar-sweep" />
    </div>
  );
}
