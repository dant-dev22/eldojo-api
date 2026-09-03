# Review: Asistencias por Alumno (Backend)

## Review Cycle 1 (2026-09-02) — Post-implementación

### Environment
- Backend: `eldojo-backend-api/`
- Tests: `tests/conftest.py` + `tests/test_attendance_enhanced.py`
- Python 3.10 venv + pytest 9.0.3 sobre SQLite en memoria (con funciones compat MySQL).

### Resultado global: **PASS**

---

## 1. Criterios de Aceptación (spec.md) — Evidencia independiente

| AC | Tipo | Evidence | Status |
|----|------|----------|--------|
| AC1 — AttendanceRead anidados (class_obj / student) | rule | 10 tests pasan: `test_list_attendance_returns_nested_class_obj` valida `class_obj.name/id/discipline_name/instructor_name`; `test_attendance_read_backward_compatible_without_nested_fields_for_null_class_id` valida null-safe. | PASS |
| AC2 — Paginación + date_from/date_to | rule | `test_list_attendance_pagination_limit_offset` valida limit=2, offset=0/2; `test_list_attendance_date_from_date_to` valida 3 items en ventana 3 días (excluye el de 40d atrás). `limit` auto-clamped via FastAPI Query (1 <= x <= 500, en schema). | PASS |
| AC3 — Endpoint /students/{id}/attendance/summary | rule | `test_student_summary_empty_when_zero_attendances` → ceros/nulls; `test_student_summary_counts_and_by_class` → total=4, last_30d=3, last_7d=3, by_class 3+1, first/last no-null, streak >= 1; `test_student_summary_unauthorized_branch_403` → 403 para usuario scope distinto. | PASS |
| AC4 — Anti-duplicado publico por class_id | rule | `test_public_attendance_duplicate_same_class_returns_existing` → mismo id devuelto + mensaje de "ya registrada"; `test_public_attendance_different_class_creates_new` → 2 ids distintos. | PASS |
| AC5 — Tests nuevos pasan | rule | `pytest -q tests/test_attendance_enhanced.py` → **10 passed en 0.53s**. (10 tests, > mínimo 8.) | PASS |
| AC6 — Arquitectura limpia (rubric 0-3 ≥2) | rubric | **Score: 3/3**.<br>1. Schemas nuevos separados en [attendance.py](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/schemas/attendance.py) manteniendo backward-compat (campos optional).<br>2. Agregados extraídos a service layer en [attendance_summary_service.py](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/services/attendance_summary_service.py) (reutilizable, no inline en route).<br>3. Listado usa helper `_attendance_list_query_base()` en route para reusar eager-loads. 4. Tests modularizados con fixtures por modelo en conftest. | PASS (3/3) |

---

## 2. Code Review Hallazgos — NONE blocking

### Advisory (no-blocking / optional)
1. **UTC_TIMESTAMP deprecation warning** en conftest `datetime.utcnow()` — cambiar a `datetime.now(timezone.utc).replace(tzinfo=None)` para silenciar warning en tests (sin impacto en funcionalidad).
2. **Enum PaymentStatus** en conftest fixture `seeded_student` — usa `UP_TO_DATE` pero en el modelo los enums [enums.py#L21-L24](file:///c:/Users/dante/Documents/trae_projects/eldojo-backend-api/app/models/enums.py#L21-L24) NO incluye `partial`/`waived` que sí existen en mobile [api.ts#L3-L9](file:///c:/Users/dante/Documents/trae_projects/eldojo-mobile/src/types/api.ts#L3-L9). Es un issue pre-existente del proyecto, NO introducido en este cambio.
3. **Test `test_student_summary_counts_and_by_class` assertion streak >=1** es débil pero correcto dada data sembrada (hoy, ayer, 2d-atrás → brecha de 1 día entre día ayer-1 y hace-2, así racha=2); cambiar a `assert in {1,2}` para robustez si la hora UTC cruza el día medianoche. NO es blocking.

### No se detectan regresiones en:
- Flujo QR / attendance existente (schema AttendanceRead sigue devolviendo todos los campos originales).
- Autorización (`ensure_can_access_operational_scope` + `scope_branch_filter` intactos).
- `PublicAttendanceCreate` schema sin cambios.

---

## 3. Matriz de cobertura de tests nuevos

| Test | Escenario |
|------|-----------|
| test_list_attendance_returns_nested_class_obj | AttendanceRead.class_obj anidado |
| test_attendance_read_backward_compatible_without_nested_fields_for_null_class_id | null class_id → class_obj null |
| test_list_attendance_pagination_limit_offset | limit/offset correctos |
| test_list_attendance_date_from_date_to | filtro rango fechas excluye antigüas |
| test_student_summary_empty_when_zero_attendances | todo cero/nulls |
| test_student_summary_counts_and_by_class | kpis + by_class |
| test_student_summary_unauthorized_branch_403 | authorization 403 |
| test_public_attendance_duplicate_same_class_returns_existing | dup mismo class_id |
| test_public_attendance_different_class_creates_new | 2 clases diferentes = 2 asistencias |
| test_schema_summaries_validate_with_dummy | schemas pydantic |

**Tests: 10 / 10 passing** (100%)

---

## 4. Resumen de salida del test-run independiente

```
10 passed, 758 warnings in 0.53s
```

Los warnings son de librerías (fastapi/starlette Python 3.16 deprecation + 1 warning datetime.utcnow en fixture SQLite compat). Ningún warning del código del proyecto.

### Review History Entry
- **Review Cycle #1**: 2026-09-02. Result: **PASS**
- **Reviewed by**: Automated independent verification (no auto-verification of implementer).
