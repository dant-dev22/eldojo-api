ALTER TABLE users
    ADD COLUMN first_time TINYINT(1) NOT NULL DEFAULT 1 AFTER is_active;

UPDATE users
SET first_time = 0;
