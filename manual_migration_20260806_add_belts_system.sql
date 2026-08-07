-- ============================================================
-- Migration: Sistema de cinturones, stripes e historial
-- Fecha: 2026-08-06
-- Tablas: belt_levels, belt_stripes, student_belt_histories
-- Alter: students (current_belt_level_id, current_stripe_id)
-- ============================================================

-- -----------------------------------------------------------
-- 1. belt_levels - Catálogo de niveles/cinturones por organización
-- -----------------------------------------------------------
CREATE TABLE belt_levels (
    id INT NOT NULL AUTO_INCREMENT,
    organization_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(150) NOT NULL,
    color_hex VARCHAR(7) NOT NULL,
    text_color_hex VARCHAR(7) NOT NULL DEFAULT '#FFFFFF',
    order_index INT NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    description TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_belt_levels_org_order UNIQUE (organization_id, order_index),
    CONSTRAINT uq_belt_levels_org_name UNIQUE (organization_id, name),
    KEY ix_belt_levels_organization_id (organization_id),
    KEY ix_belt_levels_is_active (is_active),
    CONSTRAINT fk_belt_levels_organization_id
        FOREIGN KEY (organization_id) REFERENCES organizations(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
-- 2. belt_stripes - Catálogo de puntos/stripes por nivel
-- -----------------------------------------------------------
CREATE TABLE belt_stripes (
    id INT NOT NULL AUTO_INCREMENT,
    belt_level_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(150) NOT NULL,
    color_hex VARCHAR(7) NOT NULL,
    order_index INT NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_belt_stripes_level_order UNIQUE (belt_level_id, order_index),
    CONSTRAINT uq_belt_stripes_level_name UNIQUE (belt_level_id, name),
    KEY ix_belt_stripes_belt_level_id (belt_level_id),
    KEY ix_belt_stripes_is_active (is_active),
    CONSTRAINT fk_belt_stripes_belt_level_id
        FOREIGN KEY (belt_level_id) REFERENCES belt_levels(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
-- 3. student_belt_histories - Historial auditado de promociones
-- -----------------------------------------------------------
CREATE TABLE student_belt_histories (
    id INT NOT NULL AUTO_INCREMENT,
    student_id INT NOT NULL,
    belt_level_id INT NOT NULL,
    stripe_id INT NULL,
    awarded_at DATE NOT NULL,
    awarded_by_user_id INT NULL,
    notes TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT chk_student_belt_histories_awarded_at CHECK (awarded_at IS NOT NULL),
    KEY ix_student_belt_histories_student_id (student_id),
    KEY ix_student_belt_histories_belt_level_id (belt_level_id),
    KEY ix_student_belt_histories_stripe_id (stripe_id),
    KEY ix_student_belt_histories_awarded_at (awarded_at),
    KEY ix_student_belt_histories_awarded_by_user_id (awarded_by_user_id),
    CONSTRAINT fk_student_belt_histories_student_id
        FOREIGN KEY (student_id) REFERENCES students(id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_student_belt_histories_belt_level_id
        FOREIGN KEY (belt_level_id) REFERENCES belt_levels(id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_student_belt_histories_stripe_id
        FOREIGN KEY (stripe_id) REFERENCES belt_stripes(id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_student_belt_histories_awarded_by_user_id
        FOREIGN KEY (awarded_by_user_id) REFERENCES users(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
-- 4. ALTER TABLE students - Añadir FKs current_*
-- -----------------------------------------------------------
ALTER TABLE students
    ADD COLUMN current_belt_level_id INT NULL,
    ADD COLUMN current_stripe_id INT NULL,
    ADD KEY ix_students_current_belt_level_id (current_belt_level_id),
    ADD KEY ix_students_current_stripe_id (current_stripe_id),
    ADD CONSTRAINT fk_students_current_belt_level_id
        FOREIGN KEY (current_belt_level_id) REFERENCES belt_levels(id)
        ON DELETE RESTRICT,
    ADD CONSTRAINT fk_students_current_stripe_id
        FOREIGN KEY (current_stripe_id) REFERENCES belt_stripes(id)
        ON DELETE RESTRICT;

-- ============================================================
-- SEED DATA DE EJEMPLO (para organization_id = 1 - Demo Dojo)
-- Descomentar y ajustar @ORG_ID según corresponda en su entorno
-- ============================================================
-- SET @ORG_ID = 1;
--
-- -- BLANCA (sin stripes; los niños usan barras pero lo omitimos en el seed básico)
-- INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
-- VALUES (@ORG_ID, 'blanca', 'Blanca', '#FFFFFF', '#212121', 1, 1, 'Grado inicial para principiantes.');
-- SET @BLANCA_ID = LAST_INSERT_ID();
-- INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
--   (@BLANCA_ID, 'blanca-1', '1ª barra gris',  '#757575', 1, 1),
--   (@BLANCA_ID, 'blanca-2', '2ª barra gris',  '#757575', 2, 1),
--   (@BLANCA_ID, 'blanca-3', '3ª barra gris',  '#757575', 3, 1),
--   (@BLANCA_ID, 'blanca-4', '4ª barra gris',  '#757575', 4, 1);
--
-- -- AZUL
-- INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
-- VALUES (@ORG_ID, 'azul', 'Azul', '#1565C0', '#FFFFFF', 2, 1, 'Primer cinturón de graduación.');
-- SET @AZUL_ID = LAST_INSERT_ID();
-- INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
--   (@AZUL_ID, 'azul-1', '1er punto',  '#F9A825', 1, 1),
--   (@AZUL_ID, 'azul-2', '2º punto',   '#F9A825', 2, 1),
--   (@AZUL_ID, 'azul-3', '3er punto',  '#F9A825', 3, 1),
--   (@AZUL_ID, 'azul-4', '4º punto',   '#F9A825', 4, 1);
--
-- -- PÚRPURA
-- INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
-- VALUES (@ORG_ID, 'purpura', 'Púrpura', '#6A1B9A', '#FFFFFF', 3, 1, 'Grado intermedio avanzado.');
-- SET @PURPURA_ID = LAST_INSERT_ID();
-- INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
--   (@PURPURA_ID, 'purpura-1', '1er punto',  '#F9A825', 1, 1),
--   (@PURPURA_ID, 'purpura-2', '2º punto',   '#F9A825', 2, 1),
--   (@PURPURA_ID, 'purpura-3', '3er punto',  '#F9A825', 3, 1),
--   (@PURPURA_ID, 'purpura-4', '4º punto',   '#F9A825', 4, 1);
--
-- -- MARRÓN
-- INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
-- VALUES (@ORG_ID, 'marron', 'Marrón', '#5D4037', '#FFFFFF', 4, 1, 'Último grado antes de cinta negra.');
-- SET @MARRON_ID = LAST_INSERT_ID();
-- INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
--   (@MARRON_ID, 'marron-1', '1er punto',  '#F9A825', 1, 1),
--   (@MARRON_ID, 'marron-2', '2º punto',   '#F9A825', 2, 1),
--   (@MARRON_ID, 'marron-3', '3er punto',  '#F9A825', 3, 1),
--   (@MARRON_ID, 'marron-4', '4º punto',   '#F9A825', 4, 1);
--
-- -- NEGRA
-- INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
-- VALUES (@ORG_ID, 'negra', 'Negra', '#212121', '#FFFFFF', 5, 1, 'Grado de instructor.');
-- SET @NEGRA_ID = LAST_INSERT_ID();
-- INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
--   (@NEGRA_ID, 'negra-1', '1er grau / 1º dan',  '#F9A825', 1, 1),
--   (@NEGRA_ID, 'negra-2', '2º grau / 2º dan',   '#F9A825', 2, 1),
--   (@NEGRA_ID, 'negra-3', '3er grau / 3er dan',  '#F9A825', 3, 1),
--   (@NEGRA_ID, 'negra-4', '4º grau / 4º dan',   '#F9A825', 4, 1);
