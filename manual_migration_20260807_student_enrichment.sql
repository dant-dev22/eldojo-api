-- ============================================================
-- Migration: Enriquecimiento de ficha de alumno
-- Fecha: 2026-08-07
-- Descripción: Teléfono, email, contacto emergencia,
--              ficha médica, documentos (waiver + fotos),
--              personas autorizadas para retiro de menores.
-- ============================================================

-- -----------------------------------------------------------
-- 1. Nuevos campos directamente en students: teléfono y email
-- -----------------------------------------------------------
ALTER TABLE students
    ADD COLUMN phone VARCHAR(50) NULL COMMENT 'Teléfono principal del alumno'
        AFTER guardian_phone,
    ADD COLUMN email VARCHAR(255) NULL COMMENT 'Email personal del alumno'
        AFTER phone,
    ADD COLUMN is_minor TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Flag: Si el alumno es menor de edad (se infiere tambien por edad)'
        AFTER email,
    ADD KEY ix_students_phone (phone),
    ADD KEY ix_students_email (email);

-- -----------------------------------------------------------
-- 2. emergency_contacts - Contactos de emergencia por alumno
-- -----------------------------------------------------------
CREATE TABLE emergency_contacts (
    id INT NOT NULL AUTO_INCREMENT,
    student_id INT NOT NULL,
    organization_id INT NOT NULL,
    full_name VARCHAR(200) NOT NULL COMMENT 'Nombre completo del contacto de contacto',
    relationship VARCHAR(80) NULL COMMENT 'Parentesco / vínculo con el alumno (madre, padre, tutor, etc.',
    phone VARCHAR(50) NOT NULL COMMENT 'Teléfono del contacto',
    secondary_phone VARCHAR(50) NULL COMMENT 'Teléfono adicional',
    email VARCHAR(255) NULL,
    priority INT NOT NULL DEFAULT 1 COMMENT 'Orden de prioridad (1 = principal, 2 = secundario, etc.',
    notes VARCHAR(300) NULL COMMENT 'Notas adicionales de contacto',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,
    PRIMARY KEY (id),
    KEY ix_emergency_contacts_student_id (student_id),
    KEY ix_emergency_contacts_organization_id (organization_id),
    KEY ix_emergency_contacts_deleted_at (deleted_at),
    CONSTRAINT fk_emergency_contacts_student_id
        FOREIGN KEY (student_id) REFERENCES students(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_emergency_contacts_organization_id
        FOREIGN KEY (organization_id) REFERENCES organizations(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
-- 3. medical_records - Ficha médica por alumno (1:1)
-- -----------------------------------------------------------
CREATE TABLE medical_records (
    id INT NOT NULL AUTO_INCREMENT,
    student_id INT NOT NULL UNIQUE,
    organization_id INT NOT NULL,
    blood_type VARCHAR(10) NULL COMMENT 'Tipo de sangre: A+, A-, B+, B-, AB+, AB-, O+, O-',
    allergies TEXT NULL COMMENT 'Alergias conocidas (separadas por comas o texto libre)',
    previous_injuries TEXT NULL COMMENT 'Lesiones preexistentes / operaciones previas',
    insurance_type ENUM('public', 'private', 'none') NOT NULL DEFAULT 'none' COMMENT 'Tipo de seguro médico',
    insurance_provider VARCHAR(200) NULL COMMENT 'Nombre de la compañía / clínica / EPS',
    insurance_policy_number VARCHAR(150) NULL COMMENT 'Número de póliza o afiliación',
    chronic_conditions TEXT NULL COMMENT 'Enfermedades crónicas / tratamientos continuos',
    medications TEXT NULL COMMENT 'Medicamentos de uso regular',
    physician_name VARCHAR(200) NULL COMMENT 'Nombre del médico tratante',
    physician_phone VARCHAR(50) NULL COMMENT 'Teléfono del médico',
    tetanus_vaccine_date DATE NULL COMMENT 'Fecha última vacuna tetanos',
    additional_notes TEXT NULL COMMENT 'Observaciones médicas adicionales',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_medical_records_student_id (student_id),
    KEY ix_medical_records_organization_id (organization_id),
    KEY ix_medical_records_deleted_at (deleted_at),
    CONSTRAINT fk_medical_records_student_id
        FOREIGN KEY (student_id) REFERENCES students(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_medical_records_organization_id
        FOREIGN KEY (organization_id) REFERENCES organizations(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
-- 4. student_documents - Waiver, consentimiento de fotos
-- -----------------------------------------------------------
CREATE TABLE student_documents (
    id INT NOT NULL AUTO_INCREMENT,
    student_id INT NOT NULL,
    organization_id INT NOT NULL,
    document_type ENUM('liability_waiver', 'photo_consent', 'other') NOT NULL COMMENT 'Tipo de documento',
    title VARCHAR(255) NOT NULL COMMENT 'Título / nombre amigable',
    file_url VARCHAR(500) NOT NULL COMMENT 'URL del archivo firmado / escaneado',
    file_name VARCHAR(255) NULL,
    file_size_bytes BIGINT NULL,
    signed_at DATE NULL COMMENT 'Fecha de firma del documento',
    signed_by_full_name VARCHAR(200) NULL COMMENT 'Nombre de quien firmó (alumno o tutor)',
    witness_name VARCHAR(200) NULL COMMENT 'Nombre del testigo / staff que recibió',
    expires_at DATE NULL COMMENT 'Fecha de vencimiento si aplica',
    notes VARCHAR(500) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,
    PRIMARY KEY (id),
    KEY ix_student_documents_student_id (student_id),
    KEY ix_student_documents_organization_id (organization_id),
    KEY ix_student_documents_type (document_type),
    KEY ix_student_documents_deleted_at (deleted_at),
    CONSTRAINT fk_student_documents_student_id
        FOREIGN KEY (student_id) REFERENCES students(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_student_documents_organization_id
        FOREIGN KEY (organization_id) REFERENCES organizations(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
-- 5. authorized_persons - Personas autorizadas a retirar menores
-- -----------------------------------------------------------
CREATE TABLE authorized_persons (
    id INT NOT NULL AUTO_INCREMENT,
    student_id INT NOT NULL,
    organization_id INT NOT NULL,
    full_name VARCHAR(200) NOT NULL COMMENT 'Nombre completo de la persona autorizada',
    relationship VARCHAR(80) NULL COMMENT 'Parentesco con el alumno',
    dni_type VARCHAR(20) NULL COMMENT 'Tipo de documento: DNI, CURP, Pasaporte',
    dni_number VARCHAR(80) NOT NULL COMMENT 'Número de documento / identificación',
    dni_verified TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Flag: staff verificó el documento físico contra el número',
    dni_verified_by_user_id INT NULL COMMENT 'Usuario que verificó el DNI',
    dni_photo_url VARCHAR(500) NULL COMMENT 'Foto / escaneo del documento',
    phone VARCHAR(50) NOT NULL,
    secondary_phone VARCHAR(50) NULL,
    photo_url VARCHAR(500) NULL COMMENT 'Foto de la persona (reconocimiento visual)',
    authorization_notes VARCHAR(500) NULL COMMENT 'Horario / restricciones especiales',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,
    PRIMARY KEY (id),
    KEY ix_authorized_persons_student_id (student_id),
    KEY ix_authorized_persons_organization_id (organization_id),
    KEY ix_authorized_persons_dni_number (dni_number),
    KEY ix_authorized_persons_active (is_active),
    KEY ix_authorized_persons_deleted_at (deleted_at),
    CONSTRAINT fk_authorized_persons_student_id
        FOREIGN KEY (student_id) REFERENCES students(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_authorized_persons_organization_id
        FOREIGN KEY (organization_id) REFERENCES organizations(id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_authorized_persons_verified_by_user
        FOREIGN KEY (dni_verified_by_user_id) REFERENCES users(id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
-- 6. Vista auxiliar calculada: ficha completa status
--    Se deja como query en el backend (performance).
-- -----------------------------------------------------------
