"""Fixtures compartidos para los tests del backend."""

from __future__ import annotations

from collections.abc import Generator
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.academy_pending_session import AcademyPendingSession  # noqa: F401 (importa tablas)
from app.models.authorized_person import AuthorizedPerson  # noqa: F401
from app.models.belts import BeltLevel, BeltStripe, StudentBeltHistory  # noqa: F401
from app.models.curriculum import Discipline
from app.models.email_verification import EmailVerificationToken  # noqa: F401
from app.models.emergency_contact import EmergencyContact  # noqa: F401
from app.models.student_invitation import StudentInvitationToken  # noqa: F401
from app.models.enums import (
    AttendanceMethod,
    PaymentStatus,
    StudentStatus,
    UserRole,
)
from app.models.fight_record import StudentFightRecord  # noqa: F401
from app.models.finance import Payment  # noqa: F401
from app.models.medical_record import MedicalRecord  # noqa: F401
from app.models.organization import Branch, Organization
from app.models.session_sync_ticket import SessionSyncTicket  # noqa: F401
from app.models.student import Student
from app.models.student_document import StudentDocument  # noqa: F401
from app.models.teaching import Attendance, ClassEnrollment, ClassSchedule, MartialClass
from app.models.trajectory import TrajectoryEvent  # noqa: F401
from app.models.user import AdminAssignment, User
from app.api.dependencies import require_active_user


def _register_sqlite_compat_functions(dbapi_connection, _connection_record):
    """Registra funciones compatibles con MySQL que los modelos usan en CHECKs o server_defaults.

    Portabilidad entre MySQL (producción) y SQLite en memoria para tests.
    """

    def _char_length(value) -> int:
        if value is None:
            return 0
        return len(str(value))

    def _utc_timestamp():
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    def _curdate():
        return datetime.utcnow().strftime("%Y-%m-%d")

    def _upper(value):
        return str(value).upper() if value is not None else None

    try:
        dbapi_connection.create_function("CHAR_LENGTH", 1, _char_length)
    except Exception:
        pass
    try:
        dbapi_connection.create_function("UTC_TIMESTAMP", 0, _utc_timestamp)
    except Exception:
        pass
    try:
        dbapi_connection.create_function("CURDATE", 0, _curdate)
    except Exception:
        pass
    try:
        dbapi_connection.create_function("UPPER", 1, _upper)
    except Exception:
        pass


@pytest.fixture(scope="session")
def test_db_engine():
    from sqlalchemy import event

    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _register_sqlite_compat_functions)
    return engine


@pytest.fixture(scope="session")
def TestSessionLocal(test_db_engine):
    Base.metadata.create_all(test_db_engine)
    return sessionmaker(
        bind=test_db_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


@pytest.fixture
def db_session(TestSessionLocal) -> Generator[Session, None, None]:
    """Sesión de test con rollback por método (transacción independiente por test).

    Se usa SAVEPOINT explícito para poder aislar cada test y hacer rollback
    sin necesidad de tear-down de fixtures de orden superior (seeded_*).
    """

    connection = TestSessionLocal.kw["bind"].connect()
    transaction = connection.begin()
    session: Session = Session(bind=connection, autoflush=False, autocommit=False, expire_on_commit=False)
    savepoint = connection.begin_nested()
    try:
        yield session
    finally:
        session.close()
        savepoint.rollback() if savepoint.is_active else None
        transaction.rollback()
        connection.close()


def _utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def seeded_admin_user(db_session: Session) -> User:
    admin = User(
        email="admin_test@example.com",
        password_hash="noop",
        role=UserRole.ORG_ADMIN,
        is_active=True,
        first_time=False,
    )
    db_session.add(admin)
    db_session.flush()
    return admin


@pytest.fixture
def seeded_org(db_session: Session) -> Organization:
    org = Organization(
        name="Academia Test",
        slug="TST",
        is_active=True,
    )
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def seeded_branch(db_session: Session, seeded_org: Organization) -> Branch:
    branch = Branch(
        organization_id=seeded_org.id,
        name="Sucursal Centro",
        country="MX",
        state="CDMX",
        city="Ciudad de México",
        address="Av. Reforma 123",
        timezone="America/Mexico_City",
        qr_secret="branch-qr-secret-test",
        is_active=True,
    )
    db_session.add(branch)
    db_session.flush()
    return branch


@pytest.fixture
def seeded_admin_assignment(
    db_session: Session,
    seeded_admin_user: User,
    seeded_org: Organization,
    seeded_branch: Branch,
) -> AdminAssignment:
    assignment = AdminAssignment(
        user_id=seeded_admin_user.id,
        organization_id=seeded_org.id,
        branch_id=seeded_branch.id,
    )
    db_session.add(assignment)
    db_session.flush()
    return assignment


@pytest.fixture
def seeded_discipline(db_session: Session, seeded_org: Organization) -> Discipline:
    disc = Discipline(
        organization_id=seeded_org.id,
        name="Brazilian Jiu Jitsu",
        is_active=True,
    )
    db_session.add(disc)
    db_session.flush()
    return disc


@pytest.fixture
def seeded_discipline_2(db_session: Session, seeded_org: Organization) -> Discipline:
    disc = Discipline(
        organization_id=seeded_org.id,
        name="Muay Thai",
        is_active=True,
    )
    db_session.add(disc)
    db_session.flush()
    return disc


@pytest.fixture
def seeded_class_a(
    db_session: Session,
    seeded_org: Organization,
    seeded_branch: Branch,
    seeded_discipline: Discipline,
) -> MartialClass:
    cls = MartialClass(
        organization_id=seeded_org.id,
        branch_id=seeded_branch.id,
        discipline_id=seeded_discipline.id,
        name="BJJ Avanzados",
        description="Clase para cinturones azules en adelante",
        instructor_name="Sensei Juan",
        capacity=20,
        is_active=True,
    )
    db_session.add(cls)
    db_session.flush()
    return cls


@pytest.fixture
def seeded_class_b(
    db_session: Session,
    seeded_org: Organization,
    seeded_branch: Branch,
    seeded_discipline_2: Discipline,
) -> MartialClass:
    cls = MartialClass(
        organization_id=seeded_org.id,
        branch_id=seeded_branch.id,
        discipline_id=seeded_discipline_2.id,
        name="Muay Thai Fundamentos",
        description="Fundamentos de striking",
        instructor_name="Coach Pedro",
        capacity=25,
        is_active=True,
    )
    db_session.add(cls)
    db_session.flush()
    return cls


@pytest.fixture
def seeded_student(
    db_session: Session,
    seeded_org: Organization,
    seeded_branch: Branch,
    seeded_class_a: MartialClass,
) -> Student:
    student = Student(
        organization_id=seeded_org.id,
        branch_id=seeded_branch.id,
        unique_code="STU00001",
        first_name="Carlos",
        last_name="Pérez",
        birth_date=date(1995, 6, 15),
        birth_place="CDMX",
        enrollment_date=date(2025, 1, 15),
        primary_class_id=seeded_class_a.id,
        monthly_fee=None,
        currency="USD",
        next_payment_date=None,
        payment_status=PaymentStatus.UP_TO_DATE,
        status=StudentStatus.ACTIVE,
        is_minor=False,
    )
    db_session.add(student)
    db_session.flush()
    return student


@pytest.fixture
def seeded_attendances(
    db_session: Session,
    seeded_student: Student,
    seeded_class_a: MartialClass,
    seeded_class_b: MartialClass,
    seeded_branch: Branch,
) -> list[Attendance]:
    now = _utc_naive_now()
    items: list[Attendance] = [
        Attendance(
            student_id=seeded_student.id,
            class_id=seeded_class_a.id,
            branch_id=seeded_branch.id,
            check_in_at=now,
            method=AttendanceMethod.QR,
            registered_by=None,
        ),
        Attendance(
            student_id=seeded_student.id,
            class_id=seeded_class_a.id,
            branch_id=seeded_branch.id,
            check_in_at=now - __import__("datetime").timedelta(days=1),
            method=AttendanceMethod.MANUAL,
            registered_by=None,
        ),
        Attendance(
            student_id=seeded_student.id,
            class_id=seeded_class_b.id,
            branch_id=seeded_branch.id,
            check_in_at=now - __import__("datetime").timedelta(days=2),
            method=AttendanceMethod.QR,
            registered_by=None,
        ),
        Attendance(
            student_id=seeded_student.id,
            class_id=seeded_class_a.id,
            branch_id=seeded_branch.id,
            check_in_at=now - __import__("datetime").timedelta(days=40),
            method=AttendanceMethod.MANUAL,
            registered_by=None,
        ),
    ]
    db_session.add_all(items)
    db_session.flush()
    return items


@pytest.fixture
def unauthorized_user(db_session: Session) -> User:
    user = User(
        email="foreign@example.com",
        password_hash="noop",
        role=UserRole.ORG_ADMIN,
        is_active=True,
        first_time=False,
    )
    db_session.add(user)
    foreign_org = Organization(name="Foreign Org", slug="FRN", is_active=True)
    db_session.add(foreign_org)
    db_session.flush()
    foreign_branch = Branch(
        organization_id=foreign_org.id,
        name="Foreign Branch",
        country="US",
        state="CA",
        city="LA",
        address="X",
        timezone="America/Los_Angeles",
        qr_secret="s",
        is_active=True,
    )
    db_session.add(foreign_branch)
    db_session.flush()
    assignment = AdminAssignment(
        user_id=user.id,
        organization_id=foreign_org.id,
        branch_id=foreign_branch.id,
    )
    db_session.add(assignment)
    db_session.flush()
    return user


@pytest.fixture
def test_client(
    db_session: Session,
    seeded_admin_user: User,
    seeded_admin_assignment: AdminAssignment,
) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_active_user] = lambda: seeded_admin_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_client_unauthorized(
    db_session: Session,
    unauthorized_user: User,
) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_active_user] = lambda: unauthorized_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
