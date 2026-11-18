"""Operational commands.  Usage:

    uv run python -m app.cli create-platform-admin you@example.com "Your Name" [--role super_admin]
    uv run python -m app.cli send-deadline-reminders   # run from cron / a scheduler, e.g. hourly

The password is read interactively (or from SCOUTSPHERE_ADMIN_PASSWORD for scripts) so it never
appears in shell history or process lists.
"""

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User
from app.permissions.catalog import PLATFORM_ROLES


async def _send_reminders() -> None:
    from app.services.assignments import send_deadline_reminders

    async with SessionLocal() as db:
        print(f"Sent {await send_deadline_reminders(db)} reminder(s)")


async def create_platform_admin(email: str, name: str, role: str, password: str) -> None:
    async with SessionLocal() as db:
        existing = await db.scalar(select(User).where(User.email == email))
        if existing:
            existing.platform_role = role
            print(f"Existing user {email} promoted to {role}")
        else:
            db.add(
                User(
                    email=email,
                    full_name=name,
                    password_hash=hash_password(password),
                    platform_role=role,
                )
            )
            print(f"Created {role} {email}")
        await db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("send-deadline-reminders", help="Notify scouts of assignments due within 24h")
    p = sub.add_parser("create-platform-admin")
    p.add_argument("email")
    p.add_argument("name")
    p.add_argument("--role", choices=sorted(PLATFORM_ROLES), default="super_admin")
    args = parser.parse_args()

    if args.command == "send-deadline-reminders":
        asyncio.run(_send_reminders())
        return

    password = os.environ.get("SCOUTSPHERE_ADMIN_PASSWORD") or getpass.getpass("Password: ")
    if len(password) < 10:
        sys.exit("Password must be at least 10 characters")
    asyncio.run(create_platform_admin(args.email, args.name, args.role, password))


if __name__ == "__main__":
    main()
