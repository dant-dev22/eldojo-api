-- Añade la columna token_nonce (BINARY(4)) a student_invitation_tokens.
--
-- Este nonce de 4 bytes se usa para reconstruir determinísticamente
-- el raw_token del link de invitación (junto con student_id + created_at)
-- mediante HMAC-SHA256, sin necesidad de persistir el token plano.
--
-- Filas legacy (creadas antes de esta migración) conservan NULL en
-- token_nonce; cuando el admin intente copiar su link la capa de
-- servicio detectará nonce=NULL y regenerará la invitación con nonce.
--
-- Compatibilidad MySQL/MariaDB: el script 01-migrate-db.sh considera
-- "Duplicate column name" como skip idempotente, por lo que repetir
-- esta migración no es fatal.

ALTER TABLE student_invitation_tokens
    ADD COLUMN token_nonce BINARY(4) NULL AFTER token_plain_tail;
