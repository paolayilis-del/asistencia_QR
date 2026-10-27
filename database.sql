-- ═══════════════════════════════════════════════════════════════════════
--  Sistema Web de Asistencia Docente por QR
--  Estructura completa de la base de datos · PostgreSQL 14+
-- ═══════════════════════════════════════════════════════════════════════
--
--  Este archivo reconstruye la base de datos desde cero: tipos, tablas,
--  claves, restricciones, índices, vistas, funciones y datos iniciales.
--
--  Ejecución:
--    createdb -U postgres asistencia_qr
--    psql -U postgres -d asistencia_qr -f database.sql
--
--  Acceso inicial:  admin@datly.local  /  Admin123*
--
--  Generado el 2026-08-10 a partir de backend/prisma/schema.prisma
-- ═══════════════════════════════════════════════════════════════════════

BEGIN;

-- ─────────────────────────── Extensiones ──────────────────────────────
-- gen_random_uuid() para los identificadores; unaccent para búsquedas
-- que deban ignorar tildes.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- ══════════════════ ESTRUCTURA (generada del esquema) ═════════════════

-- CreateEnum
CREATE TYPE "record_status" AS ENUM ('ACTIVE', 'INACTIVE');

-- CreateEnum
CREATE TYPE "attendance_type" AS ENUM ('CHECK_IN', 'CHECK_OUT');

-- CreateEnum
CREATE TYPE "attendance_status" AS ENUM ('ON_TIME', 'LATE', 'EARLY_DEPARTURE');

-- CreateEnum
CREATE TYPE "audit_action" AS ENUM ('CREATE', 'UPDATE', 'DELETE', 'ACTIVATE', 'DEACTIVATE', 'LOGIN', 'LOGOUT', 'ATTENDANCE');

-- CreateEnum
-- Motivo de la justificacion presentada por el docente.
CREATE TYPE "excuse_type" AS ENUM ('INCAPACIDAD', 'PERMISO', 'OTRO');

-- CreateEnum
-- Estado de la revision de la justificacion.
CREATE TYPE "excuse_status" AS ENUM ('PENDING', 'APPROVED', 'REJECTED');

-- CreateEnum
CREATE TYPE "setting_type" AS ENUM ('STRING', 'NUMBER', 'BOOLEAN', 'JSON');

-- CreateEnum
-- Niveles del servicio educativo formal segun la Ley 115 de 1994:
--   Preescolar        art. 15-18   (Decreto 2247 de 1997: prejardin, jardin,
--                                   transicion; solo transicion es obligatorio)
--   Basica primaria   art. 19-21   grados 1 a 5
--   Basica secundaria art. 19-22   grados 6 a 9
--   Media             art. 27-35   grados 10 y 11, academica o tecnica
CREATE TYPE "education_level" AS ENUM (
  'PREESCOLAR', 'BASICA_PRIMARIA', 'BASICA_SECUNDARIA', 'MEDIA'
);

-- CreateTable
CREATE TABLE "users" (
    "id" UUID NOT NULL,
    "first_name" VARCHAR(120) NOT NULL,
    "last_name" VARCHAR(120) NOT NULL,
    "document" VARCHAR(40) NOT NULL,
    "email" VARCHAR(180) NOT NULL,
    "phone" VARCHAR(30),
    "password" VARCHAR(255) NOT NULL,
    "status" "record_status" NOT NULL DEFAULT 'ACTIVE',
    "role_id" UUID NOT NULL,
    "last_login_at" TIMESTAMPTZ(3),
    "failed_login_attempts" SMALLINT NOT NULL DEFAULT 0,
    "locked_until" TIMESTAMPTZ(3),
    "must_change_password" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    "deleted_at" TIMESTAMPTZ(3),

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "refresh_tokens" (
    "id" UUID NOT NULL,
    "token_hash" VARCHAR(255) NOT NULL,
    "user_id" UUID NOT NULL,
    "expires_at" TIMESTAMPTZ(3) NOT NULL,
    "revoked_at" TIMESTAMPTZ(3),
    "ip_address" VARCHAR(60),
    "user_agent" VARCHAR(400),
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "refresh_tokens_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "roles" (
    "id" UUID NOT NULL,
    -- Identificador interno del rol. Es lo que consulta el control de acceso,
    -- y no cambia nunca: asi el nombre visible se puede editar sin que nadie
    -- pierda sus permisos.
    "code" VARCHAR(40) NOT NULL,
    -- Nombre que se muestra en la interfaz. Editable.
    "name" VARCHAR(60) NOT NULL,
    "description" VARCHAR(300),
    "is_system" BOOLEAN NOT NULL DEFAULT false,
    "status" "record_status" NOT NULL DEFAULT 'ACTIVE',
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    "deleted_at" TIMESTAMPTZ(3),

    CONSTRAINT "roles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "permissions" (
    "id" UUID NOT NULL,
    "code" VARCHAR(80) NOT NULL,
    "name" VARCHAR(120) NOT NULL,
    "module" VARCHAR(60) NOT NULL,
    "description" VARCHAR(300),
    "is_system" BOOLEAN NOT NULL DEFAULT false,
    "status" "record_status" NOT NULL DEFAULT 'ACTIVE',
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    "deleted_at" TIMESTAMPTZ(3),

    CONSTRAINT "permissions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "role_permissions" (
    "role_id" UUID NOT NULL,
    "permission_id" UUID NOT NULL,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "role_permissions_pkey" PRIMARY KEY ("role_id","permission_id")
);

-- CreateTable
CREATE TABLE "teachers" (
    "id" UUID NOT NULL,
    "code" VARCHAR(40) NOT NULL,
    "first_name" VARCHAR(120) NOT NULL,
    "last_name" VARCHAR(120) NOT NULL,
    "document" VARCHAR(40) NOT NULL,
    "email" VARCHAR(200) NOT NULL,
    "phone" VARCHAR(30),
    -- Ruta publica desde la que se sirve la fotografia
    "photo_url" VARCHAR(300),
    -- La fotografia se guarda aqui, no en el disco: asi viaja con el
    -- respaldo de la base y no quedan archivos huerfanos al eliminar.
    -- Se normaliza a WEBP de 512x512, unos 10 KB por docente.
    "photo" BYTEA,
    "photo_mime" VARCHAR(40),
    "status" "record_status" NOT NULL DEFAULT 'ACTIVE',
    "user_id" UUID,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    "deleted_at" TIMESTAMPTZ(3),

    CONSTRAINT "teachers_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "subjects" (
    "id" UUID NOT NULL,
    "code" VARCHAR(40) NOT NULL,
    "name" VARCHAR(120) NOT NULL,
    "description" VARCHAR(300),
    "weekly_hours" SMALLINT,
    "color" VARCHAR(7) DEFAULT '#4F46E5',
    "status" "record_status" NOT NULL DEFAULT 'ACTIVE',
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    "deleted_at" TIMESTAMPTZ(3),

    CONSTRAINT "subjects_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "teacher_subjects" (
    "teacher_id" UUID NOT NULL,
    "subject_id" UUID NOT NULL,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "teacher_subjects_pkey" PRIMARY KEY ("teacher_id","subject_id")
);

-- CreateTable
-- Grados del sistema educativo. Los define la Ley 115 de 1994, asi que vienen
-- cargados y no se crean a mano: la institucion solo elige cuales ofrece.
CREATE TABLE "grades" (
    "id" UUID NOT NULL,
    -- Identificador estable del grado: TR, 1, 2 ... 11
    "code" VARCHAR(10) NOT NULL,
    "name" VARCHAR(60) NOT NULL,
    "level" "education_level" NOT NULL,
    -- Orden en la escalera educativa, de prejardin (1) a once (14)
    "position" SMALLINT NOT NULL,
    "description" VARCHAR(300),
    "is_system" BOOLEAN NOT NULL DEFAULT false,
    "status" "record_status" NOT NULL DEFAULT 'ACTIVE',
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    "deleted_at" TIMESTAMPTZ(3),

    CONSTRAINT "grades_pkey" PRIMARY KEY ("id")
);

-- CreateTable
-- Cursos o grupos de un grado: 6A, 6B, 6C. Cada institucion abre los que
-- necesite segun su matricula.
CREATE TABLE "courses" (
    "id" UUID NOT NULL,
    "grade_id" UUID NOT NULL,
    -- Letra o denominacion del grupo dentro del grado
    "letter" VARCHAR(10) NOT NULL,
    -- Nombre completo ya compuesto, por ejemplo "6A". Se guarda resuelto para
    -- poder buscarlo y ordenarlo sin recomponerlo en cada consulta.
    "name" VARCHAR(80) NOT NULL,
    -- Jornada en la que funciona el curso. Opcional: hay grupos que no se
    -- adscriben a una sola.
    "shift_id" UUID,
    -- Docente director de grupo
    "homeroom_teacher_id" UUID,
    "capacity" SMALLINT,
    "status" "record_status" NOT NULL DEFAULT 'ACTIVE',
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    "deleted_at" TIMESTAMPTZ(3),

    CONSTRAINT "courses_pkey" PRIMARY KEY ("id")
);

-- CreateTable
-- Cursos que atiende cada docente. Un docente puede estar en varios y un
-- curso lo atienden varios docentes.
CREATE TABLE "teacher_courses" (
    "teacher_id" UUID NOT NULL,
    "course_id" UUID NOT NULL,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "teacher_courses_pkey" PRIMARY KEY ("teacher_id","course_id")
);

-- CreateTable
CREATE TABLE "shifts" (
    "id" UUID NOT NULL,
    "name" VARCHAR(80) NOT NULL,
    "description" VARCHAR(300),
    "status" "record_status" NOT NULL DEFAULT 'ACTIVE',
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    "deleted_at" TIMESTAMPTZ(3),

    CONSTRAINT "shifts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "schedules" (
    "id" UUID NOT NULL,
    "teacher_id" UUID NOT NULL,
    "shift_id" UUID NOT NULL,
    "subject_id" UUID,
    -- Curso al que se dicta esa franja
    "course_id" UUID,
    "day_of_week" SMALLINT,
    "check_in_time" VARCHAR(5) NOT NULL,
    "check_out_time" VARCHAR(5) NOT NULL,
    "tolerance_minutes" SMALLINT NOT NULL DEFAULT 10,
    "status" "record_status" NOT NULL DEFAULT 'ACTIVE',
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    "deleted_at" TIMESTAMPTZ(3),

    CONSTRAINT "schedules_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "attendances" (
    "id" UUID NOT NULL,
    "teacher_id" UUID NOT NULL,
    "schedule_id" UUID,
    "type" "attendance_type" NOT NULL,
    "status" "attendance_status" NOT NULL,
    "date" DATE NOT NULL,
    "registered_at" TIMESTAMPTZ(3) NOT NULL,
    "expected_time" VARCHAR(5),
    "minutes_diff" SMALLINT NOT NULL DEFAULT 0,
    "latitude" DOUBLE PRECISION,
    "longitude" DOUBLE PRECISION,
    "location_accuracy" DOUBLE PRECISION,
    "location_source" VARCHAR(30),
    "ip_address" VARCHAR(60),
    "user_agent" VARCHAR(400),
    "device" VARCHAR(120),
    "notes" VARCHAR(400),
    "registered_by_id" UUID,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    "deleted_at" TIMESTAMPTZ(3),

    CONSTRAINT "attendances_pkey" PRIMARY KEY ("id")
);

-- CreateTable
-- Justificaciones que presenta un docente para explicar una ausencia, una
-- tardanza o una salida anticipada. El archivo viaja dentro de la base de
-- datos, igual que la fotografia del docente.
CREATE TABLE "excuses" (
    "id" UUID NOT NULL,
    "teacher_id" UUID NOT NULL,
    "attendance_id" UUID,
    "type" "excuse_type" NOT NULL,
    "status" "excuse_status" NOT NULL DEFAULT 'PENDING',
    "date" DATE NOT NULL,
    "reason" TEXT NOT NULL,
    "file_name" VARCHAR(200),
    "file_mime" VARCHAR(80),
    "file_size" BIGINT,
    "file_data" BYTEA,
    "reviewed_by_id" UUID,
    "reviewed_at" TIMESTAMPTZ(3),
    "review_notes" TEXT,
    "created_by_id" UUID,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    "deleted_at" TIMESTAMPTZ(3),

    CONSTRAINT "excuses_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "audit_logs" (
    "id" UUID NOT NULL,
    "user_id" UUID,
    "user_email" VARCHAR(180),
    "user_name" VARCHAR(240),
    "action" "audit_action" NOT NULL,
    "module" VARCHAR(60) NOT NULL,
    "entity_id" VARCHAR(60),
    "description" VARCHAR(500) NOT NULL,
    "ip_address" VARCHAR(60),
    "user_agent" VARCHAR(400),
    "device" VARCHAR(120),
    "metadata" JSONB,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    "deleted_at" TIMESTAMPTZ(3),

    CONSTRAINT "audit_logs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "settings" (
    "id" UUID NOT NULL,
    "key" VARCHAR(80) NOT NULL,
    "value" TEXT NOT NULL,
    "type" "setting_type" NOT NULL DEFAULT 'STRING',
    "group" VARCHAR(60) NOT NULL DEFAULT 'general',
    "label" VARCHAR(160) NOT NULL,
    "description" VARCHAR(400),
    "is_public" BOOLEAN NOT NULL DEFAULT false,
    "is_system" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    "deleted_at" TIMESTAMPTZ(3),

    CONSTRAINT "settings_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "users_document_key" ON "users"("document");

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "users"("email");

-- CreateIndex
CREATE INDEX "users_status_deleted_at_idx" ON "users"("status", "deleted_at");

-- CreateIndex
CREATE INDEX "users_role_id_idx" ON "users"("role_id");

-- CreateIndex
CREATE INDEX "users_email_idx" ON "users"("email");

-- CreateIndex
CREATE INDEX "refresh_tokens_user_id_revoked_at_idx" ON "refresh_tokens"("user_id", "revoked_at");

-- CreateIndex
CREATE INDEX "refresh_tokens_expires_at_idx" ON "refresh_tokens"("expires_at");

-- CreateIndex
CREATE UNIQUE INDEX "roles_code_key" ON "roles"("code");

CREATE UNIQUE INDEX "roles_name_key" ON "roles"("name");

-- CreateIndex
CREATE INDEX "roles_status_deleted_at_idx" ON "roles"("status", "deleted_at");

-- CreateIndex
CREATE UNIQUE INDEX "permissions_code_key" ON "permissions"("code");

-- CreateIndex
CREATE INDEX "permissions_module_idx" ON "permissions"("module");

-- CreateIndex
CREATE INDEX "permissions_status_deleted_at_idx" ON "permissions"("status", "deleted_at");

-- CreateIndex
CREATE INDEX "role_permissions_permission_id_idx" ON "role_permissions"("permission_id");

-- CreateIndex
CREATE UNIQUE INDEX "teachers_code_key" ON "teachers"("code");

-- CreateIndex
CREATE UNIQUE INDEX "teachers_document_key" ON "teachers"("document");

-- CreateIndex
CREATE UNIQUE INDEX "teachers_email_key" ON "teachers"("email");

-- CreateIndex
CREATE UNIQUE INDEX "teachers_user_id_key" ON "teachers"("user_id");

-- CreateIndex
CREATE INDEX "teachers_status_deleted_at_idx" ON "teachers"("status", "deleted_at");

-- CreateIndex
CREATE INDEX "teachers_code_idx" ON "teachers"("code");

-- CreateIndex
CREATE INDEX "teachers_last_name_first_name_idx" ON "teachers"("last_name", "first_name");

-- CreateIndex
CREATE UNIQUE INDEX "subjects_code_key" ON "subjects"("code");

-- CreateIndex
CREATE INDEX "subjects_status_deleted_at_idx" ON "subjects"("status", "deleted_at");

-- CreateIndex
CREATE INDEX "subjects_code_idx" ON "subjects"("code");

-- CreateIndex
CREATE INDEX "teacher_subjects_subject_id_idx" ON "teacher_subjects"("subject_id");

-- CreateIndex
CREATE UNIQUE INDEX "grades_code_key" ON "grades"("code");

CREATE INDEX "grades_level_position_idx" ON "grades"("level", "position");

CREATE INDEX "grades_status_deleted_at_idx" ON "grades"("status", "deleted_at");

-- Un grado no puede tener dos grupos con la misma letra a la vez. El indice
-- ignora los eliminados, para que la letra pueda reutilizarse despues.
CREATE UNIQUE INDEX "courses_grade_letter_key"
  ON "courses"("grade_id", "letter") WHERE "deleted_at" IS NULL;

CREATE INDEX "courses_grade_id_idx" ON "courses"("grade_id");

CREATE INDEX "courses_shift_id_idx" ON "courses"("shift_id");

CREATE INDEX "courses_homeroom_teacher_id_idx" ON "courses"("homeroom_teacher_id");

CREATE INDEX "courses_status_deleted_at_idx" ON "courses"("status", "deleted_at");

CREATE INDEX "teacher_courses_course_id_idx" ON "teacher_courses"("course_id");

CREATE UNIQUE INDEX "shifts_name_key" ON "shifts"("name");

-- CreateIndex
CREATE INDEX "shifts_status_deleted_at_idx" ON "shifts"("status", "deleted_at");

-- CreateIndex
CREATE INDEX "schedules_teacher_id_status_idx" ON "schedules"("teacher_id", "status");

-- CreateIndex
CREATE INDEX "schedules_teacher_id_day_of_week_idx" ON "schedules"("teacher_id", "day_of_week");

-- CreateIndex
CREATE INDEX "schedules_shift_id_idx" ON "schedules"("shift_id");

-- CreateIndex
CREATE INDEX "schedules_subject_id_idx" ON "schedules"("subject_id");

CREATE INDEX "schedules_course_id_idx" ON "schedules"("course_id");

-- CreateIndex
CREATE INDEX "attendances_teacher_id_date_idx" ON "attendances"("teacher_id", "date");

-- CreateIndex
CREATE INDEX "attendances_date_type_idx" ON "attendances"("date", "type");

-- CreateIndex
CREATE INDEX "attendances_status_idx" ON "attendances"("status");

-- CreateIndex
CREATE INDEX "attendances_schedule_id_idx" ON "attendances"("schedule_id");

-- CreateIndex
CREATE INDEX "attendances_deleted_at_idx" ON "attendances"("deleted_at");

-- CreateIndex
CREATE INDEX "excuses_teacher_id_date_idx" ON "excuses"("teacher_id", "date");

-- CreateIndex
CREATE INDEX "excuses_status_idx" ON "excuses"("status");

-- CreateIndex
CREATE INDEX "excuses_date_idx" ON "excuses"("date");

-- CreateIndex
CREATE INDEX "excuses_deleted_at_idx" ON "excuses"("deleted_at");

-- CreateIndex
CREATE INDEX "audit_logs_user_id_idx" ON "audit_logs"("user_id");

-- CreateIndex
CREATE INDEX "audit_logs_action_idx" ON "audit_logs"("action");

-- CreateIndex
CREATE INDEX "audit_logs_module_idx" ON "audit_logs"("module");

-- CreateIndex
CREATE INDEX "audit_logs_created_at_idx" ON "audit_logs"("created_at");

-- CreateIndex
CREATE UNIQUE INDEX "settings_key_key" ON "settings"("key");

-- CreateIndex
CREATE INDEX "settings_group_idx" ON "settings"("group");

-- AddForeignKey
ALTER TABLE "users" ADD CONSTRAINT "users_role_id_fkey" FOREIGN KEY ("role_id") REFERENCES "roles"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "refresh_tokens" ADD CONSTRAINT "refresh_tokens_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "role_permissions" ADD CONSTRAINT "role_permissions_role_id_fkey" FOREIGN KEY ("role_id") REFERENCES "roles"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "role_permissions" ADD CONSTRAINT "role_permissions_permission_id_fkey" FOREIGN KEY ("permission_id") REFERENCES "permissions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "teachers" ADD CONSTRAINT "teachers_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "teacher_subjects" ADD CONSTRAINT "teacher_subjects_teacher_id_fkey" FOREIGN KEY ("teacher_id") REFERENCES "teachers"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "teacher_subjects" ADD CONSTRAINT "teacher_subjects_subject_id_fkey" FOREIGN KEY ("subject_id") REFERENCES "subjects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "schedules" ADD CONSTRAINT "schedules_teacher_id_fkey" FOREIGN KEY ("teacher_id") REFERENCES "teachers"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "schedules" ADD CONSTRAINT "schedules_shift_id_fkey" FOREIGN KEY ("shift_id") REFERENCES "shifts"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "schedules" ADD CONSTRAINT "schedules_subject_id_fkey" FOREIGN KEY ("subject_id") REFERENCES "subjects"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- Un grado con cursos abiertos no se elimina: se quedaria el curso sin grado
ALTER TABLE "courses" ADD CONSTRAINT "courses_grade_id_fkey" FOREIGN KEY ("grade_id") REFERENCES "grades"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "courses" ADD CONSTRAINT "courses_shift_id_fkey" FOREIGN KEY ("shift_id") REFERENCES "shifts"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- Si el director de grupo deja la institucion, el curso sigue existiendo
ALTER TABLE "courses" ADD CONSTRAINT "courses_homeroom_teacher_id_fkey" FOREIGN KEY ("homeroom_teacher_id") REFERENCES "teachers"("id") ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "teacher_courses" ADD CONSTRAINT "teacher_courses_teacher_id_fkey" FOREIGN KEY ("teacher_id") REFERENCES "teachers"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "teacher_courses" ADD CONSTRAINT "teacher_courses_course_id_fkey" FOREIGN KEY ("course_id") REFERENCES "courses"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "schedules" ADD CONSTRAINT "schedules_course_id_fkey" FOREIGN KEY ("course_id") REFERENCES "courses"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "attendances" ADD CONSTRAINT "attendances_teacher_id_fkey" FOREIGN KEY ("teacher_id") REFERENCES "teachers"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "attendances" ADD CONSTRAINT "attendances_schedule_id_fkey" FOREIGN KEY ("schedule_id") REFERENCES "schedules"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "excuses" ADD CONSTRAINT "excuses_teacher_id_fkey" FOREIGN KEY ("teacher_id") REFERENCES "teachers"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "excuses" ADD CONSTRAINT "excuses_attendance_id_fkey" FOREIGN KEY ("attendance_id") REFERENCES "attendances"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "excuses" ADD CONSTRAINT "excuses_reviewed_by_id_fkey" FOREIGN KEY ("reviewed_by_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "audit_logs" ADD CONSTRAINT "audit_logs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;


-- ═══════════════════ GENERACIÓN DE IDENTIFICADORES ════════════════════
-- La aplicación genera los UUID, pero al insertar directamente por SQL
-- conviene que la base también sepa hacerlo.

ALTER TABLE "users" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "refresh_tokens" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "roles" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "permissions" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "teachers" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "subjects" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "grades" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "courses" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "shifts" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "schedules" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "attendances" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "excuses" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "audit_logs" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "settings" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();


-- ═════════════════════ RESTRICCIONES DE VALIDACIÓN ════════════════════
-- Las reglas viven también en la base: si algún día otro programa
-- escribe en estas tablas, los datos siguen siendo coherentes.

-- Formato HH:mm de 24 horas en los horarios
ALTER TABLE "schedules" ADD CONSTRAINT "schedules_check_in_time_formato"
  CHECK ("check_in_time" ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$');
ALTER TABLE "schedules" ADD CONSTRAINT "schedules_check_out_time_formato"
  CHECK ("check_out_time" ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$');

-- La salida debe ser posterior a la entrada
ALTER TABLE "schedules" ADD CONSTRAINT "schedules_salida_posterior"
  CHECK ("check_out_time" > "check_in_time");

-- Día de la semana válido: 0 = domingo … 6 = sábado
ALTER TABLE "schedules" ADD CONSTRAINT "schedules_dia_valido"
  CHECK ("day_of_week" IS NULL OR "day_of_week" BETWEEN 0 AND 6);

-- Tolerancia dentro de un rango razonable (RN007)
ALTER TABLE "schedules" ADD CONSTRAINT "schedules_tolerancia_valida"
  CHECK ("tolerance_minutes" BETWEEN 0 AND 120);

-- Intensidad horaria semanal positiva
ALTER TABLE "subjects" ADD CONSTRAINT "subjects_horas_validas"
  CHECK ("weekly_hours" IS NULL OR "weekly_hours" BETWEEN 1 AND 60);

-- El grado ocupa un lugar en la escalera educativa: 1 = prejardin, 14 = once
ALTER TABLE "grades" ADD CONSTRAINT "grades_posicion_valida"
  CHECK ("position" BETWEEN 1 AND 30);

-- Cupo del curso positivo y dentro de lo razonable
ALTER TABLE "courses" ADD CONSTRAINT "courses_cupo_valido"
  CHECK ("capacity" IS NULL OR "capacity" BETWEEN 1 AND 100);

-- Color hexadecimal de la asignatura
ALTER TABLE "subjects" ADD CONSTRAINT "subjects_color_formato"
  CHECK ("color" IS NULL OR "color" ~ '^#[0-9A-Fa-f]{6}$');

-- Correos con formato mínimo verificable
ALTER TABLE "users" ADD CONSTRAINT "users_correo_formato"
  CHECK ("email" ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$');
ALTER TABLE "teachers" ADD CONSTRAINT "teachers_correo_formato"
  CHECK ("email" ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$');

-- Los intentos fallidos nunca son negativos
ALTER TABLE "users" ADD CONSTRAINT "users_intentos_no_negativos"
  CHECK ("failed_login_attempts" >= 0);

-- Hora esperada de la marcación, si se registró
ALTER TABLE "attendances" ADD CONSTRAINT "attendances_hora_esperada_formato"
  CHECK ("expected_time" IS NULL OR "expected_time" ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$');


-- ══════════════════════ ÍNDICES PARA SOFT DELETE ══════════════════════
-- Casi toda consulta del sistema filtra por "deleted_at IS NULL". Un
-- índice parcial solo cubre esas filas: ocupa menos y se recorre más
-- rápido que uno completo, porque los registros eliminados no entran.

CREATE INDEX "users_vigentes_idx"       ON "users" ("status") WHERE "deleted_at" IS NULL;
CREATE INDEX "teachers_vigentes_idx"    ON "teachers" ("status") WHERE "deleted_at" IS NULL;
CREATE INDEX "subjects_vigentes_idx"    ON "subjects" ("status") WHERE "deleted_at" IS NULL;
CREATE INDEX "shifts_vigentes_idx"      ON "shifts" ("status") WHERE "deleted_at" IS NULL;
CREATE INDEX "schedules_vigentes_idx"   ON "schedules" ("teacher_id", "day_of_week") WHERE "deleted_at" IS NULL;
CREATE INDEX "attendances_vigentes_idx" ON "attendances" ("teacher_id", "date") WHERE "deleted_at" IS NULL;

-- Búsqueda por texto en los listados, insensible a mayúsculas
CREATE INDEX "teachers_busqueda_idx" ON "teachers" (lower("last_name"), lower("first_name"));
CREATE INDEX "subjects_busqueda_idx" ON "subjects" (lower("name"));

-- Consulta del detalle de auditoría por contenido del JSON
CREATE INDEX "audit_logs_metadata_idx" ON "audit_logs" USING GIN ("metadata");


-- ════════════════════════════════ VISTAS ══════════════════════════════

-- Marcaciones con los nombres ya resueltos: evita repetir los mismos
-- JOIN en cada informe.
CREATE OR REPLACE VIEW "v_asistencia_detallada" AS
SELECT
  a."id",
  a."date"                                        AS fecha,
  a."registered_at"                               AS registrado_en,
  t."code"                                        AS codigo_docente,
  t."first_name" || ' ' || t."last_name"          AS docente,
  t."document"                                    AS documento,
  s."name"                                        AS jornada,
  m."name"                                        AS asignatura,
  a."type"                                        AS tipo,
  a."status"                                      AS estado,
  a."expected_time"                               AS hora_esperada,
  a."minutes_diff"                                AS diferencia_minutos,
  a."ip_address"                                  AS direccion_ip,
  a."device"                                      AS dispositivo
FROM "attendances" a
  JOIN "teachers"  t ON t."id" = a."teacher_id"
  LEFT JOIN "schedules" h ON h."id" = a."schedule_id"
  LEFT JOIN "shifts"    s ON s."id" = h."shift_id"
  LEFT JOIN "subjects"  m ON m."id" = h."subject_id"
WHERE a."deleted_at" IS NULL;

COMMENT ON VIEW "v_asistencia_detallada" IS
  'Marcaciones vigentes con docente, jornada y asignatura ya resueltos.';

-- Consolidado de puntualidad por docente, base de los reportes.
CREATE OR REPLACE VIEW "v_resumen_docente" AS
SELECT
  t."id"                                          AS docente_id,
  t."code"                                        AS codigo,
  t."first_name" || ' ' || t."last_name"          AS docente,
  COUNT(a."id")                                   AS total_marcaciones,
  COUNT(*) FILTER (WHERE a."type" = 'CHECK_IN')   AS entradas,
  COUNT(*) FILTER (WHERE a."type" = 'CHECK_OUT')  AS salidas,
  COUNT(*) FILTER (WHERE a."status" = 'ON_TIME')  AS puntuales,
  COUNT(*) FILTER (WHERE a."status" = 'LATE')     AS tardanzas,
  COALESCE(SUM(a."minutes_diff") FILTER (WHERE a."status" = 'LATE'), 0) AS minutos_retraso,
  CASE WHEN COUNT(a."id") = 0 THEN 100
       ELSE ROUND(COUNT(*) FILTER (WHERE a."status" = 'ON_TIME') * 100.0 / COUNT(a."id"))
  END                                             AS porcentaje_puntualidad
FROM "teachers" t
  LEFT JOIN "attendances" a ON a."teacher_id" = t."id" AND a."deleted_at" IS NULL
WHERE t."deleted_at" IS NULL
GROUP BY t."id", t."code", t."first_name", t."last_name";

COMMENT ON VIEW "v_resumen_docente" IS
  'Totales de asistencia y porcentaje de puntualidad por docente.';


-- ═══════════════════════════════ FUNCIONES ════════════════════════════

-- Evalúa la puntualidad de una entrada (RN007 y RN008). La aplicación
-- aplica la misma regla; tenerla aquí permite recalcular o auditar
-- marcaciones directamente desde SQL.
CREATE OR REPLACE FUNCTION fn_evaluar_puntualidad(
  p_hora_real      VARCHAR(5),
  p_hora_esperada  VARCHAR(5),
  p_tolerancia     SMALLINT
) RETURNS "attendance_status" AS $$
DECLARE
  v_diferencia INTEGER;
BEGIN
  v_diferencia :=
    (split_part(p_hora_real, ':', 1)::INT * 60 + split_part(p_hora_real, ':', 2)::INT) -
    (split_part(p_hora_esperada, ':', 1)::INT * 60 + split_part(p_hora_esperada, ':', 2)::INT);

  IF v_diferencia > p_tolerancia THEN
    RETURN 'LATE';
  END IF;

  RETURN 'ON_TIME';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_evaluar_puntualidad IS
  'Devuelve LATE si se supera la tolerancia, ON_TIME en caso contrario (RN007/RN008).';

-- Diferencia en minutos entre dos horas HH:mm. Positivo = más tarde.
CREATE OR REPLACE FUNCTION fn_diferencia_minutos(
  p_hora_a VARCHAR(5),
  p_hora_b VARCHAR(5)
) RETURNS INTEGER AS $$
BEGIN
  RETURN
    (split_part(p_hora_a, ':', 1)::INT * 60 + split_part(p_hora_a, ':', 2)::INT) -
    (split_part(p_hora_b, ':', 1)::INT * 60 + split_part(p_hora_b, ':', 2)::INT);
END;
$$ LANGUAGE plpgsql IMMUTABLE;


-- ═════════════════════ DOCUMENTACIÓN DE LAS TABLAS ════════════════════

COMMENT ON TABLE "users" IS 'Cuentas de acceso al sistema. La contraseña se guarda como hash bcrypt.';
COMMENT ON TABLE "refresh_tokens" IS 'Tokens de renovación de sesión, hasheados y con rotación en cada uso.';
COMMENT ON TABLE "roles" IS 'Perfiles de acceso. Los marcados como del sistema no pueden eliminarse.';
COMMENT ON TABLE "permissions" IS 'Catálogo de capacidades granulares con formato modulo.accion.';
COMMENT ON TABLE "role_permissions" IS 'Tabla puente que asigna permisos a cada rol.';
COMMENT ON TABLE "teachers" IS 'Personal docente sujeto al control de asistencia.';
COMMENT ON TABLE "subjects" IS 'Asignaturas que se imparten en la institución.';
COMMENT ON TABLE "teacher_subjects" IS 'Asignaturas que dicta cada docente (muchos a muchos).';
COMMENT ON TABLE "grades" IS 'Grados del servicio educativo formal segun la Ley 115 de 1994.';
COMMENT ON TABLE "courses" IS 'Cursos o grupos de cada grado: 6A, 6B, 6C.';
COMMENT ON TABLE "teacher_courses" IS 'Cursos que atiende cada docente.';
COMMENT ON TABLE "shifts" IS 'Jornadas institucionales sobre las que se arman los horarios.';
COMMENT ON TABLE "schedules" IS 'Franja horaria de un docente. Contra ella se mide la puntualidad.';
COMMENT ON TABLE "attendances" IS 'Marcaciones de entrada y salida. Es la evidencia del sistema.';
COMMENT ON TABLE "audit_logs" IS 'Bitácora de toda acción del sistema (RN009).';
COMMENT ON TABLE "settings" IS 'Parámetros del sistema editables sin desplegar código.';


-- ═══════════════════════════ DATOS INICIALES ══════════════════════════
-- Mínimo imprescindible para que el sistema arranque y se pueda entrar.

-- ── Permisos ──
INSERT INTO "permissions" ("id", "code", "name", "module", "is_system", "status", "created_at", "updated_at") VALUES
  (gen_random_uuid(), 'users.read', 'Consultar usuarios', 'Usuarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'users.create', 'Crear usuarios', 'Usuarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'users.update', 'Editar usuarios', 'Usuarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'users.delete', 'Eliminar usuarios', 'Usuarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'users.activate', 'Activar usuarios', 'Usuarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'users.deactivate', 'Inactivar usuarios', 'Usuarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'users.export', 'Exportar usuarios', 'Usuarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'users.reset-password', 'Restablecer contraseña usuarios', 'Usuarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'roles.read', 'Consultar roles', 'Roles', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'roles.create', 'Crear roles', 'Roles', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'roles.update', 'Editar roles', 'Roles', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'roles.delete', 'Eliminar roles', 'Roles', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'roles.activate', 'Activar roles', 'Roles', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'roles.deactivate', 'Inactivar roles', 'Roles', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'roles.export', 'Exportar roles', 'Roles', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'permissions.read', 'Consultar permisos', 'Permisos', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'permissions.create', 'Crear permisos', 'Permisos', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'permissions.update', 'Editar permisos', 'Permisos', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'permissions.delete', 'Eliminar permisos', 'Permisos', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'permissions.activate', 'Activar permisos', 'Permisos', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'permissions.deactivate', 'Inactivar permisos', 'Permisos', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'permissions.export', 'Exportar permisos', 'Permisos', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'teachers.read', 'Consultar docentes', 'Docentes', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'teachers.create', 'Crear docentes', 'Docentes', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'teachers.update', 'Editar docentes', 'Docentes', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'teachers.delete', 'Eliminar docentes', 'Docentes', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'teachers.activate', 'Activar docentes', 'Docentes', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'teachers.deactivate', 'Inactivar docentes', 'Docentes', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'teachers.export', 'Exportar docentes', 'Docentes', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'subjects.read', 'Consultar asignaturas', 'Asignaturas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'subjects.create', 'Crear asignaturas', 'Asignaturas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'subjects.update', 'Editar asignaturas', 'Asignaturas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'subjects.delete', 'Eliminar asignaturas', 'Asignaturas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'subjects.activate', 'Activar asignaturas', 'Asignaturas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'subjects.deactivate', 'Inactivar asignaturas', 'Asignaturas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'subjects.export', 'Exportar asignaturas', 'Asignaturas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'grades.read', 'Consultar grados', 'Grados', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'grades.update', 'Editar grados', 'Grados', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'grades.activate', 'Activar grados', 'Grados', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'grades.deactivate', 'Inactivar grados', 'Grados', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'grades.export', 'Exportar grados', 'Grados', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'courses.read', 'Consultar cursos', 'Cursos', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'courses.create', 'Crear cursos', 'Cursos', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'courses.update', 'Editar cursos', 'Cursos', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'courses.delete', 'Eliminar cursos', 'Cursos', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'courses.activate', 'Activar cursos', 'Cursos', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'courses.deactivate', 'Inactivar cursos', 'Cursos', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'courses.export', 'Exportar cursos', 'Cursos', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'shifts.read', 'Consultar jornadas', 'Jornadas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'shifts.create', 'Crear jornadas', 'Jornadas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'shifts.update', 'Editar jornadas', 'Jornadas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'shifts.delete', 'Eliminar jornadas', 'Jornadas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'shifts.activate', 'Activar jornadas', 'Jornadas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'shifts.deactivate', 'Inactivar jornadas', 'Jornadas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'shifts.export', 'Exportar jornadas', 'Jornadas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'schedules.read', 'Consultar horarios', 'Horarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'schedules.create', 'Crear horarios', 'Horarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'schedules.update', 'Editar horarios', 'Horarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'schedules.delete', 'Eliminar horarios', 'Horarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'schedules.activate', 'Activar horarios', 'Horarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'schedules.deactivate', 'Inactivar horarios', 'Horarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'schedules.export', 'Exportar horarios', 'Horarios', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'attendance.read', 'Consultar asistencia', 'Asistencia', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'attendance.create', 'Crear asistencia', 'Asistencia', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'attendance.export', 'Exportar asistencia', 'Asistencia', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'attendance.self', 'Registrar propia asistencia asistencia', 'Asistencia', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'attendance.delete', 'Eliminar asistencia', 'Asistencia', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'reports.read', 'Consultar reportes', 'Reportes', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'reports.export', 'Exportar reportes', 'Reportes', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'audit.read', 'Consultar auditoría', 'Auditoría', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'audit.export', 'Exportar auditoría', 'Auditoría', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'settings.read', 'Consultar configuración', 'Configuración', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'settings.update', 'Editar configuración', 'Configuración', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'dashboard.read', 'Consultar dashboard', 'Dashboard', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'excuses.self', 'Gestionar propias excusas', 'Excusas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'excuses.read', 'Consultar excusas', 'Excusas', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'excuses.review', 'Revisar excusas', 'Excusas', TRUE, 'ACTIVE', NOW(), NOW());

-- ── Roles ──
INSERT INTO "roles" ("id", "code", "name", "description", "is_system", "status", "created_at", "updated_at") VALUES
  (gen_random_uuid(), 'SUPER_ADMIN', 'Rector(a)', 'Control total del sistema. Acceso irrestricto a todos los módulos.', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'ADMINISTRADOR', 'Administrador(a)', 'Gestión operativa completa. No administra el catálogo de permisos.', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'COORDINADOR', 'Coordinador(a)', 'Supervisa docentes, horarios, asistencia y reportes. Sin gestión de usuarios.', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'DOCENTE', 'Docente', 'Registra su propia entrada y salida y consulta su historial.', TRUE, 'ACTIVE', NOW(), NOW());

-- ── Asignación de permisos a cada rol ──
-- SUPER_ADMIN: 77 permisos
INSERT INTO "role_permissions" ("role_id", "permission_id", "created_at")
SELECT r."id", p."id", NOW()
FROM "roles" r CROSS JOIN "permissions" p
WHERE r."code" = 'SUPER_ADMIN'
  AND p."code" IN ('users.read', 'users.create', 'users.update', 'users.delete', 'users.activate', 'users.deactivate', 'users.export', 'users.reset-password', 'roles.read', 'roles.create', 'roles.update', 'roles.delete', 'roles.activate', 'roles.deactivate', 'roles.export', 'permissions.read', 'permissions.create', 'permissions.update', 'permissions.delete', 'permissions.activate', 'permissions.deactivate', 'permissions.export', 'teachers.read', 'teachers.create', 'teachers.update', 'teachers.delete', 'teachers.activate', 'teachers.deactivate', 'teachers.export', 'grades.read', 'grades.update', 'grades.activate', 'grades.deactivate', 'grades.export', 'courses.read', 'courses.create', 'courses.update', 'courses.delete', 'courses.activate', 'courses.deactivate', 'courses.export', 'subjects.read', 'subjects.create', 'subjects.update', 'subjects.delete', 'subjects.activate', 'subjects.deactivate', 'subjects.export', 'shifts.read', 'shifts.create', 'shifts.update', 'shifts.delete', 'shifts.activate', 'shifts.deactivate', 'shifts.export', 'schedules.read', 'schedules.create', 'schedules.update', 'schedules.delete', 'schedules.activate', 'schedules.deactivate', 'schedules.export', 'attendance.read', 'attendance.create', 'attendance.export', 'attendance.self', 'attendance.delete', 'reports.read', 'reports.export', 'audit.read', 'audit.export', 'settings.read', 'settings.update', 'dashboard.read', 'excuses.self', 'excuses.read', 'excuses.review');

-- ADMINISTRADOR: 56 permisos
INSERT INTO "role_permissions" ("role_id", "permission_id", "created_at")
SELECT r."id", p."id", NOW()
FROM "roles" r CROSS JOIN "permissions" p
WHERE r."code" = 'ADMINISTRADOR'
  AND p."code" IN ('users.read', 'users.create', 'users.update', 'users.delete', 'users.activate', 'users.deactivate', 'users.export', 'users.reset-password', 'roles.read', 'roles.create', 'roles.update', 'roles.activate', 'roles.deactivate', 'roles.export', 'permissions.read', 'teachers.read', 'teachers.create', 'teachers.update', 'teachers.delete', 'teachers.activate', 'teachers.deactivate', 'teachers.export', 'grades.read', 'grades.update', 'grades.activate', 'grades.deactivate', 'grades.export', 'courses.read', 'courses.create', 'courses.update', 'courses.delete', 'courses.activate', 'courses.deactivate', 'courses.export', 'subjects.read', 'subjects.create', 'subjects.update', 'subjects.delete', 'subjects.activate', 'subjects.deactivate', 'subjects.export', 'shifts.read', 'shifts.create', 'shifts.update', 'shifts.delete', 'shifts.activate', 'shifts.deactivate', 'shifts.export', 'schedules.read', 'schedules.create', 'schedules.update', 'schedules.delete', 'schedules.activate', 'schedules.deactivate', 'schedules.export', 'attendance.read', 'attendance.create', 'attendance.export', 'reports.read', 'reports.export', 'audit.read', 'audit.export', 'settings.read', 'settings.update', 'dashboard.read', 'excuses.self', 'excuses.read', 'excuses.review');

-- COORDINADOR: 21 permisos
INSERT INTO "role_permissions" ("role_id", "permission_id", "created_at")
SELECT r."id", p."id", NOW()
FROM "roles" r CROSS JOIN "permissions" p
WHERE r."code" = 'COORDINADOR'
  AND p."code" IN ('dashboard.read', 'teachers.read', 'teachers.update', 'teachers.export', 'grades.read', 'courses.read', 'courses.create', 'courses.update', 'courses.export', 'subjects.read', 'subjects.create', 'subjects.update', 'subjects.export', 'shifts.read', 'schedules.read', 'schedules.create', 'schedules.update', 'schedules.export', 'attendance.read', 'attendance.create', 'attendance.export', 'reports.read', 'reports.export', 'audit.read', 'excuses.read', 'excusas.review');

-- DOCENTE: 3 permisos
INSERT INTO "role_permissions" ("role_id", "permission_id", "created_at")
SELECT r."id", p."id", NOW()
FROM "roles" r CROSS JOIN "permissions" p
WHERE r."code" = 'DOCENTE'
  AND p."code" IN ('attendance.self', 'dashboard.read', 'excuses.self');

-- ── Usuario inicial (SUPER_ADMIN) ──
-- Contraseña: Admin123*  — cámbiela tras el primer ingreso.
INSERT INTO "users" ("id", "first_name", "last_name", "document", "email", "password", "status", "role_id", "created_at", "updated_at")
SELECT gen_random_uuid(), 'Super', 'Admin', '1000000000', 'admin@datly.local', '$2b$12$9D8cDSxvVcEgUOrcXAyJT.i0wzWfLRpnOZaUfG/01UdgYMwCPv/Fm', 'ACTIVE', r."id", NOW(), NOW()
FROM "roles" r WHERE r."code" = 'SUPER_ADMIN';

-- ── Configuración ──
INSERT INTO "settings" ("id", "key", "value", "type", "group", "label", "description", "is_public", "is_system", "created_at", "updated_at") VALUES
  (gen_random_uuid(), 'qr.public_url', 'https://asistencia-qr-rusg.onrender.com/marcar', 'STRING'::"setting_type", 'qr', 'URL pública del QR institucional', 'Destino al que apunta el código QR único de la institución.', TRUE, FALSE, NOW(), NOW()),
  (gen_random_uuid(), 'qr.institution_name', 'IED Los Laureles', 'STRING'::"setting_type", 'qr', 'Nombre institucional', 'Se muestra bajo el código QR al descargarlo.', TRUE, FALSE, NOW(), NOW()),
  (gen_random_uuid(), 'attendance.default_tolerance_minutes', '10', 'NUMBER'::"setting_type", 'attendance', 'Tolerancia por defecto (minutos)', 'Se aplica a los horarios que no definen una tolerancia propia.', FALSE, FALSE, NOW(), NOW()),
  (gen_random_uuid(), 'attendance.window_minutes', '180', 'NUMBER'::"setting_type", 'attendance', 'Ventana de marcación (minutos)', 'Margen máximo respecto a la hora del horario para aceptar una marcación.', FALSE, FALSE, NOW(), NOW()),
  (gen_random_uuid(), 'app.timezone', 'America/Bogota', 'STRING'::"setting_type", 'general', 'Zona horaria institucional', 'Determina el cálculo de puntualidad y el corte de día.', TRUE, TRUE, NOW(), NOW()),
  (gen_random_uuid(), 'app.institution_short_name', 'IED Los Laureles', 'STRING'::"setting_type", 'general', 'Nombre corto institucional', 'Se muestra en la cabecera de la aplicación.', TRUE, FALSE, NOW(), NOW());

-- ── Ubicación del colegio (validación geográfica de marcaciones) ──
INSERT INTO "settings" ("id", "key", "value", "type", "group", "label", "description", "is_public", "is_system", "created_at", "updated_at") VALUES
  (gen_random_uuid(), 'school.location_latitude', '10.9326672', 'STRING'::"setting_type", 'school', 'Latitud del colegio', 'Latitud en grados decimales del punto medio de la IED.', FALSE, FALSE, NOW(), NOW()),
  (gen_random_uuid(), 'school.location_longitude', '-74.7916050', 'STRING'::"setting_type", 'school', 'Longitud del colegio', 'Longitud en grados decimales del punto medio de la IED.', FALSE, FALSE, NOW(), NOW()),
  (gen_random_uuid(), 'school.location_radius_meters', '16', 'NUMBER'::"setting_type", 'school', 'Radio de marcación (metros)', 'Radio máximo permitido desde el punto del colegio para registrar asistencia.', FALSE, FALSE, NOW(), NOW()),
  (gen_random_uuid(), 'school.location_required', 'true', 'STRING'::"setting_type", 'school', 'Obligar a marcar dentro del colegio', 'Si es true, el docente debe estar dentro del radio para registrar asistencia.', FALSE, FALSE, NOW(), NOW()),
  (gen_random_uuid(), 'school.location_permanent', 'true', 'STRING'::"setting_type", 'school', 'Ubicación permanente del docente', 'Si es true, las pantallas de marcación siguen la ubicación del docente mientras están abiertas.', FALSE, FALSE, NOW(), NOW());

-- ── Jornadas ──
INSERT INTO "shifts" ("id", "name", "description", "status", "created_at", "updated_at") VALUES
  (gen_random_uuid(), 'Mañana', 'Jornada de la mañana', 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'Tarde', 'Jornada de la tarde', 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'Noche', 'Jornada nocturna', 'ACTIVE', NOW(), NOW());

-- ── Grados (Ley 115 de 1994) ──
-- La escalera educativa la fija la ley, no la institucion: por eso vienen
-- cargados y marcados como del sistema. Cada institucion decide cuales ofrece
-- activandolos o inactivandolos, y abre sus cursos en la tabla "courses".
--
--   Preescolar         art. 15-18. Decreto 2247 de 1997 define los tres
--                      grados; solo transicion es obligatorio.
--   Basica primaria    art. 21. Cinco grados.
--   Basica secundaria  art. 22. Cuatro grados.
--   Media              art. 27-35. Dos grados, academica o tecnica.
INSERT INTO "grades" ("id", "code", "name", "level", "position", "description", "is_system", "status", "created_at", "updated_at") VALUES
  (gen_random_uuid(), 'PJ', 'Prejardín',  'PREESCOLAR'::"education_level",         1, 'Preescolar. No obligatorio.', TRUE, 'INACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'JA', 'Jardín',     'PREESCOLAR'::"education_level",         2, 'Preescolar. No obligatorio.', TRUE, 'INACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'TR', 'Transición', 'PREESCOLAR'::"education_level",         3, 'Preescolar. Grado obligatorio (art. 17).', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), '1',  'Primero',    'BASICA_PRIMARIA'::"education_level",    4, 'Básica primaria.', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), '2',  'Segundo',    'BASICA_PRIMARIA'::"education_level",    5, 'Básica primaria.', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), '3',  'Tercero',    'BASICA_PRIMARIA'::"education_level",    6, 'Básica primaria.', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), '4',  'Cuarto',     'BASICA_PRIMARIA'::"education_level",    7, 'Básica primaria.', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), '5',  'Quinto',     'BASICA_PRIMARIA'::"education_level",    8, 'Básica primaria.', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), '6',  'Sexto',      'BASICA_SECUNDARIA'::"education_level",  9, 'Básica secundaria.', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), '7',  'Séptimo',    'BASICA_SECUNDARIA'::"education_level", 10, 'Básica secundaria.', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), '8',  'Octavo',     'BASICA_SECUNDARIA'::"education_level", 11, 'Básica secundaria.', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), '9',  'Noveno',     'BASICA_SECUNDARIA'::"education_level", 12, 'Básica secundaria.', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), '10', 'Décimo',     'MEDIA'::"education_level",             13, 'Educación media.', TRUE, 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), '11', 'Undécimo',   'MEDIA'::"education_level",             14, 'Educación media. Otorga el título de bachiller.', TRUE, 'ACTIVE', NOW(), NOW());

-- ── Cursos de ejemplo ──
-- Un grupo A por cada grado activo, para que la institución tenga de dónde
-- partir. Los demás se abren desde la pantalla de Cursos.
INSERT INTO "courses" ("id", "grade_id", "letter", "name", "status", "created_at", "updated_at")
SELECT gen_random_uuid(), g."id", 'A', g."code" || 'A', 'ACTIVE', NOW(), NOW()
FROM "grades" g
WHERE g."status" = 'ACTIVE';

-- ── Asignaturas de ejemplo ──
INSERT INTO "subjects" ("id", "code", "name", "weekly_hours", "color", "status", "created_at", "updated_at") VALUES
  (gen_random_uuid(), 'MAT-101', 'Matemáticas', 6, '#4F46E5', 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'LEN-201', 'Lengua Castellana', 5, '#0EA5E9', 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'CNA-110', 'Ciencias Naturales', 4, '#10B981', 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'SOC-120', 'Ciencias Sociales', 4, '#F59E0B', 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'TEC-305', 'Tecnología e Informática', 3, '#8B5CF6', 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'EFI-140', 'Educación Física', 2, '#EF4444', 'ACTIVE', NOW(), NOW());

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════
--  Comprobación rápida tras la ejecución:
--
--    SELECT COUNT(*) FROM permissions;   -- esperado: 65
--    SELECT COUNT(*) FROM roles;         -- esperado: 4
--    SELECT COUNT(*) FROM users;         -- esperado: 1
--    SELECT COUNT(*) FROM shifts;        -- esperado: 3
--    SELECT COUNT(*) FROM subjects;      -- esperado: 6
-- ═══════════════════════════════════════════════════════════════════════