from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest


def utc_naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt


# ---------------------------------------------------------------------------
# RF1 — Schemas anidados (AttendanceRead.class_obj)
# ---------------------------------------------------------------------------

def test_list_attendance_returns_nested_class_obj(test_client, seeded_student, seeded_class_a, seeded_attendances):
    """GET /attendance?student_id=X debe devolver class_obj con nombre y disciplina."""
    resp = test_client.get("/api/v1/attendance", params={"student_id": seeded_student.id, "limit": 10})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) >= 1
    with_class = [d for d in data if d.get("class_id") == seeded_class_a.id][0]
    assert with_class["class_obj"] is not None
    assert with_class["class_obj"]["id"] == seeded_class_a.id
    assert with_class["class_obj"]["name"] == seeded_class_a.name
    assert with_class["class_obj"]["discipline_name"] is not None
    assert with_class["class_obj"]["instructor_name"] == seeded_class_a.instructor_name


def test_attendance_read_backward_compatible_without_nested_fields_for_null_class_id(
    test_client, seeded_student, seeded_branch, db_session
):
    """Attendance con class_id=null debe devolver class_obj=null sin romper schema."""
    from app.models.enums import AttendanceMethod
    from app.models.teaching import Attendance

    att = Attendance(
        student_id=seeded_student.id,
        class_id=None,
        branch_id=seeded_branch.id,
        check_in_at=utc_naive(datetime.now(timezone.utc)),
        method=AttendanceMethod.MANUAL,
    )
    db_session.add(att)
    db_session.commit()

    resp = test_client.get("/api/v1/attendance", params={"student_id": seeded_student.id})
    assert resp.status_code == 200
    data = resp.json()
    null_class_item = next(d for d in data if d["id"] == att.id)
    assert null_class_item["class_obj"] is None


# ---------------------------------------------------------------------------
# RF2 — Paginación y filtros por fecha
# ---------------------------------------------------------------------------

def test_list_attendance_pagination_limit_offset(test_client, seeded_student, seeded_attendances):
    """Debe respetar limit y offset en el orden correcto (check_in_at DESC)."""
    all_resp = test_client.get("/api/v1/attendance", params={"student_id": seeded_student.id})
    all_items = all_resp.json()
    assert len(all_items) == len(seeded_attendances)
    # Los primeros 2, debe ser la fecha más reciente
    page = test_client.get("/api/v1/attendance", params={"student_id": seeded_student.id, "limit": 2, "offset": 0}).json()
    assert len(page) == 2
    assert page[0]["id"] == all_items[0]["id"]
    page2 = test_client.get("/api/v1/attendance", params={"student_id": seeded_student.id, "limit": 2, "offset": 2}).json()
    assert len(page2) == 2
    assert page2[0]["id"] != page[0]["id"]


def test_list_attendance_date_from_date_to(test_client, seeded_student, seeded_attendances):
    """Solo asistencias dentro del rango."""
    today = utc_naive(datetime.now(timezone.utc)).date()
    # Últimos 3 días: deben incluirse las de hoy, ayer y hace 2 días; excluirse la de hace 40
    date_from = today - timedelta(days=3)
    date_to = today
    resp = test_client.get(
        "/api/v1/attendance",
        params={
            "student_id": seeded_student.id,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        },
    )
    assert resp.status_code == 200
    in_range = resp.json()
    assert len(in_range) == 3


# ---------------------------------------------------------------------------
# RF3 — Endpoint de resumen por alumno
# ---------------------------------------------------------------------------

def test_student_summary_empty_when_zero_attendances(test_client, db_session):
    """Alumno SIN asistencias devuelve ceros y nulls correctamente."""
    from app.models.curriculum import Discipline
    from app.models.enums import PaymentStatus, StudentStatus
    from app.models.organization import Branch, Organization
    from app.models.student import Student
    from app.models.teaching import MartialClass

    org = Organization(name="E2", slug="E2T", is_active=True)
    db_session.add(org)
    db_session.flush()
    branch = Branch(
        organization_id=org.id,
        name="B2",
        country="X", state="Y", city="Z", address="X",
        timezone="UTC",
        qr_secret="secret",
        is_active=True,
    )
    db_session.add(branch)
    db_session.flush()
    disc = Discipline(organization_id=org.id, name="D", is_active=True)
    db_session.add(disc)
    db_session.flush()
    cls = MartialClass(
        organization_id=org.id, branch_id=branch.id, discipline_id=disc.id, name="C", is_active=True,
    )
    db_session.add(cls)
    db_session.flush()
    student_no_att = Student(
        organization_id=org.id,
        branch_id=branch.id,
        unique_code="EMPTY001",
        first_name="Vacio", last_name="Alumno",
        birth_date=date(2000, 1, 1),
        birth_place="x",
        enrollment_date=date(2025, 1, 1),
        primary_class_id=cls.id,
        currency="USD",
        payment_status=PaymentStatus.UP_TO_DATE,
        status=StudentStatus.ACTIVE,
        is_minor=False,
    )
    db_session.add(student_no_att)
    db_session.flush()
    # Asignar admin al scope de este alumno para pasar authorization
    from app.models.user import User, AdminAssignment
    from app.models.enums import UserRole
    # Sobreescribir dependency: usar dependency_overrides temporal para un user super_admin en vez
    from app.api.dependencies import require_active_user
    super_admin = User(
        email="super@x.com", password_hash="x", role=UserRole.SUPER_ADMIN, is_active=True, first_time=False,
    )
    db_session.add(super_admin)
    db_session.flush()
    try:
        from app.main import app
        app.dependency_overrides[require_active_user] = lambda: super_admin
        resp = test_client.get(f"/api/v1/students/{student_no_att.id}/attendance/summary")
    finally:
        app.dependency_overrides.pop(require_active_user, None)
    assert resp.status_code == 200, resp.text
    s = resp.json()
    assert s["student_id"] == student_no_att.id
    assert s["total_attendances"] == 0
    assert s["last_7_days"] == 0
    assert s["last_30_days"] == 0
    assert s["by_class"] == []
    assert s["first_attendance_at"] is None
    assert s["last_attendance_at"] is None
    assert s["streak_days"] == 0


def test_student_summary_counts_and_by_class(test_client, seeded_student, seeded_class_a, seeded_class_b, seeded_attendances):
    """Verifica totales, breakdown por clase y KPIs."""
    resp = test_client.get(f"/api/v1/students/{seeded_student.id}/attendance/summary")
    assert resp.status_code == 200, resp.text
    s = resp.json()
    # 4 asistencias sembradas (3 últimos días + 1 de hace 40)
    assert s["total_attendances"] == 4
    assert s["last_30_days"] == 3
    assert s["last_7_days"] == 3
    by_class_ids = {row["class_id"]: row for row in s["by_class"]}
    # BJJ Avanzados: 1 (hoy) +1 (ayer) +1 (hace 40) = 3; Muay Thai: 1
    assert by_class_ids[seeded_class_a.id]["count"] == 3
    assert by_class_ids[seeded_class_b.id]["count"] == 1
    assert s["first_attendance_at"] is not None
    assert s["last_attendance_at"] is not None
    # Rachas: hoy, ayer, hace 2 días => brecha de 1 día entre ayer-1 y hace-2; racha: 2
    assert s["streak_days"] >= 1


def test_student_summary_unauthorized_branch_403(test_client_unauthorized, seeded_student):
    """Usuario con scope a otra org/sucursal recibe 403."""
    resp = test_client_unauthorized.get(f"/api/v1/students/{seeded_student.id}/attendance/summary")
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# RF4 — Anti-duplicado por class_id
# ---------------------------------------------------------------------------

def test_public_attendance_duplicate_same_class_returns_existing(
    test_client,
    db_session,
    seeded_org,
    seeded_branch,
    seeded_student,
    seeded_class_a,
):
    """Misma clase + alumno en 8h => retorna registro existente."""
    slugify_text = __import__("app.api.routes.public_attendance", fromlist=["slugify_text"]).slugify_text
    branch_slug = slugify_text(seeded_branch.name)
    org_slug = seeded_org.slug
    path = f"/api/v1/public/attendance/{org_slug}/{branch_slug}"

    r1 = test_client.post(path, json={"student_id": seeded_student.id, "class_id": seeded_class_a.id})
    assert r1.status_code == 201, r1.text
    id1 = r1.json()["attendance_id"]

    r2 = test_client.post(path, json={"student_id": seeded_student.id, "class_id": seeded_class_a.id})
    assert r2.status_code == 201, r2.text
    id2 = r2.json()["attendance_id"]
    assert id1 == id2, f"Se esperaba id duplicado pero id1={id1} id2={id2}"
    assert "registrada" in r2.json()["message"].lower() or "ya" in r2.json()["message"].lower()


def test_public_attendance_different_class_creates_new(
    test_client,
    db_session,
    seeded_org,
    seeded_branch,
    seeded_student,
    seeded_class_a,
    seeded_class_b,
):
    """Distinta clase + mismo alumno en 8h => crea un nuevo registro."""
    slugify_text = __import__("app.api.routes.public_attendance", fromlist=["slugify_text"]).slugify_text
    branch_slug = slugify_text(seeded_branch.name)
    org_slug = seeded_org.slug
    path = f"/api/v1/public/attendance/{org_slug}/{branch_slug}"

    r1 = test_client.post(path, json={"student_id": seeded_student.id, "class_id": seeded_class_a.id})
    assert r1.status_code == 201, r1.text
    id1 = r1.json()["attendance_id"]

    r2 = test_client.post(path, json={"student_id": seeded_student.id, "class_id": seeded_class_b.id})
    assert r2.status_code == 201, r2.text
    id2 = r2.json()["attendance_id"]
    assert id1 != id2, "Se esperaba crear 2 asistencias distintas por ser clases diferentes"


# ---------------------------------------------------------------------------
# RF1 + RF3 adicional: schema validation unitarios sin request
# ---------------------------------------------------------------------------

def test_schema_summaries_validate_with_dummy():
    from app.schemas.attendance import (
        AttendanceSummaryPerClass,
        MartialClassReadSummary,
        StudentAttendanceSummary,
        StudentReadSummary,
    )

    class_summary = MartialClassReadSummary(id=1, name="JJ", discipline_name="BJJ", instructor_name="S")
    student_summary = StudentReadSummary(id=1, unique_code="ABC1", first_name="X", last_name="Y")
    per_class = AttendanceSummaryPerClass(class_id=1, class_name="JJ", count=10)
    kpi = StudentAttendanceSummary(
        student_id=1,
        total_attendances=10,
        last_7_days=5,
        last_30_days=10,
        by_class=[per_class],
        first_attendance_at=utc_naive(datetime.now(timezone.utc)),
        last_attendance_at=utc_naive(datetime.now(timezone.utc)),
        streak_days=3,
    )
    assert kpi.total_attendances == 10
    assert class_summary.id == 1
    assert student_summary.unique_code == "ABC1"
