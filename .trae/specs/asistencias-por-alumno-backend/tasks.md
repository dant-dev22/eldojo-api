# Tasks: Asistencias por Alumno (Backend)

## Task 1: Ampliar schemas de asistencia con anidados (AttendanceRead + summaries)
**Priority**: high
**Dependencies**: (ninguna)
**Status**: pending

### Work
- Editar `app/schemas/attendance.py`:
  - Crear `MartialClassReadSummary` (id, name, discipline_name, instructor_name, ConfigDict from_attributes=True).
  - Crear `StudentReadSummary` (id, unique_code, first_name, last_name, from_attributes=True).
  - Añadir `AttendanceRead.class_obj: MartialClassReadSummary | None = None`.
  - Añadir `AttendanceRead.student: StudentReadSummary | None = None`.
- Crear nuevo schema `AttendanceSummaryPerClass` (`class_id: int`, `class_name: str`, `count: int`).
- Crear nuevo schema `StudentAttendanceSummary`:
  - student_id: int
  - total_attendances: int
  - last_7_days: int
  - last_30_days: int
  - by_class: list[AttendanceSummaryPerClass]
  - first_attendance_at: datetime | None
  - last_attendance_at: datetime | None
  - streak_days: int

### Test Requirements (local)
- **(rule) TR1.1**: `pydantic` valida instancias de cada schema nuevo con valores dummy (no-query).
- **(rule) TR1.2**: `AttendanceRead` serializa OK SIN `class_obj` ni `student` (backward-compat sin cambios en campos antiguos).

---

## Task 2: Mejorar GET /attendance (paginación, fechas, selectinload)
**Priority**: high
**Dependencies**: Task 1
**Status**: pending

### Work
- Editar `app/api/routes/attendance.py`:
  - Añadir imports: `from datetime import datetime, timedelta, timezone`, `from sqlalchemy.orm import selectinload`.
  - Añadir query params a `list_attendance`: `date_from: date | None = Query(default=None)`, `date_to: date | None = Query(default=None)`, `limit: int = Query(default=100, ge=1, le=500)`, `offset: int = Query(default=0, ge=0)`.
  - Construir query base con `selectinload(Attendance.class_obj).selectinload(Attendance.class_obj.discipline).selectinload(Attendance.student)`.
  - Filtros: `date_from` => `check_in_at >= datetime.combine(date_from, time.min)`; `date_to` => `check_in_at <= datetime.combine(date_to, time.max)`.
  - Añadir `.limit(limit).offset(offset)` al final.
  - Mantener autorización scope branch filter existente.

### Test Requirements
- **(rule) TR2.1**: Listado con limit=2 y offset=0 retorna máximo 2 items.
- **(rule) TR2.2**: date_from/date_to excluyen items fuera del rango.
- **(rule) TR2.3**: Los items incluyen `class_obj` cuando `class_id` no es null (schema anidado serializa).

---

## Task 3: Nuevo endpoint GET /students/{student_id}/attendance/summary
**Priority**: high
**Dependencies**: Task 1, Task 2
**Status**: pending

### Work
- Opción A (preferida): Añadir la ruta en `app/api/routes/students.py` (cohesivo con el recurso students) O en el mismo `attendance.py`. Mantener consistencia con rutas existentes (preferible `students.py` ya que es la ficha del alumno). Se añadirá `GET /students/{student_id}/attendance/summary` response_model=StudentAttendanceSummary.
- Agregar lógica helper (puede ser inline o en `app/services/attendance_summary_service.py`) para calcular:
  - Totales.
  - last_7_days / last_30_days (ventanas UTC).
  - first/last attendance_at.
  - by_class: group by class_id, left join MartialClass para nombre, contar (excluye class_id null).
  - streak_days: tomar check_in_at.date() DISTINCT ordenadas DESC, contar consecutivos desde la fecha más reciente (si última fecha no es hoy, la racha puede ser 0 o X según la brecha con hoy? Se interpreta como "racha más reciente" desde la última fecha hacia atrás).
- Autorización: obtener student por ID, asegurar que alumno exista y `ensure_can_access_operational_scope` sobre org/branch del alumno.

### Test Requirements
- **(rule) TR3.1**: Alumno sin asistencias retorna total=0, streaks=0, by_class=[].
- **(rule) TR3.2**: Alumno con 5 asistencias, 3 en los últimos 30 días, 2 en 7 días, by_class suma == total_attendances (excluyendo class_id nulls).
- **(rule) TR3.3**: Usuario sin permiso a esa branch => HTTP 403.

---

## Task 4: Anti-duplicado por class_id en create_public_attendance
**Priority**: high
**Dependencies**: (ninguna)
**Status**: pending

### Work
- Editar `app/api/routes/public_attendance.py`, sección `existing_attendance = db.scalar(...)`:
  - Si `payload.class_id is not None`: `Attendance.class_id == payload.class_id` AÑADIR al and_ de duplicados.
  - Si `payload.class_id is None`: no añadir condición extra (comportamiento actual).
- Añadir comentario breve explicando la semántica.

### Test Requirements
- **(rule) TR4.1**: Mismo class_id en 2 posts => retorna attendance_id idéntico (ya registrada).
- **(rule) TR4.2**: Distinto class_id en 2 posts => retorna attendance_id diferentes (2 asistencias creadas).

---

## Task 5: Setup tests con fixtures + tests nuevos
**Priority**: high
**Dependencies**: Task 1-4
**Status**: pending

### Work
- Crear carpeta `tests/` en el root del backend (eldojo-backend-api/tests/).
- Crear `tests/conftest.py` con fixtures:
  - `db_session`: SQLAlchemy Session sobre SQLite :memory:, crea todas las tablas (Base.metadata.create_all).
  - Fixtures de seed: `org`, `branch`, `discipline`, `class_a` (Jiu Jitsu), `class_b` (Muay Thai), `student1` (con user asociado ficticio O dejar user_id null si permite el schema; revisar constraints).
  - `app_test`: FastAPI TestClient que reemplaza `get_db` por la session en memoria y reemplaza `require_active_user` por un usuario dummy con permisos de org_admin en la org sembrada (dependency_overrides).
- Crear `tests/test_attendance_enhanced.py` con mínimo 8 tests cubriendo TR1.1-TR4.2.

### Test Requirements (suite)
- **(rule) TR5.1**: `pytest tests/test_attendance_enhanced.py -q` exit_code 0.
- **(rule) TR5.2**: >=8 tests descubiertos y pasan.
- **(rubric) TR5.3**: Calidad de tests (0-3, umbral >=2).
  - 3: Cada test cubre un escenario aislado, limpia state, nombres claros, asserts granular.
  - 2: Tests pasan, cubren escenarios pero con acoplamiento leve (ej: reutilizan datos sin reset).
  - 1: Tests pasan pero coverage de escenarios mínimo.
  - 0: Faltan tests o fallan.
