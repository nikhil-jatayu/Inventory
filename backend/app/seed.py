from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Role, User

SEED_USERS = [
    ("admin", "Administrator", "admin@123", Role.ADMIN),
    ("store", "Store Keeper", "store@123", Role.STORE),
    ("quality", "Quality Officer", "quality@123", Role.QUALITY),
    ("viewer", "Dashboard Viewer", "viewer@123", Role.VIEWER),
]


def seed(db: Session) -> list[str]:
    created = []
    for username, full_name, password, role in SEED_USERS:
        if db.scalar(select(User.id).where(User.username == username)):
            continue
        db.add(
            User(
                username=username,
                full_name=full_name,
                hashed_password=hash_password(password),
                role=role,
            )
        )
        created.append(username)
    db.commit()
    return created


def main() -> None:
    with SessionLocal() as db:
        created = seed(db)
    if created:
        print(f"Created users: {', '.join(created)}")
    else:
        print("Seed users already exist")


if __name__ == "__main__":
    main()
