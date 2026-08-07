-- ============================================================
-- Migration: Sistema de trayectoria / recuerdos por alumno
-- Fecha: 2026-08-06
-- Tablas: trajectory_events
-- ============================================================

-- -----------------------------------------------------------
-- 1. trajectory_events - Sucesos / recuerdos en la trayectoria de un alumno
-- -----------------------------------------------------------
CREATE TABLE trajectory_events (
    id INT NOT NULL AUTO_INCREMENT,
    student_id INT NOT NULL,
    organization_id INT NOT NULL,
    event_date DATE NOT NULL,
    content VARCHAR(280) NOT NULL,
    created_by_user_id INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,
    PRIMARY KEY (id),
    CONSTRAINT chk_trajectory_events_content_length CHECK (CHAR_LENGTH(content) <= 280),
    CONSTRAINT chk_trajectory_events_event_date CHECK (event_date IS NOT NULL),
    KEY ix_trajectory_events_student_id (student_id),
    KEY ix_trajectory_events_organization_id (organization_id),
    KEY ix_trajectory_events_event_date (event_date),
    KEY ix_trajectory_events_created_by_user_id (created_by_user_id),
    KEY ix_trajectory_events_deleted_at (deleted_at),
    CONSTRAINT fk_trajectory_events_student_id
        FOREIGN KEY (student_id) REFERENCES students(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_trajectory_events_organization_id
        FOREIGN KEY (organization_id) REFERENCES organizations(id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_trajectory_events_created_by_user_id
        FOREIGN KEY (created_by_user_id) REFERENCES users(id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
