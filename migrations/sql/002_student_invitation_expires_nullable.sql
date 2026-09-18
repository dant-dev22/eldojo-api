-- Permite que los tokens de invitación del alumno NO tengan expiración forzada.
-- Si expires_at IS NULL => el link nunca expira (hasta que es usado o invalidado).
--
-- Idempotente: verifica INFORMATION_SCHEMA antes de modificar.

DELIMITER $$

DROP PROCEDURE IF EXISTS `_migrate_002_alter_expires_nullable`$$

CREATE PROCEDURE `_migrate_002_alter_expires_nullable`()
BEGIN
    DECLARE _col_type TEXT;

    SELECT COLUMN_TYPE
    INTO _col_type
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'student_invitation_tokens'
      AND COLUMN_NAME  = 'expires_at'
    LIMIT 1;

    IF _col_type IS NOT NULL AND _col_type NOT LIKE '%datetime%' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Columna expires_at no es DATETIME, migración 002 abortada';
    END IF;

    IF _col_type IS NOT NULL THEN
        SET @_sql002 = CONCAT(
            'ALTER TABLE student_invitation_tokens ',
            'MODIFY COLUMN expires_at DATETIME NULL'
        );
        PREPARE stmt002 FROM @_sql002;
        EXECUTE stmt002;
        DEALLOCATE PREPARE stmt002;
    END IF;
END$$

DELIMITER ;

CALL `_migrate_002_alter_expires_nullable`();
DROP PROCEDURE IF EXISTS `_migrate_002_alter_expires_nullable`;
