"""Fill existing organizations with realistic demo data, for local testing only.

Everything is created through the public API (as demo staff members), so all business rules,
histories, audit entries and notifications are produced exactly as real usage would. The only
direct database write is adding the demo staff to each organization, because that normally
needs the owner's own login (an invitation).

Usage (backend running at localhost:8000, from the backend directory):

    uv run python scripts/seed_demo.py "BSDS-1 Football Organisation" --size full
    uv run python scripts/seed_demo.py "Aluddin House" --size small

Demo logins are written to ../demo-accounts.md (git-ignored). Refuses to run outside the
local environment, and refuses to seed the same organization twice.
"""

import argparse
import asyncio
import io
import random
import secrets
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.models.organization import Organization, OrganizationMember  # noqa: E402
from app.models.rbac import Role  # noqa: E402
from app.models.user import User  # noqa: E402

API = "http://localhost:8000/api/v1"
MARKER = "[demo data]"
ACCOUNTS_FILE = Path(__file__).resolve().parents[2] / "demo-accounts.md"
TODAY = date.today()
NOW = datetime.now(UTC)

# ---- names -------------------------------------------------------------------------------
NAMES = {
    "England": (["Jack", "Harry", "Oliver", "Mason", "Callum", "Reece", "Jordan", "Kieran", "Toby", "Ethan"],
                ["Walker", "Henderson", "Barnes", "Shaw", "Clarke", "Bennett", "Holloway", "Price", "Mitchell", "Reid"]),
    "Spain": (["Pablo", "Sergio", "Álvaro", "Iker", "Marcos", "Dani", "Hugo", "Adrián", "Rubén", "Mario"],
              ["García", "Navarro", "Ortega", "Iglesias", "Ramos", "Molina", "Serrano", "Vidal", "Castro", "Herrera"]),
    "Brazil": (["Gabriel", "Lucas", "Matheus", "Thiago", "Rafael", "Vinícius", "Bruno", "Caio", "Felipe", "Igor"],
               ["Silva", "Souza", "Oliveira", "Pereira", "Costa", "Almeida", "Ribeiro", "Carvalho", "Gomes", "Rocha"]),
    "France": (["Hugo", "Théo", "Lucas", "Mathis", "Enzo", "Nathan", "Kylian", "Rayan", "Yanis", "Adrien"],
               ["Martin", "Bernard", "Dubois", "Moreau", "Laurent", "Lefèvre", "Fontaine", "Girard", "Mercier", "Blanc"]),
    "Germany": (["Leon", "Jonas", "Felix", "Lukas", "Niklas", "Moritz", "Tim", "Julian", "Paul", "Finn"],
                ["Müller", "Schmidt", "Weber", "Wagner", "Becker", "Hoffmann", "Krause", "Wolf", "Neumann", "Brandt"]),
    "Nigeria": (["Chidi", "Emeka", "Tunde", "Samuel", "Victor", "Ademola", "Kelechi", "Ifeanyi", "Joshua", "Daniel"],
                ["Okafor", "Adeyemi", "Nwosu", "Balogun", "Eze", "Okonkwo", "Bello", "Obi", "Adebayo", "Uche"]),
    "Pakistan": (["Hamza", "Ali", "Usman", "Bilal", "Zain", "Saad", "Hassan", "Faraz", "Ahmed", "Talha"],
                 ["Khan", "Malik", "Qureshi", "Butt", "Sheikh", "Raza", "Iqbal", "Chaudhry", "Abbasi", "Siddiqui"]),
    "Croatia": (["Luka", "Ivan", "Marko", "Josip", "Ante", "Mateo", "Filip", "Domagoj", "Petar", "Toni"],
                ["Horvat", "Kovačić", "Babić", "Marić", "Jurić", "Novak", "Perić", "Vuković", "Knežević", "Matić"]),
    "Netherlands": (["Daan", "Sem", "Milan", "Jesse", "Thijs", "Bram", "Lars", "Ruben", "Stijn", "Joris"],
                    ["de Jong", "Jansen", "de Vries", "van Dijk", "Bakker", "Visser", "Smit", "Meijer", "Mulder", "Bos"]),
    "Ghana": (["Kwame", "Kofi", "Yaw", "Kwabena", "Fiifi", "Abdul", "Emmanuel", "Isaac", "Joseph", "Mohammed"],
              ["Mensah", "Asante", "Owusu", "Boateng", "Appiah", "Osei", "Agyeman", "Darko", "Ofori", "Addo"]),
}  # fmt: skip

# Formation-ish squad shape: position -> share of the squad.
SQUAD_SHAPE = ["GK", "GK", "CB", "CB", "CB", "LB", "RB", "CDM", "CM", "CM", "CAM", "LM", "RM",
               "LW", "RW", "ST", "ST", "CF", "LWB", "RWB", "CB", "CM"]  # fmt: skip
SECONDARY = {"CB": ["CDM"], "LB": ["LWB", "LM"], "RB": ["RWB", "RM"], "CDM": ["CM", "CB"],
             "CM": ["CDM", "CAM"], "CAM": ["CM", "CF"], "LM": ["LW", "LB"], "RM": ["RW", "RB"],
             "LW": ["LM", "ST"], "RW": ["RM", "ST"], "ST": ["CF"], "CF": ["ST", "CAM"],
             "LWB": ["LB", "LM"], "RWB": ["RB", "RM"], "GK": []}  # fmt: skip

# Which attributes stand out for each position (scouts rate these higher).
PROFILE = {
    "GK": ["positioning", "decision_making", "leadership", "awareness", "agility"],
    "CB": ["strength", "positioning", "defensive_contribution", "leadership", "awareness"],
    "LB": ["speed", "stamina", "crossing", "defensive_contribution", "work_rate"],
    "RB": ["speed", "stamina", "crossing", "defensive_contribution", "work_rate"],
    "LWB": ["stamina", "crossing", "speed", "work_rate", "acceleration"],
    "RWB": ["stamina", "crossing", "speed", "work_rate", "acceleration"],
    "CDM": ["positioning", "defensive_contribution", "passing", "stamina", "discipline"],
    "CM": ["passing", "decision_making", "stamina", "first_touch", "awareness"],
    "CAM": ["passing", "dribbling", "first_touch", "decision_making", "confidence"],
    "LM": ["crossing", "speed", "stamina", "dribbling", "work_rate"],
    "RM": ["crossing", "speed", "stamina", "dribbling", "work_rate"],
    "LW": ["dribbling", "speed", "acceleration", "crossing", "confidence"],
    "RW": ["dribbling", "speed", "acceleration", "crossing", "confidence"],
    "ST": ["shooting", "movement", "first_touch", "strength", "confidence"],
    "CF": ["shooting", "movement", "passing", "first_touch", "awareness"],
}
ALL_ATTRS = ["passing", "ball_control", "dribbling", "shooting", "first_touch", "crossing",
             "speed", "acceleration", "strength", "stamina", "agility", "positioning",
             "decision_making", "awareness", "defensive_contribution", "movement", "work_rate",
             "discipline", "confidence", "leadership"]  # fmt: skip

KITS = [((200, 16, 46), (255, 255, 255)), ((19, 64, 146), (255, 255, 255)),
        ((24, 24, 24), (240, 200, 40)), ((255, 255, 255), (20, 20, 20)),
        ((0, 120, 72), (255, 255, 255)), ((108, 29, 69), (130, 196, 255)),
        ((250, 160, 20), (20, 20, 20)), ((90, 170, 230), (255, 255, 255))]  # fmt: skip
SKIN = [
    (255, 224, 189),
    (234, 192, 134),
    (198, 134, 66),
    (141, 85, 36),
    (96, 56, 30),
    (224, 172, 105),
]
HAIR = [(30, 20, 15), (60, 40, 25), (110, 75, 40), (200, 160, 90), (15, 15, 15)]

STRENGTHS = {
    "GK": "Commands the box, quick off the line, distributes calmly under pressure.",
    "CB": "Dominant in the air, reads danger early, comfortable stepping into midfield.",
    "FB": "Overlaps relentlessly and delivers early crosses; recovers quickly.",
    "DM": "Screens the back line, wins second balls and keeps possession simple.",
    "CM": "Scans constantly, receives on the half-turn and switches play with accuracy.",
    "AM": "Finds pockets between the lines and plays the final pass with real disguise.",
    "W": "Explosive over the first five yards, beats defenders one-on-one, direct.",
    "ST": "Clever movement across the front post, clinical with first-time finishes.",
}
WEAKNESSES = ["Decision-making in the final third can be rushed.",
              "Needs to add strength to compete physically at the next level.",
              "Concentration dips late in games.", "Weaker foot is used only reluctantly.",
              "Positioning when the ball is on the far side needs work.",
              "Tends to drift out of games when the team is under pressure."]  # fmt: skip


def group(pos: str) -> str:
    return {"GK": "GK", "CB": "CB", "LB": "FB", "RB": "FB", "LWB": "FB", "RWB": "FB", "CDM": "DM",
            "CM": "CM", "CAM": "AM", "LM": "W", "RM": "W", "LW": "W", "RW": "W", "ST": "ST",
            "CF": "ST"}[pos]  # fmt: skip


# ---- portraits -----------------------------------------------------------------------------
def portrait(rng: random.Random, kit: tuple, number: int | None) -> bytes:
    """A flat, stylized head-and-shoulders portrait in club colours (no real people)."""
    size = 600
    bg_top = tuple(max(0, c - 60) for c in kit[0])
    img = Image.new("RGB", (size, size), bg_top)
    d = ImageDraw.Draw(img)
    for y in range(size):  # vertical gradient
        t = y / size
        d.line([(0, y), (size, y)], fill=tuple(int(bg_top[i] * (1 - t) + 18 * t) for i in range(3)))
    skin, hair = rng.choice(SKIN), rng.choice(HAIR)
    cx = size // 2 + rng.randint(-20, 20)
    d.rounded_rectangle([cx - 210, 400, cx + 210, size + 60], radius=110, fill=kit[0])  # shirt
    d.polygon([(cx - 55, 400), (cx + 55, 400), (cx, 470)], fill=kit[1])  # collar
    d.rectangle([cx - 45, 330, cx + 45, 420], fill=skin)  # neck
    d.ellipse([cx - 105, 140, cx + 105, 370], fill=skin)  # head
    style = rng.randint(0, 2)
    if style == 0:
        d.pieslice([cx - 112, 125, cx + 112, 330], 180, 360, fill=hair)
    elif style == 1:
        d.ellipse([cx - 115, 110, cx + 115, 250], fill=hair)
        d.ellipse([cx - 100, 175, cx + 100, 370], fill=skin)
    else:
        d.chord([cx - 108, 132, cx + 108, 300], 190, 350, fill=hair)
    for ex in (cx - 40, cx + 40):  # eyes
        d.ellipse([ex - 9, 245, ex + 9, 262], fill=(35, 30, 30))
    d.arc([cx - 35, 285, cx + 35, 330], 20, 160, fill=(120, 60, 50), width=5)  # smile
    if number:
        try:
            font = ImageFont.load_default(size=90)
        except TypeError:
            font = ImageFont.load_default()
        d.text((cx, 520), str(number), fill=kit[1], font=font, anchor="mm")
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)
    return out.getvalue()


# ---- API client ------------------------------------------------------------------------------
class Api:
    def __init__(self, token: str, org_id: str):
        self.c = httpx.Client(
            base_url=API, timeout=30,
            headers={"Authorization": f"Bearer {token}", "X-Organization-Id": org_id},
        )  # fmt: skip

    def __call__(self, method: str, path: str, ok=(200, 201, 204), **kw):
        r = self.c.request(method, path, **kw)
        if r.status_code not in ok:
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
        return (
            r.json()
            if r.content and r.headers.get("content-type", "").startswith("application/json")
            else None
        )


def login(email: str, password: str, full_name: str) -> str:
    c = httpx.Client(base_url=API, timeout=30)
    r = c.post("/auth/login", json={"email": email, "password": password})
    if r.status_code == 401:
        c.post(
            "/auth/register", json={"email": email, "password": password, "full_name": full_name}
        ).raise_for_status()
        r = c.post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def SessionLocal():  # noqa: N802
    """No pooling: each asyncio.run() below has its own event loop."""
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    return async_sessionmaker(engine, expire_on_commit=False)()


# ---- staff -----------------------------------------------------------------------------------
STAFF = {
    "full": [("admin", "club_admin", "Sara Whitfield"), ("manager", "recruitment_manager", "Marco Bellini"),
             ("scout1", "scout", "Daniel Osei"), ("scout2", "scout", "Ayesha Rahman"),
             ("scout3", "scout", "Tomás Ferreira"), ("coach", "coach", "Graham Doyle")],
    "small": [("admin", "club_admin", "Imran Qadir"), ("manager", "recruitment_manager", "Lena Hartmann"),
              ("scout1", "scout", "Bilal Anwar"), ("scout2", "scout", "Chloé Martin")],
}  # fmt: skip


async def add_members(org_id: str, members: list[tuple[str, str]]) -> None:
    """Direct insert: joining normally requires the owner to send an invitation."""
    async with SessionLocal() as db:
        for email, role_key in members:
            user = await db.scalar(select(User).where(User.email == email))
            role = await db.scalar(select(Role).where(Role.key == role_key))
            existing = await db.scalar(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == org_id,
                    OrganizationMember.user_id == user.id,
                )
            )
            if existing is None:
                db.add(OrganizationMember(organization_id=org_id, user_id=user.id, role_id=role.id))
        await db.commit()


async def find_org(name: str) -> tuple[str, str]:
    async with SessionLocal() as db:
        org = await db.scalar(select(Organization).where(Organization.name == name))
        if org is None:
            sys.exit(f'No organization called "{name}". Check the exact name.')
        return str(org.id), org.slug


# ---- the seeding itself ------------------------------------------------------------------------
@dataclass
class World:
    rng: random.Random
    size: str
    org_id: str
    slug: str
    clubs: dict[str, dict] = field(default_factory=dict)  # name -> club
    kit: dict[str, tuple] = field(default_factory=dict)
    players: list[dict] = field(default_factory=list)  # player + "pos", "club", "quality"
    matches: list[dict] = field(default_factory=list)


def dob_for(rng: random.Random, age: int) -> str:
    return (TODAY - timedelta(days=age * 365 + rng.randint(15, 350))).isoformat()


def make_player(
    w: World, api: Api, pos: str, age: int, club: str, number: int | None, *, photo: bool
) -> dict:
    rng = w.rng
    nat = rng.choice(list(NAMES))
    first, last = NAMES[nat]
    name = f"{rng.choice(first)} {rng.choice(last)}"
    gk = pos == "GK"
    height = (
        rng.randint(186, 198)
        if gk
        else rng.randint(166, 194)
        if group(pos) in ("CB", "ST")
        else rng.randint(165, 186)
    )
    body = {
        "full_name": name, "date_of_birth": dob_for(rng, age), "nationality": nat,
        "height_cm": height, "weight_kg": max(55, min(95, height - 108 + rng.randint(-5, 6))),
        "preferred_foot": rng.choices(["right", "left", "both"], [70, 24, 6])[0],
        "primary_position": pos,
        "secondary_positions": rng.sample(SECONDARY[pos], k=min(len(SECONDARY[pos]), rng.randint(0, 2))),
        "biography": f"{name} is a {age}-year-old {pos} from {nat}. " + STRENGTHS[group(pos)],
        # most records are private; some are shared with the network so other clubs can see them
        "visibility": "network" if rng.random() < 0.35 else "private",
        "allow_duplicate": True,
    }  # fmt: skip
    p = api("POST", "/players", json=body)
    p.update(pos=pos, club=club, quality=rng.uniform(4.5, 8.8), number=number)
    if photo:
        data = portrait(rng, w.kit[club], number)
        api("PUT", f"/players/{p['id']}/photo", files={"file": ("p.jpg", data, "image/jpeg")})
    w.players.append(p)
    return p


def career(w: World, api: Api, p: dict, *, current_club: str | None) -> None:
    """Past spells with stats, plus an open spell at the current club (if not in a squad)."""
    rng = w.rng
    age = p["age"]
    start = TODAY.replace(month=7, day=1) - timedelta(days=365 * min(age - 15, rng.randint(2, 5)))
    others = [c for c in w.clubs if c != p["club"]]
    for _ in range(rng.randint(1, 2) if age > 19 else 1):
        end = start + timedelta(days=365 * rng.randint(1, 2) - 1)
        if end >= TODAY - timedelta(days=60):
            break
        apps = rng.randint(8, 38) * (end.year - start.year or 1)
        attacking = group(p["pos"]) in ("ST", "W", "AM")
        api("POST", f"/players/{p['id']}/career", json={
            "club_id": w.clubs[rng.choice(others)]["id"], "spell_type": rng.choice(["permanent", "permanent", "loan", "youth"]),
            "start_date": start.isoformat(), "end_date": end.isoformat(), "appearances": apps,
            "goals": int(apps * (rng.uniform(0.2, 0.6) if attacking else rng.uniform(0, 0.08))),
            "assists": int(apps * (rng.uniform(0.1, 0.35) if attacking else rng.uniform(0, 0.12))),
        })  # fmt: skip
        start = end + timedelta(days=1)
    if current_club:
        apps = rng.randint(4, 30)
        api("POST", f"/players/{p['id']}/career", json={
            "club_id": w.clubs[current_club]["id"], "start_date": start.isoformat(), "appearances": apps,
            "goals": int(apps * rng.uniform(0, 0.4)), "assists": int(apps * rng.uniform(0, 0.25)),
        })  # fmt: skip


def seed_clubs_and_squads(w: World, api: Api, home: str, opponents: list[str]) -> None:
    rng = w.rng
    for i, name in enumerate([home, *opponents]):
        club = api("POST", "/clubs", json={
            "name": name, "short_name": "".join(x[0] for x in name.split())[:4].upper(),
            "country": rng.choice(["England", "Spain", "Pakistan", "Netherlands"]),
            "city": name.split()[0], "founded_year": rng.randint(1880, 2015),
            "description": f"{MARKER} " + ("Our club." if i == 0 else "Opponent / scouting target club."),
        })  # fmt: skip
        w.clubs[name] = club
        w.kit[name] = KITS[i % len(KITS)]

    squads = {"First Team": ("senior", 22 if w.size == "full" else 18, (19, 33)),
              "U21": ("u21", 14 if w.size == "full" else 0, (18, 20)),
              "U18": ("u18", 12 if w.size == "full" else 6, (15, 17))}  # fmt: skip
    for team_name, (team_type, count, (lo, hi)) in squads.items():
        if not count:
            continue
        team = api(
            "POST",
            "/teams",
            json={"club_id": w.clubs[home]["id"], "name": team_name, "team_type": team_type},
        )
        numbers = rng.sample(range(1, 50), count)
        for i in range(count):
            pos = SQUAD_SHAPE[i % len(SQUAD_SHAPE)]
            p = make_player(
                w, api, pos, rng.randint(lo, hi), home, numbers[i], photo=rng.random() < 0.75
            )
            career(w, api, p, current_club=None)
            api("POST", f"/teams/{team['id']}/players", json={
                "player_id": p["id"], "squad_number": numbers[i], "position": pos,
                "registered_on": (TODAY - timedelta(days=rng.randint(20, 400))).isoformat(),
            })  # fmt: skip

    # Players at other clubs: the scouting targets.
    per_club = 6 if w.size == "full" else 4
    for name in opponents:
        for _ in range(per_club):
            pos = rng.choice(SQUAD_SHAPE)
            p = make_player(w, api, pos, rng.randint(16, 31), name, None, photo=rng.random() < 0.6)
            career(w, api, p, current_club=name)


def seed_league(w: World, api: Api, home: str, opponents: list[str]) -> None:
    rng = w.rng
    comp = api("POST", "/competitions", json={
        "name": "Demo Premier League" if w.size == "full" else "Demo Regional League",
        "country": "England", "competition_type": "league",
    })  # fmt: skip
    year = TODAY.year if TODAY.month >= 8 else TODAY.year - 1
    season = api("POST", f"/competitions/{comp['id']}/seasons", json={
        "name": f"{year}/{str(year + 1)[2:]}", "start_date": f"{year}-08-01", "end_date": f"{year + 1}-05-31",
    })  # fmt: skip
    clubs = [home, *opponents]
    for name in clubs:
        api("POST", f"/seasons/{season['id']}/participants", json={"club_id": w.clubs[name]["id"]})

    by_club = {}
    for p in w.players:
        by_club.setdefault(p["club"], []).append(p)
    fixtures = [(a, b) for a in clubs for b in clubs if a != b]
    rng.shuffle(fixtures)
    n_played = 18 if w.size == "full" else 8
    n_future = 8 if w.size == "full" else 4
    # make sure our own club appears in plenty of fixtures
    fixtures.sort(key=lambda f: home not in f)
    chosen = fixtures[: n_played + n_future]
    rng.shuffle(chosen)
    for i, (h, a) in enumerate(chosen):
        played = i < n_played
        kickoff = (
            NOW - timedelta(days=4 + i * 5)
            if played
            else NOW + timedelta(days=3 + (i - n_played) * 6)
        )
        kickoff = kickoff.replace(
            hour=rng.choice([13, 15, 18, 19]), minute=rng.choice([0, 30]), second=0, microsecond=0
        )
        m = api("POST", "/matches", json={
            "season_id": season["id"], "home_club_id": w.clubs[h]["id"], "away_club_id": w.clubs[a]["id"],
            "kickoff_at": kickoff.isoformat(), "venue": f"{h.split()[0]} Stadium", "round_label": f"Matchday {i + 1}",
        })  # fmt: skip
        m.update(home=h, away=a, played=played, kickoff=kickoff)
        w.matches.append(m)
        if not played:
            continue
        hs, as_ = (
            rng.choices(range(5), [30, 33, 22, 10, 5])[0],
            rng.choices(range(5), [36, 33, 19, 8, 4])[0],
        )
        # the result first: events and statistics need a finished (or live) match
        api(
            "PATCH",
            f"/matches/{m['id']}",
            json={"status": "finished", "home_score": hs, "away_score": as_},
        )
        for side, goals in ((h, hs), (a, as_)):
            scorers = [p for p in by_club.get(side, []) if p["pos"] != "GK"] or [None]
            for _ in range(goals):
                scorer = rng.choice(scorers)
                api("POST", f"/matches/{m['id']}/events", json={
                    "event_type": "goal", "minute": rng.randint(1, 90), "club_id": w.clubs[side]["id"],
                    "player_id": scorer["id"] if scorer else None,
                })  # fmt: skip
            for _ in range(rng.randint(0, 3)):
                booked = rng.choice(scorers)
                api("POST", f"/matches/{m['id']}/events", json={
                    "event_type": "yellow_card", "minute": rng.randint(10, 90), "club_id": w.clubs[side]["id"],
                    "player_id": booked["id"] if booked else None,
                })  # fmt: skip

        def side_stats(goals: int) -> dict:
            shots = rng.randint(max(goals, 4), 20)
            return {"shots": shots, "shots_on_target": rng.randint(goals, max(goals, shots // 2)),
                    "corners": rng.randint(1, 11), "fouls": rng.randint(5, 18), "offsides": rng.randint(0, 5),
                    "yellow_cards": rng.randint(0, 4), "red_cards": rng.choices([0, 1], [92, 8])[0]}  # fmt: skip

        poss = rng.randint(36, 64)
        api("PUT", f"/matches/{m['id']}/statistics", json={
            "home": {"possession_pct": poss, **side_stats(hs)}, "away": {"possession_pct": 100 - poss, **side_stats(as_)},
        })  # fmt: skip


def ratings_for(rng: random.Random, p: dict, k: int) -> dict[str, int]:
    """Scout ratings that reflect the player's position profile and underlying quality."""
    strong = PROFILE[p["pos"]]
    attrs = list(dict.fromkeys(strong[:3] + rng.sample(ALL_ATTRS, k=len(ALL_ATTRS))))[:k]
    out = {}
    for a in attrs:
        base = p["quality"] + (1.0 if a in strong else -0.6)
        out[a] = max(1, min(10, round(rng.gauss(base, 0.9))))
    return out


def report_body(rng: random.Random, p: dict, **extra) -> dict:
    q = p["quality"]
    rec = (
        "strongly_recommend"
        if q > 7.6
        else "recommend"
        if q > 6.4
        else "monitor"
        if q > 5.2
        else "not_recommended"
    )
    return {
        "player_id": p["id"], "position_observed": p["pos"], "recommendation": rec,
        "observed_on": (TODAY - timedelta(days=rng.randint(1, 60))).isoformat(),
        "strengths": STRENGTHS[group(p["pos"])], "weaknesses": rng.choice(WEAKNESSES),
        "development_areas": "Would benefit from regular minutes at a higher level.",
        "general_observations": f"Watched {p['full_name']} for the full 90 minutes. "
        + rng.choice(["Influential throughout.", "Quiet first half, decisive second half.",
                      "Consistent and reliable.", "Showed flashes of real quality."]),
        "ratings": ratings_for(rng, p, rng.randint(6, 12)),
        **extra,
    }  # fmt: skip


def seed_scouting(w: World, staff: dict[str, Api], staff_ids: dict[str, str], home: str) -> dict:
    rng = w.rng
    scouts = [k for k in staff if k.startswith("scout")]
    profiles = {}
    regions = [
        ["England", "Netherlands"],
        ["Pakistan", "Middle East"],
        ["Brazil", "Portugal", "Spain"],
    ]
    for i, s in enumerate(scouts):
        profiles[s] = staff[s]("POST", "/scouts", json={
            "bio": "Experienced scout covering youth and senior football.",
            "experience_years": rng.randint(2, 18), "positions": rng.sample(list(PROFILE), 4),
            "age_groups": rng.sample(["u17", "u19", "u21", "u23", "senior"], 2), "regions": regions[i % 3],
        })["id"]  # fmt: skip
    mgr = staff["manager"]
    targets = [p for p in w.players if p["club"] != home]
    rng.shuffle(targets)
    deadline = lambda d: (NOW + timedelta(days=d)).isoformat()  # noqa: E731

    # One assignment per lifecycle state, so every screen has something to show.
    flows = ["approved", "approved", "approved", "under_review", "submitted", "in_progress",
             "accepted", "assigned", "draft", "cancelled", "rejected"]  # fmt: skip
    if w.size == "small":
        flows = ["approved", "approved", "submitted", "in_progress", "assigned", "draft"]
    for i, final in enumerate(flows):
        scout = scouts[i % len(scouts)]
        sapi = staff[scout]
        p = targets[i % len(targets)]
        a = mgr("POST", "/assignments", json={
            "scout_id": profiles[scout], "target_type": "player", "target_id": p["id"],
            "title": f"Assess {p['full_name']} ({p['pos']})",
            "instructions": "Watch at least one full match. Focus on decision-making under pressure.",
            "criteria": "Ready for first-team minutes within a season?",
            "deadline": deadline(rng.randint(5, 30)), "assign_now": final != "draft",
        })  # fmt: skip
        aid = a["id"]
        if final in ("draft", "assigned"):
            continue
        if final == "cancelled":
            mgr(
                "POST",
                f"/assignments/{aid}/transition",
                json={"to": "cancelled", "note": "Player has signed elsewhere."},
            )
            continue
        sapi("POST", f"/assignments/{aid}/transition", json={"to": "accepted"})
        if final == "accepted":
            continue
        sapi("POST", f"/assignments/{aid}/transition", json={"to": "in_progress"})
        rep = sapi("POST", "/scouting-reports", json=report_body(rng, p, assignment_id=aid))
        if final == "in_progress":
            continue
        sapi("POST", f"/scouting-reports/{rep['id']}/submit")
        sapi("POST", f"/assignments/{aid}/transition", json={"to": "submitted"})
        if final == "submitted":
            continue
        mgr("POST", f"/assignments/{aid}/transition", json={"to": "under_review"})
        if final == "under_review":
            continue
        if final == "rejected":
            mgr(
                "POST",
                f"/scouting-reports/{rep['id']}/review",
                json={"decision": "rejected", "comment": "Not enough evidence from live viewing."},
            )
            mgr(
                "POST",
                f"/assignments/{aid}/transition",
                json={"to": "rejected", "note": "Report did not meet the brief."},
            )
            continue
        mgr(
            "POST",
            f"/scouting-reports/{rep['id']}/review",
            json={"decision": "approved", "comment": "Thorough and well argued."},
        )
        mgr("POST", f"/assignments/{aid}/transition", json={"to": "approved"})

    # Independent reports (no assignment): mostly approved so recruitment matching has data.
    n = 40 if w.size == "full" else 14
    pool = targets + [p for p in w.players if p["club"] == home]
    for i in range(n):
        scout = scouts[i % len(scouts)]
        p = rng.choice(pool)
        rep = staff[scout]("POST", "/scouting-reports", json=report_body(rng, p))
        roll = rng.random()
        if roll < 0.08:
            continue  # stays a draft
        staff[scout]("POST", f"/scouting-reports/{rep['id']}/submit")
        if roll < 0.15:
            continue  # waiting for review
        decision = (
            "approved" if roll < 0.85 else "revision_requested" if roll < 0.93 else "rejected"
        )
        comment = {"approved": None, "revision_requested": "Please add more detail on his defending.",
                   "rejected": "Duplicate of an existing report."}[decision]  # fmt: skip
        mgr(
            "POST",
            f"/scouting-reports/{rep['id']}/review",
            json={"decision": decision, "comment": comment},
        )
    return profiles


def seed_recruitment(
    w: World, staff: dict[str, Api], staff_ids: dict[str, str], profiles: dict, home: str
) -> None:
    rng = w.rng
    mgr = staff["manager"]
    reqs = [
        {"title": "Creative central midfielder", "position": "CM", "min_age": 18, "max_age": 26,
         "priority": "high", "attributes": {"passing": 6}, "budget_min": 50_000, "budget_max": 400_000, "currency": "EUR"},
        {"title": "Left-footed centre back", "position": "CB", "min_age": 19, "max_age": 30,
         "preferred_foot": "left", "priority": "urgent", "budget_max": 600_000, "currency": "EUR"},
        {"title": "Young striker for the U21s", "position": "ST", "max_age": 21, "priority": "medium"},
        {"title": "Backup goalkeeper", "position": "GK", "min_age": 22, "priority": "low"},
    ]  # fmt: skip
    if w.size == "small":
        reqs = reqs[:2]
    paths = [["under_evaluation", "shortlisted", "scout_assigned"], ["shortlisted", "trial_proposed", "negotiation"],
             ["under_evaluation"], ["shortlisted", "rejected"], ["negotiation", "signed"], []]  # fmt: skip
    for i, body in enumerate(reqs):
        body = {**body, "instructions": "Prioritise players with first-team experience."}
        req = mgr("POST", "/recruitment/requirements", json=body)
        mgr("PATCH", f"/recruitment/requirements/{req['id']}", json={"status": "open"})
        # Candidates come from the app's own discovery (they meet every criterion, including
        # minimum scout ratings), topped up with players who fit position, age and foot.
        found = mgr("GET", f"/recruitment/requirements/{req['id']}/matches?page_size=10")["items"]
        by_id = {p["id"]: p for p in w.players}
        fits = [by_id[m["player"]["id"]] for m in found if m["player"]["id"] in by_id]
        fits += [
            p
            for p in w.players
            if p not in fits
            and p["club"] != home
            and (p["pos"] == body["position"] or body["position"] in SECONDARY.get(p["pos"], []))
            and body.get("min_age", 0) <= p["age"] <= body.get("max_age", 99)
            and body.get("preferred_foot", p["preferred_foot"]) in (p["preferred_foot"], "both")
        ]
        for j, p in enumerate(fits[:5]):
            c = mgr(
                "POST",
                f"/recruitment/requirements/{req['id']}/candidates",
                json={"player_id": p["id"], "notes": "Flagged by the scouting team."},
            )
            for stage in paths[(i + j) % len(paths)]:
                if stage == "scout_assigned":
                    scout = rng.choice(list(profiles.values()))
                    mgr("POST", f"/recruitment/candidates/{c['id']}/assign-scout", json={
                        "scout_id": scout, "deadline": (NOW + timedelta(days=14)).isoformat(),
                        "instructions": "Second opinion before we commit."})  # fmt: skip
                    continue
                if stage == "signed" and i != 1:
                    continue  # only one signing, on the centre back requirement
                mgr(
                    "POST",
                    f"/recruitment/candidates/{c['id']}/stage",
                    json={"to": stage, "note": "Agreed in the weekly recruitment meeting."},
                )

    # Shortlists: private to their creator until shared.
    lists = [("Summer window targets", "high", "manager"), ("Academy prospects", "medium", "manager"),
             ("Loan options", "low", "admin")]  # fmt: skip
    for name, prio, owner in lists if w.size == "full" else lists[:2]:
        sl = staff[owner](
            "POST",
            "/recruitment/shortlists",
            json={
                "name": name,
                "priority": prio,
                "description": "Working list for the recruitment meeting.",
            },
        )
        pool = [p for p in w.players if (p["age"] <= 19) == (name == "Academy prospects")]
        for p in rng.sample(pool, k=min(6, len(pool))):
            staff[owner]("POST", f"/recruitment/shortlists/{sl['id']}/players", json={
                "player_id": p["id"], "priority": rng.choice(["low", "medium", "high"]),
                "notes": rng.choice(["Watch again live.", "Agent says he is open to a move.", "Price may be too high.", None]),
            })  # fmt: skip
        share_with = [
            staff_ids[k] for k in ("coach", "admin", "manager") if k in staff_ids and k != owner
        ][:2]
        if name != "Loan options":
            staff[owner](
                "PUT", f"/recruitment/shortlists/{sl['id']}/shares", json={"user_ids": share_with}
            )


def HEADER(password: str) -> list[str]:  # noqa: N802
    return [
        "# ScoutSphere demo accounts (local only, not committed)", "",
        "Created by `backend/scripts/seed_demo.py`. Every demo account uses the same password.", "",
        f"Password: `{password}`", "", "| Organization | Role | Name | Email |", "|---|---|---|---|",
    ]  # fmt: skip


# ---- main ------------------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("organization", help="exact organization name")
    parser.add_argument("--size", choices=["full", "small"], default="full")
    parser.add_argument("--seed", type=int, default=7, help="random seed (same seed, same data)")
    args = parser.parse_args()
    if get_settings().environment not in ("local", "test"):
        sys.exit("Refusing to seed demo data outside the local environment.")

    org_id, slug = asyncio.run(find_org(args.organization))
    rng = random.Random(f"{args.seed}-{org_id}")
    w = World(rng=rng, size=args.size, org_id=org_id, slug=slug)

    # One shared password for every demo login, created once and kept in demo-accounts.md.
    password = None
    if ACCOUNTS_FILE.exists():
        for line in ACCOUNTS_FILE.read_text().splitlines():
            if line.startswith("Password: `"):
                password = line.split("`")[1]
    if password is None:  # save it before any account is created with it
        password = "Demo-" + secrets.token_urlsafe(9)
        ACCOUNTS_FILE.write_text("\n".join(HEADER(password)) + "\n")

    roster = STAFF[args.size]
    tag = slug.split("-")[0][:10]
    accounts = [(key, role, name, f"demo.{tag}.{key}@example.com") for key, role, name in roster]
    tokens = {key: login(email, password, name) for key, _, name, email in accounts}
    asyncio.run(add_members(org_id, [(email, role) for _, role, _, email in accounts]))
    staff = {key: Api(tokens[key], org_id) for key in tokens}
    staff_ids = {key: staff[key]("GET", "/auth/me")["user"]["id"] for key in staff}

    admin = staff["admin"]
    existing = admin("GET", "/clubs?scope=mine&page_size=100")["items"]
    if any(MARKER in (c.get("description") or "") for c in existing):
        sys.exit(f'"{args.organization}" already has demo data. Nothing was changed.')

    home = {"full": "BSDS United FC", "small": "Aluddin Athletic"}[args.size]
    pool = ["Riverside Rovers", "Northgate Albion", "Harbour City", "Eastfield Town",
            "Kingsbridge Wanderers", "Lakeside United", "Westbrook Athletic"]  # fmt: skip
    opponents = pool if args.size == "full" else pool[2:6]

    print(f"Seeding {args.organization} ({args.size})…")
    seed_clubs_and_squads(w, admin, home, opponents)
    print(f"  {len(w.clubs)} clubs, {len(w.players)} players")
    seed_league(w, admin, home, opponents)
    print(f"  {len(w.matches)} matches")
    profiles = seed_scouting(w, staff, staff_ids, home)
    print(f"  {len(profiles)} scouts with assignments and reports")
    seed_recruitment(w, staff, staff_ids, profiles, home)
    print("  recruitment requirements, pipeline and shortlists")

    # Keep a readable list of demo logins (git-ignored).
    lines = ACCOUNTS_FILE.read_text().splitlines()
    labels = {
        "club_admin": "Club Administrator",
        "recruitment_manager": "Recruitment Manager",
        "scout": "Scout",
        "coach": "Coach",
    }
    for _, role, name, email in accounts:
        row = f"| {args.organization} | {labels[role]} | {name} | `{email}` |"
        if row not in lines:
            lines.append(row)
    ACCOUNTS_FILE.write_text("\n".join(lines) + "\n")
    print(f"Done. Demo logins: {ACCOUNTS_FILE}")


if __name__ == "__main__":
    main()
