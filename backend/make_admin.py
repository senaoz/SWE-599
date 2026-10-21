"""Grant or revoke admin rights: python -m backend.make_admin <email> [--revoke]"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from backend.database import SessionLocal, init_db
from backend.models import User


async def main(email: str, revoke: bool) -> int:
    await init_db()
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"No user with email {email}; register the account first.", file=sys.stderr)
            return 1
        user.is_admin = not revoke
        await db.commit()
    print(f"{email}: is_admin={not revoke}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("--revoke", action="store_true")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.email, args.revoke)))
