"""Tests E2E del Sprint 1 — Portal Alumno Backend.

12 pasos D.1-D.12 del checklist de aceptación.
Ejecutar con: pytest tests/test_sprint1_e2e.py -v

Estrategia de auth en tests:
- Usamos SOLO un TestClient (anon_client) con override de get_db.
- Para requests admin, envolvemos la llamada en admin_request_context() que
  activa temporalmente override de require_active_user y lo restaura inmediatamente.
  Así no contaminamos los endpoints posteriores que necesitan tokens reales.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from urllib.parse import urlparse, parse_qs

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import require_active_user
from app.db.session import get_db
from app.main import app


API_PREFIX = "/api/v1"
TEST_PASSWORD = "NuevaPass1234"
TEST_STUDENT_EMAIL = "alumno_sprint1@example.com"


# ---------------------------------------------------------------------------
# Fixtures y helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def anon_client(db_session) -> Generator[TestClient, None, None]:
    """Cliente base: solo inyecta la db, NO toca overrides de auth en absoluto."""
    prev_get_db = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        yield client
    if prev_get_db is not None:
        app.dependency_overrides[get_db] = prev_get_db
    else:
        app.dependency_overrides.pop(get_db, None)


@contextmanager
def admin_request_context(db_session, seeded_admin_user):
    """Activa overrides de admin SOLO durante el bloque `with`. Al salir restaura todo."""
    prev_db = app.dependency_overrides.get(get_db)
    prev_active = app.dependency_overrides.get(require_active_user)
    try:
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[require_active_user] = lambda: seeded_admin_user
        yield
    finally:
        if prev_db is not None:
            app.dependency_overrides[get_db] = prev_db
        else:
            app.dependency_overrides.pop(get_db, None)
        if prev_active is not None:
            app.dependency_overrides[require_active_user] = prev_active
        else:
            app.dependency_overrides.pop(require_active_user, None)


def _make_student_payload(seeded_org, seeded_branch, seeded_class_a, *,
                          enable_portal_access: bool,
                          student_email: str | None = None,
                          first_name: str = "Laura",
                          last_name: str = "González") -> dict:
    return {
        "organization_id": seeded_org.id,
        "branch_id": seeded_branch.id,
        "first_name": first_name,
        "last_name": last_name,
        "birth_date": date(2000, 5, 20).isoformat(),
        "birth_place": "CDMX",
        "enrollment_date": date(2025, 2, 10).isoformat(),
        "primary_class_id": seeded_class_a.id,
        "currency": "MXN",
        "payment_status": "up_to_date",
        "status": "active",
        "is_minor": False,
        "enable_portal_access": enable_portal_access,
        "student_email": student_email,
    }


def _extract_raw_token(invitation_link: str) -> str:
    parsed = urlparse(invitation_link)
    qs = parse_qs(parsed.query)
    return qs["token"][0]


# ===========================================================================
# D.1 — D.12: Flujo E2E completo en un solo test (cada paso depende del anterior)
# ===========================================================================
def test_sprint1_full_flow_d1_to_d12(
    anon_client,
    db_session,
    seeded_admin_user,
    seeded_admin_assignment,
    seeded_org,
    seeded_branch,
    seeded_class_a,
):
    """12 pasos secuenciales: create → preview → redeem → login → me → resend → revoke."""
    base = API_PREFIX

    # ------------------------------------------------------------------ D.1
    # D.1: Crear alumno CON portal habilitado → 201 + link + metadata
    payload_on = _make_student_payload(
        seeded_org, seeded_branch, seeded_class_a,
        enable_portal_access=True,
        student_email=TEST_STUDENT_EMAIL,
        first_name="Laura",
        last_name="González",
    )
    with admin_request_context(db_session, seeded_admin_user):
        r = anon_client.post(f"{base}/students", json=payload_on)
    assert r.status_code == 201, f"D.1 create (ON) status={r.status_code} body={r.text}"
    d1 = r.json()
    assert d1.get("user_id") is not None, "D.1 user_id placeholder debe existir"
    portal = d1.get("portal_access") or {}
    assert portal.get("has_linked_user") is True, "D.1 has_linked_user True"
    assert portal.get("user_is_active") is True, "D.1 user_is_active True"
    assert portal.get("pending_invitation_exists") is True, "D.1 pending_exists True"
    assert portal.get("invitation_sent_count") == 1, "D.1 sent_count == 1"
    assert portal.get("invitation_email_sent_to") == TEST_STUDENT_EMAIL, "D.1 email match"
    actual_unique_code = d1["unique_code"]
    assert len(actual_unique_code) >= 4, "D.1 unique_code autogenerado debe existir"
    invitation_link = portal.get("invitation_link")
    assert invitation_link and "token=" in invitation_link, "D.1 invitation_link con token raw"
    raw_token_1 = _extract_raw_token(invitation_link)
    assert len(raw_token_1) >= 32, "D.1 token raw ≥ 32 chars"
    student_id = d1["id"]

    # ------------------------------------------------------------------ D.2
    # D.2: Crear alumno SIN portal (backward compat) → user_id None
    payload_off = _make_student_payload(
        seeded_org, seeded_branch, seeded_class_a,
        enable_portal_access=False,
        first_name="Pedro",
        last_name="Ramírez",
    )
    with admin_request_context(db_session, seeded_admin_user):
        r = anon_client.post(f"{base}/students", json=payload_off)
    assert r.status_code == 201, f"D.2 create (OFF) status={r.status_code} body={r.text}"
    d2 = r.json()
    assert d2.get("user_id") is None, f"D.2 user_id debe ser None (backward compat) — got {d2.get('user_id')}"
    portal_off = d2.get("portal_access") or {}
    assert portal_off.get("has_linked_user") is False, "D.2 has_linked_user False"

    # ------------------------------------------------------------------ D.3
    # D.3: Preview token inválido → status "invalid"
    r = anon_client.get(f"{base}/auth/student-invitation", params={"token": "token-que-no-existe-12345"})
    assert r.status_code == 200, f"D.3 preview invalid status={r.status_code} body={r.text}"
    d3 = r.json()
    assert d3.get("status") == "invalid", f"D.3 status == invalid → got {d3.get('status')}"

    # ------------------------------------------------------------------ D.4
    # D.4: Preview token VÁLIDO → status "valid" + metadata dojo/alumno
    r = anon_client.get(f"{base}/auth/student-invitation", params={"token": raw_token_1})
    assert r.status_code == 200, f"D.4 preview valid status={r.status_code} body={r.text}"
    d4 = r.json()
    assert d4.get("status") == "valid", f"D.4 status == valid → got {d4.get('status')}"
    assert d4.get("first_name") == "Laura", "D.4 first_name Laura"
    assert d4.get("last_name") == "González", "D.4 last_name González"
    assert d4.get("unique_code") == actual_unique_code, f"D.4 unique_code autogenerado match → {d4.get('unique_code')} vs {actual_unique_code}"
    assert d4.get("suggested_email") == TEST_STUDENT_EMAIL, "D.4 suggested_email"
    assert d4.get("dojo_name") == seeded_org.name, "D.4 dojo_name = Academia Test"
    assert d4.get("expires_at") is not None, "D.4 expires_at presente"

    # ------------------------------------------------------------------ D.5
    # D.5: Redeem token → auto-login TokenResponse (role student, email overrideado)
    redeem_payload = {
        "token": raw_token_1,
        "email": TEST_STUDENT_EMAIL,
        "password": TEST_PASSWORD,
        "confirm_password": TEST_PASSWORD,
        "accept_terms": True,
    }
    r = anon_client.post(f"{base}/auth/student-invitation/redeem", json=redeem_payload)
    assert r.status_code == 200, f"D.5 redeem status={r.status_code} body={r.text}"
    d5 = r.json()
    access_token = d5.get("access_token")
    assert access_token, "D.5 access_token presente"
    token_type = d5.get("token_type")
    assert token_type == "bearer", "D.5 token_type bearer"
    user = d5.get("user") or {}
    assert user.get("role") == "student", f"D.5 user.role student → got {user.get('role')}"
    assert user.get("email") == TEST_STUDENT_EMAIL, f"D.5 email override OK"
    assert user.get("email_verified_at") is not None, "D.5 email_verified_at seteado"
    student_auth_headers = {"Authorization": f"Bearer {access_token}"}

    # ------------------------------------------------------------------ D.6b
    # D.6b: Login normal post-redeem debe funcionar (ya email_verified_at no es None)
    r = anon_client.post(f"{base}/auth/login", json={
        "email": TEST_STUDENT_EMAIL,
        "password": TEST_PASSWORD,
    })
    assert r.status_code == 200, f"D.6b login status={r.status_code} body={r.text}"
    d6b = r.json()
    assert d6b.get("access_token"), "D.6b login devuelve access_token"
    assert (d6b.get("user") or {}).get("role") == "student", "D.6b login role student"

    # ------------------------------------------------------------------ D.7
    # D.7: PATCH /me/password — current_password incorrecta → 401
    r = anon_client.patch(
        f"{base}/me/password",
        headers=student_auth_headers,
        json={
            "current_password": "PassMala1234",
            "new_password": "OtraPass5678",
            "confirm_password": "OtraPass5678",
        },
    )
    assert r.status_code == 401, f"D.7 password mala 401 → got {r.status_code} body={r.text}"

    # ------------------------------------------------------------------ D.8
    # D.8: PATCH /me/password — current_password correcta → 200
    new_pass = "PasswordActualizada1!"
    r = anon_client.patch(
        f"{base}/me/password",
        headers=student_auth_headers,
        json={
            "current_password": TEST_PASSWORD,
            "new_password": new_pass,
            "confirm_password": new_pass,
        },
    )
    assert r.status_code == 200, f"D.8 password OK 200 → got {r.status_code} body={r.text}"
    d8 = r.json()
    assert d8.get("message"), "D.8 MessageResponse devuelto"
    # Confirmar login con la nueva password funciona
    r = anon_client.post(f"{base}/auth/login", json={
        "email": TEST_STUDENT_EMAIL,
        "password": new_pass,
    })
    assert r.status_code == 200, f"D.8 post-update login con nueva pass → {r.status_code} {r.text}"

    # ------------------------------------------------------------------ D.9
    # D.9: GET /me/attendance?limit=13 → FastAPI 422 automático (Query le=12)
    r = anon_client.get(f"{base}/me/attendance", headers=student_auth_headers, params={"limit": 13})
    assert r.status_code == 422, f"D.9 limit>12 → 422 → got {r.status_code} body={r.text}"

    # ------------------------------------------------------------------ D.10
    # D.10: GET /me/attendance/summary → vacío total=0
    r = anon_client.get(f"{base}/me/attendance/summary", headers=student_auth_headers)
    assert r.status_code == 200, f"D.10 summary status={r.status_code} body={r.text}"
    d10 = r.json()
    assert d10.get("total_attendances") == 0, f"D.10 total=0 → got {d10.get('total_attendances')}"

    # ------------------------------------------------------------------ D.11
    # D.11: POST resend-invitation → sent_count=2 + token anterior usado (status used)
    with admin_request_context(db_session, seeded_admin_user):
        r = anon_client.post(f"{base}/students/{student_id}/resend-invitation")
    assert r.status_code == 200, f"D.11 resend status={r.status_code} body={r.text}"
    d11 = r.json()
    portal11 = d11.get("portal_access") or {}
    assert portal11.get("invitation_sent_count") == 2, f"D.11 sent_count=2 → {portal11.get('invitation_sent_count')}"
    assert portal11.get("pending_invitation_exists") is True, "D.11 nuevo token pending=True"
    new_link = portal11.get("invitation_link")
    assert new_link and "token=" in new_link, "D.11 nuevo invitation_link"
    raw_token_2 = _extract_raw_token(new_link)
    assert raw_token_2 != raw_token_1, "D.11 tokens distintos"
    # Verificar token 1 → ahora "used"
    r = anon_client.get(f"{base}/auth/student-invitation", params={"token": raw_token_1})
    assert r.status_code == 200
    assert (r.json()).get("status") == "used", "D.11 token anterior status=used"
    # Verificar token 2 → "valid"
    r = anon_client.get(f"{base}/auth/student-invitation", params={"token": raw_token_2})
    assert r.status_code == 200
    assert (r.json()).get("status") == "valid", "D.11 token nuevo status=valid"

    # ------------------------------------------------------------------ D.12
    # D.12: POST revoke-portal-access → user_is_active=False + pending=False + login 403
    with admin_request_context(db_session, seeded_admin_user):
        r = anon_client.post(f"{base}/students/{student_id}/revoke-portal-access")
    assert r.status_code == 200, f"D.12 revoke status={r.status_code} body={r.text}"
    d12 = r.json()
    portal12 = d12.get("portal_access") or {}
    assert portal12.get("has_linked_user") is True, "D.12 has_linked_user sigue True (no desasignamos user_id)"
    assert portal12.get("user_is_active") is False, "D.12 user_is_active=False"
    assert portal12.get("pending_invitation_exists") is False, "D.12 pending_exists=False"
    # Login del alumno ahora debe fallar (is_active=False) → 403 "El usuario está inactivo"
    r = anon_client.post(f"{base}/auth/login", json={
        "email": TEST_STUDENT_EMAIL,
        "password": new_pass,
    })
    assert r.status_code == 403, f"D.12 login revocado 403 → got {r.status_code} body={r.text}"


# ===========================================================================
# Tests aislados adicionales de endpoints /me
# ===========================================================================
def test_sprint1_me_email_change_409_on_duplicate(
    anon_client,
    db_session,
    seeded_admin_user,
    seeded_admin_assignment,
    seeded_org,
    seeded_branch,
    seeded_class_a,
):
    """Cambiar email a uno ya existente → 409 Conflict."""
    base = API_PREFIX

    # Crear alumno 1 con portal ON
    p1 = _make_student_payload(seeded_org, seeded_branch, seeded_class_a,
        enable_portal_access=True, student_email="a1@example.com")
    with admin_request_context(db_session, seeded_admin_user):
        s1_resp = anon_client.post(f"{base}/students", json=p1)
    s1_resp.raise_for_status()
    s1 = s1_resp.json()
    t1 = _extract_raw_token(s1["portal_access"]["invitation_link"])
    redeem1_resp = anon_client.post(f"{base}/auth/student-invitation/redeem", json={
        "token": t1, "email": "a1@example.com",
        "password": "TestPass1234", "confirm_password": "TestPass1234",
        "accept_terms": True,
    })
    assert redeem1_resp.status_code == 200, f"redeem alumno 1 → {redeem1_resp.status_code} {redeem1_resp.text}"

    # Crear alumno 2 con portal ON
    p2 = _make_student_payload(seeded_org, seeded_branch, seeded_class_a,
        enable_portal_access=True, student_email="a2@example.com",
        first_name="Mario", last_name="López")
    with admin_request_context(db_session, seeded_admin_user):
        s2_resp = anon_client.post(f"{base}/students", json=p2)
    s2_resp.raise_for_status()
    s2 = s2_resp.json()
    t2 = _extract_raw_token(s2["portal_access"]["invitation_link"])
    redeem2_resp = anon_client.post(f"{base}/auth/student-invitation/redeem", json={
        "token": t2, "email": "a2@example.com",
        "password": "TestPass5678", "confirm_password": "TestPass5678",
        "accept_terms": True,
    })
    assert redeem2_resp.status_code == 200, f"redeem alumno 2 status={redeem2_resp.status_code} body={redeem2_resp.text}"
    redeem2 = redeem2_resp.json()
    assert (redeem2.get("user") or {}).get("role") == "student", f"alumno 2 debe ser role student: {redeem2.get('user')}"
    h2 = {"Authorization": f"Bearer {redeem2['access_token']}"}

    # Verificar que GET /me (require_active_user + role student) funciona
    r_me = anon_client.get(f"{base}/me", headers=h2)
    assert r_me.status_code == 200, f"GET /me alumno 2 status={r_me.status_code} body={r_me.text}"

    # Alumno 2 intenta cambiar su email a "a1@example.com" (ocupado) → 409
    r = anon_client.patch(f"{base}/me/email", headers=h2, json={"new_email": "a1@example.com"})
    assert r.status_code == 409, f"email duplicate 409 → got {r.status_code} body={r.text}"


# ===========================================================================
# Test: Bloqueo login para alumnos no activados (email_verified_at=None)
# ===========================================================================
def test_sprint1_login_student_blocked_before_redeem(
    anon_client,
    db_session,
    seeded_admin_user,
    seeded_admin_assignment,
    seeded_org,
    seeded_branch,
    seeded_class_a,
):
    """STUDENT + email_verified_at=None → login 403 'enlace de activación'."""
    from app.core.security import hash_password
    from app.models.user import User

    base = API_PREFIX
    p = _make_student_payload(seeded_org, seeded_branch, seeded_class_a,
        enable_portal_access=True, student_email="bloqueado@example.com")
    with admin_request_context(db_session, seeded_admin_user):
        s_resp = anon_client.post(f"{base}/students", json=p)
    s_resp.raise_for_status()
    created = s_resp.json()
    placeholder_user_id = created["user_id"]
    assert placeholder_user_id is not None

    # Actualizamos el password del placeholder a uno conocido para poder probar el login
    placeholder_user = db_session.get(User, placeholder_user_id)
    assert placeholder_user is not None
    placeholder_email = placeholder_user.email
    known_password = "TempBloq1234"
    placeholder_user.password_hash = hash_password(known_password)
    db_session.commit()

    # Ahora sí: login con el email placeholder + password conocido
    r = anon_client.post(f"{base}/auth/login", json={
        "email": placeholder_email,
        "password": known_password,
    })
    assert r.status_code == 403, f"bloqueo login 403 → got {r.status_code} body={r.text}"
    body = r.json()
    msg = (body.get("detail") or "").lower()
    assert "enlace" in msg or "activación" in msg, f"msg debe mencionar enlace: {body.get('detail')}"
