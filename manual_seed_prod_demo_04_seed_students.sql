SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

SET @target_email := 'dantedev22@gmail.com';
SET @seed_tag := 'seed_demo_prod_20260730';
SET @student_count := 40;

DROP TEMPORARY TABLE IF EXISTS tmp_seed_context;
DROP TEMPORARY TABLE IF EXISTS tmp_seed_classes;
DROP TEMPORARY TABLE IF EXISTS tmp_seed_numbers;

CREATE TEMPORARY TABLE tmp_seed_context AS
SELECT
    u.id AS user_id,
    aa.organization_id AS organization_id,
    COALESCE(
        (
            SELECT aa2.branch_id
              FROM admin_assignments aa2
             WHERE aa2.user_id = u.id
               AND aa2.organization_id = aa.organization_id
               AND aa2.branch_id IS NOT NULL
             ORDER BY aa2.created_at ASC, aa2.id ASC
             LIMIT 1
        ),
        (
            SELECT b.id
              FROM branches b
             WHERE b.organization_id = aa.organization_id
             ORDER BY b.id ASC
             LIMIT 1
        )
    ) AS branch_id
FROM users u
JOIN admin_assignments aa
  ON aa.user_id = u.id
WHERE CONVERT(u.email USING utf8mb4) COLLATE utf8mb4_unicode_ci
      = CONVERT(@target_email USING utf8mb4) COLLATE utf8mb4_unicode_ci
ORDER BY aa.created_at ASC, aa.id ASC
LIMIT 1;

CREATE TEMPORARY TABLE tmp_seed_classes AS
SELECT
    (
        SELECT c.id
          FROM classes c
          JOIN tmp_seed_context ctx
            ON ctx.organization_id = c.organization_id
           AND ctx.branch_id = c.branch_id
         WHERE CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
               = CONVERT(CONCAT(@seed_tag, ' | Grupo infantil demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
         LIMIT 1
    ) AS class_kids_id,
    (
        SELECT c.id
          FROM classes c
          JOIN tmp_seed_context ctx
            ON ctx.organization_id = c.organization_id
           AND ctx.branch_id = c.branch_id
         WHERE CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
               = CONVERT(CONCAT(@seed_tag, ' | Grupo intermedio demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
         LIMIT 1
    ) AS class_teens_id,
    (
        SELECT c.id
          FROM classes c
          JOIN tmp_seed_context ctx
            ON ctx.organization_id = c.organization_id
           AND ctx.branch_id = c.branch_id
         WHERE CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
               = CONVERT(CONCAT(@seed_tag, ' | Grupo adultos demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
         LIMIT 1
    ) AS class_adults_id;

CREATE TEMPORARY TABLE tmp_seed_numbers AS
WITH RECURSIVE seq AS (
    SELECT 1 AS n
    UNION ALL
    SELECT n + 1
      FROM seq
     WHERE n < @student_count
)
SELECT n
  FROM seq;

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
)
SELECT
    ctx.organization_id,
    ctx.branch_id,
    UPPER(SUBSTRING(MD5(CONCAT(@seed_tag, '-', ctx.organization_id, '-', n.n)), 1, 8)) AS unique_code,
    NULL AS user_id,
    CASE MOD(n.n, 10)
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
    END AS first_name,
    CASE MOD(n.n, 10)
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
    END AS last_name,
    DATE_SUB(UTC_DATE(), INTERVAL (7 + MOD(n.n, 21)) YEAR) AS birth_date,
    'Santo Domingo' AS birth_place,
    120 + MOD(n.n * 7, 70) AS height_cm,
    NULL AS photo_url,
    DATE_SUB(UTC_DATE(), INTERVAL (10 + MOD(n.n * 9, 320)) DAY) AS enrollment_date,
    CASE
        WHEN MOD(n.n, 3) = 1 THEN cls.class_kids_id
        WHEN MOD(n.n, 3) = 2 THEN cls.class_teens_id
        ELSE cls.class_adults_id
    END AS primary_class_id,
    CASE
        WHEN MOD(n.n, 3) = 1 THEN 35.00
        WHEN MOD(n.n, 3) = 2 THEN 45.00
        ELSE 55.00
    END AS monthly_fee,
    'USD' AS currency,
    CASE
        WHEN n.n <= 28 THEN DATE_ADD(LAST_DAY(UTC_DATE()), INTERVAL 1 DAY)
        WHEN n.n <= 36 THEN DATE_ADD(UTC_DATE(), INTERVAL (1 + MOD(n.n, 5)) DAY)
        ELSE DATE_SUB(UTC_DATE(), INTERVAL (3 + MOD(n.n, 8)) DAY)
    END AS next_payment_date,
    CASE
        WHEN n.n <= 28 THEN 'up_to_date'
        WHEN n.n <= 36 THEN 'due_soon'
        ELSE 'overdue'
    END AS payment_status,
    CASE
        WHEN n.n <= 34 THEN 'active'
        WHEN n.n <= 38 THEN 'frozen'
        ELSE 'inactive'
    END AS status,
    CASE
        WHEN TIMESTAMPDIFF(YEAR, DATE_SUB(UTC_DATE(), INTERVAL (7 + MOD(n.n, 21)) YEAR), UTC_DATE()) < 18
            THEN CONCAT('Tutor ',
                CASE MOD(n.n, 10)
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
                END
            )
        ELSE NULL
    END AS guardian_name,
    CASE
        WHEN TIMESTAMPDIFF(YEAR, DATE_SUB(UTC_DATE(), INTERVAL (7 + MOD(n.n, 21)) YEAR), UTC_DATE()) < 18
            THEN CONCAT('+1809', LPAD(100000 + n.n, 6, '0'))
        ELSE NULL
    END AS guardian_phone,
    @seed_tag AS notes
FROM tmp_seed_numbers n
CROSS JOIN tmp_seed_context ctx
CROSS JOIN tmp_seed_classes cls
WHERE cls.class_kids_id IS NOT NULL
  AND cls.class_teens_id IS NOT NULL
  AND cls.class_adults_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
        FROM students s
       WHERE CONVERT(s.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
             = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci
  );

SELECT
    'students_seeded' AS step,
    COUNT(*) AS seeded_students
FROM students s
JOIN tmp_seed_context ctx
  ON ctx.organization_id = s.organization_id
 AND ctx.branch_id = s.branch_id
WHERE CONVERT(s.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
      = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci;
