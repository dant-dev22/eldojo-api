r"""Script one-off: Reinicia el usuario admin de prueba (dantedev22@gmail.com)
en PROD (MySQL) eliminando alumnos/clases existentes de sus organizaciones y
creando 2 alumnos nuevos con cuenta APROBADA, datos completos y 2 clases.

BASE DE DATOS  : Compatible 100% con MySQL (usa los mismos models/enums/engine
                 del backend a traves de SessionLocal).

IMPORTANTE     : Usa SIEMPRE el Python del VIRTUALENV del proyecto, NO el
                 python3 del sistema operativo, ya que las dependencias
                 (sqlalchemy, pymysql, etc.) solo estan instaladas ahi.

========================================================================
  COMO EJECUTARLO EN UN VPS / LINUX (PROD)
========================================================================

  # 1) Entra al folder raiz del backend:
  cd /eldojo/eldojo-api
     (o donde este clonado el proyecto - adaptar el path)

  # 2) Identifica el virtualenv del proyecto. Suele ser uno de:
  ls -la | grep -E "(venv|\.venv)"
     Si NO existe, crearlo:  python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

  # 3) DRY-RUN (RECOMENDADO SIEMPRE primero - NO toca NADA en BD):
  .venv/bin/python scripts/reset_test_admin.py
        (o si el venv se llama "venv" sin punto:  venv/bin/python ...)

     Si en vez de eso te da un menu elegible, prueba a ACTIVARLO antes:
       source .venv/bin/activate
       python scripts/reset_test_admin.py

  # 4) APLICAR CAMBIOS (COMMIT real sobre MySQL):
  APPLY=1 .venv/bin/python scripts/reset_test_admin.py

========================================================================
  NOTAS SOBRE MYSQL
========================================================================
  - El script NO usa SQLite ni features Postgres. Todo via SQLAlchemy +
    SessionLocal (que en prod apunta a MySQL via DATABASE_URL).
  - Los DELETEs se ejecutan respetando orden de FKs para evitar errores
    1451 "Cannot delete or update a parent row".
  - Todos los ENUMs se persisten usando SqlEnum (los mismos que el backend).
  - rowcount se usa solo para informar; el COMMIT/ROLLBACK es atomico.
"""

from __future__ import annotations

import os
import random
import secrets
import string
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _bootstrap_or_die() -> None:
    """Valida que se este ejecutando con el interprete correcto.

    Si sqlalchemy no se puede importar, probablemente el usuario invoco
    `python3 scripts/...` del sistema y no el del virtualenv. En ese
    caso mostramos un mensaje de error UTIL y salimos sin traceback.
    """

    project_root = Path(__file__).resolve().parent.parent
    candidate_pythons: list[Path] = []
    for venv_name in (".venv", "venv"):
        if (project_root / venv_name / "bin" / "python").exists():
            candidate_pythons.append(project_root / venv_name / "bin" / "python")
        if (project_root / venv_name / "Scripts" / "python.exe").exists():
            candidate_pythons.append(project_root / venv_name / "Scripts" / "python.exe")

    try:
        import sqlalchemy  # noqa: F401
    except Exception as exc:
        sys.stderr.write("=" * 72 + "\n")
        sys.stderr.write("[ERROR DE ENTORNO] No se pudo importar 'sqlalchemy'.\n")
        sys.stderr.write("=" * 72 + "\n")
        sys.stderr.write(f"  Python que estas usando : {sys.executable}\n")
        sys.stderr.write(f"  Proyecto raiz          : {project_root}\n")
        sys.stderr.write(f"  Detalle importacion    : {type(exc).__name__}: {exc}\n\n")
        sys.stderr.write("  >>> ESTAS USANDO EL PYTHON DEL SISTEMA, NO EL DEL VIRTUALENV <<<\n\n")
        if candidate_pythons:
            sys.stderr.write("  Solucion (VPS/Linux - DRY-RUN primero):\n")
            for p in candidate_pythons:
                sys.stderr.write(f"    {p} scripts/reset_test_admin.py\n")
            sys.stderr.write("\n  Para APLICAR cambios:\n")
            for p in candidate_pythons:
                sys.stderr.write(f"    APPLY=1 {p} scripts/reset_test_admin.py\n")
        else:
            sys.stderr.write("  No encontre ningun virtualenv en el proyecto.\n")
            sys.stderr.write("  Crealo e instala las dependencias:\n")
            sys.stderr.write(f"    cd {project_root}\n")
            sys.stderr.write("    python3 -m venv .venv\n")
            sys.stderr.write("    source .venv/bin/activate\n")
            sys.stderr.write("    pip install -r requirements.txt\n\n")
            sys.stderr.write("  Luego re-ejecuta el script.\n")
        sys.stderr.write("\n")
        raise SystemExit(3)

    try:
        import pymysql  # noqa: F401
    except Exception:
        # pymysql es opcional en local (SQLite) pero avisa en prod si falta
        pass


_bootstrap_or_die()


from sqlalchemy import delete, select, update  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.core.student_codes import build_student_unique_code  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.authorized_person import AuthorizedPerson  # noqa: E402
from app.models.belts import BeltLevel, BeltStripe, StudentBeltHistory  # noqa: E402
from app.models.curriculum import Discipline  # noqa: E402
from app.models.emergency_contact import EmergencyContact  # noqa: E402
from app.models.enums import (  # noqa: E402
    AttendanceMethod,
    PaymentMethod,
    PaymentRecordStatus,
    PaymentStatus,
    StudentStatus,
    UserRole,
)
from app.models.fight_record import FightRecordType, StudentFightRecord  # noqa: E402
from app.models.finance import Payment  # noqa: E402
from app.models.medical_record import MedicalRecord  # noqa: E402
from app.models.organization import Branch, Organization  # noqa: E402
from app.models.student import Student  # noqa: E402
from app.models.student_document import StudentDocument  # noqa: E402
from app.models.student_invitation import StudentInvitationToken  # noqa: E402
from app.models.teaching import (  # noqa: E402
    Attendance,
    ClassEnrollment,
    ClassSchedule,
    MartialClass,
)
from app.models.trajectory import TrajectoryEvent  # noqa: E402
from app.models.user import AdminAssignment, User  # noqa: E402


ADMIN_EMAIL = "dantedev22@gmail.com"
APPLY = (os.getenv("APPLY") or "0").strip() in {"1", "true", "yes", "on"}
STUDENT_PASSWORD_RAW = "DojoTest2026!"

# VALORES LITERALES DE ENUM COINCIDIENDO EXACTAMENTE CON LOS DEFINIDOS EN EL ESQUEMA
# MYSQL. Usamos strings hardcodeados (no Enum.value ni nada intermedio) para
# evitar cualquier desviacion de SQLAlchemy por SQLEnum sin values_callable.
ENUM_STR = {
    "UserRole__STUDENT":             "student",
    "UserRole__ORG_ADMIN":           "org_admin",
    "PaymentStatus__UP_TO_DATE":     "up_to_date",
    "PaymentStatus__DUE_SOON":       "due_soon",
    "PaymentStatus__OVERDUE":        "overdue",
    "StudentStatus__ACTIVE":         "active",
    "StudentStatus__FROZEN":         "frozen",
    "StudentStatus__INACTIVE":       "inactive",
    "PaymentMethod__CASH":           "cash",
    "PaymentMethod__TRANSFER":       "transfer",
    "PaymentMethod__CARD":           "card",
    "PaymentMethod__OTHER":          "other",
    "PaymentRecordStatus__PAID":     "paid",
    "PaymentRecordStatus__PENDING":  "pending",
    "PaymentRecordStatus__VOID":     "void",
    "AttendanceMethod__QR":          "qr",
    "AttendanceMethod__MANUAL":      "manual",
    "FightRecordType__VICTORY":      "victoria",
    "FightRecordType__DRAW":         "empate",
    "FightRecordType__LOSS":         "derrota",
}

BELT_CATALOG: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("BJJ", [
        ("Blanca",  "#FFFFFF", "#111111"),
        ("Azul",    "#0D47A1", "#FFFFFF"),
        ("Morada",  "#6A1B9A", "#FFFFFF"),
        ("Marron",  "#5D4037", "#FFFFFF"),
        ("Negra",   "#111111", "#FFFFFF"),
    ]),
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

STUDENT_FIRST_NAMES = ["Sofia", "Mateo", "Valentina", "Diego", "Camila", "Santiago", "Luciana", "Leonardo"]
STUDENT_LAST_NAMES = ["Garcia", "Rodriguez", "Martinez", "Lopez", "Hernandez", "Perez", "Gonzalez", "Sanchez"]
RANDOM_EMAIL_DOMAINS = ["example.com", "testmail.io", "demo-edu.org", "mailtest.xyz"]


def _random_email(first_name: str, last_name: str) -> str:
    """Genera un email aleatorio que NO contenga 'dante'."""
    prefix = f"{first_name.lower()}.{last_name.lower()}"
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    domain = random.choice(RANDOM_EMAIL_DOMAINS)
    email = f"{prefix}{suffix}@{domain}"
    assert "dante" not in email, f"Generated email contains 'dante': {email}"
    return email


def _random_phone() -> str:
    return f"+52 {random.randint(33, 55)}{random.randint(10000000, 99999999)}"


def _random_dni() -> str:
    return "".join(random.choices(string.digits, k=10))


def _validate_mysql_enums(db: Session) -> None:
    """Pre-check: lee SHOW COLUMNS para las tablas con ENUM y verifica que
    los literales que vamos a escribir (ENUM_STR) coinciden con los valores
    reales del ENUM de MySQL. Si hay desviación, falla con mensaje claro
    (evita el error Data truncated 1265 en medio del INSERT).

    Solo se ejecuta cuando el dialecto es mysql/mariadb; en SQLite se salta.
    """
    import re

    from sqlalchemy import text as _sa_text

    engine = db.get_bind()
    dialect_name = getattr(getattr(engine, "dialect", None), "name", "?")
    if dialect_name not in ("mysql", "mariadb", "pymysql", "aiomysql", "mysqlconnector", "mysqldb"):
        return

    enum_checks = [
        ("student_fight_records", "record_type",   [
            ENUM_STR["FightRecordType__VICTORY"],
            ENUM_STR["FightRecordType__DRAW"],
            ENUM_STR["FightRecordType__LOSS"],
        ]),
        ("users",     "role",           [ENUM_STR["UserRole__STUDENT"]]),
        ("students",  "status",         [ENUM_STR["StudentStatus__ACTIVE"]]),
        ("students",  "payment_status", [ENUM_STR["PaymentStatus__UP_TO_DATE"]]),
        ("payments",  "method",         [ENUM_STR["PaymentMethod__TRANSFER"]]),
        ("payments",  "status",         [ENUM_STR["PaymentRecordStatus__PAID"]]),
        ("attendance","method",         [ENUM_STR["AttendanceMethod__QR"]]),
    ]

    print("  Pre-check ENUMs en MySQL (SHOW COLUMNS)...")
    problems: list[str] = []
    for table, col, required_vals in enum_checks:
        row = db.execute(_sa_text(f"SHOW COLUMNS FROM `{table}` LIKE :col"), {"col": col}).fetchone()
        if row is None:
            continue
        if isinstance(row, dict):
            type_str = str(row.get("Type") or "")
        else:
            type_str = str(row[1]) if len(row) > 1 else ""
        vset: list[str] = []
        m = re.match(r"^enum\((.*)\)$", type_str, re.IGNORECASE)
        if m:
            vset = re.findall(r"'((?:''|[^'])*)'", m.group(1))
            vset = [v.replace("''", "'") for v in vset]
        if not vset:
            continue
        missing = [v for v in required_vals if v not in vset]
        if missing:
            problems.append(
                f"  ⚠️  {table}.{col}: valores ENUM reales={vset} — FALTAN={missing}"
            )
        else:
            print(f"    ✅ {table}.{col:<15s} contiene {required_vals}")

    if problems:
        print()
        for p in problems:
            print(p)
        print("\n[ERROR] Los ENUMs del esquema MySQL NO coinciden con los literales del script.")
        print("        Esto evitara el error 'Data truncated for column ...' (MySQL 1265).")
        raise SystemExit(6)
    print()


def _fetch_admin_ctx(db: Session) -> tuple[Optional[User], list[Organization], list[Branch]]:
    admin = db.scalar(select(User).where(User.email == ADMIN_EMAIL).limit(1))
    if admin is None:
        return None, [], []
    assign_ids: set[int] = set()
    assignments = db.scalars(
        select(AdminAssignment).where(AdminAssignment.user_id == admin.id)
    ).all()
    for a in assignments:
        if a.organization_id:
            assign_ids.add(a.organization_id)
    if not assign_ids:
        return admin, [], []
    orgs = db.scalars(select(Organization).where(Organization.id.in_(assign_ids))).all()
    branches = db.scalars(select(Branch).where(Branch.organization_id.in_(assign_ids))).all()
    return admin, list(orgs), list(branches)


def _purge_org_student_data(db: Session, org_ids: list[int], branch_ids: list[int]) -> dict[str, int]:
    """Elimina (hard-delete via DELETE) TODOS los datos de alumnos y clases
    asociados a las organizaciones indicadas. Devuelve conteos.

    Para MySQL con FKs ON DELETE RESTRICT se necesita:
      1) UNLINK previo (UPDATE ... SET fk_col = NULL) de todo RESTRICT
         que apunte a tablas que vamos a borrar.
      2) Orden de DELETE: HIJAS antes que PADRES.
         Students se BORRA ANTES que classes (students.primary_class_id
         tiene FK RESTRICT hacia classes.id).
    """
    if not org_ids:
        return {}
    counts: dict[str, int] = {}

    student_ids_stmt = select(Student.id).where(Student.organization_id.in_(org_ids))
    student_ids = list(db.scalars(student_ids_stmt).all())

    user_ids_stmt = select(Student.user_id).where(
        Student.organization_id.in_(org_ids), Student.user_id.isnot(None)
    )
    user_ids = [uid for uid in db.scalars(user_ids_stmt).all() if uid is not None]

    class_ids_stmt = select(MartialClass.id).where(MartialClass.organization_id.in_(org_ids))
    class_ids = list(db.scalars(class_ids_stmt).all())

    if student_ids:
        _UNLINKS = [
            (
                "unlink students.primary_class/current_belt/stripe/user",
                update(Student)
                .where(Student.id.in_(student_ids))
                .values(
                    primary_class_id=None,
                    current_belt_level_id=None,
                    current_stripe_id=None,
                    user_id=None,
                ),
            ),
            (
                "unlink student_belt_histories.awarded_by_user",
                update(StudentBeltHistory)
                .where(StudentBeltHistory.student_id.in_(student_ids))
                .values(awarded_by_user_id=None),
            ),
            (
                "unlink trajectory_events.created_by_user",
                update(TrajectoryEvent)
                .where(TrajectoryEvent.student_id.in_(student_ids))
                .values(created_by_user_id=None),
            ),
            (
                "unlink authorized_persons.dni_verified_by_user",
                update(AuthorizedPerson)
                .where(AuthorizedPerson.student_id.in_(student_ids))
                .values(dni_verified_by_user_id=None),
            ),
            (
                "unlink student_invitation_tokens.user/admin",
                update(StudentInvitationToken)
                .where(StudentInvitationToken.student_id.in_(student_ids))
                .values(user_id=None, created_by_admin_id=None),
            ),
            (
                "unlink attendance.registered_by",
                update(Attendance)
                .where(Attendance.student_id.in_(student_ids))
                .values(registered_by=None),
            ),
        ]
    else:
        _UNLINKS = []

    for name, stmt in _UNLINKS:
        result = db.execute(stmt)
        counts[name] = int(getattr(result, "rowcount", 0) or 0)

    # NOTA: payments.recorded_by es NOT NULL + FK users.id ON DELETE RESTRICT.
    # No podemos nulificarlo, pero borramos payments ENTERAMENTE ANTES que los
    # rows en users (ver orden _DELETES), así que la FK nunca se viola.

    _DELETES = [
        ("student_fight_records", delete(StudentFightRecord).where(StudentFightRecord.student_id.in_(student_ids)) if student_ids else None),
        ("trajectory_events", delete(TrajectoryEvent).where(TrajectoryEvent.student_id.in_(student_ids)) if student_ids else None),
        ("student_belt_histories", delete(StudentBeltHistory).where(StudentBeltHistory.student_id.in_(student_ids)) if student_ids else None),
        ("student_documents", delete(StudentDocument).where(StudentDocument.student_id.in_(student_ids)) if student_ids else None),
        ("authorized_persons", delete(AuthorizedPerson).where(AuthorizedPerson.student_id.in_(student_ids)) if student_ids else None),
        ("medical_records", delete(MedicalRecord).where(MedicalRecord.student_id.in_(student_ids)) if student_ids else None),
        ("emergency_contacts", delete(EmergencyContact).where(EmergencyContact.student_id.in_(student_ids)) if student_ids else None),
        ("student_invitation_tokens", delete(StudentInvitationToken).where(StudentInvitationToken.student_id.in_(student_ids)) if student_ids else None),
        ("attendance", delete(Attendance).where(Attendance.student_id.in_(student_ids)) if student_ids else None),
        ("payments", delete(Payment).where(Payment.organization_id.in_(org_ids))),
        ("class_enrollments", delete(ClassEnrollment).where(ClassEnrollment.student_id.in_(student_ids)) if student_ids else None),
        ("students", delete(Student).where(Student.organization_id.in_(org_ids))),
        ("class_schedules", delete(ClassSchedule).where(ClassSchedule.class_id.in_(class_ids)) if class_ids else None),
        ("classes", delete(MartialClass).where(MartialClass.organization_id.in_(org_ids))),
    ]

    if user_ids:
        _DELETES.append(("users", delete(User).where(User.id.in_(user_ids), User.role == ENUM_STR["UserRole__STUDENT"])))

    for name, stmt in _DELETES:
        if stmt is None:
            counts[name] = 0
            continue
        result = db.execute(stmt)
        counts[name] = int(getattr(result, "rowcount", 0) or 0)

    return counts


def _ensure_disciplines_and_belts(db: Session, org: Organization) -> dict[str, Discipline]:
    """Asegura 3 disciplinas y, si la ORG NO TIENE NINGUN belt_level, crea
    un catalogo inicial de 5 niveles (BJJ) con 4 stripes cada uno.

    NOTA sobre UNIQUE(organization_id, name): NO se puede crear un "Blanca"
    para BJJ y otro "Blanca" para JUDO en la misma ORG. Por eso, si ya
    existen belt_levels en la org, SKIP de creacion (el catalogo ya
    existia con convenciones de nombres desconocidas).
    """
    disc_map: dict[str, Discipline] = {}
    for dname in ["MMA", "BJJ", "JUDO"]:
        d = db.scalar(
            select(Discipline).where(
                Discipline.organization_id == org.id, Discipline.name == dname
            )
        )
        if d is None:
            d = Discipline(organization_id=org.id, name=dname, is_active=True)
            db.add(d)
            db.flush()
        disc_map[dname] = d

    any_belt = db.scalar(select(BeltLevel.id).where(BeltLevel.organization_id == org.id))
    if any_belt is None:
        disc = disc_map.get("BJJ") or list(disc_map.values())[0]
        specs = BELT_CATALOG[0][1]
        for idx, (name, color_hex, text_color_hex) in enumerate(specs, start=1):
            belt = BeltLevel(
                organization_id=org.id,
                name=name,
                display_name=f"{disc.name} - Cinta {name}",
                color_hex=color_hex,
                text_color_hex=text_color_hex,
                order_index=idx,
                is_active=True,
            )
            db.add(belt)
            db.flush()
            for s in range(1, 5):
                db.add(
                    BeltStripe(
                        belt_level_id=belt.id,
                        name=f"Punteo {s}",
                        display_name=f"{name} - Punteo {s}",
                        color_hex=color_hex,
                        order_index=s,
                        is_active=True,
                    )
                )
    db.flush()
    return disc_map


def _create_two_classes(db: Session, org: Organization, branch: Branch, disc_map: dict[str, Discipline]) -> list[MartialClass]:
    created: list[MartialClass] = []

    class_specs = [
        {
            "name": "MMA - Clase General (Tarde)",
            "discipline": "MMA",
            "instructor": "Prof. Carlos Reyes",
            "capacity": 20,
            "description": "Clase integral de MMA para todos los niveles. Técnicas de striking, grappling y defensa personal.",
            "schedules": [
                (1, time(18, 0), time(19, 30)),
                (3, time(18, 0), time(19, 30)),
                (5, time(18, 0), time(19, 30)),
            ],
        },
        {
            "name": "BJJ - Fundamentos (Mañana)",
            "discipline": "BJJ",
            "instructor": "Prof. Ana Torres",
            "capacity": 15,
            "description": "Clase enfocada en fundamentos de Jiu-Jitsu Brasileño. Ideal para principiantes y perfeccionamiento técnico.",
            "schedules": [
                (2, time(9, 0), time(10, 30)),
                (4, time(9, 0), time(10, 30)),
                (6, time(10, 0), time(11, 30)),
            ],
        },
    ]

    for spec in class_specs:
        disc = disc_map[spec["discipline"]]
        cls = MartialClass(
            organization_id=org.id,
            branch_id=branch.id,
            discipline_id=disc.id,
            name=spec["name"],
            description=spec["description"],
            instructor_name=spec["instructor"],
            capacity=spec["capacity"],
            is_active=True,
        )
        db.add(cls)
        db.flush()
        for dow, st, et in spec["schedules"]:
            db.add(
                ClassSchedule(
                    class_id=cls.id,
                    day_of_week=dow,
                    start_time=st,
                    end_time=et,
                )
            )
        created.append(cls)
    db.flush()
    return created


def _create_one_student(
    db: Session,
    *,
    org: Organization,
    branch: Branch,
    admin: User,
    index: int,
    classes: list[MartialClass],
    belt_white_id: int,
    belt_blue_id: int,
    stripe_2_id: int | None,
) -> tuple[User, Student]:
    random.seed(f"seed-{admin.id}-{org.id}-{index}-{date.today().isoformat()}")

    first_name = STUDENT_FIRST_NAMES[index % len(STUDENT_FIRST_NAMES)]
    last_name = f"{STUDENT_LAST_NAMES[(index * 2) % len(STUDENT_LAST_NAMES)]} {STUDENT_LAST_NAMES[(index * 3 + 1) % len(STUDENT_LAST_NAMES)]}"
    email = _random_email(first_name, last_name.split(" ")[0])
    phone = _random_phone()

    birth_dt = date(2000 - index * 3, 5 + index, 10 + index * 2)
    enroll_dt = date.today() - timedelta(days=120 - index * 10)
    next_pay_dt = date.today() + timedelta(days=20)
    height = 165 + index * 5
    is_minor = index == 1

    user = User(
        first_name=first_name,
        last_name=last_name.split(" ")[0],
        email=email,
        password_hash=hash_password(STUDENT_PASSWORD_RAW),
        role=ENUM_STR["UserRole__STUDENT"],
        is_active=True,
        email_verified_at=datetime.now(tz=timezone.utc).replace(tzinfo=None),
        first_time=False,
        last_login_at=(datetime.now(tz=timezone.utc) - timedelta(days=index + 1)).replace(tzinfo=None),
    )
    db.add(user)
    db.flush()

    student = Student(
        organization_id=org.id,
        branch_id=branch.id,
        unique_code=build_student_unique_code(db, org),
        user_id=user.id,
        first_name=first_name,
        last_name=last_name,
        birth_date=birth_dt,
        birth_place="Ciudad de Mexico, CDMX",
        height_cm=height,
        photo_url=None,
        enrollment_date=enroll_dt,
        primary_class_id=classes[index % len(classes)].id,
        monthly_fee=Decimal("1500.00"),
        currency="MXN",
        next_payment_date=next_pay_dt,
        payment_status=ENUM_STR["PaymentStatus__UP_TO_DATE"],
        status=ENUM_STR["StudentStatus__ACTIVE"],
        current_belt_level_id=belt_blue_id if index == 0 else belt_white_id,
        current_stripe_id=stripe_2_id if index == 0 else None,
        guardian_name="Maria de los Angeles Ruiz" if is_minor else None,
        guardian_phone=_random_phone() if is_minor else None,
        phone=phone,
        email=email,
        is_minor=is_minor,
        notes=f"Alumno de prueba #{index + 1}. Cuenta APROBADA creada via script reset_test_admin. Perfil completo para QA.",
        rd_victorias=2 + index,
        rd_empates=1,
        rd_derrotas=index,
    )
    db.add(student)
    db.flush()

    for cls in classes:
        db.add(
            ClassEnrollment(
                student_id=student.id,
                class_id=cls.id,
                enrolled_at=datetime.combine(enroll_dt, time(10, 0)),
                is_active=True,
            )
        )

    for month_offset in range(2):
        period_start = (date.today().replace(day=1) - timedelta(days=month_offset * 30)).replace(day=1)
        period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        db.add(
            Payment(
                student_id=student.id,
                organization_id=org.id,
                branch_id=branch.id,
                amount=Decimal("1500.00"),
                currency="MXN",
                period_start=period_start,
                period_end=period_end,
                paid_at=datetime.combine(period_start, time(9, 30)) + timedelta(days=2),
                method=ENUM_STR["PaymentMethod__TRANSFER"],
                status=ENUM_STR["PaymentRecordStatus__PAID"],
                recorded_by=admin.id,
                notes="Pago mensual - Colegiatura regular",
            )
        )

    for day_off in [1, 3, 7, 14]:
        at_class = classes[day_off % len(classes)]
        db.add(
            Attendance(
                student_id=student.id,
                class_id=at_class.id,
                branch_id=branch.id,
                check_in_at=datetime.now() - timedelta(days=day_off, hours=2),
                method=ENUM_STR["AttendanceMethod__QR"],
                registered_by=admin.id,
            )
        )

    belt_level_for_hist = belt_blue_id if index == 0 else belt_white_id
    stripe_for_hist = stripe_2_id if index == 0 else None
    db.add(
        StudentBeltHistory(
            student_id=student.id,
            belt_level_id=belt_level_for_hist,
            stripe_id=stripe_for_hist,
            awarded_at=enroll_dt + timedelta(days=60),
            awarded_by_user_id=admin.id,
            notes="Examen de graduación - Promoción aplicada por comité técnico.",
        )
    )

    db.add(
        EmergencyContact(
            student_id=student.id,
            organization_id=org.id,
            full_name=f"Patricia {last_name.split(' ')[0]}",
            relationship="Madre" if is_minor else "Hermana",
            phone=_random_phone(),
            secondary_phone=_random_phone(),
            email=_random_email("paty", last_name.split(" ")[0]),
            priority=1,
            notes="Llamar primero en caso de emergencia médica.",
        )
    )

    db.add(
        MedicalRecord(
            student_id=student.id,
            organization_id=org.id,
            blood_type="O+" if index == 0 else "A-",
            allergies="Penicilina" if index == 1 else None,
            previous_injuries="Esguince tobillo izquierdo (2024) - Recuperado completamente." if index == 0 else None,
            insurance_type="private",
            insurance_provider="AXA Salud" if index == 0 else "Seguro Popular",
            insurance_policy_number=f"POL-{random.randint(100000, 999999)}",
            chronic_conditions=None,
            medications=None,
            physician_name="Dr. Fernando Mendoza",
            physician_phone=_random_phone(),
            tetanus_vaccine_date=date.today() - timedelta(days=365 * 2),
            additional_notes="Apto para actividad física intensa. Sin restricciones.",
        )
    )

    if is_minor:
        db.add(
            AuthorizedPerson(
                student_id=student.id,
                organization_id=org.id,
                full_name=f"Jose Alberto {last_name.split(' ')[0]}",
                relationship="Padre",
                dni_type="INE",
                dni_number=_random_dni(),
                dni_verified=True,
                dni_verified_by_user_id=admin.id,
                dni_photo_url=None,
                phone=_random_phone(),
                secondary_phone=_random_phone(),
                photo_url=None,
                authorization_notes="Autoriza retiro del alumno en cualquier horario de clases.",
                is_active=True,
            )
        )

    docs = [
        ("liability_waiver", "Carta Responsiva firmada", f"{first_name}_{last_name.split(' ')[0]}_responsiva.pdf"),
        ("photo_consent", "Consentimiento de Imagen", f"{first_name}_consentimiento_imagen.pdf"),
    ]
    for dtype, title, fname in docs:
        db.add(
            StudentDocument(
                student_id=student.id,
                organization_id=org.id,
                document_type=dtype,
                title=title,
                file_url=f"https://cdn.eldojo.tech/docs/{secrets.token_hex(8)}/{fname}",
                file_name=fname,
                file_size_bytes=random.randint(80000, 450000),
                signed_at=enroll_dt,
                signed_by_full_name=f"Patricia {last_name.split(' ')[0]}",
                witness_name=admin.first_name + " " + (admin.last_name or ""),
                notes="Documento verificado y archivado digitalmente.",
            )
        )

    trajectory_events = [
        (enroll_dt, f"Inscripción oficial en {classes[index % len(classes)].name}. ¡Bienvenido al Dojo!"),
        (enroll_dt + timedelta(days=10), "Primera clase completa. Excelente desempeño en técnicas básicas."),
        (enroll_dt + timedelta(days=60), "Graduación: promoción de cinta. ¡Sigue avanzando!"),
    ]
    for ev_date, content in trajectory_events:
        db.add(
            TrajectoryEvent(
                student_id=student.id,
                organization_id=org.id,
                event_date=ev_date,
                content=content,
                created_by_user_id=admin.id,
            )
        )

    fight_data = [
        (ENUM_STR["FightRecordType__VICTORY"], "Rival Prueba A", enroll_dt + timedelta(days=45)),
        (ENUM_STR["FightRecordType__DRAW"],    "Rival Prueba B", enroll_dt + timedelta(days=75)),
        (ENUM_STR["FightRecordType__LOSS"],    "Rival Prueba C", enroll_dt + timedelta(days=95)),
    ]
    from sqlalchemy import text as _sa_text

    for rtype, opp, fdate in fight_data:
        db.execute(
            _sa_text(
                """
                INSERT INTO student_fight_records
                    (student_id, record_type, opponent_name, fight_date, deleted_at,
                     created_at, updated_at)
                VALUES
                    (:sid, :rtype, :opp, :fdate, NULL, NOW(), NOW())
                """
            ),
            {"sid": student.id, "rtype": rtype, "opp": opp, "fdate": fdate},
        )

    db.flush()
    return user, student


def _banner(title: str) -> None:
    sep = "=" * 72
    print(f"\n{sep}\n  {title}\n{sep}")


def main() -> int:
    print()
    print(r"  ______ _     _____       _       _____               _             _           ")
    print(r" |  ____| |   |  __ \     (_)     |_   _|        /\   | |           (_)          ")
    print(r" | |__  | |   | |  | | ___ _  ___   | |  _ __   /  \  | |_ ___  _ __ _ _ __ ___  ")
    print(r" |  __| | |   | |  | |/ _ \ |/ _ \  | | | '_ \ / /\ \ | __/ _ \| '__| | '_ ` _ \ ")
    print(r" | |____| |___| |__| |  __/ | (_) || |_| | | / ____ \| || (_) | |  | | | | | | |")
    print(r" |______|_____|_____/ \___|_|\___/_____|_| |_/_/    \_\\__\___/|_|  |_|_| |_| |_|")
    print()
    print(f"  MODO          :  {'APLICAR CAMBIOS (COMMIT)' if APPLY else 'DRY-RUN (sin cambios)'}")
    print(f"  ADMIN EMAIL   :  {ADMIN_EMAIL}")
    print(f"  STUDENT PASS  :  {STUDENT_PASSWORD_RAW}")
    print()

    with SessionLocal() as db:
        try:
            from sqlalchemy import text as _sa_text
            diag = db.execute(_sa_text("SELECT 1")).scalar()
            engine = db.get_bind()
            dialect_name = getattr(engine, "dialect", None)
            dialect_name = getattr(dialect_name, "name", "?") if dialect_name else "?"
            db_url_censored = (
                str(engine.url).replace(":" + str(engine.url.password or "") + "@", ":***@")
                if getattr(engine, "url", None) is not None else "?"
            )
            print(f"  DB Dialecto   :  {dialect_name}  (SELECT 1 = {diag})")
            print(f"  DB URL        :  {db_url_censored}")
            if dialect_name not in ("mysql", "mariadb", "pymysql", "aiomysql", "mysqlconnector", "mysqldb"):
                print(f"\n  ⚠️  ADVERTENCIA: El dialecto detectado es {dialect_name!r},"
                      f" no se parece a MySQL.\n"
                      f"     Si estas en PROD y la conexion NO apunta a MySQL,"
                      f" CANCELA con Ctrl+C ahora mismo.")
            print()
        except Exception as exc:
            print(f"[FATAL] No se pudo hacer SELECT 1 contra la BD. Revisa DATABASE_URL.")
            print(f"       Detalle : {type(exc).__name__}: {exc}")
            return 4

        # Pre-check ENUMs MySQL: SI HAY DESVIACIÓN SE SALE AQUÍ,
        # NO HASTA MEDIO INSERT (evita MySQL 1265 Data truncated).
        _validate_mysql_enums(db)

        admin, orgs, branches = _fetch_admin_ctx(db)
        if admin is None:
            print(f"[FATAL] No existe usuario admin con email={ADMIN_EMAIL!r}")
            return 2
        if not orgs:
            print(f"[WARN] El admin {admin.email} no tiene organizaciones asignadas.")
            return 0

        _banner("CONTEXTO DETECTADO")
        print(f"  Admin   : id={admin.id}  email={admin.email}  role={admin.role.value}")
        print(f"  Nombre  : {admin.first_name or '-'} {admin.last_name or '-'}")
        print()
        for org in orgs:
            print(f"  Organizacion: id={org.id}  slug={org.slug}  name={org.name}")
        print()
        for br in branches:
            print(f"  Sucursal    : id={br.id}  org={br.organization_id}  name={br.name}  [{br.timezone}]")

        org_ids = [o.id for o in orgs]
        branch_ids = [b.id for b in branches]

        _banner("PURGA DE DATOS EXISTENTES (alumnos + clases + relaciones)")
        purge_counts = _purge_org_student_data(db, org_ids, branch_ids)
        total_purged = sum(purge_counts.values())
        for k, v in purge_counts.items():
            print(f"  - {k:<30s}: {v:>6d} fila(s)")
        print(f"  {'TOTAL FILAS A ELIMINAR':<30s}: {total_purged:>6d}")

        if not APPLY:
            print("\n[DRY-RUN] Cancelando transaccion - no se aplicó ningún cambio.")
            db.rollback()
            print("\nPara APLICAR los cambios, volver a correr con:  APPLY=1 python scripts/reset_test_admin.py")
            return 0

        target_org = orgs[0]
        target_branch = branches[0] if branches else None
        if target_branch is None:
            target_branch = Branch(
                organization_id=target_org.id,
                name="Matriz",
                country="Mexico",
                state="CDMX",
                city="Ciudad de Mexico",
                address="Av. Reforma 123, Col. Centro",
                timezone="America/Mexico_City",
                qr_secret=secrets.token_hex(16),
                is_active=True,
            )
            db.add(target_branch)
            db.flush()
            print(f"\n  -> Sucursal 'Matriz' creada (id={target_branch.id})")

        _banner("ASEGURANDO DISCIPLINAS Y CATALOGO DE CINTURONES")
        disc_map = _ensure_disciplines_and_belts(db, target_org)
        for dn, d in disc_map.items():
            print(f"  - Disciplina {dn:<4s} -> id={d.id}")

        _banner("CREANDO 2 CLASES CON HORARIOS")
        new_classes = _create_two_classes(db, target_org, target_branch, disc_map)
        for c in new_classes:
            scheds = db.scalars(select(ClassSchedule).where(ClassSchedule.class_id == c.id)).all()
            print(f"  - Clase id={c.id}  {c.name}")
            print(f"       Instructor : {c.instructor_name}  |  Capacidad: {c.capacity}")
            print(f"       Horarios   : {len(scheds)} sesiones/semana")

        belts_org: list[BeltLevel] = db.scalars(
            select(BeltLevel)
            .where(BeltLevel.organization_id == target_org.id, BeltLevel.is_active.is_(True))
            .order_by(BeltLevel.order_index, BeltLevel.id)
        ).all()
        if not belts_org:
            print("[FATAL] La organizacion no tiene ningun BeltLevel activo.")
            db.rollback()
            return 5

        # Filtrar cintas infantiles si hay cintas adulto disponibles — las pruebas
        # son con alumnos adultos (1 alumna de 26, 1 menor). Asi belt_white no
        # termina siendo 'Blanca (Infantil)' cuando existe 'Blanca' adulto.
        belts_adult = [b for b in belts_org if "infantil" not in (b.name or "").lower()]
        belts_select = belts_adult or belts_org

        if len(belts_select) == 1:
            belt_white = belts_select[0]
            belt_blue  = belts_select[0]
        else:
            belt_white = belts_select[0]
            belt_blue  = belts_select[1]

        stripe_2: BeltStripe | None = db.scalars(
            select(BeltStripe).where(
                BeltStripe.belt_level_id == belt_blue.id,
                BeltStripe.is_active.is_(True),
            ).order_by(BeltStripe.order_index)
        ).first()
        if stripe_2 is None:
            stripe_2 = db.scalars(
                select(BeltStripe).where(
                    BeltStripe.belt_level_id == belt_white.id,
                    BeltStripe.is_active.is_(True),
                ).order_by(BeltStripe.order_index)
            ).first()

        print(f"  Catalogo de cinturones disponibles: {len(belts_org)} "
              f"({len(belts_select)} despues de filtrar infantil)")
        for idx_b, b in enumerate(belts_select[:6]):
            print(f"    #{idx_b + 1} order={b.order_index}  id={b.id}  name={b.name!r}  display={b.display_name}")
        if len(belts_select) > 6:
            print(f"    ... y {len(belts_select) - 6} más.")
        print(f"  Cinta 'inicial' (para alumno 2): id={belt_white.id}  {belt_white.display_name}")
        print(f"  Cinta 'avanzada'(para alumno 1): id={belt_blue.id}   {belt_blue.display_name}")
        if stripe_2:
            print(f"  Stripe asignado (punteo avanzado): id={stripe_2.id}  {stripe_2.display_name}")

        _banner("CREANDO 2 ALUMNOS CON CUENTA APROBADA Y DATOS COMPLETOS")
        created_students: list[tuple[User, Student]] = []
        for idx in range(2):
            u, s = _create_one_student(
                db,
                org=target_org,
                branch=target_branch,
                admin=admin,
                index=idx,
                classes=new_classes,
                belt_white_id=belt_white.id,
                belt_blue_id=belt_blue.id,
                stripe_2_id=stripe_2.id if stripe_2 else None,
            )
            created_students.append((u, s))
            belt_cur = next((b for b in belts_org if b.id == s.current_belt_level_id), None)
            print(f"  --- Alumno #{idx + 1} ---")
            print(f"      User id     : {u.id}")
            print(f"      Student id  : {s.id}")
            print(f"      Nombre      : {s.first_name} {s.last_name}")
            print(f"      Email       : {u.email}")
            print(f"      Password    : {STUDENT_PASSWORD_RAW}")
            print(f"      Unique Code : {s.unique_code}")
            print(f"      Cinta actual: {belt_cur.display_name if belt_cur else '-'}")
            print(f"      Fecha nac.  : {s.birth_date.isoformat()}  (menor={s.is_minor})")
            print(f"      Mensualidad : ${s.monthly_fee} {s.currency}  |  Prox. pago: {s.next_payment_date}")
            print(f"      Estado pago : {s.payment_status}  |  Status alumno: {s.status}")
            print(f"      Clase prim. : {next((c.name for c in new_classes if c.id == s.primary_class_id), '-')}")
            print(f"      Record RD   : {s.rd_victorias}V / {s.rd_empates}E / {s.rd_derrotas}D")
            print()

        print("  -> COMMIT ...")
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            print(f"[FATAL] Error durante COMMIT - ROLLBACK ejecutado: {exc}")
            return 1

        _banner("✅ REINICIO COMPLETADO EXITOSAMENTE")
        print(f"  Organizacion : {target_org.name} (slug={target_org.slug})  id={target_org.id}")
        print(f"  Sucursal     : {target_branch.name}  id={target_branch.id}")
        print(f"  Disciplinas  : {sorted(disc_map.keys())}")
        print(f"  Clases       : {len(new_classes)}")
        print(f"  Alumnos      : {len(created_students)} (todos APROBADOS, ACTIVOS, email verificado)")
        print(f"  Credenciales :")
        for u, s in created_students:
            print(f"    • {u.email} / {STUDENT_PASSWORD_RAW}   (code={s.unique_code})")
        print(f"\n  Script ejecutado el : {datetime.now().isoformat(timespec='seconds')}")
        print(f"  ADMIN dueño         : {admin.email}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
