"use client";

import { useId, useRef, useState } from "react";

import { PlayerAvatar } from "@/components/players/player-avatar";
import { Button, ErrorText } from "@/components/ui/ui";
import { ApiError } from "@/lib/http";
import {
  checkPhotoFile,
  cropFromView,
  PHOTO_MIN_SIDE,
  type Crop,
} from "@/lib/media";

const VIEW = 272; // framing square, in CSS pixels
const MAX_ZOOM = 4;

type Framing = {
  w: number;
  h: number;
  base: number;
  zoom: number;
  x: number;
  y: number;
};

function clampOffset(f: Framing): Framing {
  const s = f.base * f.zoom;
  const minX = VIEW - f.w * s;
  const minY = VIEW - f.h * s;
  return {
    ...f,
    x: Math.min(0, Math.max(minX, f.x)),
    y: Math.min(0, Math.max(minY, f.y)),
  };
}

/** Renders the chosen square to a small data URL, used as an instant preview. */
function renderPreview(img: HTMLImageElement, crop: Crop): string {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 240;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";
  ctx.drawImage(img, crop.x, crop.y, crop.size, crop.size, 0, 0, 240, 240);
  return canvas.toDataURL("image/jpeg", 0.85);
}

/**
 * Pick a photo (browse or drag and drop), frame it as a square by dragging and zooming, then
 * save. The chosen square is sent as pixel coordinates; the server does the real crop.
 */
export function PhotoEditor({
  name,
  current,
  onSave,
  onRemove,
  saveLabel = "Save photo",
}: {
  name: string;
  current: string | null;
  onSave: (file: File, crop: Crop, preview: string) => Promise<void>;
  onRemove?: () => Promise<void>;
  saveLabel?: string;
}) {
  const inputId = useId();
  const helpId = useId();
  const imgRef = useRef<HTMLImageElement>(null);
  const drag = useRef<{ px: number; py: number; x: number; y: number } | null>(
    null,
  );
  const [file, setFile] = useState<File | null>(null);
  const [src, setSrc] = useState<string | null>(null);
  const [framing, setFraming] = useState<Framing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"save" | "remove" | null>(null);
  const [dragOver, setDragOver] = useState(false);

  function reset() {
    if (src) URL.revokeObjectURL(src);
    setFile(null);
    setSrc(null);
    setFraming(null);
  }

  function pick(f: File | undefined) {
    setError(null);
    if (!f) return;
    const problem = checkPhotoFile(f);
    if (problem) {
      setError(problem);
      return;
    }
    if (src) URL.revokeObjectURL(src);
    setFile(f);
    setSrc(URL.createObjectURL(f));
    setFraming(null);
  }

  function onLoaded(e: React.SyntheticEvent<HTMLImageElement>) {
    const { naturalWidth: w, naturalHeight: h } = e.currentTarget;
    if (Math.min(w, h) < PHOTO_MIN_SIDE) {
      setError(
        `This image is ${w}×${h}. Photos must be at least ${PHOTO_MIN_SIDE}×${PHOTO_MIN_SIDE} pixels.`,
      );
      reset();
      return;
    }
    const base = VIEW / Math.min(w, h); // "cover": the short side fills the square
    setFraming({
      w,
      h,
      base,
      zoom: 1,
      x: (VIEW - w * base) / 2,
      y: (VIEW - h * base) / 2,
    });
  }

  /** Absolute zoom, or a function of the latest zoom (so quick key presses add up). */
  function zoomTo(zoom: number | ((current: number) => number)) {
    setFraming((f) => {
      if (!f) return f;
      const target = typeof zoom === "function" ? zoom(f.zoom) : zoom;
      const z = Math.min(MAX_ZOOM, Math.max(1, target));
      // keep the point under the centre of the frame fixed while zooming
      const cx = (VIEW / 2 - f.x) / (f.base * f.zoom);
      const cy = (VIEW / 2 - f.y) / (f.base * f.zoom);
      return clampOffset({
        ...f,
        zoom: z,
        x: VIEW / 2 - cx * f.base * z,
        y: VIEW / 2 - cy * f.base * z,
      });
    });
  }

  function nudge(dx: number, dy: number) {
    setFraming((f) =>
      f ? clampOffset({ ...f, x: f.x + dx, y: f.y + dy }) : f,
    );
  }

  async function save() {
    if (!file || !framing || !imgRef.current) return;
    const crop = cropFromView(
      { w: framing.w, h: framing.h },
      {
        size: VIEW,
        scale: framing.base * framing.zoom,
        offsetX: framing.x,
        offsetY: framing.y,
      },
    );
    setBusy("save");
    setError(null);
    try {
      await onSave(file, crop, renderPreview(imgRef.current, crop));
      reset();
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : "The photo could not be saved. Try again.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    if (!onRemove || !window.confirm(`Remove ${name}'s photo?`)) return;
    setBusy("remove");
    setError(null);
    try {
      await onRemove();
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "The photo could not be removed.",
      );
    } finally {
      setBusy(null);
    }
  }

  const input = (
    <input
      id={inputId}
      type="file"
      accept="image/jpeg,image/png,image/webp"
      className="sr-only"
      onChange={(e) => {
        pick(e.target.files?.[0]);
        e.target.value = ""; // allow choosing the same file again
      }}
    />
  );

  if (src) {
    const s = framing ? framing.base * framing.zoom : 1;
    return (
      <div className="space-y-3">
        <p id={helpId} className="text-xs opacity-70">
          Drag to position, use the slider to zoom. Arrow keys move, + and −
          zoom.
        </p>
        <div
          role="application"
          aria-label="Photo framing. Drag or use arrow keys to move, plus and minus to zoom."
          aria-describedby={helpId}
          tabIndex={0}
          className="relative cursor-grab touch-none overflow-hidden rounded-[3px] bg-dugout ring-2 ring-volt select-none active:cursor-grabbing"
          style={{ width: VIEW, height: VIEW }}
          onPointerDown={(e) => {
            if (!framing) return;
            e.currentTarget.setPointerCapture(e.pointerId);
            drag.current = {
              px: e.clientX,
              py: e.clientY,
              x: framing.x,
              y: framing.y,
            };
          }}
          onPointerMove={(e) => {
            const d = drag.current;
            if (!d) return;
            setFraming((f) =>
              f
                ? clampOffset({
                    ...f,
                    x: d.x + e.clientX - d.px,
                    y: d.y + e.clientY - d.py,
                  })
                : f,
            );
          }}
          onPointerUp={() => (drag.current = null)}
          onPointerCancel={() => (drag.current = null)}
          onKeyDown={(e) => {
            const step = e.shiftKey ? 40 : 10;
            const keys: Record<string, () => void> = {
              ArrowLeft: () => nudge(step, 0),
              ArrowRight: () => nudge(-step, 0),
              ArrowUp: () => nudge(0, step),
              ArrowDown: () => nudge(0, -step),
              "+": () => zoomTo((z) => z + 0.2),
              "=": () => zoomTo((z) => z + 0.2),
              "-": () => zoomTo((z) => z - 0.2),
            };
            if (keys[e.key]) {
              e.preventDefault();
              keys[e.key]();
            }
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- local object URL being framed */}
          <img
            ref={imgRef}
            src={src}
            alt="Selected photo"
            draggable={false}
            onLoad={onLoaded}
            className="pointer-events-none absolute top-0 left-0 max-w-none origin-top-left"
            style={
              framing
                ? {
                    width: framing.w * s,
                    height: framing.h * s,
                    transform: `translate(${framing.x}px, ${framing.y}px)`,
                  }
                : { opacity: 0 }
            }
          />
          {/* rule-of-thirds guides */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
          >
            <div className="absolute inset-y-0 left-1/3 w-px bg-white/30" />
            <div className="absolute inset-y-0 left-2/3 w-px bg-white/30" />
            <div className="absolute inset-x-0 top-1/3 h-px bg-white/30" />
            <div className="absolute inset-x-0 top-2/3 h-px bg-white/30" />
          </div>
        </div>
        <label
          className="flex items-center gap-3 text-xs"
          style={{ maxWidth: VIEW }}
        >
          <span className="eyebrow opacity-70">Zoom</span>
          <input
            type="range"
            min={1}
            max={MAX_ZOOM}
            step={0.01}
            value={framing?.zoom ?? 1}
            onChange={(e) => zoomTo(Number(e.target.value))}
            className="flex-1"
            aria-label="Zoom"
          />
        </label>
        <ErrorText>{error}</ErrorText>
        <div className="flex flex-wrap gap-2">
          <Button onClick={save} disabled={!framing || busy !== null}>
            {busy === "save" ? "Saving…" : saveLabel}
          </Button>
          <label htmlFor={inputId} className="btn btn-secondary cursor-pointer">
            Choose another
          </label>
          <Button variant="secondary" onClick={reset} disabled={busy !== null}>
            Cancel
          </Button>
          {input}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          pick(e.dataTransfer.files?.[0]);
        }}
        className={`flex flex-wrap items-center gap-4 rounded-[3px] border border-dashed p-3 transition-colors ${
          dragOver ? "border-volt bg-volt/10" : "border-line-strong"
        }`}
      >
        <PlayerAvatar name={name} src={current} size="lg" />
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <label htmlFor={inputId} className="btn btn-primary cursor-pointer">
              {current ? "Change photo" : "Upload photo"}
            </label>
            {current && onRemove && (
              <Button
                variant="danger"
                onClick={remove}
                disabled={busy !== null}
              >
                {busy === "remove" ? "Removing…" : "Remove"}
              </Button>
            )}
          </div>
          <p className="text-xs opacity-60">
            Or drag an image here. JPEG, PNG or WebP, up to 5 MB.
            <br />
            Location and camera details are removed automatically.
          </p>
          {input}
        </div>
      </div>
      <ErrorText>{error}</ErrorText>
    </div>
  );
}
