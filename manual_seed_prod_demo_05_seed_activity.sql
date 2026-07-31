SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

SET @target_email := 'dantedev22@gmail.com';
SET @seed_tag := 'seed_demo_prod_20260730';
SET @user_id := NULL;
SET @organization_id := NULL;
SET @branch_id := NULL;

DROP TEMPORARY TABLE IF EXISTS tmp_seed_students;
DROP TEMPORARY TABLE IF EXISTS tmp_seed_classes;
DROP TEMPORARY TABLE IF EXISTS tmp_seed_numbers;

SET @user_id := (
    SELECT u.id
      FROM users u
     WHERE CONVERT(u.email USING utf8mb4) COLLATE utf8mb4_unicode_ci
           = CONVERT(@target_email USING utf8mb4) COLLATE utf8mb4_unicode_ci
     LIMIT 1
);

SET @organization_id := (
    SELECT aa.organization_id
      FROM admin_assignments aa
     WHERE aa.user_id = @user_id
     ORDER BY aa.created_at ASC, aa.id ASC
     LIMIT 1
);

SET @branch_id := COALESCE(
    (
        SELECT aa.branch_id
          FROM admin_assignments aa
         WHERE aa.user_id = @user_id
           AND aa.organization_id = @organization_id
           AND aa.branch_id IS NOT NULL
         ORDER BY aa.created_at ASC, aa.id ASC
         LIMIT 1
    ),
    (
        SELECT b.id
          FROM branches b
         WHERE b.organization_id = @organization_id
         ORDER BY b.id ASC
         LIMIT 1
    )
);

CREATE TEMPORARY TABLE tmp_seed_students AS
SELECT
    s.id AS student_id,
    s.primary_class_id,
    s.monthly_fee,
    ROW_NUMBER() OVER (ORDER BY s.id ASC) AS n
FROM students s
WHERE s.organization_id = @organization_id
  AND s.branch_id = @branch_id
  AND CONVERT(s.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
      = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci;

CREATE TEMPORARY TABLE tmp_seed_classes AS
SELECT
    (
        SELECT c.id
          FROM classes c
         WHERE c.organization_id = @organization_id
           AND c.branch_id = @branch_id
           AND CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
               = CONVERT(CONCAT(@seed_tag, ' | Grupo infantil demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
         LIMIT 1
    ) AS class_kids_id,
    (
        SELECT c.id
          FROM classes c
         WHERE c.organization_id = @organization_id
           AND c.branch_id = @branch_id
           AND CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
               = CONVERT(CONCAT(@seed_tag, ' | Grupo intermedio demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
         LIMIT 1
    ) AS class_teens_id,
    (
        SELECT c.id
          FROM classes c
         WHERE c.organization_id = @organization_id
           AND c.branch_id = @branch_id
           AND CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
               = CONVERT(CONCAT(@seed_tag, ' | Grupo adultos demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
         LIMIT 1
    ) AS class_adults_id;

CREATE TEMPORARY TABLE tmp_seed_numbers AS
SELECT 1 AS seq
UNION ALL SELECT 2
UNION ALL SELECT 3
UNION ALL SELECT 4;

INSERT INTO class_enrollments (
    student_id,
    class_id,
    enrolled_at,
    is_active
)
SELECT
    ss.student_id,
    ss.primary_class_id,
    DATE_SUB(UTC_TIMESTAMP(), INTERVAL (15 + MOD(ss.n * 3, 220)) DAY),
    1
FROM tmp_seed_students ss
WHERE ss.primary_class_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
        FROM class_enrollments ce
       WHERE ce.student_id = ss.student_id
         AND ce.class_id = ss.primary_class_id
         AND ce.is_active = 1
  );

INSERT INTO class_enrollments (
    student_id,
    class_id,
    enrolled_at,
    is_active
)
SELECT
    ss.student_id,
    CASE
        WHEN ss.primary_class_id = cls.class_kids_id THEN cls.class_teens_id
        WHEN ss.primary_class_id = cls.class_teens_id THEN cls.class_adults_id
        ELSE cls.class_kids_id
    END AS class_id,
    DATE_SUB(UTC_TIMESTAMP(), INTERVAL (5 + MOD(ss.n * 2, 90)) DAY),
    1
FROM tmp_seed_students ss
CROSS JOIN tmp_seed_classes cls
WHERE MOD(ss.n, 9) = 0
  AND NOT EXISTS (
      SELECT 1
        FROM class_enrollments ce
       WHERE ce.student_id = ss.student_id
         AND ce.class_id = CASE
             WHEN ss.primary_class_id = cls.class_kids_id THEN cls.class_teens_id
             WHEN ss.primary_class_id = cls.class_teens_id THEN cls.class_adults_id
             ELSE cls.class_kids_id
         END
         AND ce.is_active = 1
  );

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
)
SELECT
    ss.student_id,
    @organization_id,
    @branch_id,
    ss.monthly_fee,
    'USD',
    CAST(DATE_FORMAT(UTC_DATE(), '%Y-%m-01') AS DATE),
    LAST_DAY(UTC_DATE()),
    DATE_SUB(UTC_TIMESTAMP(), INTERVAL MOD(ss.n * 2, 12) DAY),
    CASE MOD(ss.n, 4)
        WHEN 1 THEN 'cash'
        WHEN 2 THEN 'transfer'
        WHEN 3 THEN 'card'
        ELSE 'other'
    END AS method,
    'paid',
    @user_id,
    @seed_tag
FROM tmp_seed_students ss
WHERE ss.n <= 28
  AND NOT EXISTS (
      SELECT 1
        FROM payments p
       WHERE p.student_id = ss.student_id
         AND p.organization_id = @organization_id
         AND p.branch_id = @branch_id
         AND p.period_start = CAST(DATE_FORMAT(UTC_DATE(), '%Y-%m-01') AS DATE)
         AND p.status = 'paid'
         AND CONVERT(p.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
             = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci
  );

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
)
SELECT
    ss.student_id,
    @organization_id,
    @branch_id,
    ss.monthly_fee,
    'USD',
    CAST(DATE_FORMAT(DATE_SUB(UTC_DATE(), INTERVAL 1 MONTH), '%Y-%m-01') AS DATE),
    LAST_DAY(DATE_SUB(UTC_DATE(), INTERVAL 1 MONTH)),
    DATE_SUB(UTC_TIMESTAMP(), INTERVAL (25 + MOD(ss.n, 5)) DAY),
    CASE MOD(ss.n, 4)
        WHEN 1 THEN 'cash'
        WHEN 2 THEN 'transfer'
        WHEN 3 THEN 'card'
        ELSE 'other'
    END AS method,
    'paid',
    @user_id,
    @seed_tag
FROM tmp_seed_students ss
WHERE ss.n <= 14
  AND NOT EXISTS (
      SELECT 1
        FROM payments p
       WHERE p.student_id = ss.student_id
         AND p.organization_id = @organization_id
         AND p.branch_id = @branch_id
         AND p.period_start = CAST(DATE_FORMAT(DATE_SUB(UTC_DATE(), INTERVAL 1 MONTH), '%Y-%m-01') AS DATE)
         AND p.status = 'paid'
         AND CONVERT(p.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
             = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci
  );

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
)
SELECT
    ss.student_id,
    @organization_id,
    @branch_id,
    ss.monthly_fee,
    'USD',
    CAST(DATE_FORMAT(DATE_SUB(UTC_DATE(), INTERVAL 1 MONTH), '%Y-%m-01') AS DATE),
    LAST_DAY(DATE_SUB(UTC_DATE(), INTERVAL 1 MONTH)),
    DATE_SUB(UTC_TIMESTAMP(), INTERVAL (18 + MOD(ss.n, 7)) DAY),
    CASE MOD(ss.n, 4)
        WHEN 1 THEN 'cash'
        WHEN 2 THEN 'transfer'
        WHEN 3 THEN 'card'
        ELSE 'other'
    END AS method,
    'paid',
    @user_id,
    @seed_tag
FROM tmp_seed_students ss
WHERE ss.n BETWEEN 29 AND 36
  AND NOT EXISTS (
      SELECT 1
        FROM payments p
       WHERE p.student_id = ss.student_id
         AND p.organization_id = @organization_id
         AND p.branch_id = @branch_id
         AND p.period_start = CAST(DATE_FORMAT(DATE_SUB(UTC_DATE(), INTERVAL 1 MONTH), '%Y-%m-01') AS DATE)
         AND p.status = 'paid'
         AND CONVERT(p.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
             = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci
  );

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
)
SELECT
    ss.student_id,
    @organization_id,
    @branch_id,
    ss.monthly_fee,
    'USD',
    CAST(DATE_FORMAT(UTC_DATE(), '%Y-%m-01') AS DATE),
    LAST_DAY(UTC_DATE()),
    UTC_TIMESTAMP(),
    CASE MOD(ss.n, 4)
        WHEN 1 THEN 'cash'
        WHEN 2 THEN 'transfer'
        WHEN 3 THEN 'card'
        ELSE 'other'
    END AS method,
    'pending',
    @user_id,
    @seed_tag
FROM tmp_seed_students ss
WHERE (
        (ss.n BETWEEN 29 AND 36 AND MOD(ss.n, 2) = 0)
        OR ss.n >= 37
      )
  AND NOT EXISTS (
      SELECT 1
        FROM payments p
       WHERE p.student_id = ss.student_id
         AND p.organization_id = @organization_id
         AND p.branch_id = @branch_id
         AND p.period_start = CAST(DATE_FORMAT(UTC_DATE(), '%Y-%m-01') AS DATE)
         AND p.status = 'pending'
         AND CONVERT(p.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
             = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci
  );

INSERT INTO attendance (
    student_id,
    class_id,
    branch_id,
    check_in_at,
    method,
    registered_by
)
SELECT
    ss.student_id,
    ss.primary_class_id,
    @branch_id,
    DATE_ADD(
        DATE_SUB(UTC_TIMESTAMP(), INTERVAL MOD(ss.n + (num.seq * 3), 28) DAY),
        INTERVAL (17 + MOD(ss.n, 4)) HOUR
    ) AS check_in_at,
    CASE
        WHEN MOD(ss.n + num.seq, 3) = 0 THEN 'qr'
        ELSE 'manual'
    END AS method,
    @user_id
FROM tmp_seed_students ss
JOIN tmp_seed_numbers num
  ON num.seq <= CASE
      WHEN ss.n <= 15 THEN 4
      WHEN ss.n <= 30 THEN 3
      ELSE 2
  END
WHERE ss.primary_class_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
        FROM attendance a
       WHERE a.student_id = ss.student_id
         AND a.class_id = ss.primary_class_id
         AND a.check_in_at = DATE_ADD(
             DATE_SUB(UTC_TIMESTAMP(), INTERVAL MOD(ss.n + (num.seq * 3), 28) DAY),
             INTERVAL (17 + MOD(ss.n, 4)) HOUR
         )
  );

SELECT
    'activity_seeded' AS step,
    @organization_id AS organization_id,
    @branch_id AS branch_id,
    (
        SELECT COUNT(*)
          FROM students s
         WHERE s.organization_id = @organization_id
           AND s.branch_id = @branch_id
           AND CONVERT(s.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
               = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci
    ) AS seeded_students,
    (
        SELECT COUNT(*)
          FROM class_enrollments ce
          JOIN students s
            ON s.id = ce.student_id
         WHERE s.organization_id = @organization_id
           AND s.branch_id = @branch_id
           AND CONVERT(s.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
               = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci
    ) AS seeded_enrollments,
    (
        SELECT COUNT(*)
          FROM payments p
         WHERE p.organization_id = @organization_id
           AND p.branch_id = @branch_id
           AND CONVERT(p.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
               = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci
    ) AS seeded_payments,
    (
        SELECT COUNT(*)
          FROM attendance a
          JOIN students s
            ON s.id = a.student_id
         WHERE s.organization_id = @organization_id
           AND s.branch_id = @branch_id
           AND CONVERT(s.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
               = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci
    ) AS seeded_attendance;
