SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

SET @target_email := 'dantedev22@gmail.com';
SET @seed_tag := 'seed_demo_prod_20260730';
SET @user_id := NULL;
SET @organization_id := NULL;
SET @branch_id := NULL;

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

START TRANSACTION;

DELETE p
  FROM payments p
 WHERE p.organization_id = @organization_id
   AND p.branch_id <=> @branch_id
   AND CONVERT(p.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
       = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci;

DELETE a
  FROM attendance a
  JOIN students s
    ON s.id = a.student_id
 WHERE s.organization_id = @organization_id
   AND s.branch_id <=> @branch_id
   AND CONVERT(s.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
       = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci;

DELETE ce
  FROM class_enrollments ce
  JOIN students s
    ON s.id = ce.student_id
 WHERE s.organization_id = @organization_id
   AND s.branch_id <=> @branch_id
   AND CONVERT(s.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
       = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci;

DELETE s
  FROM students s
 WHERE s.organization_id = @organization_id
   AND s.branch_id <=> @branch_id
   AND CONVERT(s.notes USING utf8mb4) COLLATE utf8mb4_unicode_ci
       = CONVERT(@seed_tag USING utf8mb4) COLLATE utf8mb4_unicode_ci;

DELETE cs
  FROM class_schedules cs
  JOIN classes c
    ON c.id = cs.class_id
 WHERE c.organization_id = @organization_id
   AND c.branch_id <=> @branch_id
   AND CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
       IN (
           CONVERT(CONCAT(@seed_tag, ' | Grupo infantil demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
           CONVERT(CONCAT(@seed_tag, ' | Grupo intermedio demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
           CONVERT(CONCAT(@seed_tag, ' | Grupo adultos demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
       );

DELETE c
  FROM classes c
 WHERE c.organization_id = @organization_id
   AND c.branch_id <=> @branch_id
   AND CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
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
