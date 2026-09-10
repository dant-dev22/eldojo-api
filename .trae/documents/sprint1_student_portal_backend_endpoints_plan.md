# Sprint 1: Endpoints Backend — Invitación Portal Alumno + Perfil

## Repository Research

### Convenciones y patrones existentes a respetar
1. **Dependencias auth**: `get_current_user()` → decodea token y carga User. `require_active_user()` → chequea `is_active`. Nuevo `require_student_user()` debe componerse con estas (nunca romper la cadena).
2. **Ruta pública `/auth/*`** sin dependencias de token; rutas privadas `/students/*`, `/me/*` con `require_active_user` global en [router.py](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/api/router.py#L31).
3. **Hash password**: `hash_password()` en [security.py](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/core/security.py#L43) usa SHA-256 hex. Comparación `hmac.compare_digest`.
4. **Token URL-safe + hash**: Reutilizar `generate_email_verification_token()` (32 bytes URL-safe) y `hash_email_verification_token()` (SHA-256 hex 64 chars) del mismo módulo. Coinciden perfecto con los campos `token_hash` (64) y `token_plain_tail` (8).
5. **build_token_response**: En [auth.py](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/api/routes/auth.py#L78-L97) recibe `User` y devuelve `TokenResponse` con access/refresh + `UserRead`. Se usa para redeem auto-login.
6. **`model_dump(exclude_unset=True)`** en updates parciales (patrón `AttendanceUpdate`).
7. **Paginación**: Todos los listados usan `Query(limit, offset)` con `limit.max=500`. El historial de `/me/attendance` tendrá max=12 estricto (restricción hard del proyecto).
8. **Attendance summary helper** `build_student_attendance_summary(...)` en [attendance_summary_service.py](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/services/attendance_summary_service.py#L76-L155) ya calcula streak, KPIs, breakdown por clase. Reutilizar 1:1.
9. **Helper `get_current_student`** en [me.py](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/api/routes/me.py#L27-L46) ya valida role STUDENT + existencia Student vinculada. Reutilizarla en endpoints attendance propios.
10. **Helper `utc_now()`** en [auth.py](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/api/routes/auth.py#L61-L64) = `datetime.now(timezone.utc).replace(tzinfo=None)`. Usar siempre.

### Mapa de datos a producir
```
Admin crea alumno con enable_portal_access=True
  └─► create_student: Student + User + StudentInvitationToken → devuelve StudentRead con portal_access.invitation_link populado
Admin consulta ficha
  └─► GET /students/{id}/portal-access → StudentPortalAccessStatus
Admin reenvía → POST /students/{id}/resend-invitation → regenera token, sent_count++, devuelve nuevo link
Admin revoca → POST /students/{id}/revoke-portal-access → user.is_active=False, todos los tokens used
Alumno abre link
  └─► GET /auth/student-invitation?token= → preview pública (first_name, dojo, suggested_email)
Alumno submit form
  └─► POST /auth/student-invitation/redeem → valida, setea password + email, setea email_verified_at, marca token, devuelve TokenResponse (auto login)
Alumno ya activado intenta login normal
  └─► POST /auth/login → normalmente (ya no bloquea)
Alumno NO activado intenta login normal
  └─► POST /auth/login → 403: "Tu dojo te compartió un enlace..."
Alumno logueado (STUDENT role)
  ├─► GET /me → ya existe
  ├─► PATCH /me → ya existe (foto + clase)
  ├─► PATCH /me/password → cambiar password con verificación actual
  ├─► PATCH /me/email → cambiar email con unicidad check
  ├─► GET /me/attendance (limit≤12 paginado)
  └─► GET /me/attendance/summary → KPIs + streak + breakdown por clase
```

---

## Files and Modules

| # | Ruta | Tipo cambio | Descripción |
|---|------|-------------|-------------|
| 1 | `app/api/dependencies.py` | Modificar | Agregar `require_student_user()` y helper `_attach_student_if_student_role` opcional |
| 2 | `app/core/student_invitation.py` (NUEVO) | Crear | Pure helpers: generar token raw/hash, construir link, invalidate anteriores, find raw → hasheado |
| 3 | `app/api/routes/students.py` | Modificar | Modificar `create_student` para portal flow; agregar `_populate_portal_access_status()` helper; 3 nuevos endpoints (portal-access GET, resend POST, revoke POST); extender `validate_student_links` para no romper user_id vinculación |
| 4 | `app/api/routes/auth.py` | Modificar | Extender imports de schemas y security; agregar 2 nuevos endpoints: `GET /student-invitation` y `POST /student-invitation/redeem`; extender `login()` para bloquear STUDENT no activados |
| 5 | `app/api/routes/me.py` | Modificar | Agregar `schemas/attendance` y servicios imports; 4 nuevos endpoints: `PATCH /password`, `PATCH /email`, `GET /attendance` (max 12), `GET /attendance/summary` |
| 6 | `app/schemas/me.py` | Modificar | Schema `MyPasswordChangeRequest` (current + new + confirm) + `MyEmailChangeRequest` (nuevo email) |

---

## Implementation Steps (Dependency Order)

### Paso 1 — Utilities + Dependency Guard (Cero breaking)

#### 1.1 `app/core/student_invitation.py` (NUEVO)
Crear módulo de puras funciones puras (sin estado):
```python
"""Utilidades para la generación y validación de invitaciones del portal alumno."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from app.core.config import settings
from app.core.security import generate_email_verification_token, hash_email_verification_token
from app.db.session import get_db  # noqa: F401 (para typings)
from app.models.student_invitation import StudentInvitationToken
from app.models.user import User  # noqa: F401

# Funciones:

def build_student_invitation_link(raw_token: str) -> str:
    """Construye la URL pública del link de activación."""
    base = settings.student_invitation_url_base.rstrip("/")
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}token={raw_token}"

def generate_student_invitation_token() -> tuple[str, str, str]:
    """Genera (raw_token, hashed_token, tail_8_chars).

    Devuelve valores listos para persistir en BD. El raw_token SOLO se
    devuelve una vez al cliente admin (a través de `invitation_link`).
    """
    raw = generate_email_verification_token()
    hashed = hash_email_verification_token(raw)
    tail = raw[-8:]
    return raw, hashed, tail

def invalidate_student_invitations(db, *, student_id: int | None = None, user_id: int | None = None, used_at):
    """Marca usados TODOS los tokens pendientes (por student o user)."""
    from sqlalchemy import select

    predicates = [StudentInvitationToken.used_at.is_(None)]
    if student_id is not None:
        predicates.append(StudentInvitationToken.student_id == student_id)
    if user_id is not None:
        predicates.append(StudentInvitationToken.user_id == user_id)
    pending = list(db.scalars(select(StudentInvitationToken).where(*predicates)))
    for tok in pending:
        tok.used_at = used_at
    return len(pending)

def student_invitation_expires_at(created_at) -> "datetime":
    """Expiración standard = created_at + settings.student_invitation_token_expire_days días."""
    from app.api.routes.auth import utc_now as _utc_now  # evitar circular
    ts = created_at or _utc_now()
    return ts + timedelta(days=settings.student_invitation_token_expire_days)

def find_pending_student_invitation_by_raw(db, raw_token: str) -> StudentInvitationToken | None:
    """Busca token por raw token → hashea y busca, SOLO si no usado y expiración futura."""
    from sqlalchemy import select
    from app.api.routes.auth import utc_now

    hashed = hash_email_verification_token(raw_token)
    now = utc_now()
    return db.scalar(
        select(StudentInvitationToken)
        .where(StudentInvitationToken.token_hash == hashed)
        .where(StudentInvitationToken.used_at.is_(None))
        .where(StudentInvitationToken.expires_at > now)
    )
```

#### 1.2 `app/api/dependencies.py` — `require_student_user()`
Agregar AL FINAL del archivo (respetar `bearer_scheme` ya existente):
```python
def require_student_user(
    current_user: User = Depends(require_active_user),
) -> User:
    """Asegura que el usuario autenticado tenga rol STUDENT y esté activo.

    Combina require_active_user + chequeo de rol. Usado en endpoints
    del portal alumno donde un admin NO debe poder hacer nada (ej: cambio
    de mi contraseña).
    """
    from app.models.enums import UserRole
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este endpoint solo está disponible para alumnos",
        )
    return current_user
```

---

### Paso 2 — Modificar `create_student` + Populate portal_access + Helper

#### 2.1 Helper `_populate_portal_access_status` INLINE en `students.py`
Función que recibe `db, student` y devuelve `StudentPortalAccessStatus` (para usar en `create_student`, `get_student`, `list_students` cuando sea necesario).

Lógica del helper:
- Consultar User = `db.get(User, student.user_id)` si existe
- `has_linked_user` = user_id is not None
- Consultar último token pendiente:
  ```
  SELECT * FROM student_invitation_tokens
  WHERE student_id = X AND used_at IS NULL ORDER BY created_at DESC LIMIT 1
  ```
- Si token pendiente exists:
  - `pending_invitation_exists=True`, `invitation_expires_at=expires_at`, `invitation_sent_count=sent_count`
  - `invitation_link` = construir pero **SOLO** si el admin tiene scope válido sobre la org (siempre sí, porque estamos dentro de route protegida) — **PERO**: guardar raw_token en una variable FLUJO solo durante create_student (porque ya no lo conocemos después del commit). Por lo tanto: **cuando recuperamos un token de la DB ya no tenemos raw → `invitation_link = None` excepto en POST create y POST resend (donde acabamos de generar el raw y lo tenemos a mano)**.
- `user_is_active` / `user_email_verified` = del User si existe
- `invitation_email_sent_to` = token.email_sent_to si hay token o `User.email` si existe

#### 2.2 Modificar `create_student` en `students.py`
Cambios al flujo actual:
1. **Antes de `db.add(student)`**: Leer `enable_portal_access = payload.enable_portal_access` y `student_email_val = payload.student_email`.
2. Después del `db.commit()` exitoso (línea 248): Si `enable_portal_access is False` → no hacer nada, retornar como antes.
3. Si `enable_portal_access=True`:
   - **Paso A — Validar email collision**: Si `student_email_val` existe, llamar `get_user_by_email(db, student_email_val)` importado de auth. Si existe y no es Student vinculado a él → 409. *Permitir que sea None si admin no quiere enviar email* (placeholder).
   - **Paso B — Construir User**:
     - `email = student_email_val or f"alumno-{student.unique_code}@pendiente.eldojo.tech"`
     - `password_hash = hash_password(secrets.token_urlsafe(16))` → contraseña temporal aleatoria (nunca se usa; el alumno la reemplazará en redeem).
     - `role = UserRole.STUDENT`
     - `is_active = True` (activamos el User para que redeem pueda crear sesión; pero `email_verified_at=None` hará que login normal esté bloqueado hasta redeem)
     - `first_name = student.first_name`, `last_name = student.last_name`
     - `email_verified_at = None`, `first_time = True`
   - **Paso C — Vincular**: `student.user_id = user.id` (flush para obtener id)
   - **Paso D — Generar invitación**: Usar utilities `generate_student_invitation_token()`. Insertar `StudentInvitationToken(student_id=student.id, user_id=user.id, token_hash=..., token_plain_tail=..., expires_at=..., sent_count=1, created_by_admin_id=current_user.id, email_sent_to=student_email_val)`.
   - **Paso E — Commit** (nuevo commit o re-flush student.user_id + commit)
   - **Paso F — Populate link**: Como tenemos `raw_token` a mano, **armamos el invitation_link manualmente** y poblamos el objeto `StudentPortalAccessStatus` completo. Finalmente, setear `object.__setattr__(result, "portal_access", status_obj)` antes del return.
4. En `result = refreshed or student`, después de `attach_completeness(result)`, **siempre poblar portal_access** con el helper (o con el manual si tenemos raw).

> Importante: El `student.user_id = payload.user_id` original debe seguir funcionando si admin lo pasa (link a User preexistente). Solo hacemos el flujo nuevo si `enable_portal_access=True` AND `payload.user_id is None`. Si user_id no es None y enable_portal_access=True → generamos invitación para ese User existente, no creamos User nuevo.

#### 2.3 Extender `get_student` y `list_students` opcional
- En `get_student`: Después de `attach_completeness`, poblar `portal_access` siempre con el helper.
- En `list_students`: Para no penalizar performance → **NO poblar portal_access por defecto**. Agregar query param `include_portal_access: bool = False`. Si True → iterar y poblar. El admin lo necesitará solo cuando abra la ficha individual, no el listado.

---

### Paso 3 — 3 Nuevos Endpoints en `/students/*` (Admin scope)

**3.1 GET `/students/{student_id}/portal-access` → response `StudentPortalAccessStatus`**
- `require_active_user`, obtener `student`, validar scope operacional, llamar helper y devolver status.

**3.2 POST `/students/{student_id}/resend-invitation` → response `StudentRead` (con invitation_link populado)**
- Si `student.user_id is None` → crearlo como en Paso 2.B (email placeholder o reutilizar student.email si es válido).
- Generar **NUEVO** raw token. `invalidate_student_invitations(student_id=...)`. Insertar nuevo token con `sent_count = (último sent_count if exists else 0) + 1`.
- Commit. Poblar `portal_access` con raw link a mano. Devolver Student actualizado.

**3.3 POST `/students/{student_id}/revoke-portal-access` → response `StudentRead`**
- Si student.user_id → `user = db.get(User, student.user_id)` → `user.is_active = False`.
- `invalidate_student_invitations(student_id=)` marcar todos.
- Opcionalmente `student.user_id = None` o dejarlo para poder reactivar después. Dejarlo: `student.user_id` con `is_active=False`.
- Commit. Poblar portal_access y devolver StudentRead.

---

### Paso 4 — 2 Nuevos Endpoints Públicos en `/auth/*` + Bloqueo Login

#### 4.1 Imports nuevos en `auth.py`
- Agregar:
  ```python
  from app.models.student_invitation import StudentInvitationToken
  from app.schemas.auth import (
      StudentInvitationPreviewResponse,
      StudentInvitationRedeemRequest,
  )
  from app.core.student_invitation import (
      build_student_invitation_link,
      find_pending_student_invitation_by_raw,
      invalidate_student_invitations,
  )
  ```
- Agregar también `get_user_by_email` ya está definido en el mismo archivo.

#### 4.2 `GET /auth/student-invitation` (público)
Query param `token: str = Query(..., min_length=16, max_length=512)`

Lógica:
1. `find_pending_student_invitation_by_raw(db, token)` → si None:
   - Chequear si token existió PERO está usado/expirado: búsqueda por hash sin filtros used/expires.
   - Devolver `StudentInvitationPreviewResponse(status="invalid"|"used"|"expired", message=...)`
2. Si token válido: cargar `student = db.get(Student, token.student_id)`, `branch`, `organization` para dojo_name.
3. `suggested_email = token.email_sent_to or (token.user.email if token.user_id else None)`
4. Devolver `status="valid"`, `message="Invitación válida. Completa tus datos para activar tu cuenta."`, `first_name`, `last_name`, `unique_code`, `suggested_email`, `dojo_name=organization.name`, `expires_at`.

#### 4.3 `POST /auth/student-invitation/redeem` → `TokenResponse` (auto login)
Payload `StudentInvitationRedeemRequest`.

Lógica:
1. `token = find_pending_student_invitation_by_raw(db, payload.token)` → si no → 404 con mensaje inválido.
2. `student = db.get(Student, token.student_id)` → si no → 500 (no debería).
3. Resolver `final_email`:
   - Si `payload.email`: usar este.
   - Else: `token.email_sent_to` si no es NULL y no es placeholder.
   - Else si `User.email` no es placeholder (`@pendiente.eldojo.tech`): usar User.email.
   - Else: **422** con detalle: "Debes proporcionar un correo electrónico para tu cuenta."
4. Validar unicidad `final_email`: `existing_user = get_user_by_email(db, final_email)`. Si `existing_user` existe y `existing_user.id != (token.user_id or 0)` → 409.
5. Resolver User final:
   - Si `token.user_id`: user = db.get(User, token.user_id) → actualizar:
     - `user.email = final_email`
     - `user.password_hash = hash_password(payload.password)`
     - `user.first_name = user.first_name or student.first_name`
     - `user.last_name = user.last_name or student.last_name`
     - `user.is_active = True`
     - `user.email_verified_at = utc_now()`
   - Else (no user_id, caso teórico raro): crear User nuevo con final_email + password + role STUDENT, vincular `student.user_id = user.id`
6. `token.used_at = utc_now()`
7. `invalidate_student_invitations(db, student_id=student.id, user_id=user.id, used_at=utc_now())` (por si había otros tokens del mismo alumno/user)
8. Commit.
9. Devolver `build_token_response(user)` (exactamente igual que `/auth/login`) — **Esto hace auto-login**.

#### 4.4 Extender `/auth/login` bloqueo para STUDENT no activado
Justo después del bloqueo existente:
```python
if not user.is_active:
    if user.email_verified_at is None:
        # este mensaje es para ADMIN/ORG_ADMIN academies pendientes
        ...
    ...

# NUEVO: si es STUDENT y email_verified_at es NULL (aunque is_active sea True por el placeholder)
# → debe canjear invitación primero
if user.role == UserRole.STUDENT and user.email_verified_at is None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Tu dojo te compartió un enlace exclusivo para activar tu cuenta por primera vez. Si no lo encuentras, contacta a tu instructor."
    )
```

---

### Paso 5 — 4 Nuevos Endpoints en `/me/*` (Alumno autenticado)

#### 5.1 Schemas nuevos en `app/schemas/me.py`
```python
class MyPasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate(self):
        if self.new_password != self.confirm_new_password:
            raise ValueError("Las contraseñas no coinciden")
        if self.current_password == self.new_password:
            raise ValueError("La nueva contraseña no puede ser igual a la actual")
        return self


class MyEmailChangeRequest(BaseModel):
    new_email: str = Field(min_length=5, max_length=255)

    @field_validator("new_email")
    @classmethod
    def normalize(cls, v): return v.strip().lower()
```

Importar `Field`, `field_validator`, `model_validator` de pydantic arriba.

#### 5.2 Endpoints en `app/api/routes/me.py`
Usar `Depends(require_student_user)` en vez de `require_active_user` en estos 4 endpoints para ADMIN NO pueda acceder.

##### 5.2.1 `PATCH /me/password` → `MessageResponse`
Payload: `MyPasswordChangeRequest` (body JSON, no Form)
- `user = require_student_user(...)`
- Verificar `verify_password(payload.current_password, user.password_hash)` → si no → 401.
- Poner nuevo password: `user.password_hash = hash_password(payload.new_password)`
- Commit. Devolver `{"message": "Contraseña actualizada exitosamente"}`.

##### 5.2.2 `PATCH /me/email` → `MyProfileRead`
Payload: `MyEmailChangeRequest`
- `user = require_student_user`
- Chequear unicidad: `get_user_by_email(db, payload.new_email)` → si existe y no es el mismo user → 409 "Ese correo ya está en uso"
- `user.email = payload.new_email`
- *Opcional*: `user.email_verified_at = utc_now()` si confiamos en que el alumno lo escribió bien. O dejarlo sin verificado — **decisión: marcar como verificado porque el alumno cambió su email estando autenticado con sesión válida post-activación (ya está verificado de antes). Es safe.**
- Commit. Devolver `serialize_profile(...)` actualizado (llamar a `get_current_student` y list_available_classes).

##### 5.2.3 `GET /me/attendance` → `list[AttendanceRead]` (MAX 12)
Filtros por query:
```
class_id: int | None = None
date_from: date | None = None
date_to: date | None = None
limit: int = Query(default=12, ge=1, le=12)  # HARD MAX 12, sin excepción!
offset: int = Query(default=0, ge=0)
```
- `require_student_user` → luego `student = get_current_student(db, current_user)`
- Construir query reutilizando `_attendance_list_query_base()` (definida en attendance routes). Importarla o copiar el SELECT con `selectinload(Attendance.class_obj).selectinload(MartialClass.discipline)` y `Attendance.student` → OR: alternativo, definir `_my_attendance_query_base` en `me.py`.
- Filtrar `Attendance.student_id == student.id` (seguridad, hardcodeado para que nadie pueda modificarlo).
- Aplicar filtros de clase/fecha como en `list_attendance`.
- `query = query.limit(limit).offset(offset)` → siempre limit ≤ 12.
- Devolver lista.

##### 5.2.4 `GET /me/attendance/summary` → `StudentAttendanceSummary`
Query params `class_id | date_from | date_to` igual que summary admin.
- `require_student_user` → `student = get_current_student(...)`
- Llamar `build_student_attendance_summary(db, student, class_id=class_id, date_from=date_from, date_to=date_to)` (mismo servicio que admin usa).
- Devolver resultado.

---

### Paso 6 — Importar schemas nuevos donde se use
- En `me.py` imports: AttendanceRead, StudentAttendanceSummary (de schemas.attendance); `from app.core.security import verify_password, hash_password`; `from app.api.routes.auth import get_user_by_email, utc_now` (o duplicar utc_now en me.py para no importar circular).
- En `students.py` imports: `from app.core.student_invitation import (generate_student_invitation_token, build_student_invitation_link, invalidate_student_invitations, student_invitation_expires_at)`; `from app.api.routes.auth import get_user_by_email, utc_now`; `from app.models.enums import UserRole`; `import secrets`.

---

## Dependencies and Considerations

1. **Circular imports auth ↔ students**: Para evitarlo, NUNCA importes `students.py` desde `auth.py`. El helper `utc_now` se puede duplicar en `me.py` y `student_invitation.py` si es necesario, o moverlo a `app/core/dates.py`. **Mejor**: mover `utc_now()` a `app/core/dates.py` (nuevo módulo pequeño) e importarlo desde todos lados. Esto limpia circulares. Pero si no queremos tocar muchos archivos → **usar imports locales dentro de función** (patrón Python standard para romper circulares, ya usado en `me.py` hoy no, pero se puede).
2. **`_attendance_list_query_base`** está definida en `attendance.py` sin import. Para reutilizar sin circular, **la copiamos 1 vez a `me.py`** (7 líneas) o mover a `app/services/attendance_query_service.py` (nuevo). Recomiendo **copiarla** en me.py este sprint por simplicidad.
3. **Password placeholder temporal**: NO usar strings vacíos ni fáciles de adivinar. Usar `secrets.token_urlsafe(16)` como password hash input.
4. **Email placeholder `@pendiente.eldojo.tech`**: debe ser un email sintácticamente válido (lo es) y único (por unique_code). Nunca se usa para login (bloqueado por email_verified_at=None).
5. **Performance `list_students`**: NO poblar `portal_access` por defecto (requiere 2 queries por alumno). Agregar query param `include_portal_access=False` explícito. Mobile admin solo lo activa al entrar en ficha individual.
6. **`build_token_response` post-redeem**: Devuelve TokenResponse con `user=UserRead.model_validate(user)`. El mobile AuthContext ya sabe guardarlo (`saveSession`). No hay que hacer nada especial.
7. **`limit: int = Query(default=12, ge=1, le=12)`**: `le=12` hace que si un atacante pone 13 FastAPI devuelva 422 automáticamente. Perfecto para hard constraint del proyecto.

---

## Validation

Después de implementación, ejecutar EN ORDEN:

### A) Smoke sintaxis y carga FastAPI
```powershell
cd c:\Users\dante\Documents\trae_projects\eldojo-backend-api
python -c "from app.api.dependencies import require_student_user; print('✅ dep OK')"
python -c "from app.core.student_invitation import generate_student_invitation_token, build_student_invitation_link; print('✅ core OK', generate_student_invitation_token()[2])"
python -c "from app.main import app; print(f'✅ FastAPI OK: {len(app.routes)} rutas'); # rutas nuevas deben aparecer en /docs"
```

### B) Validators nuevos
```python
from app.schemas.me import MyPasswordChangeRequest, MyEmailChangeRequest
# Test: pass iguales → falla
try: MyPasswordChangeRequest(current_password='a'*8, new_password='b'*8, confirm_new_password='c'*8)
except ValueError as e: print('✅ pass mismatch OK')
# Test: pass same current → falla
try: MyPasswordChangeRequest(current_password='a'*8, new_password='a'*8, confirm_new_password='a'*8)
except ValueError as e: print('✅ same as current OK')
# Test: email normalize → pasa
r = MyEmailChangeRequest(new_email='  TEST@MAIL.COM  ')
assert r.new_email == 'test@mail.com'
print('✅ email normalize OK')
```

### C) Test suite preexistente
```powershell
python -m pytest tests/ -x -q --tb=short 2>&1 | Select-Object -Last 20
# 10 passed, 758 warnings = OK
```

### D) Tests end-to-end manuales (Paso más importante)
Usando `TestClient` o `python` REPL + HTTPie:
1. **Admin login normal** → obtener Bearer token (como hoy).
2. **POST `/students`** con `enable_portal_access=True, student_email="nuevoalumno@test.com"` + resto campos.
   - Esperar: `201 Created` · `user_id != None` · `portal_access.pending_invitation_exists=True` · `portal_access.invitation_link` contiene `?token=`.
   - Extraer `token_raw = parse_url(link).query['token']`
   - Extraer `student.id`
3. **GET `/auth/student-invitation?token={token_raw}`** (público, no token)
   - Esperar `status='valid'`, `first_name='Juan'`, `dojo_name='X Academy'`, `suggested_email='nuevoalumno@test.com'`, `expires_at != None`.
4. **POST `/auth/student-invitation/redeem`** (público)
   - Body: `{ token, email: null (usar suggested), password: 'MiPass1234567', confirm_password: 'MiPass1234567', accept_terms: true }`
   - Esperar: `access_token != None`, `refresh_token != None`, `user.email = 'nuevoalumno@test.com'`, `user.role = 'student'`.
5. **Probar login bloqueado**: ANTES de redeem, probar `POST /auth/login` con `email=nuevoalumno@test.com, password=random(no importa)` NO pero con el placeholder password... es decir con un alumno creado pero no canjeado. Esperar `403` mensaje de dojo enlace.
6. **POST `/auth/login` DESPUÉS redeem** con email y password de redeem. Esperar 200 TokenResponse (ya no bloquea).
7. **Alumno cambia contraseña**: `PATCH /me/password` usando Bearer token de alumno, con contraseña actual + nueva. Esperar `200 message OK`. Luego `POST /auth/login` con contraseña vieja → 401, con nueva → 200.
8. **Alumno cambia email**: `PATCH /me/email` a `alumno_nuevo@test.com`. Luego login con email nuevo.
9. **POST `/students/{id}/resend-invitation` (ADMIN token)**. Esperar 200, `portal_access.invitation_sent_count = 2`, nuevo link. Probar ANTIGUO token → `invalid`, NUEVO token → `valid`.
10. **POST `/students/{id}/revoke-portal-access` (ADMIN)**. Luego alumno login con cualquier credencial válida → `403 inactive` o `401 bad`.
11. **GET `/me/attendance?limit=12` (ALUMNO token)**. Si no hay asistencias devuelve []. Probar `?limit=13` → 422.
12. **GET `/me/attendance/summary` (ALUMNO)**. Si no hay asistencias → `total_attendances=0, streak_days=0`.

---

## Risks

| Riesgo | Prob | Impacto | Mitigación |
|--------|------|---------|------------|
| Circular imports auth ↔ students ↔ me | Alta | Alto | Usar imports locales dentro de funciones o mover `utc_now` a `app/core/dates.py`. |
| SQLAlchemy `Student.user_id = ...` no se persiste por olvido `db.flush()` o `commit()` | Alta | Medio | 2 commits: primero Student solo, luego flujo portal con flush y commit. |
| Email placeholder `@pendiente` choca con constraint UNIQUE `users.email` | Baja | Medio | unique_code es unique, así que email también es unique. Validar antes de crear User. |
| Admin llama `resend-invitation` pero `student.user_id` es None (no se creó User en create) | Media | Alto | En resend: si user_id None → crear User flujo normal (mismo que create_student 2B). |
| `/me/attendance` devuelve asistencia de otro alumno por bug de filtros | Baja | CRÍTICO | **Hardcodear predicado `Attendance.student_id == student.id`** como primera condición del query, en código independiente de los query params. Nunca confiar en query param student_id. El endpoint NO debe aceptar `student_id` como query param. |
| Redeem con mismo email que admin existente | Baja | Medio | `get_user_by_email()` antes de guardar. Si existe y no coinciden IDs → 409. |
| `TokenResponse` devuelve `user.password_hash` por mal schema UserRead | Muy Baja | Alta | Revisar `UserRead` schema no contiene `password_hash`. |
