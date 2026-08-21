-- ============================================================
-- Migration: manual_migration_20260821_seed_belts_all_orgs
-- Objetivo: Insertar catálogo de cintas INFANTILES y ADULTOS
--           para TODAS las organizaciones existentes, y
--           asignar CINTA BLANCA por defecto a alumnos que
--           aún no tienen cinta asignada (según edad).
--
-- Stripes: siempre color NEGRO (#212121).
-- Infantiles (<16): Blanco Infantil, Gris, Amarillo, Naranja, Verde
-- Adultos    (>=16): Blanca, Azul, Púrpura, Marrón, Negra,
--                    Rojo+Negro, Rojo+Blanco, Rojo
-- ============================================================

DELIMITER $$

DROP PROCEDURE IF EXISTS seed_belts_for_all_orgs$$
CREATE PROCEDURE seed_belts_for_all_orgs()
BEGIN
  DECLARE done INT DEFAULT FALSE;
  DECLARE v_org_id INT;
  DECLARE v_org_name VARCHAR(255);

  DECLARE org_cursor CURSOR FOR
    SELECT id, name FROM organizations WHERE is_active = 1 ORDER BY id;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

  OPEN org_cursor;
  org_loop: LOOP
    FETCH org_cursor INTO v_org_id, v_org_name;
    IF done THEN LEAVE org_loop; END IF;

    -- ============================================================
    -- CINTURONES INFANTILES (order_index 1..9  para separar)
    -- ============================================================

    -- Blanco Infantil
    INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
    SELECT v_org_id, 'blanca_infantil', 'Blanca (Infantil)', '#FFFFFF', '#212121', 1, 1, 'Grado inicial - menores 16 años'
    WHERE NOT EXISTS (SELECT 1 FROM belt_levels WHERE organization_id = v_org_id AND name = 'blanca_infantil');
    SET @ID = LAST_INSERT_ID();
    IF @ID > 0 THEN
      INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
        (@ID, 'bi-1', '1ª barra', '#212121', 1, 1),
        (@ID, 'bi-2', '2ª barra', '#212121', 2, 1),
        (@ID, 'bi-3', '3ª barra', '#212121', 3, 1),
        (@ID, 'bi-4', '4ª barra', '#212121', 4, 1);
    END IF;

    -- Gris Infantil
    INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
    SELECT v_org_id, 'gris_infantil', 'Gris', '#616161', '#FFFFFF', 2, 1, 'Segundo grado infantil'
    WHERE NOT EXISTS (SELECT 1 FROM belt_levels WHERE organization_id = v_org_id AND name = 'gris_infantil');
    SET @ID = LAST_INSERT_ID();
    IF @ID > 0 THEN
      INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
        (@ID, 'gi-1', '1ª barra', '#212121', 1, 1),
        (@ID, 'gi-2', '2ª barra', '#212121', 2, 1),
        (@ID, 'gi-3', '3ª barra', '#212121', 3, 1),
        (@ID, 'gi-4', '4ª barra', '#212121', 4, 1);
    END IF;

    -- Amarillo Infantil
    INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
    SELECT v_org_id, 'amarillo_infantil', 'Amarillo', '#FDD835', '#212121', 3, 1, 'Tercer grado infantil'
    WHERE NOT EXISTS (SELECT 1 FROM belt_levels WHERE organization_id = v_org_id AND name = 'amarillo_infantil');
    SET @ID = LAST_INSERT_ID();
    IF @ID > 0 THEN
      INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
        (@ID, 'ai-1', '1ª barra', '#212121', 1, 1),
        (@ID, 'ai-2', '2ª barra', '#212121', 2, 1),
        (@ID, 'ai-3', '3ª barra', '#212121', 3, 1),
        (@ID, 'ai-4', '4ª barra', '#212121', 4, 1);
    END IF;

    -- Naranja Infantil
    INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
    SELECT v_org_id, 'naranja_infantil', 'Naranja', '#FB8C00', '#FFFFFF', 4, 1, 'Cuarto grado infantil'
    WHERE NOT EXISTS (SELECT 1 FROM belt_levels WHERE organization_id = v_org_id AND name = 'naranja_infantil');
    SET @ID = LAST_INSERT_ID();
    IF @ID > 0 THEN
      INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
        (@ID, 'ni-1', '1ª barra', '#212121', 1, 1),
        (@ID, 'ni-2', '2ª barra', '#212121', 2, 1),
        (@ID, 'ni-3', '3ª barra', '#212121', 3, 1),
        (@ID, 'ni-4', '4ª barra', '#212121', 4, 1);
    END IF;

    -- Verde Infantil
    INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
    SELECT v_org_id, 'verde_infantil', 'Verde', '#43A047', '#FFFFFF', 5, 1, 'Ultimo grado infantil'
    WHERE NOT EXISTS (SELECT 1 FROM belt_levels WHERE organization_id = v_org_id AND name = 'verde_infantil');
    SET @ID = LAST_INSERT_ID();
    IF @ID > 0 THEN
      INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
        (@ID, 'vi-1', '1ª barra', '#212121', 1, 1),
        (@ID, 'vi-2', '2ª barra', '#212121', 2, 1),
        (@ID, 'vi-3', '3ª barra', '#212121', 3, 1),
        (@ID, 'vi-4', '4ª barra', '#212121', 4, 1);
    END IF;

    -- ============================================================
    -- CINTURONES ADULTOS (order_index 10..19 para separar)
    -- ============================================================

    -- Blanca Adulto
    INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
    SELECT v_org_id, 'blanca', 'Blanca', '#FFFFFF', '#212121', 10, 1, 'Grado inicial adultos (>=16)'
    WHERE NOT EXISTS (SELECT 1 FROM belt_levels WHERE organization_id = v_org_id AND name = 'blanca');
    SET @ID = LAST_INSERT_ID();
    IF @ID > 0 THEN
      INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
        (@ID, 'ba-1', '1ª barra', '#212121', 1, 1),
        (@ID, 'ba-2', '2ª barra', '#212121', 2, 1),
        (@ID, 'ba-3', '3ª barra', '#212121', 3, 1),
        (@ID, 'ba-4', '4ª barra', '#212121', 4, 1);
    END IF;

    -- Azul
    INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
    SELECT v_org_id, 'azul', 'Azul', '#1565C0', '#FFFFFF', 11, 1, 'Primer grado de graduacion'
    WHERE NOT EXISTS (SELECT 1 FROM belt_levels WHERE organization_id = v_org_id AND name = 'azul');
    SET @ID = LAST_INSERT_ID();
    IF @ID > 0 THEN
      INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
        (@ID, 'az-1', '1ª barra', '#212121', 1, 1),
        (@ID, 'az-2', '2ª barra', '#212121', 2, 1),
        (@ID, 'az-3', '3ª barra', '#212121', 3, 1),
        (@ID, 'az-4', '4ª barra', '#212121', 4, 1);
    END IF;

    -- Purpura
    INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
    SELECT v_org_id, 'purpura', 'Purpura', '#6A1B9A', '#FFFFFF', 12, 1, 'Grado intermedio avanzado'
    WHERE NOT EXISTS (SELECT 1 FROM belt_levels WHERE organization_id = v_org_id AND name = 'purpura');
    SET @ID = LAST_INSERT_ID();
    IF @ID > 0 THEN
      INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
        (@ID, 'pu-1', '1ª barra', '#212121', 1, 1),
        (@ID, 'pu-2', '2ª barra', '#212121', 2, 1),
        (@ID, 'pu-3', '3ª barra', '#212121', 3, 1),
        (@ID, 'pu-4', '4ª barra', '#212121', 4, 1);
    END IF;

    -- Marron
    INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
    SELECT v_org_id, 'marron', 'Marron', '#5D4037', '#FFFFFF', 13, 1, 'Ultimo grado antes de cinta negra'
    WHERE NOT EXISTS (SELECT 1 FROM belt_levels WHERE organization_id = v_org_id AND name = 'marron');
    SET @ID = LAST_INSERT_ID();
    IF @ID > 0 THEN
      INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
        (@ID, 'ma-1', '1ª barra', '#212121', 1, 1),
        (@ID, 'ma-2', '2ª barra', '#212121', 2, 1),
        (@ID, 'ma-3', '3ª barra', '#212121', 3, 1),
        (@ID, 'ma-4', '4ª barra', '#212121', 4, 1);
    END IF;

    -- Negra
    INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
    SELECT v_org_id, 'negra', 'Negra', '#212121', '#FFFFFF', 14, 1, 'Grado de instructor / Dan'
    WHERE NOT EXISTS (SELECT 1 FROM belt_levels WHERE organization_id = v_org_id AND name = 'negra');
    SET @ID = LAST_INSERT_ID();
    IF @ID > 0 THEN
      INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
        (@ID, 'ne-1', '1 Dan', '#212121', 1, 1),
        (@ID, 'ne-2', '2 Dan', '#212121', 2, 1),
        (@ID, 'ne-3', '3 Dan', '#212121', 3, 1),
        (@ID, 'ne-4', '4 Dan', '#212121', 4, 1);
    END IF;

    -- Rojo y Negro (Coral bajo)
    INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
    SELECT v_org_id, 'rojo_negro', 'Rojo y Negro', '#C62828', '#FFFFFF', 15, 1, 'Grado maestro Coral (cintas rojo-negro, 5-6 Dan)'
    WHERE NOT EXISTS (SELECT 1 FROM belt_levels WHERE organization_id = v_org_id AND name = 'rojo_negro');
    SET @ID = LAST_INSERT_ID();
    IF @ID > 0 THEN
      INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
        (@ID, 'rn-1', '5 Dan', '#212121', 1, 1),
        (@ID, 'rn-2', '6 Dan', '#212121', 2, 1);
    END IF;

    -- Rojo y Blanco (Coral alto)
    INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
    SELECT v_org_id, 'rojo_blanco', 'Rojo y Blanco', '#E53935', '#FFFFFF', 16, 1, 'Grado maestro Coral alto (7-8 Dan)'
    WHERE NOT EXISTS (SELECT 1 FROM belt_levels WHERE organization_id = v_org_id AND name = 'rojo_blanco');
    SET @ID = LAST_INSERT_ID();
    IF @ID > 0 THEN
      INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
        (@ID, 'rb-1', '7 Dan', '#212121', 1, 1),
        (@ID, 'rb-2', '8 Dan', '#212121', 2, 1);
    END IF;

    -- Rojo (Han)
    INSERT INTO belt_levels (organization_id, name, display_name, color_hex, text_color_hex, order_index, is_active, description)
    SELECT v_org_id, 'rojo', 'Rojo', '#B71C1C', '#FFFFFF', 17, 1, 'Grado maximo Han (9-10 Dan)'
    WHERE NOT EXISTS (SELECT 1 FROM belt_levels WHERE organization_id = v_org_id AND name = 'rojo');
    SET @ID = LAST_INSERT_ID();
    IF @ID > 0 THEN
      INSERT INTO belt_stripes (belt_level_id, name, display_name, color_hex, order_index, is_active) VALUES
        (@ID, 'ro-1', '9 Dan',  '#212121', 1, 1),
        (@ID, 'ro-2', '10 Dan', '#212121', 2, 1);
    END IF;

    -- ============================================================
    -- UPDATE ALUMNOS -> marcar is_minor y asignar cinta blanca
    -- (solo si current_belt_level_id es NULL / sin cinta)
    -- ============================================================
    UPDATE students s
    SET s.is_minor = IF(TIMESTAMPDIFF(YEAR, s.birth_date, CURDATE()) < 16, 1, 0)
    WHERE s.organization_id = v_org_id;

    UPDATE students s
    INNER JOIN belt_levels bl ON bl.organization_id = s.organization_id AND bl.name = 'blanca_infantil'
    SET s.current_belt_level_id = bl.id, s.current_stripe_id = NULL
    WHERE s.organization_id = v_org_id
      AND s.current_belt_level_id IS NULL
      AND TIMESTAMPDIFF(YEAR, s.birth_date, CURDATE()) < 16;

    UPDATE students s
    INNER JOIN belt_levels bl ON bl.organization_id = s.organization_id AND bl.name = 'blanca'
    SET s.current_belt_level_id = bl.id, s.current_stripe_id = NULL
    WHERE s.organization_id = v_org_id
      AND s.current_belt_level_id IS NULL
      AND TIMESTAMPDIFF(YEAR, s.birth_date, CURDATE()) >= 16;

  END LOOP;
  CLOSE org_cursor;
END$$
DELIMITER ;

-- Ejecutar
CALL seed_belts_for_all_orgs();

-- ============================================================
-- RESUMEN POST-EJECUCION
-- ============================================================
SELECT 'Resumen por organizacion:' AS resumen;
SELECT
  o.id AS org_id,
  o.name AS organizacion,
  COUNT(DISTINCT bl.id) AS cintas_activas,
  COUNT(DISTINCT CASE WHEN bl.name LIKE '%infantil%' THEN bl.id END) AS infantiles,
  COUNT(DISTINCT CASE WHEN bl.name NOT LIKE '%infantil%' THEN bl.id END) AS adultas,
  COUNT(DISTINCT bs.id) AS stripes
FROM organizations o
LEFT JOIN belt_levels bl ON bl.organization_id = o.id
LEFT JOIN belt_stripes bs ON bs.belt_level_id = bl.id
WHERE o.is_active = 1
GROUP BY o.id, o.name ORDER BY o.id;

SELECT 'Estado alumnos:' AS info;
SELECT
  o.name AS organizacion,
  COUNT(s.id) AS total,
  SUM(s.is_minor) AS menores_16,
  SUM(1-s.is_minor) AS adultos,
  SUM(CASE WHEN s.current_belt_level_id IS NOT NULL THEN 1 ELSE 0 END) AS con_cinta,
  SUM(CASE WHEN s.current_belt_level_id IS NULL THEN 1 ELSE 0 END) AS sin_cinta
FROM organizations o
LEFT JOIN students s ON s.organization_id = o.id
WHERE o.is_active = 1
GROUP BY o.id, o.name ORDER BY o.id;

DROP PROCEDURE IF EXISTS seed_belts_for_all_orgs;
