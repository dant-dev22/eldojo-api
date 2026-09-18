-- Añade columnas para el código OTP de verificación por correo
-- en el flujo de activación de la cuenta del alumno (2 pasos).
--
-- Columnas nuevas (todas NULLABLE → backward compatible con invitaciones legacy):
--   verification_code_hash:       SHA-256 del código de 6 dígitos, único por invitación.
--   verification_code_plain_tail: Últimos 4 dígitos del código para auditoría.
--   verification_code_sent_at:    Fecha UTC en que se emitió y envió el código.
--   verification_code_expires_at: Fecha UTC de vencimiento (máx 24h desde sent_at).
--   verification_code_verified_at: Fecha UTC en que el alumno ingresó el código correcto.
--
-- Regla de negocio en runtime (app/core + routes):
--   SI verification_code_hash IS NULL → flujo legacy, no se pide código (bypass).
--   SI verification_code_hash IS NOT NULL → redeem requiere verified_at NOT NULL
--   (409 Conflict si el alumno intenta activar sin antes pasar verify-code).
--
-- Idempotente: cada columna se verifica contra INFORMATION_SCHEMA antes de ALTER.

DELIMITER $$

DROP PROCEDURE IF EXISTS `_migrate_004_add_verification_code_cols`$$

CREATE PROCEDURE `_migrate_004_add_verification_code_cols`()
BEGIN
    DECLARE _exists INT DEFAULT 0;

    -- 1) verification_code_hash VARCHAR(64) NULL UNIQUE
    SELECT COUNT(*)
    INTO _exists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'student_invitation_tokens'
      AND COLUMN_NAME  = 'verification_code_hash'
    LIMIT 1;

    IF _exists = 0 THEN
        SET @_sql = CONCAT(
            'ALTER TABLE student_invitation_tokens ',
            'ADD COLUMN verification_code_hash VARCHAR(64) NULL UNIQUE AFTER email_sent_to'
        );
        PREPARE stmt FROM @_sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;

    -- 2) verification_code_plain_tail VARCHAR(4) NULL
    SET _exists = 0;
    SELECT COUNT(*)
    INTO _exists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'student_invitation_tokens'
      AND COLUMN_NAME  = 'verification_code_plain_tail'
    LIMIT 1;

    IF _exists = 0 THEN
        SET @_sql = CONCAT(
            'ALTER TABLE student_invitation_tokens ',
            'ADD COLUMN verification_code_plain_tail VARCHAR(4) NULL AFTER verification_code_hash'
        );
        PREPARE stmt FROM @_sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;

    -- 3) verification_code_sent_at DATETIME NULL
    SET _exists = 0;
    SELECT COUNT(*)
    INTO _exists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'student_invitation_tokens'
      AND COLUMN_NAME  = 'verification_code_sent_at'
    LIMIT 1;

    IF _exists = 0 THEN
        SET @_sql = CONCAT(
            'ALTER TABLE student_invitation_tokens ',
            'ADD COLUMN verification_code_sent_at DATETIME NULL AFTER verification_code_plain_tail'
        );
        PREPARE stmt FROM @_sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;

    -- 4) verification_code_expires_at DATETIME NULL
    SET _exists = 0;
    SELECT COUNT(*)
    INTO _exists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'student_invitation_tokens'
      AND COLUMN_NAME  = 'verification_code_expires_at'
    LIMIT 1;

    IF _exists = 0 THEN
        SET @_sql = CONCAT(
            'ALTER TABLE student_invitation_tokens ',
            'ADD COLUMN verification_code_expires_at DATETIME NULL AFTER verification_code_sent_at'
        );
        PREPARE stmt FROM @_sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;

    -- 5) verification_code_verified_at DATETIME NULL
    SET _exists = 0;
    SELECT COUNT(*)
    INTO _exists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'student_invitation_tokens'
      AND COLUMN_NAME  = 'verification_code_verified_at'
    LIMIT 1;

    IF _exists = 0 THEN
        SET @_sql = CONCAT(
            'ALTER TABLE student_invitation_tokens ',
            'ADD COLUMN verification_code_verified_at DATETIME NULL AFTER verification_code_expires_at'
        );
        PREPARE stmt FROM @_sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END$$

DELIMITER ;

CALL `_migrate_004_add_verification_code_cols`();
DROP PROCEDURE IF EXISTS `_migrate_004_add_verification_code_cols`;
