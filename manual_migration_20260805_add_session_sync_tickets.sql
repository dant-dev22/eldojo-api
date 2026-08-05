CREATE TABLE session_sync_tickets (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    ticket_hash VARCHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_session_sync_tickets_ticket_hash (ticket_hash),
    KEY ix_session_sync_tickets_user_id (user_id),
    KEY ix_session_sync_tickets_expires_at (expires_at),
    CONSTRAINT fk_session_sync_tickets_user_id
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
);
