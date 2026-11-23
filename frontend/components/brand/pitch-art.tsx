import { useId } from "react";

/**
 * A live scouting map: a properly proportioned pitch whose chalk lines draw themselves in,
 * then a looping sequence plays. A ball is passed through five scouted players, leaving a
 * trail, and each player is "locked on" with a ripple and a rating tag as the ball arrives.
 * A soft floodlight band sweeps across the grass. All motion is CSS (see `.pitch-*` in
 * globals.css) and stops, leaving a still frame, when the visitor prefers reduced motion.
 */

// Pitch is 105 x 68 m drawn at 6.29 units per metre inside a 680 x 440 box.
const L = 10; // left touchline x
const R = 670; // right touchline x
const T = 10;
const B = 430;
const MID_X = 340;
const MID_Y = 220;

const CYCLE = 9; // seconds per loop
const START = 2.2; // seconds before the first loop: lets the lines draw in first
const RUN = 0.72; // share of the loop the ball spends moving

type Target = { x: number; y: number; pos: string; rating: string };
const TARGETS: Target[] = [
  { x: 150, y: 92, pos: "LW", rating: "8.4" },
  { x: 252, y: 300, pos: "CM", rating: "7.9" },
  { x: 430, y: 150, pos: "CAM", rating: "9.1" },
  { x: 505, y: 330, pos: "RB", rating: "8.2" },
  { x: 600, y: 220, pos: "ST", rating: "8.8" },
];

const ROUTE = TARGETS.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${p.y}`).join(
  " ",
);

/** When (in seconds from the loop start) the ball reaches each target. */
function arrivals() {
  const lengths = TARGETS.slice(1).map((p, i) =>
    Math.hypot(p.x - TARGETS[i].x, p.y - TARGETS[i].y),
  );
  const total = lengths.reduce((a, b) => a + b, 0);
  let run = 0;
  return TARGETS.map((_, i) => {
    if (i > 0) run += lengths[i - 1];
    return (run / total) * RUN * CYCLE;
  });
}

export function PitchArt({ className = "" }: { className?: string }) {
  const uid = useId().replace(/:/g, "");
  const clip = `pitch-clip-${uid}`;
  const scan = `pitch-scan-${uid}`;
  const at = arrivals();

  // Chalk lines. `pathLength=1` lets one dash rule draw every shape, whatever its size.
  let n = 0;
  const chalk = (extra: React.SVGAttributes<SVGElement> = {}) => ({
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    pathLength: 1,
    className: "pitch-draw",
    style: { animationDelay: `${(n++ % 6) * 120}ms` },
    ...extra,
  });

  // Each tag appears when the ball arrives, and all of them fade together at the end of the
  // pass. That needs per-tag keyframes, since a tag's own cycle starts at its arrival time.
  const tagKeyframes = at
    .map((t, i) => {
      const hold = (((0.9 * CYCLE - t) / CYCLE) * 100).toFixed(2);
      const gone = (((CYCLE - t) / CYCLE) * 100).toFixed(2);
      return `@keyframes pitch-tag-${i}{0%{opacity:0;transform:translateY(6px)}4%{opacity:1;transform:none}${hold}%{opacity:1;transform:none}${gone}%,100%{opacity:0;transform:none}}`;
    })
    .join("");

  return (
    <svg viewBox="0 0 680 440" className={className} aria-hidden="true">
      <style>{tagKeyframes}</style>
      <defs>
        <clipPath id={clip}>
          <rect x={L} y={T} width={R - L} height={B - T} />
        </clipPath>
        <linearGradient id={scan} x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="var(--volt)" stopOpacity="0" />
          <stop offset="0.65" stopColor="var(--volt)" stopOpacity="0.14" />
          <stop offset="0.9" stopColor="var(--volt)" stopOpacity="0.26" />
          <stop offset="1" stopColor="var(--volt)" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* mown stripes + the sweeping floodlight band, clipped to the grass */}
      <g clipPath={`url(#${clip})`}>
        {Array.from({ length: 10 }, (_, i) => (
          <rect
            key={i}
            x={L + i * 66}
            y={T}
            width={66}
            height={B - T}
            className={`pitch-fade ${i % 2 ? "fill-volt/[0.055]" : "fill-transparent"}`}
          />
        ))}
        <rect
          x={0}
          y={T}
          width={150}
          height={B - T}
          fill={`url(#${scan})`}
          className="pitch-scan"
          style={{ animationDelay: `${START}s` }}
        />
      </g>

      {/* markings */}
      <rect x={L} y={T} width={R - L} height={B - T} {...chalk()} />
      <path d={`M${MID_X} ${T}V${B}`} {...chalk()} />
      <circle cx={MID_X} cy={MID_Y} r="57.5" {...chalk()} />
      <circle
        cx={MID_X}
        cy={MID_Y}
        r="2.5"
        className="fill-current pitch-fade"
      />
      {/* penalty areas (16.5 m deep, 40.3 m wide) and six-yard boxes */}
      <rect x={L} y="93" width="104" height="254" {...chalk()} />
      <rect x={R - 104} y="93" width="104" height="254" {...chalk()} />
      <rect x={L} y="162.5" width="35" height="115" {...chalk()} />
      <rect x={R - 35} y="162.5" width="35" height="115" {...chalk()} />
      {/* penalty spots and the arcs that sit outside each box */}
      <circle
        cx={L + 69}
        cy={MID_Y}
        r="2.5"
        className="fill-current pitch-fade"
      />
      <circle
        cx={R - 69}
        cy={MID_Y}
        r="2.5"
        className="fill-current pitch-fade"
      />
      <path d="M114 174.4A57.5 57.5 0 0 1 114 265.6" {...chalk()} />
      <path d="M566 174.4A57.5 57.5 0 0 0 566 265.6" {...chalk()} />
      {/* corner arcs and goals */}
      <path d="M17 10A7 7 0 0 1 10 17" {...chalk()} />
      <path d="M670 17A7 7 0 0 1 663 10" {...chalk()} />
      <path d="M663 430A7 7 0 0 1 670 423" {...chalk()} />
      <path d="M10 423A7 7 0 0 1 17 430" {...chalk()} />
      <rect x={L - 7} y="197" width="7" height="46" {...chalk()} />
      <rect x={R} y="197" width="7" height="46" {...chalk()} />

      {/* the route the ball takes: drawn progressively behind it */}
      <path
        d={ROUTE}
        pathLength={1}
        fill="none"
        strokeWidth="2"
        strokeLinejoin="round"
        className="pitch-trail stroke-volt"
        style={{ animationDelay: `${START}s` }}
      />

      {/* scouted players */}
      {TARGETS.map((p, i) => (
        <g
          key={p.pos}
          className="pitch-appear"
          style={{ animationDelay: `${1.3 + i * 0.12}s` }}
        >
          <circle
            cx={p.x}
            cy={p.y}
            r="13"
            className="fill-volt/20 live-dot"
            style={{ animationDelay: `${i * 0.3}s` }}
          />
          <circle
            cx={p.x}
            cy={p.y}
            r="11"
            fill="none"
            strokeWidth="1.5"
            className="pitch-ring stroke-volt"
            style={{ animationDelay: `${START + at[i]}s` }}
          />
          <circle cx={p.x} cy={p.y} r="5" className="fill-volt" />
        </g>
      ))}

      {/* rating tags pop up as the ball reaches each player */}
      {TARGETS.map((p, i) => (
        <g
          key={`tag-${p.pos}`}
          className="pitch-tag"
          style={{
            animationName: `pitch-tag-${i}`,
            animationDelay: `${START + at[i]}s`,
          }}
        >
          <rect
            x={p.x - 33}
            y={p.y - 42}
            width="66"
            height="20"
            rx="2"
            className="fill-dugout stroke-volt/70"
            strokeWidth="1"
          />
          <text
            x={p.x}
            y={p.y - 28}
            textAnchor="middle"
            className="fill-volt font-mono"
            style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.06em" }}
          >
            {p.pos} {p.rating}
          </text>
        </g>
      ))}

      {/* the ball */}
      <g
        className="pitch-ball"
        style={{
          offsetPath: `path("${ROUTE}")`,
          animationDelay: `${START}s`,
        }}
      >
        <circle r="11" className="fill-volt/30" />
        <circle
          r="5.5"
          className="fill-dugout-ink stroke-dugout"
          strokeWidth="1"
        />
      </g>
    </svg>
  );
}
