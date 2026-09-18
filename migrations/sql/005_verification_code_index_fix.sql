-- Correcciones y hardening para el flujo OTP de activación de alumno.
--
-- Correcciones:
--   1) Cambia verification_code_hash UNIQUE → INDEX (non-unique).
--      MySQL permite múltiples NULLs en UNIQUE, pero SQLAlchemy declaraba
--      unique=True, lo que causaba IntegrityError edge cases en race
--      conditions o backfills. No necesitamos unicidad de hash, ya que
--      en el hash influye nonce de 6 dígitos + invitation_id en runtime.
--   2) Índice compuesto (student_id, used_at, created_at DESC) para las
--      queries frecuentes de "última invitación de un alumno".
--
-- Idempotente: cada cambio se verifica antes de aplicar.

DELIMITER $$

DROP PROCEDURE IF EXISTS `_migrate_005_verification_code_index_fix`$$

CREATE PROCEDURE `_migrate_005_verification_code_index_fix`()
BEGIN
    DECLARE _idx_name VARCHAR(128) DEFAULT '';

    -- 1) Quitar constraint UNIQUE de verification_code_hash (si existe) y
    --    dejar solo un INDEX non-unique normal.
    --    MySQL crea automáticamente un índice con nombre igual a la columna
    --    o con nombre tipo uk_* al declarar UNIQUE en-line con ADD COLUMN.
    --    Iteramos por los índices existentes sobre esa columna para
    --    eliminar cualquiera que sea UNIQUE y luego añadir el INDEX normal.
    _loop_unique_drops: LOOP
        SET _idx_name := '';
        SELECT i.INDEX_NAME
        INTO _idx_name
        FROM INFORMATION_SCHEMA.STATISTICS i
        WHERE i.TABLE_SCHEMA = DATABASE()
          AND i.TABLE_NAME   = 'student_invitation_tokens'
          AND i.COLUMN_NAME  = 'verification_code_hash'
          AND i.NON_UNIQUE   = 0
        ORDER BY i.INDEX_NAME
        LIMIT 1;

        IF _idx_name IS NULL OR _idx_name = '' THEN
            LEAVE _loop_unique_drops;
        END IF;

        SET @_sql = CONCAT(
            'ALTER TABLE student_invitation_tokens DROP INDEX `', _idx_name, '`'
        );
        PREPARE stmt FROM @_sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END LOOP _loop_unique_drops;

    -- Asegurar que exista un INDEX (non-unique) sobre verification_code_hash
    -- para búsquedas rápidas en redeem (aunque normalmente lookup por id).
    SELECT COUNT(*)
    INTO @_idx_exists
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'student_invitation_tokens'
      AND COLUMN_NAME  = 'verification_code_hash'
    LIMIT 1;

    IF @_idx_exists = 0 THEN
        SET @_sql = 'CREATE INDEX idx_sit_verification_code_hash ON student_invitation_tokens (verification_code_hash)';
        PREPARE stmt FROM @_sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;

    -- 2) Índice compuesto: student_id + used_at + created_at DESC
    --    Se usa en resend-invitation y ensureAndGetInvitation.
    SELECT COUNT(*)
    INTO @_idx_exists
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'student_invitation_tokens'
      AND INDEX_NAME   = 'idx_sit_student_used_created'
    LIMIT 1;

    IF @_idx_exists = 0 THEN
        SET @_sql = 'CREATE INDEX idx_sit_student_used_created ON student_invitation_tokens (student_id, used_at, created_at DESC)';
        PREPARE stmt FROM @_sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END$$

DELIMITER ;

CALL `_migrate_005_verification_code_index_fix`();
DROP PROCEDURE IF EXISTS `_migrate_005_verification_code_index_fix`;
