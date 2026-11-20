import { describe, expect, it } from "vitest";

import { checkPhotoFile, cropFromView, initials, mediaUrl } from "@/lib/media";

describe("cropFromView", () => {
  it("maps a centred, unzoomed frame to the centred square", () => {
    // 1000x500 image in a 250px frame: base scale 0.5, image is 500x250 on screen
    const crop = cropFromView(
      { w: 1000, h: 500 },
      { size: 250, scale: 0.5, offsetX: -125, offsetY: 0 },
    );
    expect(crop).toEqual({ x: 250, y: 0, size: 500 });
  });

  it("follows panning and zooming", () => {
    // zoom x2 (scale 1): the frame shows 250 image pixels, panned to the right edge
    const crop = cropFromView(
      { w: 1000, h: 500 },
      { size: 250, scale: 1, offsetX: -750, offsetY: -250 },
    );
    expect(crop).toEqual({ x: 750, y: 250, size: 250 });
  });

  it("never leaves the image, even with rounding at the edges", () => {
    const crop = cropFromView(
      { w: 301, h: 300 },
      { size: 272, scale: 272 / 300, offsetX: -0.6, offsetY: 0.4 },
    );
    expect(crop.x + crop.size).toBeLessThanOrEqual(301);
    expect(crop.y).toBeGreaterThanOrEqual(0);
    expect(crop.size).toBeLessThanOrEqual(300);
  });
});

describe("checkPhotoFile", () => {
  it("accepts the supported formats under the size limit", () => {
    for (const type of ["image/jpeg", "image/png", "image/webp"])
      expect(checkPhotoFile({ type, size: 1000 })).toBeNull();
  });
  it("explains what is wrong otherwise", () => {
    expect(checkPhotoFile({ type: "image/gif", size: 10 })).toMatch(
      /JPEG, PNG or WebP/,
    );
    expect(checkPhotoFile({ type: "image/svg+xml", size: 10 })).toMatch(
      /JPEG, PNG or WebP/,
    );
    expect(
      checkPhotoFile({ type: "image/png", size: 6 * 1024 * 1024 }),
    ).toMatch(/5 MB/);
    expect(checkPhotoFile({ type: "image/png", size: 0 })).toMatch(/empty/);
  });
});

it("builds initials for the monogram fallback", () => {
  expect(initials("Mateo Varga")).toBe("MV");
  expect(initials("  kwame  ")).toBe("K");
  expect(initials("Luka Modric Junior")).toBe("LJ");
  expect(initials("")).toBe("?");
});

it("prefixes signed API paths but leaves external links alone", () => {
  expect(mediaUrl("/api/v1/media/players/x.webp?exp=1&sig=a")).toMatch(
    /^http:\/\/localhost:8000\/api\/v1\/media\//,
  );
  expect(mediaUrl("https://cdn.example.com/p.jpg")).toBe(
    "https://cdn.example.com/p.jpg",
  );
  expect(mediaUrl(null)).toBeNull();
});
