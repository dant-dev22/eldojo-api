SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

SET @target_email := 'dantedev22@gmail.com';
SET @seed_tag := 'seed_demo_prod_20260730';
SET @user_id := NULL;
SET @organization_id := NULL;
SET @branch_id := NULL;
SET @attendance_anchor_date := '2026-07-30';

DROP TEMPORARY TABLE IF EXISTS tmp_seed_students;
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
    ROW_NUMBER() OVER (ORDER BY s.id ASC) AS n
FROM students s
WHERE s.organization_id = @organization_id
  AND s.branch_id = @branch_id
  AND CONVERT(s.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
      = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci;

CREATE TEMPORARY TABLE tmp_seed_numbers AS
SELECT 1 AS seq
UNION ALL SELECT 2
UNION ALL SELECT 3
UNION ALL SELECT 4;

DELETE a
  FROM attendance a
  JOIN students s
    ON s.id = a.student_id
 WHERE s.organization_id = @organization_id
   AND s.branch_id = @branch_id
   AND CONVERT(s.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
       = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci;

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
    TIMESTAMP(
        DATE_SUB(@attendance_anchor_date, INTERVAL MOD(ss.n + (num.seq * 3), 28) DAY),
        MAKETIME(17 + MOD(ss.n, 4), MOD(ss.n * 7, 60), 0)
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
WHERE ss.primary_class_id IS NOT NULL;

SELECT
    'attendance_fixed' AS step,
    @organization_id AS organization_id,
    @branch_id AS branch_id,
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
