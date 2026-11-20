/** Brand marks: drawn as inline SVG so they inherit theme colors and cost no requests. */

export function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden="true">
      <circle
        cx="20"
        cy="20"
        r="13"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
      <ellipse
        cx="20"
        cy="20"
        rx="5.5"
        ry="13"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        opacity=".55"
      />
      <path
        d="M7 20h26"
        stroke="currentColor"
        strokeWidth="1.4"
        opacity=".55"
      />
      <path
        d="M20 1v5M20 34v5M1 20h5M34 20h5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="square"
      />
      <circle cx="20" cy="20" r="3" className="fill-volt" />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span
      className={`font-display text-[1.6rem] leading-none font-extrabold tracking-[0.02em] uppercase [font-variation-settings:'opsz'_72] ${className}`}
    >
      Scout<span className="text-volt">Sphere</span>
    </span>
  );
}

/** A tactics-board pitch whose chalk lines draw themselves in. */
export function PitchArt({ className = "" }: { className?: string }) {
  const line = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    className: "pitch-line",
  } as const;
  return (
    <svg viewBox="0 0 680 440" className={className} aria-hidden="true">
      <rect x="10" y="10" width="660" height="420" {...line} />
      <path d="M340 10v420" {...line} style={{ animationDelay: "150ms" }} />
      <circle
        cx="340"
        cy="220"
        r="62"
        {...line}
        style={{ animationDelay: "300ms" }}
      />
      <rect
        x="10"
        y="118"
        width="104"
        height="204"
        {...line}
        style={{ animationDelay: "450ms" }}
      />
      <rect
        x="10"
        y="168"
        width="38"
        height="104"
        {...line}
        style={{ animationDelay: "550ms" }}
      />
      <rect
        x="566"
        y="118"
        width="104"
        height="204"
        {...line}
        style={{ animationDelay: "450ms" }}
      />
      <rect
        x="632"
        y="168"
        width="38"
        height="104"
        {...line}
        style={{ animationDelay: "550ms" }}
      />
      <path
        d="M114 182a46 46 0 0 1 0 76M566 182a46 46 0 0 0 0 76"
        {...line}
        style={{ animationDelay: "700ms" }}
      />
      {/* scouted player positions */}
      {[
        [150, 90, 0],
        [252, 300, 1],
        [430, 150, 2],
        [505, 330, 3],
        [600, 220, 4],
      ].map(([x, y, i]) => (
        <g
          key={i}
          className="stagger"
          style={{ animationDelay: `${1200 + i * 140}ms` }}
        >
          <circle cx={x} cy={y} r="13" className="fill-volt/25" />
          <circle cx={x} cy={y} r="5" className="fill-volt" />
        </g>
      ))}
      <path
        d="M150 90 C 220 140, 230 260, 252 300 S 400 190, 430 150 S 520 280, 505 330 S 570 240, 600 220"
        fill="none"
        className="stroke-volt pitch-line"
        strokeWidth="1.5"
        strokeDasharray="4 6"
        style={{ animationDelay: "1500ms" }}
      />
    </svg>
  );
}

export function BellIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      aria-hidden="true"
    >
      <path
        d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15L6 16Z"
        strokeLinejoin="round"
      />
      <path d="M10 20.5a2 2 0 0 0 4 0" />
    </svg>
  );
}
