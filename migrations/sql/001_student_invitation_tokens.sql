-- Sprint 0: Creación de tabla de tokens de invitación para activación del portal del alumno
-- Motor: MySQL 8.x | Collation: utf8mb4_unicode_ci
-- Ejecutar en entorno de producción después del deploy:
--   $ mysql -u eldojo_app -p eldojo_db < migrations/sql/001_student_invitation_tokens.sql

CREATE TABLE IF NOT EXISTS student_invitation_tokens (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT NOT NULL,
    user_id INT NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    token_plain_tail VARCHAR(8) NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    sent_count INT NOT NULL DEFAULT 1,
    created_by_admin_id INT NULL,
    email_sent_to VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sit_student
        FOREIGN KEY (student_id) REFERENCES students(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_sit_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_sit_admin
        FOREIGN KEY (created_by_admin_id) REFERENCES users(id)
        ON DELETE SET NULL,
    INDEX idx_sit_student_id (student_id),
    INDEX idx_sit_user_id (user_id),
    INDEX idx_sit_token_hash (token_hash),
    INDEX idx_sit_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
