ALTER TABLE users
    ADD COLUMN first_name VARCHAR(100) NULL AFTER id,
    ADD COLUMN last_name VARCHAR(100) NULL AFTER first_name;
