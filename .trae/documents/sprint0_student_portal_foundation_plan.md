# Sprint 0: Fundamentos del Portal del Alumno

## Repository Research

### Estado actual de la arquitectura
- **ORM**: SQLAlchemy 2.x con `DeclarativeBase` en [base.py](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/db/base.py)
- **Patrón de modelos**: Los modelos se declaran con type hints estilo `Mapped[T]` y `mapped_column()` — se replica exactamente la estructura de [email_verification.py](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/models/email_verification.py#L13-L32)
- **Registro de modelos**: Todo modelo ORM debe aparecer en doble lugar:
  1. `app/models/__init__.py` ([models/__init__.py](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/models/__init__.py#L1-L45)) — import + `__all__`
  2. `tests/conftest.py` ([conftest.py](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/tests/conftest.py#L16-L37)) — import `# noqa: F401` para que `Base.metadata.create_all()` lo detecte en tests
- **Migraciones**: No hay Alembic. Se usa `Base.metadata.create_all()` directo en el test runner SQLite. Para producción se entregará un script SQL manual ejecutable con `source migrations/sql/00X_*.sql`.
- **Schemas Pydantic**: Separados por dominio en `app/schemas/*.py`. `StudentBase` / `StudentCreate` / `StudentRead` en [student.py](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/schemas/student.py). `from_attributes=True` para mapeo ORM directo.
- **Settings**: Dataclass frozen con `os.getenv()` defaults en [config.py](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/core/config.py#L35-L83). Nuevos settings siguen el patrón.

### Convenciones descubiertas
1. **Valores moneda/email**: Siempre tienen `@field_validator` de normalización (`.strip().upper()` / `.strip().lower()`).
2. **Enums**: Se importan de `app.models.enums` en schemas.
3. **Optional fields**: Se declaran `X | None = None` con validadores tolerantes a `None`.
4. **IDs**: Siempre `Field(gt=0)`.
5. **Strings**: Siempre `Field(min_length=X, max_length=Y)`.
6. **Strings sensibles (passwords)**: min_length=8, max_length=128 (igual que `LoginRequest`).

---

## Files and Modules

| # | Ruta | Cambio |
|---|------|--------|
| 1 | `app/models/student_invitation.py` (NUEVO) | Modelo ORM `StudentInvitationToken` — análogo a `EmailVerificationToken` + campos específicos de invitación alumno |
| 2 | `app/models/__init__.py` | Registrar nuevo import + añadir a `__all__` |
| 3 | `tests/conftest.py` | Import `from app.models.student_invitation import StudentInvitationToken  # noqa: F401` |
| 4 | `migrations/sql/001_student_invitation_tokens.sql` (NUEVO) | Script SQL DDL MySQL de producción para crear la tabla |
| 5 | `app/schemas/student.py` | Extender `StudentCreate` con `enable_portal_access` + `student_email`; Agregar `StudentPortalAccessStatus` + campo `portal_access` en `StudentRead` |
| 6 | `app/schemas/auth.py` | Agregar `StudentInvitationPreviewResponse` + `StudentInvitationRedeemRequest` + `@model_validator` de match passwords |
| 7 | `app/core/config.py` | Agregar settings `student_invitation_token_expire_days` + `student_invitation_url_base` |

---

## Implementation Steps (Dependency Order)

### Paso 1 — Settings (config.py)
1. Agregar en la clase `Settings`, antes de `smtp_host`:
   ```python
   student_invitation_token_expire_days: int = int(
       os.getenv("STUDENT_INVITATION_TOKEN_EXPIRE_DAYS", "7")
   )
   student_invitation_url_base: str = os.getenv(
       "STUDENT_INVITATION_URL_BASE",
       "http://localhost:8081/activar",  # web build alumno
   )
   ```
2. Validación en import-time no requerida (son con defaults seguros).

### Paso 2 — Nuevo Modelo ORM (student_invitation.py)
Crear archivo copiando la estructura de `EmailVerificationToken` pero con:
- Tabla: `student_invitation_tokens`
- Campos obligatorios:
  - `id` PK
  - `student_id` FK a `students.id` ON DELETE CASCADE — `nullable=False` (invitación pertenece a un alumno)
  - `user_id` FK a `users.id` ON DELETE CASCADE — `nullable=True` (puede no existir User aún si el admin marcó enable pero no rellenó email; o se crea después)
  - `token_hash` String(64) nullable=False, UNIQUE (hash sha256 del token plano que enviamos)
  - `token_plain_tail` String(8) nullable=True — últimos 8 chars para debug/logs sin exponer el hash entero
  - `expires_at` DateTime, nullable=False (created_at + expire_days)
  - `used_at` DateTime | None
  - `sent_count` Integer, default=1 (cuántas veces admin reenvió; se incrementa en POST resend)
  - `created_by_admin_id` FK a `users.id` ON DELETE SET NULL — nullable=True (cuál admin lo generó; auditoría)
  - `email_sent_to` String(255) nullable=True — email al que se le envió; si admin no llenó email, queda NULL y el alumno lo escribe en redeem
  - `created_at` DateTime con `server_default=text("CURRENT_TIMESTAMP")`
- Relationships:
  - `student = relationship("Student", back_populates="invitation_tokens")`
  - `user = relationship("User", foreign_keys=[user_id], back_populates="student_invitations_owned")`
  - `created_by_admin = relationship("User", foreign_keys=[created_by_admin_id])`
- **Importante**: No olvidar que `Student` y `User` deben tener los `back_populates` correspondientes en sus archivos (revisar los modelos Student y User, agregar `invitation_tokens` y `student_invitations_owned` como `relationship` default empty list; si Student no tiene el atributo todavía, agregarlo; pero NO tocar back_populates si se generan circular imports — si pasa, usar string lazy references).

### Paso 3 — Registrar modelo
- `app/models/__init__.py`: `from app.models.student_invitation import StudentInvitationToken` + agregar a `__all__`
- `tests/conftest.py`: Import del modelo con comentario `# noqa: F401` (como los demás)

### Paso 4 — Migración SQL manual
Crear `migrations/sql/001_student_invitation_tokens.sql`:
```sql
-- Requiere MySQL 8.x
CREATE TABLE IF NOT EXISTS student_invitation_tokens (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT NOT NULL,
    user_id INT NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    token_plain_tail VARCHAR(8) NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    sent_count INT NOT NULL DEFAULT 1,
    created_by_admin_id INT NULL,
    email_sent_to VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sit_student FOREIGN KEY (student_id)
        REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_sit_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_sit_admin FOREIGN KEY (created_by_admin_id)
        REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_sit_student_id (student_id),
    INDEX idx_sit_user_id (user_id),
    INDEX idx_sit_token_hash (token_hash),
    INDEX idx_sit_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```
Nota: La carpeta `migrations/sql/` no existe — hay que crearla.

### Paso 5 — Schemas Student (student.py)
1. Agregar EN LA PARTE SUPERIOR DEL ARCHIVO (antes de `StudentBase`):
   ```python
   class StudentPortalAccessStatus(BaseModel):
       has_linked_user: bool = False
       user_is_active: bool | None = None
       user_email_verified: bool | None = None
       pending_invitation_exists: bool = False
       invitation_expires_at: datetime | None = None
       invitation_sent_count: int = 0
       invitation_link: str | None = None
       invitation_email_sent_to: str | None = None
   ```
2. Modificar `StudentCreate`:
   - No heredar de StudentBase directamente — agregar campos EXTRA:
   ```python
   class StudentCreate(StudentBase):
       enable_portal_access: bool = False
       student_email: str | None = Field(default=None, max_length=255)

       @field_validator("student_email")
       @classmethod
       def normalize_student_email(cls, value: str | None) -> str | None:
           if value is None or not value.strip():
               return None
           return value.strip().lower()
   ```
   Nota: Si `enable_portal_access=True` y `student_email` None, es válido — alumno escribirá su email al canjear.
3. Modificar `StudentRead`:
   - Agregar campo al final: `portal_access: StudentPortalAccessStatus | None = None`
4. `StudentProfileCompleteness` se queda como está.

### Paso 6 — Schemas Auth (auth.py)
1. Agregar al FINAL del archivo:
   ```python
   class StudentInvitationPreviewResponse(BaseModel):
       status: str = "valid"  # "valid" | "expired" | "used" | "invalid"
       message: str
       first_name: str | None = None
       last_name: str | None = None
       unique_code: str | None = None
       suggested_email: str | None = None
       dojo_name: str | None = None
       expires_at: datetime | None = None
   ```
   (Nota: Pydantic `datetime` requiere `from datetime import datetime` — revisar si auth.py lo importa ya; si no, agregar.)

2. Agregar `StudentInvitationRedeemRequest`:
   ```python
   class StudentInvitationRedeemRequest(BaseModel):
       token: str = Field(min_length=16, max_length=512)
       email: str | None = Field(default=None, max_length=255)
       password: str = Field(min_length=8, max_length=128)
       confirm_password: str = Field(min_length=8, max_length=128)
       accept_terms: bool = Field(..., description="Aceptar términos de uso y privacidad")

       @field_validator("email")
       @classmethod
       def normalize_email_optional(cls, value: str | None) -> str | None:
           if value is None or not value.strip():
               return None
           return value.strip().lower()

       @model_validator(mode="after")
       def validate_password_match_and_terms(self) -> "StudentInvitationRedeemRequest":
           if self.password != self.confirm_password:
               raise ValueError("Las contraseñas no coinciden")
           if not self.accept_terms:
               raise ValueError("Debes aceptar los términos para activar tu cuenta")
           return self
   ```

---

## Dependencies and Considerations

1. **Circular imports en relationships**: Si al agregar `back_populates` en `Student` y `User` causa circular import con `student_invitation`, cambiar a `lazy='dynamic'` o usar strings en back_populates (`relationship("StudentInvitationToken", back_populates="student", lazy="noload", default_factory=list)`) o mejor aún: dejar el modelo `StudentInvitationToken` con `primaryjoin` explícito y NO declarar back_populates en los padres si causa problemas (solo los hijos lo tienen). En el Sprint 0, el objetivo es que el modelo se importe sin romper; no usaremos las relationships aún — el Sprint 1 lo implementa en queries.
2. **Email en Student vs Email en User**: Actualmente `Student.email` (de [student.py schema](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/schemas/student.py#L42)) es el email de contacto del alumno (padre/tutor o alumno adulto). El `StudentCreate.student_email` NUEVO es el email que se usará para `User.email`. Son cosas distintas. No mezclar. No hay que borrar el `email` existente de `StudentBase`.
3. **Settings con valores por default**: No rompen builds existentes. Todo tiene default seguro.
4. **Campo `token_plain_tail`**: Es para auditoría únicamente; no permite reconstruir el token. Solo se guardan los últimos 8 chars para poder buscar en logs.
5. **`StudentCreate` hereda de `StudentBase`**: Agregamos los 2 campos NUEVOS. No hay problema porque son `bool` y `Optional[str]` con defaults. No rompe el endpoint `create_student` existente porque todos los clients envían JSON — FastAPI simplemente ignora los campos extra que el client no envía (usa defaults). Zero breaking changes.
6. **`StudentRead.portal_access`** = `Optional[StudentPortalAccessStatus]` = None por default. Los endpoints de listado de alumnos simplemente no lo poblarán (quedará `None`) hasta el Sprint 1 donde modificamos `create_student` y `get_student`. Zero impacto ahora.

---

## Validation

Después de escribir todos los archivos, ejecutar estas verificaciones EN ORDEN:

### Check 1 — Imports y sintaxis
```powershell
cd c:\Users\dante\Documents\trae_projects\eldojo-backend-api
python -c "from app.models.student_invitation import StudentInvitationToken; print('Modelo OK')"
python -c "from app.schemas.student import StudentCreate, StudentRead, StudentPortalAccessStatus; print('Schemas Student OK')"
python -c "from app.schemas.auth import StudentInvitationPreviewResponse, StudentInvitationRedeemRequest; print('Schemas Auth OK')"
python -c "from app.core.config import settings; print(settings.student_invitation_token_expire_days, settings.student_invitation_url_base); print('Settings OK')"
python -c "from app.models import *; print('__init__ models OK')"
```

### Check 2 — FastAPI carga sin errores
```powershell
cd c:\Users\dante\Documents\trae_projects\eldojo-backend-api
python -c "from app.main import app; print('App carga OK. Rutas:', len(app.routes))"
```

### Check 3 — Pydantic validators tests manuales
```python
from app.schemas.auth import StudentInvitationRedeemRequest

# Debe fallar: passwords no coinciden
try:
    req = StudentInvitationRedeemRequest(token="a"*32, email="test@test.com", password="pass12345", confirm_password="nocoincide", accept_terms=True)
    print("❌ No falló passwords distintas — ERROR")
except ValueError as e:
    print("✅ OK:", e)

# Debe fallar: no acepta términos
try:
    req = StudentInvitationRedeemRequest(token="a"*32, email="test@test.com", password="pass12345", confirm_password="pass12345", accept_terms=False)
    print("❌ No falló términos — ERROR")
except ValueError as e:
    print("✅ OK:", e)

# Debe pasar
req = StudentInvitationRedeemRequest(token="a"*32, email="Test@Test.COM  ", password="pass12345", confirm_password="pass12345", accept_terms=True)
print("✅ OK. Normalizado email:", req.email)
```

### Check 4 — Test suite existente sigue pasando
```powershell
cd c:\Users\dante\Documents\trae_projects\eldojo-backend-api
python -m pytest tests/ -x -q --tb=short 2>&1 | Select-Object -Last 25
```
**Regla**: Los tests preexistentes deben seguir PASANDO al 100%. Si algo falla, no es por el modelo nuevo (create_all SQLite lo auto crea), pero sí puede ser por circular import. Arreglar en ese caso.

### Check 5 — Validador de Pydantic para StudentCreate.student_email
```python
from datetime import date
from app.schemas.student import StudentCreate
from app.models.enums import PaymentStatus, StudentStatus

payload = {
  "organization_id": 1,
  "branch_id": 1,
  "first_name": "Juan",
  "last_name": "Pérez",
  "birth_date": date(2000, 1, 1),
  "birth_place": "GDL",
  "enrollment_date": date(2025, 1, 1),
  "payment_status": PaymentStatus.UP_TO_DATE,
  "status": StudentStatus.ACTIVE,
  "enable_portal_access": True,
  "student_email": "JUAN@TEST.COM  ",
}
s = StudentCreate(**payload)
assert s.student_email == "juan@test.com", "Email no normalizado"
assert s.enable_portal_access is True
print("✅ StudentCreate nuevo OK")
```

---

## Risks

| Riesgo | Impacto | Probabilidad | Mitigación |
|--------|---------|--------------|------------|
| **Circular imports** al agregar relationships en `Student` / `User` | Alto | Media | **No agregar back_populates en padres en este Sprint**. Solo declararlos cuando se necesiten en queries (Sprint 1). Si es obligatorio, usar `from __future__ import annotations` (ya está activo) + strings. |
| Tests fallan porque `Base.metadata.create_all()` no crea la tabla nueva | Medio | Baja | Asegurar que `tests/conftest.py` tenga el import `# noqa: F401`. Validar en Check 1 y 4. |
| FastAPI no carga por error en schema `StudentInvitationRedeemRequest` `@model_validator(mode="after")` | Medio | Baja | `mode="after"` requiere Pydantic >= 2.0. El proyecto ya usa pydantic v2 (ConfigDict). Si hubiese error, degradar a `@field_validator` temporal — pero el proyecto ya usa `@model_validator(mode="after")` en [StudentBase](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/schemas/student.py#L63). |
| SQL migration falla en MySQL porque `FOREIGN KEY ON DELETE SET NULL` requiere columna `created_by_admin_id` nullable | Bajo | Baja | El modelo lo declara nullable. El script SQL coincide. |
| Campo `email_sent_to` 255 chars muy corto | Bajo | Baja | RFC 5321 dice que path email es máximo 254 chars. 255 es aceptable; si se rompe, es porque el email del alumno es inválido (lo normaliza el validator anyway). |
