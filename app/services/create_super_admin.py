"""
Create the Super Admin user + assign the super_admin role.

Run: python -m scripts.create_super_admin
Reads: SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD env vars (or prompts).
"""
import asyncio
import getpass
import os
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.rbac import Role, UserRole
from app.models.user import User


async def main() -> None:
    email = os.getenv("SUPER_ADMIN_EMAIL") or input("Super Admin email: ").strip().lower()
    password = os.getenv("SUPER_ADMIN_PASSWORD") or getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8:
        print("✗ Password must be at least 8 characters", file=sys.stderr)
        sys.exit(1)

    first_name = input("First name: ").strip() or "Super"
    last_name = input("Last name: ").strip() or "Admin"

    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            print(f"✗ User {email} already exists", file=sys.stderr)
            sys.exit(1)

        user = User(
            email=email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            status="active",
        )
        db.add(user)
        await db.flush()

        role = (await db.execute(select(Role).where(Role.name == "super_admin"))).scalar_one_or_none()
        if role is None:
            print("✗ super_admin role missing — run `python -m scripts.seed_rbac` first", file=sys.stderr)
            sys.exit(1)

        db.add(UserRole(user_id=user.id, role_id=role.id))
        await db.commit()
        print(f"✔ Super Admin created: {email}")


if __name__ == "__main__":
    asyncio.run(main())