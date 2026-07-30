ALTER TABLE users
    ADD COLUMN email_verified_at DATETIME NULL AFTER is_active;

CREATE TABLE email_verification_tokens (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_email_verification_tokens_token_hash (token_hash),
    KEY ix_email_verification_tokens_user_id (user_id),
    KEY ix_email_verification_tokens_expires_at (expires_at),
    CONSTRAINT fk_email_verification_tokens_user_id
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
);
