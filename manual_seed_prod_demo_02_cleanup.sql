SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

SET @target_email := 'dantedev22@gmail.com';
SET @seed_tag := 'seed_demo_prod_20260730';

DROP TEMPORARY TABLE IF EXISTS tmp_seed_context;

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

START TRANSACTION;

DELETE p
  FROM payments p
  JOIN tmp_seed_context ctx
    ON ctx.organization_id = p.organization_id
   AND ctx.branch_id = p.branch_id
 WHERE CONVERT(p.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
       = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci;

DELETE a
  FROM attendance a
  JOIN students s
    ON s.id = a.student_id
  JOIN tmp_seed_context ctx
    ON ctx.organization_id = s.organization_id
   AND ctx.branch_id = s.branch_id
 WHERE CONVERT(s.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
       = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci;

DELETE ce
  FROM class_enrollments ce
  JOIN students s
    ON s.id = ce.student_id
  JOIN tmp_seed_context ctx
    ON ctx.organization_id = s.organization_id
   AND ctx.branch_id = s.branch_id
 WHERE CONVERT(s.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
       = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci;

DELETE s
  FROM students s
  JOIN tmp_seed_context ctx
    ON ctx.organization_id = s.organization_id
   AND ctx.branch_id = s.branch_id
 WHERE CONVERT(s.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
       = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci;

DELETE cs
  FROM class_schedules cs
  JOIN classes c
    ON c.id = cs.class_id
  JOIN tmp_seed_context ctx
    ON ctx.organization_id = c.organization_id
   AND ctx.branch_id = c.branch_id
 WHERE CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
       IN (
           CONVERT(CONCAT(@seed_tag, ' | Grupo infantil demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
           CONVERT(CONCAT(@seed_tag, ' | Grupo intermedio demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
           CONVERT(CONCAT(@seed_tag, ' | Grupo adultos demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
       );

DELETE c
  FROM classes c
  JOIN tmp_seed_context ctx
    ON ctx.organization_id = c.organization_id
   AND ctx.branch_id = c.branch_id
 WHERE CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
       IN (
           CONVERT(CONCAT(@seed_tag, ' | Grupo infantil demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
           CONVERT(CONCAT(@seed_tag, ' | Grupo intermedio demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
           CONVERT(CONCAT(@seed_tag, ' | Grupo adultos demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
       );

COMMIT;

SELECT
    'cleanup_complete' AS step,
    @target_email AS target_email,
    @seed_tag AS seed_tag;
