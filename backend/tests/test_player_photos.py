"""Player photo upload: image validation, processing, permissions and signed delivery."""

import io

import pytest
from PIL import Image

from app.core.config import get_settings
from app.services import media
from tests.conftest import hdr
from tests.helpers import API, make_player, scouting_setup, setup_org


@pytest.fixture(autouse=True)
def media_root(tmp_path):
    settings = get_settings()
    old = settings.media_root
    settings.media_root = str(tmp_path)
    yield tmp_path
    settings.media_root = old


def image_bytes(size=(400, 400), color=(200, 30, 30), fmt="JPEG", **save) -> bytes:
    out = io.BytesIO()
    mode = "RGBA" if fmt == "PNG" and len(color) == 4 else "RGB"
    Image.new(mode, size, color).save(out, fmt, **save)
    return out.getvalue()


def halves(w=400, h=200) -> bytes:
    """Left half red, right half blue."""
    img = Image.new("RGB", (w, h), (220, 0, 0))
    img.paste((0, 0, 220), (w // 2, 0, w, h))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


async def upload(client, headers, player_id, data, name="photo.jpg", ctype="image/jpeg", **crop):
    return await client.put(
        f"{API}/players/{player_id}/photo",
        files={"file": (name, data, ctype)},
        data={k: str(v) for k, v in crop.items()},
        headers=headers,
    )


async def fetch(client, path) -> Image.Image:
    r = await client.get(path)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/webp"
    return Image.open(io.BytesIO(r.content))


async def test_upload_processes_and_serves_a_square_webp(client, media_root):
    s = await scouting_setup(client)
    pid = s.player["id"]
    r = await upload(client, s.owner_h, pid, image_bytes((1000, 800)))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_uploaded_photo"] is True
    assert body["photo_url"].startswith("/api/v1/media/players/")

    full = await fetch(client, body["photo_url"])
    thumb = await fetch(client, body["photo_thumb_url"])
    assert full.format == "WEBP" and full.size == (media.FULL_SIZE, media.FULL_SIZE)
    assert thumb.size == (media.THUMB_SIZE, media.THUMB_SIZE)
    # two files on disk, nothing else (no original kept)
    assert len(list(media_root.rglob("*.webp"))) == 2

    # the list and detail views carry the thumbnail too
    listed = (await client.get(f"{API}/players", headers=s.owner_h)).json()["items"]
    assert next(p for p in listed if p["id"] == pid)["photo_thumb_url"] == body["photo_thumb_url"]


async def test_metadata_is_stripped_and_orientation_applied(client):
    s = await scouting_setup(client)
    pid = s.player["id"]
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation: rotate 90°, so 300x200 stored = 200x300 upright
    exif[0x010F] = "SecretCam"  # camera make
    raw = image_bytes((300, 200), exif=exif.tobytes())
    # A crop that only fits the *upright* image proves the rotation was applied first.
    r = await upload(client, s.owner_h, pid, raw, crop_x=0, crop_y=100, crop_size=200)
    assert r.status_code == 200, r.text
    img = await fetch(client, r.json()["photo_url"])
    assert not img.getexif() and "exif" not in img.info


async def test_crop_selects_the_chosen_square(client):
    s = await scouting_setup(client)
    r = await upload(
        client, s.owner_h, s.player["id"], halves(), "p.png", "image/png",
        crop_x=200, crop_y=0, crop_size=200,
    )  # fmt: skip
    assert r.status_code == 200, r.text
    img = (await fetch(client, r.json()["photo_url"])).convert("RGB")
    assert img.size == (200, 200)  # a small selection is not upscaled
    red, green, blue = img.getpixel((100, 100))
    assert blue > 150 and red < 60  # right (blue) half, not the default centre crop

    for bad in (
        {"crop_x": 300, "crop_y": 0, "crop_size": 200},
        {"crop_x": 0, "crop_y": 0, "crop_size": 50},
    ):
        r = await upload(client, s.owner_h, s.player["id"], halves(), "p.png", "image/png", **bad)
        assert r.json()["error"]["code"] == "invalid_crop"
    r = await upload(client, s.owner_h, s.player["id"], halves(), "p.png", "image/png", crop_x=0)
    assert r.json()["error"]["code"] == "invalid_crop"  # partial crop


async def test_transparent_png_and_webp_are_accepted(client):
    s = await scouting_setup(client)
    pid = s.player["id"]
    r = await upload(
        client, s.owner_h, pid, image_bytes(color=(0, 0, 0, 0), fmt="PNG"), "a.png", "image/png"
    )
    assert r.status_code == 200, r.text
    pixel = (await fetch(client, r.json()["photo_url"])).convert("RGB").getpixel((5, 5))
    assert pixel == (255, 255, 255)  # transparency flattened onto white
    r = await upload(client, s.owner_h, pid, image_bytes(fmt="WEBP"), "a.webp", "image/webp")
    assert r.status_code == 200, r.text


async def test_rejects_files_that_are_not_usable_photos(client):
    s = await scouting_setup(client)
    pid = s.player["id"]

    async def code(data, name="x.jpg", ctype="image/jpeg"):
        return (await upload(client, s.owner_h, pid, data, name, ctype)).json()["error"]["code"]

    assert await code(b"%PDF-1.7 not an image\x00\x01") == "unsupported_photo_type"
    assert await code(b"<svg xmlns='http://www.w3.org/2000/svg'/>", "x.svg", "image/svg+xml") == (
        "unsupported_photo_type"
    )
    assert await code(image_bytes(fmt="GIF")) == "unsupported_photo_type"  # disguised as .jpg
    assert await code(image_bytes((80, 300))) == "photo_too_small"
    assert await code(b"") == "invalid_photo"
    # a real JPEG header followed by garbage
    assert await code(image_bytes()[:200]) == "unsupported_photo_type"

    # over the 5 MB photo limit, but within the transport cap: rejected by the service
    r = await upload(client, s.owner_h, pid, b"\xff" * (5 * 1024 * 1024 + 10))
    assert r.status_code == 413 and r.json()["error"]["code"] == "photo_too_large"
    # far over: refused by the request guard before it is even read
    r = await upload(client, s.owner_h, pid, b"\xff" * (6 * 1024 * 1024))
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"
    # nothing was stored by any of the failed attempts
    assert (await client.get(f"{API}/players/{pid}", headers=s.owner_h)).json()["photo_url"] is None


async def test_decompression_bomb_is_rejected(client):
    s = await scouting_setup(client)
    out = io.BytesIO()
    Image.new("1", (9000, 9000)).save(out, "PNG")  # tiny file, 81 megapixels when decoded
    r = await upload(client, s.owner_h, s.player["id"], out.getvalue(), "b.png", "image/png")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_photo"


async def test_only_editors_of_the_player_can_change_the_photo(client):
    s = await scouting_setup(client)
    pid = s.player["id"]
    for h in (s.scout_h, s.coach_h):  # no players:write
        assert (await upload(client, h, pid, image_bytes())).status_code == 403
        assert (await client.delete(f"{API}/players/{pid}/photo", headers=h)).status_code == 403
    assert (await upload(client, s.rm_h, pid, image_bytes())).status_code == 200

    # another organization cannot touch it, even when the player is visible to them
    await client.patch(f"{API}/players/{pid}", json={"visibility": "network"}, headers=s.owner_h)
    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    ho = hdr(other_t, other_org)
    assert (await upload(client, ho, pid, image_bytes())).status_code == 404
    assert (await client.delete(f"{API}/players/{pid}/photo", headers=ho)).status_code == 404
    assert (await upload(client, None, pid, image_bytes())).status_code == 401


async def test_minors_photos_are_withheld_from_other_organizations(client):
    s = await scouting_setup(client)
    minor = await make_player(client, s.owner_t, s.org, "Young Talent", 15, visibility="network")
    adult = await make_player(client, s.owner_t, s.org, "Grown Up", 25, visibility="network")
    for p in (minor, adult):
        assert (await upload(client, s.owner_h, p["id"], image_bytes())).status_code == 200

    other_t, other_org = await setup_org(client, "o2@x.com", "Other Org")
    ho = hdr(other_t, other_org)
    seen_minor = (await client.get(f"{API}/players/{minor['id']}", headers=ho)).json()
    seen_adult = (await client.get(f"{API}/players/{adult['id']}", headers=ho)).json()
    assert seen_minor["photo_url"] is None and seen_minor["photo_thumb_url"] is None
    assert seen_minor["has_uploaded_photo"] is False
    assert seen_adult["photo_url"] is not None
    listed = {
        p["id"]: p
        for p in (await client.get(f"{API}/players?scope=network", headers=ho)).json()["items"]
    }
    assert listed[minor["id"]]["photo_thumb_url"] is None
    assert listed[adult["id"]]["photo_thumb_url"] is not None
    # the owner still sees their own minor's photo
    own = (await client.get(f"{API}/players/{minor['id']}", headers=s.owner_h)).json()
    assert own["photo_url"] is not None


async def test_replacing_and_removing_cleans_up_files(client, media_root):
    s = await scouting_setup(client)
    pid = s.player["id"]
    first = (await upload(client, s.owner_h, pid, image_bytes())).json()
    second = (await upload(client, s.owner_h, pid, image_bytes(color=(0, 90, 0)))).json()
    assert first["photo_url"] != second["photo_url"]
    assert len(list(media_root.rglob("*.webp"))) == 2  # old pair deleted
    assert (await client.get(first["photo_url"])).status_code == 404

    r = await client.delete(f"{API}/players/{pid}/photo", headers=s.owner_h)
    assert r.status_code == 200 and r.json()["photo_url"] is None
    assert list(media_root.rglob("*.webp")) == []
    assert (await client.get(second["photo_url"])).status_code == 404
    # removing again is harmless
    assert (await client.delete(f"{API}/players/{pid}/photo", headers=s.owner_h)).status_code == 200


async def test_external_link_is_used_until_a_photo_is_uploaded(client):
    s = await scouting_setup(client)
    pid = s.player["id"]
    link = "https://images.example.com/p.jpg"
    await client.patch(
        f"{API}/players/{pid}", json={"profile_picture_url": link}, headers=s.owner_h
    )
    p = (await client.get(f"{API}/players/{pid}", headers=s.owner_h)).json()
    assert p["photo_url"] == link and p["has_uploaded_photo"] is False
    up = (await upload(client, s.owner_h, pid, image_bytes())).json()
    assert up["photo_url"].startswith("/api/v1/media/")  # the upload wins
    gone = (await client.delete(f"{API}/players/{pid}/photo", headers=s.owner_h)).json()
    assert gone["photo_url"] is None and gone["profile_picture_url"] is None


async def test_signed_urls_cannot_be_forged_or_reused_after_expiry(client):
    s = await scouting_setup(client)
    url = (await upload(client, s.owner_h, s.player["id"], image_bytes())).json()["photo_url"]
    assert (await client.get(url)).status_code == 200
    assert (await client.get(url[:-4] + "0000")).status_code == 404  # tampered signature
    path, query = url.split("?")
    assert (await client.get(path)).status_code == 422  # no signature at all
    key = path.removeprefix("/api/v1/media/")
    # a valid signature for another key does not transfer
    other = key.replace(key.split("/")[2][:4], "0000", 1)
    assert (await client.get(f"/api/v1/media/{other}?{query}")).status_code == 404
    # path traversal never reaches the filesystem
    assert (await client.get(f"/api/v1/media/players/../../etc/passwd?{query}")).status_code == 404

    exp = int(query.split("exp=")[1].split("&")[0])
    assert media.verify(key, exp, query.split("sig=")[1]) is True
    assert media.verify(key, exp, query.split("sig=")[1], now=exp + 1) is False  # expired
    # URLs stay stable within a window (cacheable) and always live at least one window
    window = get_settings().media_url_hours * 3600
    t = 1_800_000_000
    assert media.signed_path(key, now=t) == media.signed_path(key, now=t + 60)
    assert int(media.signed_path(key, now=t).split("exp=")[1].split("&")[0]) - t >= window


async def test_other_routes_still_reject_nul_and_large_bodies(client):
    s = await scouting_setup(client)
    r = await client.patch(
        f"{API}/players/{s.player['id']}", json={"biography": "a\u0000b"}, headers=s.owner_h
    )
    assert r.json()["error"]["code"] == "invalid_characters"
    # the photo exemption is for multipart on the photo route only
    r = await client.put(
        f"{API}/players/{s.player['id']}/photo", content=b"x\x00y",
        headers={**s.owner_h, "Content-Type": "application/json"},
    )  # fmt: skip
    assert r.json()["error"]["code"] == "invalid_characters"
