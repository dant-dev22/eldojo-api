# Flujo de Activación de Alumno con Código por Correo + Fix CORS

## Repository Research

### Arquitectura actual
- **Backend**: FastAPI (`eldojo-backend-api`) con SQLAlchemy + MySQL.
  - Invitaciones persistidas en `student_invitation_tokens` (modelo `StudentInvitationToken`), TTL fijo 48h.
  - Las invitaciones son tokens HMAC determinísticos guardados como hash SHA-256. `build_student_invitation_link()` arma `https://mi.eldojo.tech/activar?token={raw_token}`.
  - Endpoints: `GET /auth/student-invitation` (preview público), `POST /auth/student-invitation/redeem` (activar con password), `POST /students/{id}/resend-invitation` (admin genera/recupera link).
  - CORS: `CORSMiddleware` en `main.py` usa `settings.backend_cors_origins`, origen `https://mi.eldojo.tech` está en defaults.
  - Faltan settings **no declarados** en `config.py` pero usados en runtime: `academy_verification_token_expire_hours` y `academy_pending_session_expire_hours` (referenciados en `auth.py` líneas 127/129 y `mail.py` línea 69) → puede romper build/runtime.

- **Frontend**: Expo/React Native web (`eldojo-mobile`) compila 3 targets: `dist-admin`, `dist-student`, `dist`.
  - Pantalla actual `StudentActivateScreen.tsx` enruta en `/activar` y toma `?token=` del query string.
  - Admin `StudentsListScreen.tsx` → `handleCopyInvitationLink()` llama `studentsApi.ensureAndGetInvitation()` → `resend-invitation` si no había pendiente, luego copia link al portapapeles.
  - Navegación pública permite sin auth: `/`, `/activar`, `/confirmar-cuenta`, etc. (`isPublicAllowedWithoutAuth` en `AppNavigator.tsx`).

### Problemas reportados / cambio deseado
1. **CORS al abrir link en `mi.eldojo.tech/activar?token=...`** → falta robustez en middleware (expose_headers, max_age, preflight OPTIONS) y posiblemente variantes de origen.
2. **Cambiar flujo**:
   - Admin hace click en `screens-admin-students-list-row-portal-copy-button-*`.
   - Debe **enviar un código numérico/alfa al correo del alumno** (el que el admin cargó en `student.email`), TTL 24h.
   - El link sigue existiendo y abre la **nueva pantalla Activate Account** que muestra:
     - Datos del alumno/dojo + aviso de código enviado.
     - Input para el código de 6 dígitos.
     - Botón **"Confirmar cuenta"**.
     - Opcional: reenviar código.
   - Validación correcta del código → pasar al paso 2: password + términos (como el actual StudentActivateScreen) → redeem → cuenta activa.

## Files and Modules

### Backend (eldojo-backend-api)
- `app/core/config.py`: agregar settings faltantes `academy_verification_token_expire_hours`, `academy_pending_session_expire_hours`; ampliar defaults CORS.
- `app/main.py`: robustecer `CORSMiddleware` (expose_headers, max_age) + rutas OPTIONS explícitas si fuera necesario.
- `app/models/student_invitation.py`: columnas nuevas `verification_code_hash`, `verification_code_plain_tail`, `verification_code_sent_at`, `verification_code_expires_at`, `verification_code_verified_at`.
- `migrations/sql/004_student_verification_code.sql`: migración idempotente (IF NOT EXISTS).
- `app/core/mail.py`: helpers `build_student_verification_code_*`, `send_student_verification_code_email()` y plantilla de correo.
- `app/core/student_invitation.py`: funciones `generate_student_verification_code()`, `hash_student_verification_code()`, `issue_verification_code_for_invitation()` (24h).
- `app/api/routes/students.py`: `resend_student_invitation()` debe ahora **emitir código y mandarlo por correo**; devolver `email_sent_to` + `verification_code_sent` flag.
- `app/api/routes/auth.py`:
  - `preview_student_invitation`: exponer `verification_code_sent`, `verification_code_verified`, `verification_code_expires_at`.
  - `POST /auth/student-invitation/verify-code`: validar código y marcar `verification_code_verified_at` (sin canjear aún).
  - `redeem_student_invitation`: requerir que el código esté verificado (o que sea redeem legacy con warning).
- `app/schemas/auth.py`: schemas `StudentInvitationVerifyCodeRequest`, `StudentInvitationVerifyCodeResponse`; extender `StudentInvitationPreviewResponse`; extender `StudentInvitationRedeemRequest` con `challenge_token` opcional.
- `app/schemas/student.py`: extender `StudentPortalAccessStatus` con `verification_code_sent`, `verification_code_sent_to_email`.

### Frontend (eldojo-mobile)
- `src/types/api.ts`: agregar tipos `StudentInvitationVerifyCodePayload`, `StudentInvitationVerifyCodeResponse`; extender preview response con campos de código.
- `src/api/authApi.ts`: método `verifyStudentInvitationCode()`; actualizar redeem si cambia schema.
- `src/api/studentsApi.ts`: `EnsureInvitationResult` expone `email_sent` + `code_sent_to_email`.
- **`src/screens/auth/ActivateAccountScreen.tsx` (NUEVA)** — 2 pasos:
  - Paso 1: `?token=` → preview → form código 6 dígitos (OTP input estilizado) + botón "Confirmar cuenta" + reenviar.
  - Paso 2: verificación OK → form nombre/email/password/términos → redeem → auto-login.
  - Aplicar design system ui-ux-pro-max (ver más abajo).
- `src/navigation/types.ts`: `AuthStackParamList` agrega `ActivateAccount` (mantenemos `ActivateStudent` como alias legacy o redirect interno).
- `src/navigation/publicRoutes.ts`: ruta `activate-account` segment + `ActivateAccount` entry.
- `src/navigation/AppNavigator.tsx`: registrar screen `ActivateAccount`; asegurar permiso público en `isPublicAllowedWithoutAuth`.
- `src/screens/admin/StudentsListScreen.tsx`: feedback actualizado al presionar botón portal (avisar "Código enviado a {email}" y "Link copiado").

## Implementation Steps

### Paso 1 — Backend config & CORS (bajo riesgo)
1. Editar `config.py`:
   - Agregar `academy_verification_token_expire_hours: int = 48` (default) y `academy_pending_session_expire_hours: int = 24`.
   - Agregar setting `student_verification_code_expire_hours: int = 24`.
   - Extender defaults de `BACKEND_CORS_ORIGINS` con variantes `https://www.mi.eldojo.tech, https://www.eldojo.tech, https://www.app.eldojo.tech, https://www.admin.eldojo.tech`.
2. Editar `main.py`:
   - `CORSMiddleware` agregar `expose_headers=["Content-Type", "Content-Length", "Authorization", "X-Request-ID"]` y `max_age=3600`.

### Paso 2 — Modelo + migración verification_code
1. En `models/student_invitation.py` agregar 5 columnas nuevas (todas nullable para compatibilidad con filas legacy).
2. Crear `migrations/sql/004_student_verification_code.sql` con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (MySQL: usar stored procedure idempotente típico o `CREATE PROCEDURE`/INFORMATION_SCHEMA check).
3. `app/models/__init__.py` si fuera necesario, pero StudentInvitationToken ya se importa.

### Paso 3 — Core: generación, hash y envío de código
1. `core/student_invitation.py`:
   - Constante `STUDENT_VERIFICATION_CODE_LENGTH=6`, `STUDENT_VERIFICATION_CODE_CHARSET="0123456789"` (numérico 0-9).
   - `generate_student_verification_code() -> str`.
   - `hash_student_verification_code(code: str) -> str` (reutiliza `hash_email_verification_token` ya que es SHA-256).
   - `issue_verification_code_for_invitation(db, invitation, student_email)`: escribe en invitación los campos `verification_code_hash/plain_tail/sent_at/expires_at` y limpia `verified_at` (por defecto 24h).
2. `core/mail.py`:
   - `build_student_verification_code_email_body(recipient_name, dojo_name, code, expires_hours)`.
   - `send_student_verification_code_email(recipient_email, recipient_name, dojo_name, code, expires_hours=24)` -> bool; captura `MailDeliveryError` y devuelve False sin romper caller.

### Paso 4 — Schemas nuevos
1. `schemas/auth.py`:
   - `StudentInvitationVerifyCodeRequest(token: str, code: str)`.
   - `StudentInvitationVerifyCodeResponse(status: "ok"|"wrong_code"|"expired"|"invalid", message: str, challenge_token: str | None)`.
   - `StudentInvitationPreviewResponse` agrega: `verification_code_sent: bool`, `verification_code_verified: bool`, `verification_code_expires_at: datetime | None`, `verification_code_masked_email: str | None`.
   - `StudentInvitationRedeemRequest` agrega opcional `challenge_token: str | None`.
2. `schemas/student.py`:
   - `StudentPortalAccessStatus` agrega `verification_code_sent: bool`, `verification_code_sent_to_email: str | None`.

### Paso 5 — Endpoints de invitación & redeem
1. `routes/students.py` `resend_student_invitation`:
   - Después de crear/recuperar la invitación y el User, **siempre** `issue_verification_code_for_invitation` y `send_student_verification_code_email` al `email_sent_to` o `student.email`; actualizar `sent_count`.
   - Devolver `portal_access` con flags nuevos.
2. `routes/auth.py`:
   - `preview_student_invitation`: completar campos de código desde la fila `StudentInvitationToken`.
   - Nuevo `POST /student-invitation/verify-code`:
     - Buscar invitación por token hash.
     - Si usado/expirado → 410.
     - Comparar hash del código ingresado vs `verification_code_hash`.
     - Si OK y `expires_at > now` → escribir `verification_code_verified_at=now` y devolver `challenge_token=generate_session_sync_token-like` (JWT de corta vida o nonce firmado; opción simple: reutilizar raw token como challenge ya que el código fue verificado y la pantalla lo tiene en query params).
     - Si no coincide: 400 status="wrong_code".
     - Si expiró el código: 410 status="expired".
   - Modificar `redeem_student_invitation`:
     - Si la invitación tiene `verification_code_hash` (flujo nuevo) se requiere `verification_code_verified_at IS NOT NULL`. Si no lo está → 409 "Debes verificar el código enviado a tu correo antes de activar la cuenta.".
     - Filas legacy (sin código) se aceptan sin cambio (backward compat).
   - Nuevo `POST /student-invitation/resend-code`: reenvío de código (invalida anterior, genera otro, notifica email enviado).

### Paso 6 — Frontend types & API layer
1. `types/api.ts`:
   - `StudentInvitationVerifyCodePayload = { token: string; code: string }`.
   - `StudentInvitationVerifyCodeResponse = { status: "ok"|"wrong_code"|"expired"|"invalid"; message: string; challenge_token?: string | null }`.
   - `StudentInvitationPreviewResponse`: agregar campos código.
   - `StudentPortalAccessStatus`: agregar campos código.
   - `EnsureInvitationResult`: agregar `code_sent: boolean; code_sent_to_email: string | null`.
2. `authApi.ts`:
   - `verifyStudentInvitationCode(payload)`.
   - `resendStudentInvitationCode(token)` (apunta al nuevo endpoint).
   - Ajustar `redeemStudentInvitation` para incluir `challenge_token` si lo tenemos.
3. `studentsApi.ts`: `ensureAndGetInvitation` parsea los flags nuevos del response `portal_access`.

### Paso 7 — UI: ActivateAccountScreen (nueva) con ui-ux-pro-max
1. **Diseño 2 pasos**:
   - **Paso 1 (VerifyCodeStep)**: Hero con logo de ElDojo, tarjeta centrada, eyebrow "Activación de cuenta", título "Confirma tu identidad", subtítulo "Enviamos un código de 6 dígitos a {maskedEmail}". Input OTP de 6 celdas individuales con enfoque automático, borde animado, focus ring color `agedWood`. Botón primario grande: **"Confirmar cuenta"**. Link secundario: "No llegó el código? Reenviar" con cooldown de 60s. Mensajes de error inline (código incorrecto, expirado).
   - **Paso 2 (CompleteProfileStep)**: misma UX que StudentActivateScreen pero ya con datos precargados desde preview; password confirm, términos switch, botón "Activar mi cuenta".
2. **Estados**: loading preview, error token inválido/expirado/usado, éxito y redirect a `/alumno`.
3. **Safe areas**: padding en mobile, 44pt touch targets.
4. **Componentes**: reutilizar `PublicPageChrome`, `AppCard`, `AppButton`, `AppInput`, `StatusView`.
5. **Diseño**: usar tokens existentes `colors.primary (agedWood)`, `radius.lg`, `spacing.md/lg`, sombra `shadows.cardElevated`.

### Paso 8 — Admin feedback & navegación
1. `StudentsListScreen.tsx` `handleCopyInvitationLink`:
   - Al terminar mostrar `feedbackMessage`: "Código de activación ENVIADO a {email}. Link de activación copiado al portapapeles." si `code_sent=true`.
   - Si no se pudo enviar mail pero sí se copió link: "Link copiado. No pudimos enviar el correo. Compártelo manualmente."
2. `AppNavigator.tsx`:
   - Importar `ActivateAccountScreen`.
   - Agregar en `AuthStack` con `name="ActivateAccount"`.
   - `linking.config.screens`: `ActivateAccount: PUBLIC_SCREEN_PATHS.ActivateStudent` (reutiliza path `/activar`; si queremos `/activar-cuenta` también agregarlo).
   - Mantener `ActivateStudent` para backward compat: redirigir internamente a `ActivateAccount` o eliminar registro de `ActivateStudent` y reemplazar screen por la nueva.
3. `publicRoutes.ts`:
   - Actualizar `PUBLIC_SCREEN_PATHS.ActivateStudent` si hace falta; agregar alias `ActivateAccount`.

### Paso 9 — Verificación final
- Backend: correr migración 004 manualmente en dev, revisar docs `/docs` de los endpoints nuevos.
- Frontend: `npx tsc --noEmit`, lint.
- Smoke test local: generar invitación y revisar que `verification_code_plain_tail` se guarda; preview devuelve `verification_code_sent=true`; verify-code con código correcto marca `verified_at`; redeem lo acepta.

## Dependencies and Considerations
- **MySQL idempotent ALTER**: MySQL no soporta `ADD COLUMN IF NOT EXISTS` de forma nativa en versiones antiguas. Usar procedimiento almacenado que consulte `INFORMATION_SCHEMA.COLUMNS` antes de ALTER. Mantener fallback `ALTER TABLE IGNORE` si fuera necesario.
- **Backward compatibility**: filas legacy `student_invitation_tokens` sin `verification_code_hash` siguen funcionando en redeem (no pedimos código). Esto evita romper invitaciones existentes en producción.
- **SMTP fail-open**: si el envío de correo falla (SMTP no config), el link sigue funcionando, la pantalla debe mostrar un aviso y permitir al admin compartir el link manualmente; el código OTP en ese caso se genera pero no se envía → el endpoint verify-code debe tener un bypass? **No**. Mejor: si SMTP no está configurado o falló, no escribir `verification_code_hash` (dejar null) y por tanto redeem no exigirá código (flujo legacy). Regla: `issue_verification_code_for_invitation` solo escribe el código si `send_student_verification_code_email` devolvió True.
- **Replay protection**: verify-code es de un solo uso (mejor: una vez verificado, `verification_code_verified_at` queda; no permitimos re-verificar ni canjear el código 2 veces). Además `challenge_token` se firma con expiración de 15 min si decidimos usarlo en vez de depender solo del raw token.
- **Rate limiting por token**: 5 intentos de código incorrectos por minuto → bloquear temporalmente. Implementar simple en memoria del proceso por ahora (dict `failed_attempts[token_hash] = count+timestamp`) o en la fila `StudentInvitationToken` agregando columna si se quiere; queda fuera de este alcance inicial pero es una mejora.

## Validation
- Backend:
  - FastAPI docs `GET /docs` → probar `GET /auth/student-invitation?token=...` antes y después de generar código.
  - Probar `POST /auth/student-invitation/verify-code` con código correcto/incorrecto/expirado.
  - Probar redeem antes de verify (debe fallar con 409 pidiendo código) y después de verify (debe pasar).
  - CORS: navegador en `https://mi.eldojo.tech` con fetch directo a `https://api.eldojo.tech/api/v1/auth/student-invitation?token=...` → no debe aparecer `blocked by CORS policy`; verificar OPTIONS preflight devuelve 204 y headers Access-Control-Allow-Origin/Methods/Headers.
- Frontend:
  - `npx tsc --noEmit` en `eldojo-mobile`.
  - Pantalla nueva en web: probar navegación directa a `/activar?token=Xjqxc-XcarXLyxQx-EykA5nsDbDimcO42Vb5_A.BWPP5Q`.
  - Estados: código incompleto (botón deshabilitado), código incorrecto (error inline), reenvío (cooldown).
  - Pasar al form de contraseña, completar, verificar redirect.
- Admin:
  - Click en botón portal de un alumno sin invitación → debe llamar resend-invitation, copiar link y mostrar mensaje con email de envío de código.

## Risks
- **Riesgo**: Migración ALTER en producción bloquea la tabla por segundos. Mitigación: ejecutar en ventana de bajo tráfico; usar `ALTER TABLE ... ALGORITHM=INPLACE, LOCK=NONE` si MySQL/InnoDB lo soporta (5.6+).
- **Riesgo**: SMTP no configurado en producción y se activa el bypass accidentalmente con código nulo → todo el mundo skpea la verificación. Mitigación: regla de "solo NULL si send_mail devolvió False y no hay código previo"; además unit test manual de los 3 escenarios (mail OK / mail FAIL / sin SMTP settings).
- **Riesgo**: CORS sigue fallando en producción porque Nginx o Varnish frente a FastAPI no pasa los headers. Mitigación: además del middleware, revisar configuración Nginx de `mi.eldojo.tech` → `add_header Access-Control-Allow-Origin always` + permitir OPTIONS siempre y no cachear preflight.
- **Riesgo**: UX mala del input OTP sin manejo de pegado (paste) desde correo. Mitigación: en el input OTP detectar `onPaste` y distribuir dígitos a las 6 celdas.
