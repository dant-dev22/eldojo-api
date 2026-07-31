SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

SET @target_email := 'dantedev22@gmail.com';
SET @seed_tag := 'seed_demo_prod_20260730';
SET @user_id := NULL;
SET @organization_id := NULL;
SET @branch_id := NULL;
SET @discipline_id := NULL;

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

INSERT INTO branches (
    organization_id,
    name,
    country,
    state,
    city,
    address,
    timezone,
    qr_secret,
    is_active
)
SELECT
    @organization_id,
    'Sucursal Principal',
    'Republica Dominicana',
    'Distrito Nacional',
    'Santo Domingo',
    'Direccion principal',
    'America/Santo_Domingo',
    SHA2(CONCAT(@seed_tag, '-branch-', @organization_id), 256),
    1
WHERE @organization_id IS NOT NULL
  AND @branch_id IS NULL;

SET @branch_id := COALESCE(
    @branch_id,
    (
        SELECT b.id
          FROM branches b
         WHERE b.organization_id = @organization_id
         ORDER BY b.id ASC
         LIMIT 1
    )
);

INSERT INTO disciplines (
    organization_id,
    name,
    is_active
)
SELECT
    @organization_id,
    'Disciplina Demo',
    1
WHERE @organization_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
        FROM disciplines d
       WHERE d.organization_id = @organization_id
         AND d.is_active = 1
  );

SET @discipline_id := (
    SELECT d.id
      FROM disciplines d
     WHERE d.organization_id = @organization_id
       AND d.is_active = 1
     ORDER BY d.created_at ASC, d.id ASC
     LIMIT 1
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
    @organization_id,
    @branch_id,
    @discipline_id,
    'Karate Infantil',
    CONCAT(@seed_tag, ' | Grupo infantil demo'),
    'Sensei Rivera',
    18,
    1
WHERE @organization_id IS NOT NULL
  AND @branch_id IS NOT NULL
  AND @discipline_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
        FROM classes c
       WHERE c.organization_id = @organization_id
         AND c.branch_id = @branch_id
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
    @organization_id,
    @branch_id,
    @discipline_id,
    'Karate Intermedio',
    CONCAT(@seed_tag, ' | Grupo intermedio demo'),
    'Sensei Morales',
    20,
    1
WHERE @organization_id IS NOT NULL
  AND @branch_id IS NOT NULL
  AND @discipline_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
        FROM classes c
       WHERE c.organization_id = @organization_id
         AND c.branch_id = @branch_id
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
    @organization_id,
    @branch_id,
    @discipline_id,
    'Karate Adultos',
    CONCAT(@seed_tag, ' | Grupo adultos demo'),
    'Sensei Castillo',
    24,
    1
WHERE @organization_id IS NOT NULL
  AND @branch_id IS NOT NULL
  AND @discipline_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
        FROM classes c
       WHERE c.organization_id = @organization_id
         AND c.branch_id = @branch_id
         AND CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
             = CONVERT(CONCAT(@seed_tag, ' | Grupo adultos demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
  );

INSERT INTO class_schedules (class_id, day_of_week, start_time, end_time)
SELECT c.id, x.day_of_week, x.start_time, x.end_time
FROM classes c
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
WHERE c.organization_id = @organization_id
  AND c.branch_id = @branch_id
  AND CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
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
    @organization_id AS organization_id,
    @branch_id AS branch_id,
    @discipline_id AS discipline_id,
    (
        SELECT COUNT(*)
          FROM classes c
         WHERE c.organization_id = @organization_id
           AND c.branch_id = @branch_id
           AND CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
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
         WHERE c.organization_id = @organization_id
           AND c.branch_id = @branch_id
           AND CONVERT(c.description USING utf8mb4) COLLATE utf8mb4_unicode_ci
               IN (
                   CONVERT(CONCAT(@seed_tag, ' | Grupo infantil demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
                   CONVERT(CONCAT(@seed_tag, ' | Grupo intermedio demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
                   CONVERT(CONCAT(@seed_tag, ' | Grupo adultos demo') USING utf8mb4) COLLATE utf8mb4_unicode_ci
               )
    ) AS seeded_schedules;
