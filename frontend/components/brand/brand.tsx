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
