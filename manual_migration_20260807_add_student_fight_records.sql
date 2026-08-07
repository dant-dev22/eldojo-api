-- ============================================================
-- Migration: Tabla student_fight_records (registros individuales de peleas)
-- Fecha: 2026-08-07
-- Cada alumno puede tener N peleas, cada una con tipo, rival y fecha
--
-- IMPORTANTE: SET SESSION al inicio para evitar ERROR 1419 en entornos
-- con binary logging (RDS, Cloud SQL, réplicas) donde el usuario no tiene SUPER.
-- Esto sólo afecta la sesión actual del SOURCE, NO el servidor globalmente.
-- ============================================================

-- Habilita creación de triggers/programas almacenados sin privilegio SUPER.
-- (Sólo válido para esta conexión / SOURCE. No requiere DBA.)
SET SESSION log_bin_trust_function_creators = 1;

-- -----------------------------------------------------------
-- 1. Tabla student_fight_records (índices inline = idempotente)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_fight_records (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    student_id      INT          NOT NULL,
    record_type     ENUM('victoria','empate','derrota') NOT NULL,
    opponent_name   VARCHAR(50)  NOT NULL,
    fight_date      DATE         NOT NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at      DATETIME     NULL,

    CONSTRAINT fk_student_fight_records_student
        FOREIGN KEY (student_id) REFERENCES students(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT chk_student_fight_records_opponent_not_empty
        CHECK (CHAR_LENGTH(TRIM(opponent_name)) > 0),

    -- Índices declarados inline → al re-ejecutar con IF NOT EXISTS no hay
    -- errores de "duplicate key name" (a diferencia de ALTER TABLE ADD INDEX).
    INDEX ix_student_fight_records_student       (student_id),
    INDEX ix_student_fight_records_date          (fight_date),
    INDEX ix_student_fight_records_type          (record_type),
    INDEX ix_student_fight_records_student_date  (student_id, fight_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------
-- 2. Trigger para mantener sincronizados los totales
--    rd_victorias / rd_empates / rd_derrotas en students
--    al INSERTAR un nuevo registro
-- -----------------------------------------------------------
DROP TRIGGER IF EXISTS trg_student_fight_records_after_insert;
DELIMITER //
CREATE TRIGGER trg_student_fight_records_after_insert
AFTER INSERT ON student_fight_records
FOR EACH ROW
BEGIN
    CASE NEW.record_type
        WHEN 'victoria' THEN
            UPDATE students SET rd_victorias = rd_victorias + 1 WHERE id = NEW.student_id;
        WHEN 'empate' THEN
            UPDATE students SET rd_empates   = rd_empates   + 1 WHERE id = NEW.student_id;
        WHEN 'derrota' THEN
            UPDATE students SET rd_derrotas  = rd_derrotas  + 1 WHERE id = NEW.student_id;
    END CASE;
END //
DELIMITER ;

-- -----------------------------------------------------------
-- 3. Trigger al ACTUALIZAR un registro (cambio de tipo o de alumno)
-- -----------------------------------------------------------
DROP TRIGGER IF EXISTS trg_student_fight_records_after_update;
DELIMITER //
CREATE TRIGGER trg_student_fight_records_after_update
AFTER UPDATE ON student_fight_records
FOR EACH ROW
BEGIN
    -- Restar del tipo anterior en el alumno anterior (o actual si no cambió alumno)
    CASE OLD.record_type
        WHEN 'victoria' THEN
            UPDATE students SET rd_victorias = GREATEST(rd_victorias - 1, 0) WHERE id = OLD.student_id;
        WHEN 'empate' THEN
            UPDATE students SET rd_empates   = GREATEST(rd_empates   - 1, 0) WHERE id = OLD.student_id;
        WHEN 'derrota' THEN
            UPDATE students SET rd_derrotas  = GREATEST(rd_derrotas  - 1, 0) WHERE id = OLD.student_id;
    END CASE;

    -- Sumar al nuevo tipo en el alumno nuevo
    CASE NEW.record_type
        WHEN 'victoria' THEN
            UPDATE students SET rd_victorias = rd_victorias + 1 WHERE id = NEW.student_id;
        WHEN 'empate' THEN
            UPDATE students SET rd_empates   = rd_empates   + 1 WHERE id = NEW.student_id;
        WHEN 'derrota' THEN
            UPDATE students SET rd_derrotas  = rd_derrotas  + 1 WHERE id = NEW.student_id;
    END CASE;
END //
DELIMITER ;

-- -----------------------------------------------------------
-- 4. Trigger al ELIMINAR físicamente un registro (restar del total)
-- -----------------------------------------------------------
DROP TRIGGER IF EXISTS trg_student_fight_records_after_delete;
DELIMITER //
CREATE TRIGGER trg_student_fight_records_after_delete
AFTER DELETE ON student_fight_records
FOR EACH ROW
BEGIN
    CASE OLD.record_type
        WHEN 'victoria' THEN
            UPDATE students SET rd_victorias = GREATEST(rd_victorias - 1, 0) WHERE id = OLD.student_id;
        WHEN 'empate' THEN
            UPDATE students SET rd_empates   = GREATEST(rd_empates   - 1, 0) WHERE id = OLD.student_id;
        WHEN 'derrota' THEN
            UPDATE students SET rd_derrotas  = GREATEST(rd_derrotas  - 1, 0) WHERE id = OLD.student_id;
    END CASE;
END //
DELIMITER ;
