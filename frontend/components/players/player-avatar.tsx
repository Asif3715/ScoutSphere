"use client";

import { useState } from "react";

import { initials, mediaUrl } from "@/lib/media";

const SIZES = {
  xs: "h-7 w-7 text-[0.62rem]",
  sm: "h-9 w-9 text-xs",
  md: "h-14 w-14 text-base",
  lg: "h-28 w-28 text-3xl",
  xl: "h-40 w-40 text-5xl",
} as const;

/**
 * A player's photo, or a monogram badge when there is none (or it fails to load). Square
 * with a hard volt corner tick: a squad-card look rather than a generic round avatar.
 */
export function PlayerAvatar({
  name,
  src,
  size = "sm",
  className = "",
}: {
  name: string;
  src: string | null | undefined;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const url = mediaUrl(src);
  const [failed, setFailed] = useState<string | null>(null);
  const show = url && failed !== url;
  return (
    <span
      className={`relative inline-grid shrink-0 place-items-center overflow-hidden rounded-[3px] bg-dugout font-display font-extrabold text-volt uppercase ring-1 ring-line ${SIZES[size]} ${className}`}
    >
      {show ? (
        // eslint-disable-next-line @next/next/no-img-element -- signed, per-user URLs; not optimizable
        <img
          src={url}
          alt={`Photo of ${name}`}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFailed(url)}
          className="h-full w-full object-cover"
        />
      ) : (
        <span
          aria-label={`${name} (no photo)`}
          role="img"
          className="tracking-wide"
        >
          {initials(name)}
        </span>
      )}
      <span
        aria-hidden="true"
        className="absolute top-0 right-0 h-1.5 w-1.5 bg-volt"
      />
    </span>
  );
}
