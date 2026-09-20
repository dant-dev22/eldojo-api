-- Sprint 1: Tabla de tokens de reseteo de contraseña para alumnos.
-- Motor: MySQL 8.x | Collation: utf8mb4_unicode_ci
-- Ejecutar en producción después del deploy:
--   $ mysql -u eldojo_app -p eldojo_db < migrations/sql/007_student_password_reset_tokens.sql

CREATE TABLE IF NOT EXISTS student_password_reset_tokens (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT NOT NULL,
    user_id INT NULL,
    token_hash VARCHAR(64) NOT NULL,
    token_nonce BINARY(4) NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    created_by_admin_id INT NULL,
    email_sent_to VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sprt_student
        FOREIGN KEY (student_id) REFERENCES students(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_sprt_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_sprt_admin
        FOREIGN KEY (created_by_admin_id) REFERENCES users(id)
        ON DELETE SET NULL,
    UNIQUE KEY uk_sprt_token_hash (token_hash),
    INDEX idx_sprt_student_id (student_id),
    INDEX idx_sprt_user_id (user_id),
    INDEX idx_sprt_expires_at (expires_at),
    INDEX idx_sprt_student_used_created (student_id, used_at, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
