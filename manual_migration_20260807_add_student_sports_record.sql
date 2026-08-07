-- ============================================================
-- Migration: Campos de record deportivo por alumno (Victorias / Empates / Derrotas)
-- Fecha: 2026-08-07
-- Tablas: students (ALTER TABLE)
-- ============================================================

-- -----------------------------------------------------------
-- 1. Agregar columnas de record deportivo a students
--    rd = record deportivo
-- -----------------------------------------------------------
ALTER TABLE students
    ADD COLUMN rd_victorias INT NOT NULL DEFAULT 0,
    ADD COLUMN rd_empates   INT NOT NULL DEFAULT 0,
    ADD COLUMN rd_derrotas  INT NOT NULL DEFAULT 0;

-- -----------------------------------------------------------
-- 2. Indices para consultas frecuentes (rankings / ordenamientos)
-- -----------------------------------------------------------
ALTER TABLE students
    ADD INDEX ix_students_rd_victorias (rd_victorias),
    ADD INDEX ix_students_rd_derrotas  (rd_derrotas);

-- -----------------------------------------------------------
-- 3. Constraints de integridad: no pueden ser negativos
-- -----------------------------------------------------------
ALTER TABLE students
    ADD CONSTRAINT chk_students_rd_victorias_non_negative CHECK (rd_victorias >= 0),
    ADD CONSTRAINT chk_students_rd_empates_non_negative   CHECK (rd_empates   >= 0),
    ADD CONSTRAINT chk_students_rd_derrotas_non_negative  CHECK (rd_derrotas  >= 0);
