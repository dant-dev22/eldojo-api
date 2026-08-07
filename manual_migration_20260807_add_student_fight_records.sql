-- ============================================================
-- Migration: Tabla student_fight_records (registros individuales de peleas)
-- Fecha: 2026-08-07
-- Cada alumno puede tener N peleas, cada una con tipo, rival y fecha
--
-- IMPORTANTE: La sincronización de los totales rd_victorias / rd_empates /
-- rd_derrotas en la tabla `students` YA NO SE HACE CON TRIGGERS.
-- Motivos:
--   1) Entornos managed (RDS/Cloud SQL/réplicas) con binary logging suelen
--      tener log_bin_trust_function_creators como variable GLOBAL-ONLY y el
--      usuario de la app NO tiene SUPER ni SET GLOBAL → ERROR 1229 + 1419.
--   2) El endpoint DELETE de la API es SOFT DELETE (deleted_at), por lo que
--      el trigger AFTER DELETE físico NUNCA se dispararía y habría
--      divergencia silenciosa de totales.
--
-- En su lugar, la sincronización se realiza en la capa de servicio del
-- backend (app/services/fight_record_sync.py) de forma atómica y transaccional
-- en los endpoints POST / PATCH / DELETE.
--
-- Para reconciliación / backfill inicial, ver el SP al final del archivo.
-- ============================================================

-- -----------------------------------------------------------
-- 1. Tabla student_fight_records (índices inline + IF NOT EXISTS)
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

    INDEX ix_student_fight_records_student       (student_id),
    INDEX ix_student_fight_records_date          (fight_date),
    INDEX ix_student_fight_records_type          (record_type),
    INDEX ix_student_fight_records_student_date  (student_id, fight_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 2. Reconciliación / Backfill (opcional, ejecutar una vez)
--
-- Si ya hay registros en student_fight_records o si los totales en
-- students se desincronizaron por cualquier motivo, ejecuta el
-- siguiente bloque para reconstruir rd_victorias / rd_empates / rd_derrotas
-- a partir de los registros NO borrados (soft delete compatible).
--
-- Descomenta el bloque inferior cuando lo necesites.
-- ============================================================
--
-- UPDATE students s
--   LEFT JOIN (
--       SELECT student_id,
--              SUM(record_type = 'victoria') AS v,
--              SUM(record_type = 'empate')   AS e,
--              SUM(record_type = 'derrota')  AS d
--         FROM student_fight_records
--        WHERE deleted_at IS NULL
--        GROUP BY student_id
--   ) r ON r.student_id = s.id
--   SET s.rd_victorias = COALESCE(r.v, 0),
--       s.rd_empates   = COALESCE(r.e, 0),
--       s.rd_derrotas  = COALESCE(r.d, 0);
--
-- SELECT 'Backfill completado. Filas en students actualizadas según COUNT real.' AS resultado;
