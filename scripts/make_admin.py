"""
Give (or remove) admin access to an existing account.

Usage, from the backend folder:
    python3 scripts/make_admin.py you@example.com          # make admin
    python3 scripts/make_admin.py you@example.com --remove # remove admin

The account must already exist (sign up in the app first).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from db.session import AsyncSessionLocal  # noqa: E402
from app.users.models import User  # noqa: E402
import app.conversations.models  # noqa: E402,F401
import app.documents.models  # noqa: E402,F401


async def main(email: str, remove: bool) -> int:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email.lower().strip()))).scalar_one_or_none()
        if user is None:
            print(f"No account found for {email}. Sign up in the app first.")
            return 1
        user.is_admin = not remove
        await db.commit()
        print(f"{email} is {'no longer an admin' if remove else 'now an admin'}.")
        return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(asyncio.run(main(sys.argv[1], "--remove" in sys.argv)))
