import argparse
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Item, Role, StockTransaction, StockTxnType, Unit, User

SEED_USERS = [
    ("admin", "Administrator", "admin@123", Role.ADMIN),
    ("store", "Store Keeper", "store@123", Role.STORE),
    ("quality", "Quality Officer", "quality@123", Role.QUALITY),
    ("viewer", "Dashboard Viewer", "viewer@123", Role.VIEWER),
]

# Exact initial item rows from the client-provided DA SVARN STOCK DASHBOARD workbook.
CLIENT_ITEMS = [
    {"name": "8U", "project": "Indus", "family": "FCT", "model_no": None, "opening_inventory": Decimal("1000"), "reorder_level": Decimal("500"), "critical_level": Decimal("250")},
    {"name": "12U Old", "project": "Indus", "family": "FCT", "model_no": None, "opening_inventory": Decimal("0"), "reorder_level": Decimal("0"), "critical_level": Decimal("0")},
    {"name": "12U New", "project": "Indus", "family": "FCT", "model_no": None, "opening_inventory": Decimal("0"), "reorder_level": Decimal("0"), "critical_level": Decimal("0")},
    {"name": "VRLA", "project": "Indus", "family": "FCT", "model_no": None, "opening_inventory": Decimal("0"), "reorder_level": Decimal("0"), "critical_level": Decimal("0")},
    {"name": "23U", "project": "Indus", "family": "FCT", "model_no": None, "opening_inventory": Decimal("0"), "reorder_level": Decimal("0"), "critical_level": Decimal("0")},
    {"name": "25U", "project": "Indus", "family": "FCT", "model_no": None, "opening_inventory": Decimal("0"), "reorder_level": Decimal("0"), "critical_level": Decimal("0")},
    {"name": "35U", "project": "Indus", "family": "FCT", "model_no": "35UFCT221CX", "opening_inventory": Decimal("0"), "reorder_level": Decimal("0"), "critical_level": Decimal("0")},
    {"name": "LED 2.5W", "project": "Indus", "family": "LED", "model_no": None, "opening_inventory": Decimal("0"), "reorder_level": Decimal("0"), "critical_level": Decimal("0")},
    {"name": "FCTS6D", "project": "RELIANCE", "family": "FCTS", "model_no": None, "opening_inventory": Decimal("0"), "reorder_level": Decimal("0"), "critical_level": Decimal("0")},
    {"name": "FCTS6D", "project": "AIRTEL", "family": "FCTS", "model_no": None, "opening_inventory": Decimal("0"), "reorder_level": Decimal("0"), "critical_level": Decimal("0")},
]


def seed_users(db: Session) -> list[str]:
    created = []
    for username, full_name, password, role in SEED_USERS:
        if db.scalar(select(User.id).where(User.username == username)):
            continue
        db.add(User(username=username, full_name=full_name, hashed_password=hash_password(password), role=role))
        created.append(username)
    db.flush()
    return created


def seed_units(db: Session) -> list[str]:
    created = []
    existing = {unit.name.casefold() for unit in db.scalars(select(Unit)).all()}
    for number in range(1, 5):
        name = f"Unit-{number}"
        if name.casefold() not in existing:
            db.add(Unit(name=name, is_active=True))
            created.append(name)
    db.flush()
    return created


def seed_client_items(db: Session) -> list[str]:
    created = []
    for item_data in CLIENT_ITEMS:
        item = db.scalar(select(Item).where(
            Item.name.ilike(item_data["name"]), Item.project.ilike(item_data["project"])
        ))
        if item is None:
            # Upgrade a matching legacy item whose project was not recorded yet.
            legacy = db.scalar(select(Item).where(
                Item.name.ilike(item_data["name"]), Item.project == "General"
            ))
            if legacy is not None and item_data["project"] not in {"RELIANCE", "AIRTEL"}:
                item = legacy
                item.project = item_data["project"]
            elif legacy is not None and item_data["project"] == "RELIANCE":
                item = legacy
                item.project = item_data["project"]
        if item is None:
            item = Item(
                name=item_data["name"], project=item_data["project"], family=item_data["family"],
                model_no=item_data["model_no"], reorder_level=item_data["reorder_level"],
                critical_level=item_data["critical_level"], is_active=True,
            )
            db.add(item)
            db.flush()
            created.append(f"{item.name} ({item.project})")
        else:
            item.name = item_data["name"]
            item.project = item_data["project"]
            item.family = item_data["family"]
            item.model_no = item_data["model_no"]
            item.reorder_level = item_data["reorder_level"]
            item.critical_level = item_data["critical_level"]
            item.is_active = True
            db.flush()

        if item_data["opening_inventory"] > 0:
            has_ledger = db.scalar(select(StockTransaction.id).where(StockTransaction.item_id == item.id).limit(1))
            if has_ledger is None:
                db.add(StockTransaction(
                    item_id=item.id, type=StockTxnType.OPENING,
                    quantity=item_data["opening_inventory"], date=date.today(),
                    ref="CLIENT-ITEM-MASTER", remarks="Initial inventory from client workbook",
                ))
    db.flush()
    return created


def deactivate_non_client_items(db: Session) -> list[str]:
    approved = {(row["name"].casefold(), row["project"].casefold()) for row in CLIENT_ITEMS}
    deactivated = []
    for item in db.scalars(select(Item).where(Item.is_active.is_(True))).all():
        if (item.name.casefold(), item.project.casefold()) not in approved:
            item.is_active = False
            deactivated.append(f"{item.name} ({item.project})")
    db.flush()
    return deactivated


def seed(db: Session, *, deactivate_extras: bool = False) -> dict[str, list[str]]:
    result = {
        "users": seed_users(db),
        "units": seed_units(db),
        "items": seed_client_items(db),
        "deactivated_items": [],
    }
    if deactivate_extras:
        result["deactivated_items"] = deactivate_non_client_items(db)
    db.commit()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed user accounts and client workbook master data.")
    parser.add_argument(
        "--deactivate-non-client-items", action="store_true",
        help="Soft-deactivate active items not in the client's workbook master. History is preserved.",
    )
    args = parser.parse_args()
    with SessionLocal() as db:
        result = seed(db, deactivate_extras=args.deactivate_non_client_items)
    for key, values in result.items():
        print(f"{key}: {', '.join(values) if values else 'no changes'}")


if __name__ == "__main__":
    main()
