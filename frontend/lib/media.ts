import { API_URL } from "@/lib/api";

/** Signed API paths become absolute URLs; external image links pass through unchanged. */
export function mediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  return path.startsWith("/api/") ? `${API_URL}${path}` : path;
}

export const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const PHOTO_MAX_BYTES = 5 * 1024 * 1024;
export const PHOTO_MIN_SIDE = 100;

/** Mirrors the server's checks so most problems are explained before uploading. */
export function checkPhotoFile(file: {
  type: string;
  size: number;
}): string | null {
  if (!PHOTO_TYPES.includes(file.type)) return "Use a JPEG, PNG or WebP image.";
  if (file.size > PHOTO_MAX_BYTES) return "Photos must be 5 MB or smaller.";
  if (file.size === 0) return "That file is empty.";
  return null;
}

export type Crop = { x: number; y: number; size: number };

/**
 * Converts the on-screen framing (image offset and scale inside a square viewport) into a
 * square in the image's own pixels, clamped so it always lies inside the image.
 */
export function cropFromView(
  natural: { w: number; h: number },
  view: { size: number; scale: number; offsetX: number; offsetY: number },
): Crop {
  const size = Math.max(
    1,
    Math.min(natural.w, natural.h, Math.round(view.size / view.scale)),
  );
  const clamp = (v: number, max: number) =>
    Math.min(Math.max(0, Math.round(v)), max);
  return {
    x: clamp(-view.offsetX / view.scale, natural.w - size),
    y: clamp(-view.offsetY / view.scale, natural.h - size),
    size,
  };
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0][0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase();
}
