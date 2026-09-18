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
-- Idempotente: verifica INFORMATION_SCHEMA antes de añadir la columna.

DELIMITER $$

DROP PROCEDURE IF EXISTS `_migrate_003_add_token_nonce`$$

CREATE PROCEDURE `_migrate_003_add_token_nonce`()
BEGIN
    DECLARE _exists INT DEFAULT 0;

    SELECT COUNT(*)
    INTO _exists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'student_invitation_tokens'
      AND COLUMN_NAME  = 'token_nonce'
    LIMIT 1;

    IF _exists = 0 THEN
        SET @_sql003 = CONCAT(
            'ALTER TABLE student_invitation_tokens ',
            'ADD COLUMN token_nonce BINARY(4) NULL AFTER token_plain_tail'
        );
        PREPARE stmt003 FROM @_sql003;
        EXECUTE stmt003;
        DEALLOCATE PREPARE stmt003;
    END IF;
END$$

DELIMITER ;

CALL `_migrate_003_add_token_nonce`();
DROP PROCEDURE IF EXISTS `_migrate_003_add_token_nonce`;
