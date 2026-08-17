"""Carga datos semilla minimos para el entorno local (backend-api).

Idempotente: no sobreescribe datos si ya existen con el mismo slug/email.
Ejecutar:
    .venv\\Scripts\\python.exe scripts\\seed.py
"""
from __future__ import annotations

import hashlib
from datetime import date

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.curriculum import Discipline
from app.models.organization import Branch, Organization
from app.models.user import AdminAssignment, User
from app.models.belts import BeltLevel, BeltStripe
from app.models.enums import UserRole


ADMIN_EMAIL = "dantedev22@gmail.com"
ADMIN_PASSWORD = "d4nt3r4d"
ORG_SLUG = "ELD"


BELT_CATALOG = [
    # BJJ
    ("BJJ", [
        ("Blanca",  "#FFFFFF", "#111111"),
        ("Azul",    "#0D47A1", "#FFFFFF"),
        ("Morada",  "#6A1B9A", "#FFFFFF"),
        ("Marron",  "#5D4037", "#FFFFFF"),
        ("Negra",   "#111111", "#FFFFFF"),
    ]),
    # Judo
    ("JUDO", [
        ("Blanca",  "#FFFFFF", "#111111"),
        ("Amarilla","#F9A825", "#111111"),
        ("Naranja", "#EF6C00", "#FFFFFF"),
        ("Verde",   "#2E7D32", "#FFFFFF"),
        ("Azul",    "#0D47A1", "#FFFFFF"),
        ("Marron",  "#5D4037", "#FFFFFF"),
        ("Negra",   "#111111", "#FFFFFF"),
    ]),
]


def build_demo_password_hash(raw_password: str) -> str:
    """Hash simple de ejemplo (SHA-256). No usar en produccion."""
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


def ensure_belts_for_discipline(session, organization_id: int, discipline_name: str, belt_specs: list[tuple[str, str, str]]) -> None:
    existing_count = session.scalar(
        select(BeltLevel.id).where(BeltLevel.organization_id == organization_id)
    )
    if existing_count is not None:
        return
    disc = session.scalar(
        select(Discipline).where(
            Discipline.organization_id == organization_id,
            Discipline.name == discipline_name,
        )
    )
    if disc is None:
        return
    for idx, (name, color_hex, text_color_hex) in enumerate(belt_specs, start=1):
        belt = BeltLevel(
            organization_id=organization_id,
            name=name,
            display_name=f"{disc.name} - Cinta {name}",
            color_hex=color_hex,
            text_color_hex=text_color_hex,
            order_index=idx,
            is_active=True,
        )
        session.add(belt)
        session.flush()
        for s in range(1, 5):
            session.add(
                BeltStripe(
                    belt_level_id=belt.id,
                    name=f"Punteo {s}",
                    display_name=f"{name} - Punteo {s}",
                    color_hex=color_hex,
                    order_index=s,
                    is_active=True,
                )
            )


def run_seed() -> None:
    with SessionLocal() as session:
        organization = session.scalar(
            select(Organization).where(Organization.slug == ORG_SLUG)
        )
        if organization is None:
            organization = Organization(
                name="El Dojo",
                slug=ORG_SLUG,
                is_active=True,
            )
            session.add(organization)
            session.flush()

        branch = session.scalar(
            select(Branch).where(
                Branch.organization_id == organization.id,
                Branch.name == "Matriz",
            )
        )
        if branch is None:
            branch = Branch(
                organization_id=organization.id,
                name="Matriz",
                country="Mexico",
                state="CDMX",
                city="Ciudad de Mexico",
                address="Av. Principal 123",
                timezone="America/Mexico_City",
                qr_secret="seed-secret-matriz",
                is_active=True,
            )
            session.add(branch)
            session.flush()

        discipline_by_name: dict[str, Discipline] = {}
        for discipline_name in ["MMA", "BJJ", "JUDO"]:
            discipline = session.scalar(
                select(Discipline).where(
                    Discipline.organization_id == organization.id,
                    Discipline.name == discipline_name,
                )
            )
            if discipline is None:
                discipline = Discipline(
                    organization_id=organization.id,
                    name=discipline_name,
                    is_active=True,
                )
                session.add(discipline)
                session.flush()
            discipline_by_name[discipline_name] = discipline

        for d_name, specs in BELT_CATALOG:
            ensure_belts_for_discipline(session, organization.id, d_name, specs)

        user = session.scalar(select(User).where(User.email == ADMIN_EMAIL))
        if user is None:
            user = User(
                first_name="Dante",
                last_name="Dev",
                email=ADMIN_EMAIL,
                password_hash=build_demo_password_hash(ADMIN_PASSWORD),
                role=UserRole.ORG_ADMIN,
                is_active=True,
            )
            session.add(user)
            session.flush()
        else:
            if not user.first_name:
                user.first_name = "Dante"
            if not user.last_name:
                user.last_name = "Dev"

        assignment = session.scalar(
            select(AdminAssignment).where(
                AdminAssignment.user_id == user.id,
                AdminAssignment.organization_id == organization.id,
            )
        )
        if assignment is None:
            session.add(
                AdminAssignment(
                    user_id=user.id,
                    organization_id=organization.id,
                    branch_id=None,
                )
            )

        session.commit()

    print("=== SEED OK (backend-api) ===")
    print(f"Organizacion : {organization.name} ({organization.slug}) id={organization.id}")
    print(f"Sucursal     : {branch.name} [{branch.timezone}] id={branch.id}")
    print(f"Disciplinas  : {sorted(discipline_by_name.keys())}")
    print(f"Admin        : {ADMIN_EMAIL} id={user.id} role=org_admin")
    print(f"Password     : {ADMIN_PASSWORD}  (SHA-256 demo, reemplazar en prod)")
    print(f"Fecha        : {date.today().isoformat()}")


if __name__ == "__main__":
    run_seed()
