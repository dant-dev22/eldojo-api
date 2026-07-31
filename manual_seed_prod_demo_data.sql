-- Seed demo data for a single production dojo.
-- Safe to rerun: it deletes only rows previously created by this script.
--
-- Default target:
--   dantedev22@gmail.com
--
-- Before running in the VPS, review these variables if needed:
SET @target_email := 'dantedev22@gmail.com';
SET @seed_tag := 'seed_demo_prod_20260730';
SET @student_count := 40;

DELIMITER $$

DROP PROCEDURE IF EXISTS seed_prod_demo_data_for_account$$

CREATE PROCEDURE seed_prod_demo_data_for_account()
BEGIN
    DECLARE v_target_email VARCHAR(255);
    DECLARE v_seed_tag VARCHAR(64);
    DECLARE v_student_count INT;

    DECLARE v_user_id INT;
    DECLARE v_org_id INT;
    DECLARE v_branch_id INT;
    DECLARE v_discipline_id INT;

    DECLARE v_class_kids_id INT;
    DECLARE v_class_teens_id INT;
    DECLARE v_class_adults_id INT;
    DECLARE v_primary_class_id INT;
    DECLARE v_secondary_class_id INT;
    DECLARE v_student_id INT;

    DECLARE v_i INT DEFAULT 1;
    DECLARE v_j INT DEFAULT 1;
    DECLARE v_attendance_count INT DEFAULT 0;

    DECLARE v_first_name VARCHAR(100);
    DECLARE v_last_name VARCHAR(100);
    DECLARE v_birth_date DATE;
    DECLARE v_enrollment_date DATE;
    DECLARE v_monthly_fee DECIMAL(10, 2);
    DECLARE v_next_payment_date DATE;
    DECLARE v_student_payment_status VARCHAR(20);
    DECLARE v_student_status VARCHAR(20);
    DECLARE v_unique_code VARCHAR(8);
    DECLARE v_guardian_name VARCHAR(150);
    DECLARE v_guardian_phone VARCHAR(50);

    DECLARE v_period_start DATE;
    DECLARE v_period_end DATE;
    DECLARE v_previous_period_start DATE;
    DECLARE v_previous_period_end DATE;
    DECLARE v_payment_method VARCHAR(20);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET v_target_email = COALESCE(@target_email, 'dantedev22@gmail.com');
    SET v_seed_tag = COALESCE(@seed_tag, 'seed_demo_prod_20260730');
    SET v_student_count = COALESCE(@student_count, 40);

    SELECT u.id
      INTO v_user_id
      FROM users u
     WHERE u.email = v_target_email
     LIMIT 1;

    IF v_user_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'No se encontro el usuario objetivo en users.email.';
    END IF;

    SELECT aa.organization_id
      INTO v_org_id
      FROM admin_assignments aa
     WHERE aa.user_id = v_user_id
     ORDER BY aa.created_at ASC, aa.id ASC
     LIMIT 1;

    IF v_org_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'El usuario no tiene organization_id asociado en admin_assignments.';
    END IF;

    SELECT COALESCE(
        (
            SELECT aa.branch_id
              FROM admin_assignments aa
             WHERE aa.user_id = v_user_id
               AND aa.organization_id = v_org_id
               AND aa.branch_id IS NOT NULL
             ORDER BY aa.created_at ASC, aa.id ASC
             LIMIT 1
        ),
        (
            SELECT b.id
              FROM branches b
             WHERE b.organization_id = v_org_id
             ORDER BY b.id ASC
             LIMIT 1
        )
    )
      INTO v_branch_id;

    IF v_branch_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'No se encontro branch para la organizacion del usuario.';
    END IF;

    START TRANSACTION;

    DELETE FROM payments
     WHERE organization_id = v_org_id
       AND branch_id = v_branch_id
       AND notes = v_seed_tag;

    DELETE FROM attendance
     WHERE student_id IN (
           SELECT s.id
             FROM students s
            WHERE s.organization_id = v_org_id
              AND s.branch_id = v_branch_id
              AND s.notes = v_seed_tag
     );

    DELETE FROM class_enrollments
     WHERE student_id IN (
           SELECT s.id
             FROM students s
            WHERE s.organization_id = v_org_id
              AND s.branch_id = v_branch_id
              AND s.notes = v_seed_tag
     );

    DELETE FROM students
     WHERE organization_id = v_org_id
       AND branch_id = v_branch_id
       AND notes = v_seed_tag;

    DELETE FROM class_schedules
     WHERE class_id IN (
           SELECT c.id
             FROM classes c
            WHERE c.organization_id = v_org_id
              AND c.branch_id = v_branch_id
              AND c.description LIKE CONCAT(v_seed_tag, '%')
     );

    DELETE FROM classes
     WHERE organization_id = v_org_id
       AND branch_id = v_branch_id
       AND description LIKE CONCAT(v_seed_tag, '%');

    SELECT d.id
      INTO v_discipline_id
      FROM disciplines d
     WHERE d.organization_id = v_org_id
       AND d.is_active = 1
     ORDER BY d.created_at ASC, d.id ASC
     LIMIT 1;

    IF v_discipline_id IS NULL THEN
        INSERT INTO disciplines (
            organization_id,
            name,
            is_active
        ) VALUES (
            v_org_id,
            'Disciplina Demo',
            1
        );

        SET v_discipline_id = LAST_INSERT_ID();
    END IF;

    INSERT INTO classes (
        organization_id,
        branch_id,
        discipline_id,
        name,
        description,
        instructor_name,
        capacity,
        is_active
    ) VALUES (
        v_org_id,
        v_branch_id,
        v_discipline_id,
        'Karate Infantil',
        CONCAT(v_seed_tag, ' | Grupo infantil demo'),
        'Sensei Rivera',
        18,
        1
    );
    SET v_class_kids_id = LAST_INSERT_ID();

    INSERT INTO classes (
        organization_id,
        branch_id,
        discipline_id,
        name,
        description,
        instructor_name,
        capacity,
        is_active
    ) VALUES (
        v_org_id,
        v_branch_id,
        v_discipline_id,
        'Karate Intermedio',
        CONCAT(v_seed_tag, ' | Grupo intermedio demo'),
        'Sensei Morales',
        20,
        1
    );
    SET v_class_teens_id = LAST_INSERT_ID();

    INSERT INTO classes (
        organization_id,
        branch_id,
        discipline_id,
        name,
        description,
        instructor_name,
        capacity,
        is_active
    ) VALUES (
        v_org_id,
        v_branch_id,
        v_discipline_id,
        'Karate Adultos',
        CONCAT(v_seed_tag, ' | Grupo adultos demo'),
        'Sensei Castillo',
        24,
        1
    );
    SET v_class_adults_id = LAST_INSERT_ID();

    INSERT INTO class_schedules (class_id, day_of_week, start_time, end_time) VALUES
        (v_class_kids_id, 1, '17:00:00', '18:00:00'),
        (v_class_kids_id, 3, '17:00:00', '18:00:00'),
        (v_class_teens_id, 2, '18:00:00', '19:15:00'),
        (v_class_teens_id, 4, '18:00:00', '19:15:00'),
        (v_class_adults_id, 1, '19:30:00', '21:00:00'),
        (v_class_adults_id, 4, '19:30:00', '21:00:00');

    SET v_period_start = CAST(DATE_FORMAT(UTC_DATE(), '%Y-%m-01') AS DATE);
    SET v_period_end = LAST_DAY(UTC_DATE());
    SET v_previous_period_start = CAST(DATE_FORMAT(DATE_SUB(UTC_DATE(), INTERVAL 1 MONTH), '%Y-%m-01') AS DATE);
    SET v_previous_period_end = LAST_DAY(DATE_SUB(UTC_DATE(), INTERVAL 1 MONTH));

    WHILE v_i <= v_student_count DO
        SET v_first_name = CASE MOD(v_i, 10)
            WHEN 1 THEN 'Mateo'
            WHEN 2 THEN 'Sofia'
            WHEN 3 THEN 'Lucas'
            WHEN 4 THEN 'Valentina'
            WHEN 5 THEN 'Thiago'
            WHEN 6 THEN 'Camila'
            WHEN 7 THEN 'Daniel'
            WHEN 8 THEN 'Victoria'
            WHEN 9 THEN 'Nicolas'
            ELSE 'Emma'
        END;

        SET v_last_name = CASE MOD(v_i, 10)
            WHEN 1 THEN 'Garcia'
            WHEN 2 THEN 'Martinez'
            WHEN 3 THEN 'Lopez'
            WHEN 4 THEN 'Rodriguez'
            WHEN 5 THEN 'Perez'
            WHEN 6 THEN 'Santos'
            WHEN 7 THEN 'Torres'
            WHEN 8 THEN 'Diaz'
            WHEN 9 THEN 'Castro'
            ELSE 'Fernandez'
        END;

        SET v_birth_date = DATE_SUB(
            UTC_DATE(),
            INTERVAL (7 + MOD(v_i, 21)) YEAR
        );

        SET v_enrollment_date = DATE_SUB(
            UTC_DATE(),
            INTERVAL (10 + MOD(v_i * 9, 320)) DAY
        );

        IF MOD(v_i, 3) = 1 THEN
            SET v_primary_class_id = v_class_kids_id;
            SET v_monthly_fee = 35.00;
        ELSEIF MOD(v_i, 3) = 2 THEN
            SET v_primary_class_id = v_class_teens_id;
            SET v_monthly_fee = 45.00;
        ELSE
            SET v_primary_class_id = v_class_adults_id;
            SET v_monthly_fee = 55.00;
        END IF;

        IF v_i <= 28 THEN
            SET v_student_payment_status = 'up_to_date';
            SET v_next_payment_date = DATE_ADD(v_period_end, INTERVAL 1 DAY);
        ELSEIF v_i <= 36 THEN
            SET v_student_payment_status = 'due_soon';
            SET v_next_payment_date = DATE_ADD(UTC_DATE(), INTERVAL (1 + MOD(v_i, 5)) DAY);
        ELSE
            SET v_student_payment_status = 'overdue';
            SET v_next_payment_date = DATE_SUB(UTC_DATE(), INTERVAL (3 + MOD(v_i, 8)) DAY);
        END IF;

        IF v_i <= 34 THEN
            SET v_student_status = 'active';
        ELSEIF v_i <= 38 THEN
            SET v_student_status = 'frozen';
        ELSE
            SET v_student_status = 'inactive';
        END IF;

        IF TIMESTAMPDIFF(YEAR, v_birth_date, UTC_DATE()) < 18 THEN
            SET v_guardian_name = CONCAT('Tutor ', v_last_name);
            SET v_guardian_phone = CONCAT('+1809', LPAD(100000 + v_i, 6, '0'));
        ELSE
            SET v_guardian_name = NULL;
            SET v_guardian_phone = NULL;
        END IF;

        SET v_unique_code = UPPER(SUBSTRING(REPLACE(UUID(), '-', ''), 1, 8));
        SET v_payment_method = CASE MOD(v_i, 4)
            WHEN 1 THEN 'cash'
            WHEN 2 THEN 'transfer'
            WHEN 3 THEN 'card'
            ELSE 'other'
        END;

        INSERT INTO students (
            organization_id,
            branch_id,
            unique_code,
            user_id,
            first_name,
            last_name,
            birth_date,
            birth_place,
            height_cm,
            photo_url,
            enrollment_date,
            primary_class_id,
            monthly_fee,
            currency,
            next_payment_date,
            payment_status,
            status,
            guardian_name,
            guardian_phone,
            notes
        ) VALUES (
            v_org_id,
            v_branch_id,
            v_unique_code,
            NULL,
            v_first_name,
            v_last_name,
            v_birth_date,
            'Santo Domingo',
            120 + MOD(v_i * 7, 70),
            NULL,
            v_enrollment_date,
            v_primary_class_id,
            v_monthly_fee,
            'USD',
            v_next_payment_date,
            v_student_payment_status,
            v_student_status,
            v_guardian_name,
            v_guardian_phone,
            v_seed_tag
        );

        SET v_student_id = LAST_INSERT_ID();

        INSERT INTO class_enrollments (
            student_id,
            class_id,
            enrolled_at,
            is_active
        ) VALUES (
            v_student_id,
            v_primary_class_id,
            DATE_SUB(UTC_TIMESTAMP(), INTERVAL (15 + MOD(v_i * 3, 220)) DAY),
            1
        );

        IF MOD(v_i, 9) = 0 THEN
            IF v_primary_class_id = v_class_kids_id THEN
                SET v_secondary_class_id = v_class_teens_id;
            ELSEIF v_primary_class_id = v_class_teens_id THEN
                SET v_secondary_class_id = v_class_adults_id;
            ELSE
                SET v_secondary_class_id = v_class_kids_id;
            END IF;

            INSERT INTO class_enrollments (
                student_id,
                class_id,
                enrolled_at,
                is_active
            ) VALUES (
                v_student_id,
                v_secondary_class_id,
                DATE_SUB(UTC_TIMESTAMP(), INTERVAL (5 + MOD(v_i * 2, 90)) DAY),
                1
            );
        END IF;

        IF v_i <= 28 THEN
            INSERT INTO payments (
                student_id,
                organization_id,
                branch_id,
                amount,
                currency,
                period_start,
                period_end,
                paid_at,
                method,
                status,
                recorded_by,
                notes
            ) VALUES (
                v_student_id,
                v_org_id,
                v_branch_id,
                v_monthly_fee,
                'USD',
                v_period_start,
                v_period_end,
                DATE_SUB(UTC_TIMESTAMP(), INTERVAL MOD(v_i * 2, 12) DAY),
                v_payment_method,
                'paid',
                v_user_id,
                v_seed_tag
            );

            IF v_i <= 14 THEN
                INSERT INTO payments (
                    student_id,
                    organization_id,
                    branch_id,
                    amount,
                    currency,
                    period_start,
                    period_end,
                    paid_at,
                    method,
                    status,
                    recorded_by,
                    notes
                ) VALUES (
                    v_student_id,
                    v_org_id,
                    v_branch_id,
                    v_monthly_fee,
                    'USD',
                    v_previous_period_start,
                    v_previous_period_end,
                    DATE_SUB(UTC_TIMESTAMP(), INTERVAL (25 + MOD(v_i, 5)) DAY),
                    v_payment_method,
                    'paid',
                    v_user_id,
                    v_seed_tag
                );
            END IF;
        ELSEIF v_i <= 36 THEN
            INSERT INTO payments (
                student_id,
                organization_id,
                branch_id,
                amount,
                currency,
                period_start,
                period_end,
                paid_at,
                method,
                status,
                recorded_by,
                notes
            ) VALUES (
                v_student_id,
                v_org_id,
                v_branch_id,
                v_monthly_fee,
                'USD',
                v_previous_period_start,
                v_previous_period_end,
                DATE_SUB(UTC_TIMESTAMP(), INTERVAL (18 + MOD(v_i, 7)) DAY),
                v_payment_method,
                'paid',
                v_user_id,
                v_seed_tag
            );

            IF MOD(v_i, 2) = 0 THEN
                INSERT INTO payments (
                    student_id,
                    organization_id,
                    branch_id,
                    amount,
                    currency,
                    period_start,
                    period_end,
                    paid_at,
                    method,
                    status,
                    recorded_by,
                    notes
                ) VALUES (
                    v_student_id,
                    v_org_id,
                    v_branch_id,
                    v_monthly_fee,
                    'USD',
                    v_period_start,
                    v_period_end,
                    UTC_TIMESTAMP(),
                    v_payment_method,
                    'pending',
                    v_user_id,
                    v_seed_tag
                );
            END IF;
        ELSE
            INSERT INTO payments (
                student_id,
                organization_id,
                branch_id,
                amount,
                currency,
                period_start,
                period_end,
                paid_at,
                method,
                status,
                recorded_by,
                notes
            ) VALUES (
                v_student_id,
                v_org_id,
                v_branch_id,
                v_monthly_fee,
                'USD',
                v_period_start,
                v_period_end,
                UTC_TIMESTAMP(),
                v_payment_method,
                'pending',
                v_user_id,
                v_seed_tag
            );
        END IF;

        IF v_i <= 15 THEN
            SET v_attendance_count = 4;
        ELSEIF v_i <= 30 THEN
            SET v_attendance_count = 3;
        ELSE
            SET v_attendance_count = 2;
        END IF;

        SET v_j = 1;
        WHILE v_j <= v_attendance_count DO
            INSERT INTO attendance (
                student_id,
                class_id,
                branch_id,
                check_in_at,
                method,
                registered_by
            ) VALUES (
                v_student_id,
                v_primary_class_id,
                v_branch_id,
                DATE_ADD(
                    DATE_SUB(UTC_TIMESTAMP(), INTERVAL MOD(v_i + (v_j * 3), 28) DAY),
                    INTERVAL (17 + MOD(v_i, 4)) HOUR
                ),
                IF(MOD(v_i + v_j, 3) = 0, 'qr', 'manual'),
                v_user_id
            );

            SET v_j = v_j + 1;
        END WHILE;

        SET v_i = v_i + 1;
    END WHILE;

    COMMIT;

    SELECT
        v_target_email AS target_email,
        v_org_id AS organization_id,
        v_branch_id AS branch_id,
        (
            SELECT COUNT(*)
              FROM students s
             WHERE s.organization_id = v_org_id
               AND s.branch_id = v_branch_id
               AND s.notes = v_seed_tag
        ) AS seeded_students,
        (
            SELECT COUNT(*)
              FROM classes c
             WHERE c.organization_id = v_org_id
               AND c.branch_id = v_branch_id
               AND c.description LIKE CONCAT(v_seed_tag, '%')
        ) AS seeded_classes,
        (
            SELECT COUNT(*)
              FROM payments p
             WHERE p.organization_id = v_org_id
               AND p.branch_id = v_branch_id
               AND p.notes = v_seed_tag
        ) AS seeded_payments,
        (
            SELECT COUNT(*)
              FROM attendance a
             WHERE a.student_id IN (
                   SELECT s.id
                     FROM students s
                    WHERE s.organization_id = v_org_id
                      AND s.branch_id = v_branch_id
                      AND s.notes = v_seed_tag
             )
        ) AS seeded_attendance;
END$$

CALL seed_prod_demo_data_for_account()$$
DROP PROCEDURE IF EXISTS seed_prod_demo_data_for_account$$

DELIMITER ;
