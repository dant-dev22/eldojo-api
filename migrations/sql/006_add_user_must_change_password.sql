-- Añade columna must_change_password (BOOLEAN default FALSE) a la tabla users.
--
-- Esta columna indica que el usuario portal (normalmente STUDENT) tiene
-- su email verificado pero su contraseña fue generada automáticamente
-- por un admin y DEBE ser cambiada antes de usar la cuenta. Se usa en
-- el nuevo flujo de "aprobación automática + link de reset de password".
--
-- Idempotente: solo añade la columna si aún no existe.

DELIMITER $$

DROP PROCEDURE IF EXISTS `_migrate_006_add_user_must_change_password`$$

CREATE PROCEDURE `_migrate_006_add_user_must_change_password`()
BEGIN
    DECLARE _col_exists INT DEFAULT 0;

    SELECT COUNT(*)
    INTO _col_exists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'users'
      AND COLUMN_NAME  = 'must_change_password'
    LIMIT 1;

    IF _col_exists = 0 THEN
        ALTER TABLE users
            ADD COLUMN must_change_password TINYINT(1) NOT NULL DEFAULT 0
            AFTER first_time;
    END IF;
END$$

DELIMITER ;

CALL `_migrate_006_add_user_must_change_password`();
DROP PROCEDURE IF EXISTS `_migrate_006_add_user_must_change_password`;
