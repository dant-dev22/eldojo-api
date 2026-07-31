CREATE TABLE academy_pending_sessions (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    ticket_hash VARCHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    activated_at DATETIME NULL,
    used_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_academy_pending_sessions_ticket_hash (ticket_hash),
    KEY ix_academy_pending_sessions_user_id (user_id),
    KEY ix_academy_pending_sessions_expires_at (expires_at),
    CONSTRAINT fk_academy_pending_sessions_user_id
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
);
