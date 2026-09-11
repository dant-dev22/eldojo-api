-- Permite que los tokens de invitación del alumno NO tengan expiración forzada.
-- Si expires_at IS NULL => el link nunca expira (hasta que es usado o invalidado).

ALTER TABLE student_invitation_tokens
    MODIFY COLUMN expires_at DATETIME NULL;
