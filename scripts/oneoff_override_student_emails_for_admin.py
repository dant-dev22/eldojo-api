"""One-off script: asigna un email fijo (DEFAULT_STUDENT_EMAIL) a TODOS los
alumnos de las organizaciones donde el usuario admin identificado por
ADMIN_EMAIL tiene una asignación administrativa.

Uso (producción segura - dry-run por default):

  # 1) Ver qué se tocaría (SIN MODIFICAR NADA):
  python scripts/oneoff_override_student_emails_for_admin.py

  # 2) Aplicar cambios efectivamente:
  APPLY_CHANGES=1 python scripts/oneoff_override_student_emails_for_admin.py

El script:
  - Resuelve ADMIN_EMAIL (default: dantedev@gmail.com) en `users` → user_id.
  - Busca todas las organizations asociadas via `admin_assignments`.
  - Selecciona todos los `students` de esas organizations.
  - SET students.email = DEFAULT_STUDENT_EMAIL.
  - Opcionalmente, también actualiza `student_invitation_tokens.email_sent_to`
    en las invitaciones pendientes (used_at IS NULL) para que la próxima
    emisión OTP vaya al correo correcto.
  - Antes de cada cambio, imprime un resumen (dry-run) y el DETAIL de cada
    fila que se modificará.

Las variables de entorno (con defaults listos para el caso de uso actual):
  ADMIN_EMAIL              dantedev@gmail.com
  DEFAULT_STUDENT_EMAIL    dante.novoa@alumnos.udg.mx
  APPLY_CHANGES            0 | 1    (0 = dry-run, 1 = commit)
  UPDATE_PENDING_EMAIL_SENT_TO  1   (1 = también actualiza invitaciones pendientes)
"""

from __future__ import annotations

import os
import sys
from typing import Iterable

# Asegurar que el directorio raíz del proyecto esté en sys.path para
# poder importar `app.*` sin instalación via pip.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.models.student import Student  # noqa: E402
from app.models.student_invitation import StudentInvitationToken  # noqa: E402
from app.models.user import AdminAssignment, User  # noqa: E402


ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "dantedev@gmail.com").strip().lower()
DEFAULT_STUDENT_EMAIL = (
    os.getenv("DEFAULT_STUDENT_EMAIL") or "dante.novoa@alumnos.udg.mx"
).strip().lower()
APPLY_CHANGES = (os.getenv("APPLY_CHANGES") or "0").strip() in {"1", "true", "yes", "on"}
UPDATE_PENDING_EMAIL_SENT_TO = (
    os.getenv("UPDATE_PENDING_EMAIL_SENT_TO") or "1"
).strip() in {"1", "true", "yes", "on"}


def _resolve_admin_orgs(db: Session, admin_email: str) -> tuple[User | None, list[Organization]]:
    """Devuelve (admin_user, [organizations donde es admin])."""
    admin = db.scalar(select(User).where(User.email == admin_email).limit(1))
    if admin is None:
        return None, []
    org_ids: set[int] = set()
    assignments = db.scalars(
        select(AdminAssignment).where(AdminAssignment.user_id == admin.id)
    ).all()
    for a in assignments:
        if a.organization_id:
            org_ids.add(a.organization_id)
    if not org_ids:
        return admin, []
    orgs = db.scalars(
        select(Organization).where(Organization.id.in_(org_ids))
    ).all()
    return admin, list(orgs)


def _fetch_students(db: Session, org_ids: Iterable[int]) -> list[Student]:
    ids = list(org_ids)
    if not ids:
        return []
    return db.scalars(
        select(Student)
        .where(Student.organization_id.in_(ids))
        .order_by(Student.organization_id, Student.id)
    ).all()


def _fetch_pending_invitations(db: Session, student_ids: list[int]) -> list[StudentInvitationToken]:
    if not student_ids:
        return []
    return db.scalars(
        select(StudentInvitationToken).where(
            StudentInvitationToken.student_id.in_(student_ids),
            StudentInvitationToken.used_at.is_(None),
        )
    ).all()


def main() -> int:
    print("================================================================")
    print("ONE-OFF: Sobreescribir email alumnos de un admin")
    print("================================================================")
    print(f"  ADMIN_EMAIL              : {ADMIN_EMAIL}")
    print(f"  DEFAULT_STUDENT_EMAIL    : {DEFAULT_STUDENT_EMAIL}")
    print(f"  APPLY_CHANGES            : {'YES (COMMIT)' if APPLY_CHANGES else 'NO (dry-run)'}")
    print(f"  UPDATE_PENDING_EMAIL_SENT_TO : {'YES' if UPDATE_PENDING_EMAIL_SENT_TO else 'NO'}")
    print()

    with SessionLocal() as db:
        admin, orgs = _resolve_admin_orgs(db, ADMIN_EMAIL)

        if admin is None:
            print(f"[ERROR] No existe usuario con email = {ADMIN_EMAIL!r}")
            return 2

        print(f"Admin detectado  : id={admin.id}  email={admin.email}  role={admin.role.value}")
        if not orgs:
            print("[WARN] El admin no tiene ninguna organización asignada via admin_assignments.")
            return 0

        print("Organizaciones afectadas:")
        for o in orgs:
            print(f"  - org id={o.id}  slug={getattr(o, 'slug', '-')}  name={getattr(o, 'name', '-')}")
        print()

        students = _fetch_students(db, [o.id for o in orgs])
        print(f"Alumnos totales en esas organizaciones: {len(students)}")

        changed_students: list[tuple[int, str | None, str]] = []
        for s in students:
            current = (s.email or "").strip().lower()
            if current != DEFAULT_STUDENT_EMAIL:
                changed_students.append((s.id, s.email, DEFAULT_STUDENT_EMAIL))

        print(f"  Alumnos con email distinto al target: {len(changed_students)}")
        if changed_students:
            print(f"  Primeros 12 detalles (muestra):")
            for sid, old_email, new_email in changed_students[:12]:
                print(
                    f"    - student_id={sid:<6}  old={old_email!r:>40s}  ->  new={new_email!r}"
                )
            if len(changed_students) > 12:
                print(f"    ... y {len(changed_students) - 12} más.")

        pending_invitation_updates: list[tuple[int, str | None, str]] = []
        if UPDATE_PENDING_EMAIL_SENT_TO and students:
            all_student_ids = [s.id for s in students]
            invs = _fetch_pending_invitations(db, all_student_ids)
            print(f"\nInvitaciones pendientes (used_at IS NULL): {len(invs)}")
            for inv in invs:
                current = (inv.email_sent_to or "").strip().lower()
                if current != DEFAULT_STUDENT_EMAIL:
                    pending_invitation_updates.append(
                        (inv.id, inv.email_sent_to, DEFAULT_STUDENT_EMAIL)
                    )
            print(f"  Invitaciones a actualizar email_sent_to: {len(pending_invitation_updates)}")

        total_changes = len(changed_students) + len(pending_invitation_updates)
        if total_changes == 0:
            print("\n✅ No hay cambios que aplicar. Todo ya coincide.")
            return 0

        if not APPLY_CHANGES:
            print("\n================================================================")
            print("MODO DRY-RUN: no se aplicó ningún cambio a la base de datos.")
            print("Para aplicar, volver a correr con:")
            print("  APPLY_CHANGES=1 python " + os.path.basename(__file__))
            print("================================================================")
            return 0

        print("\n▶ Aplicando cambios y haciendo COMMIT ...")
        try:
            if changed_students:
                student_ids = [sid for sid, _old, _new in changed_students]
                db.execute(
                    update(Student)
                    .where(Student.id.in_(student_ids))
                    .values(email=DEFAULT_STUDENT_EMAIL)
                    .execution_options(synchronize_session=False)
                )

            if pending_invitation_updates:
                inv_ids = [iid for iid, _old, _new in pending_invitation_updates]
                db.execute(
                    update(StudentInvitationToken)
                    .where(StudentInvitationToken.id.in_(inv_ids))
                    .values(email_sent_to=DEFAULT_STUDENT_EMAIL)
                    .execution_options(synchronize_session=False)
                )

            db.commit()
        except Exception as exc:
            db.rollback()
            print(f"[FATAL] Error durante actualización (ROLLBACK): {exc}")
            return 1

        print(
            f"\n✅ COMMIT OK. Cambios aplicados:"
            f"\n   • {len(changed_students)} fila(s) en students.email"
            f"\n   • {len(pending_invitation_updates)} fila(s) en student_invitation_tokens.email_sent_to"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
