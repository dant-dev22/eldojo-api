SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

SET @target_email := 'dantedev22@gmail.com';
SET @seed_tag := 'seed_demo_prod_20260730';

DROP TEMPORARY TABLE IF EXISTS tmp_seed_context;
DROP TEMPORARY TABLE IF EXISTS tmp_seed_discipline;

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

INSERT INTO disciplines (
    organization_id,
    name,
    is_active
)
SELECT
    ctx.organization_id,
    'Disciplina Demo',
    1
FROM tmp_seed_context ctx
WHERE NOT EXISTS (
    SELECT 1
      FROM disciplines d
     WHERE d.organization_id = ctx.organization_id
       AND d.is_active = 1
);

CREATE TEMPORARY TABLE tmp_seed_discipline AS
SELECT d.id AS discipline_id
  FROM disciplines d
  JOIN tmp_seed_context ctx
    ON ctx.organization_id = d.organization_id
 WHERE d.is_active = 1
 ORDER BY d.created_at ASC, d.id ASC
 LIMIT 1;

INSERT INTO classes (
    organization_id,
    branch_id,
    discipline_id,
    name,
    description,
    instructor_name,
    capacity,
    is_active
)
SELECT
    ctx.organization_id,
    ctx.branch_id,
    d.discipline_id,
    'Karate Infantil',
    CONCAT(@seed_tag, ' | Grupo infantil demo'),
    'Sensei Rivera',
    18,
    1
FROM tmp_seed_context ctx
JOIN tmp_seed_discipline d
WHERE NOT EXISTS (
    SELECT 1
      FROM classes c
     WHERE c.organization_id = ctx.organization_id
       AND c.branch_id = ctx.branch_id
       AND CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
           = CONVERT(CONCAT(@seed_tag, ' | Grupo infantil demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
);

INSERT INTO classes (
    organization_id,
    branch_id,
    discipline_id,
    name,
    description,
    instructor_name,
    capacity,
    is_active
)
SELECT
    ctx.organization_id,
    ctx.branch_id,
    d.discipline_id,
    'Karate Intermedio',
    CONCAT(@seed_tag, ' | Grupo intermedio demo'),
    'Sensei Morales',
    20,
    1
FROM tmp_seed_context ctx
JOIN tmp_seed_discipline d
WHERE NOT EXISTS (
    SELECT 1
      FROM classes c
     WHERE c.organization_id = ctx.organization_id
       AND c.branch_id = ctx.branch_id
       AND CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
           = CONVERT(CONCAT(@seed_tag, ' | Grupo intermedio demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
);

INSERT INTO classes (
    organization_id,
    branch_id,
    discipline_id,
    name,
    description,
    instructor_name,
    capacity,
    is_active
)
SELECT
    ctx.organization_id,
    ctx.branch_id,
    d.discipline_id,
    'Karate Adultos',
    CONCAT(@seed_tag, ' | Grupo adultos demo'),
    'Sensei Castillo',
    24,
    1
FROM tmp_seed_context ctx
JOIN tmp_seed_discipline d
WHERE NOT EXISTS (
    SELECT 1
      FROM classes c
     WHERE c.organization_id = ctx.organization_id
       AND c.branch_id = ctx.branch_id
       AND CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
           = CONVERT(CONCAT(@seed_tag, ' | Grupo adultos demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
);

INSERT INTO class_schedules (class_id, day_of_week, start_time, end_time)
SELECT c.id, x.day_of_week, x.start_time, x.end_time
FROM classes c
JOIN tmp_seed_context ctx
  ON ctx.organization_id = c.organization_id
 AND ctx.branch_id = c.branch_id
JOIN (
    SELECT 'Karate Infantil' AS class_name, 1 AS day_of_week, '17:00:00' AS start_time, '18:00:00' AS end_time
    UNION ALL SELECT 'Karate Infantil', 3, '17:00:00', '18:00:00'
    UNION ALL SELECT 'Karate Intermedio', 2, '18:00:00', '19:15:00'
    UNION ALL SELECT 'Karate Intermedio', 4, '18:00:00', '19:15:00'
    UNION ALL SELECT 'Karate Adultos', 1, '19:30:00', '21:00:00'
    UNION ALL SELECT 'Karate Adultos', 4, '19:30:00', '21:00:00'
) x
  ON CONVERT(c.name USING utf8mb4) COLLATE utf8mb4_unicode_ci
     = CONVERT(x.class_name USING utf8mb4) COLLATE utf8mb4_unicode_ci
WHERE CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
      IN (
          CONVERT(CONCAT(@seed_tag, ' | Grupo infantil demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
          CONVERT(CONCAT(@seed_tag, ' | Grupo intermedio demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
          CONVERT(CONCAT(@seed_tag, ' | Grupo adultos demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
      )
  AND NOT EXISTS (
      SELECT 1
        FROM class_schedules cs
       WHERE cs.class_id = c.id
         AND cs.day_of_week = x.day_of_week
         AND cs.start_time = x.start_time
         AND cs.end_time = x.end_time
  );

SELECT
    'classes_seeded' AS step,
    (
        SELECT COUNT(*)
          FROM classes c
          JOIN tmp_seed_context ctx
            ON ctx.organization_id = c.organization_id
           AND ctx.branch_id = c.branch_id
         WHERE CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
               IN (
                   CONVERT(CONCAT(@seed_tag, ' | Grupo infantil demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
                   CONVERT(CONCAT(@seed_tag, ' | Grupo intermedio demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
                   CONVERT(CONCAT(@seed_tag, ' | Grupo adultos demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
               )
    ) AS seeded_classes,
    (
        SELECT COUNT(*)
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
               )
    ) AS seeded_schedules;
