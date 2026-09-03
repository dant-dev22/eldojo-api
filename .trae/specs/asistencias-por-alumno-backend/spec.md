# Especificación: Asistencias por Alumno (Backend)

## Problema
Actualmente los endpoints de asistencia devuelven únicamente IDs (class_id, student_id) como integers, sin datos anidados del nombre de la clase, disciplina, ni datos del alumno. Esto obliga al frontend a hacer N+1 queries para obtener el nombre de cada clase cuando muestra el historial de asistencias de un alumno. Además, no existe un endpoint de resumen de asistencias por alumno (KPIs: totales, últimos 7/30 días, desglose por clase, racha). También, la lógica anti-duplicado en el flujo público evita registros por alumno dentro de una ventana de 8h, pero no discrimina por clase, por lo que un alumno NO puede registrar asistencia a dos clases distintas en el mismo día (p.ej. Jiu Jitsu 7am + Muay Thai 7pm), lo cual es un caso de uso válido.

## Usuarios Afectados
- Administradores (org_admin, branch_admin, super_admin) que consultan la ficha de un alumno.
- Futuros reportes/dashboards de asistencia.
- Frontend móvil en StudentDetailView.

## Objetivos
1. Devolver, en cada registro de asistencia, los datos anidados (resumidos) de la clase (id, name, discipline_name, instructor_name) y del alumno (id, unique_code, first_name, last_name) cuando corresponda, para eliminar N+1 queries.
2. Disponibilizar un endpoint de resumen/estadísticas de asistencias por alumno.
3. Añadir paginación y filtros por rango de fechas al listado de asistencias.
4. Permitir doble check-in en el mismo día cuando las clases sean DIFERENTES en el flujo público (anti-duplicado ajustado por class_id).
5. Añadir tests unitarios con mocks para toda la funcionalidad nueva.

## No Objetivos
- Modificar el modelo de datos Attendance (ya tiene todos los campos necesarios).
- Cambiar el flujo existente de escaneo QR en el dashboard admin (solo consumirán los nuevos datos anidados sin cambios adicionales).
- Implementar reporting avanzado (PDF, gráficos), solo datos crudos y agregados.

## Requerimientos Funcionales
### RF1 — Schemas anidados para Attendance
- [schemas/attendance.py] AttendanceRead incluirá, de forma opcional y compatible hacia atrás:
  - `class_obj` (opcional, MartialClassReadSummary): id, name, discipline_name, instructor_name.
  - `student` (opcional, StudentReadSummary): id, unique_code, first_name, last_name.
- [schemas/attendance.py] Crear schemas `MartialClassReadSummary` y `StudentReadSummary` para este fin.
- Ambos son opcionales: si la relación es null (class_id null), el campo se omite o es null.

### RF2 — Listado de asistencias optimizado
- [routes/attendance.py] GET /attendance aceptará nuevos query params opcionales:
  - `date_from` (YYYY-MM-DD, filtrar check_in_at >= inicio del día).
  - `date_to` (YYYY-MM-DD, filtrar check_in_at <= fin del día).
  - `limit` (int >=1, default 100, max 500).
  - `offset` (int >=0, default 0).
- El listado debe usar `selectinload(Attendance.class_obj, Attendance.student, MartialClass.discipline)` para cargar relaciones en 1 query.
- Orden: `check_in_at DESC, id DESC`.

### RF3 — Endpoint de resumen por alumno
- [routes/students.py o attendance.py] Nuevo endpoint GET `/students/{student_id}/attendance/summary` autenticado.
- Retorna:
  - `student_id` (int)
  - `total_attendances` (int)
  - `last_7_days` (int, check_in_at >= now_utc - 7d)
  - `last_30_days` (int, check_in_at >= now_utc - 30d)
  - `by_class`: `[{class_id, class_name, count}]` para cada clase con >=1 asistencia.
  - `first_attendance_at` (datetime | null)
  - `last_attendance_at` (datetime | null)
  - `streak_days` (int: racha actual de días consecutivos con al menos 1 asistencia, contando desde la más reciente hacia atrás; si no hay asistencias, 0).
- Debe respetar los scopes de autorización (ensure_can_access_operational_scope sobre la org/branch del alumno).

### RF4 — Anti-duplicado ajustado por clase en flujo público
- [routes/public_attendance.py] La query de "existing_attendance" en create_public_attendance discriminará por class_id:
  - Si `payload.class_id IS NOT NULL`: buscar duplicados dentro de la ventana 8h CON la MISMA class_id.
  - Si `payload.class_id IS NULL`: mantener comportamiento actual (sin distinguir clase).
- De esta forma, un alumno sí puede tener 2 asistencias en 8h si son clases distintas.

### RF5 — Tests unitarios con mocks
- Crear carpeta tests/ en el repo si no existe.
- Tests con pytest usando SQLAlchemy Session sobre SQLite en memoria (o mocks), fastapi TestClient, y mocks de dependencias auth (no requieren JWT real).
- Casos mínimos a cubrir:
  - list_attendance devuelve class_obj anidado.
  - list_attendance filtra correctamente por date_from / date_to.
  - list_attendance aplica limit y offset.
  - endpoint summary devuelve KPIs correctos para 0, 1 y N asistencias.
  - anti-duplicado: mismo class_id => retorna existente; distinto class_id => crea registro nuevo.
  - summary autorización 403 para alumno ajeno a la branch.

## Requerimientos No Funcionales
- NFR1 (Backward compatible): Todo cambio en schemas existentes debe ser aditivo (campos opcionales). Ningún consumer existente se debe romper.
- NFR2 (Performance): GET /attendance con relaciones anidadas usa máximo 3 queries (1 para count de total sería extra pero opcional; no requerido en esta fase).
- NFR3 (Seguridad): Endpoint nuevo summary debe usar el mismo scope filter de authorization.
- NFR4 (Tipado): Todos los schemas nuevos tipados estrictamente con Pydantic v2; ningún `Any`.
- NFR5 (Tests): Al menos 8 tests unitarios nuevos que pasen con `pytest tests/test_attendance_enhanced.py`.

## Restricciones y Dependencias
- Dependencias: FastAPI, Pydantic v2, SQLAlchemy 2.x, pytest.
- Restricción: NO modificar tablas existentes ni crear migraciones.
- Restricción: El enum AttendanceMethod no cambia.

## Suposiciones
- El frontend ya está consumiendo `AttendanceRead` y la adición de campos opcionales no causa regresiones.
- Para `streak_days`, contamos días (calendario) consecutivos, check_in_at convertido a UTC (no por timezone de branch; simplificación acordada; se puede mejorar en iteración futura).
- `by_class` incluye solo class_id no nulos; asistencias con class_id=null no aparecen en el breakdown (no tienen clase).

## Criterios de Aceptación
### (rule) AC1 — AttendanceRead con class_obj y student opcionales
- El schema AttendanceRead incluye los campos opcionales `class_obj` y `student`.
- Un GET /attendance?student_id=X retorna cada asistencia con `class_obj` poblado (donde class_id no sea null).

### (rule) AC2 — Paginación y filtros por fecha
- GET /attendance?date_from=2026-09-01&date_to=2026-09-30&limit=5&offset=0 retorna máximo 5 registros en ese rango.
- Ignorar límite: default 100, máximo 500. Si se pasa limit>500 debe clamp a 500.

### (rule) AC3 — Endpoint de resumen
- GET /students/{id}/attendance/summary devuelve la estructura RF3.
- Para un alumno con 0 asistencias: totals=0, streaks=0, first/last=null, by_class=[].

### (rule) AC4 — Anti-duplicado por clase
- POST /public/attendance/org/branch con mismo class_id y alumno en 8h => retorna 201 con attendance existente y mensaje "Asistencia ya registrada...".
- POST distinto class_id en mismo alumno en 8h => retorna 201 con registro NUEVO y attendance_id diferente.

### (rule) AC5 — Tests nuevos pasan
- pytest tests/test_attendance_enhanced.py exit code 0, >=8 tests pasan.

### (rubric) AC6 — Arquitectura limpia (escala 0-3, umbral >=2)
- 3: schemas nuevos coherentes, endpoints nuevos en router correcto, lógica agregada en services/ o helpers reutilizable en lugar de inline.
- 2: todo funciona pero lógica de aggregation inline en route, sin helper.
- 1: funciona pero con duplicación o desviación de convenciones.
- 0: regresiones o código no idiomático.
