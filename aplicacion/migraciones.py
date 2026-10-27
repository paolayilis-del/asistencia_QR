"""
Migraciones de esquema que se aplican al arrancar.

`database.sql` es la fuente de la estructura y así seguirá siendo para quien
monte una instalación desde cero. Este módulo cubre otro caso: una base que ya
está en producción, a la que se le añade una tabla o un permiso sin que nadie
pueda volver a ejecutar el script completo.

Por eso todo lo que hay aquí es idempotente y se puede repetir sin efecto:

- `CREATE TABLE IF NOT EXISTS` para objetos nuevos
- `DO $$ ... $$` para los tipos ENUM, que no admiten `IF NOT EXISTS`
- `INSERT ... ON CONFLICT DO NOTHING` para los permisos

Nunca lanza: si algo falla se registra en el log y la aplicación sigue
arrancando. Un despliegue no debe caerse porque falte un índice, y una
pantalla vacía se arregla reiniciando cuando la base esté disponible.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from .extensiones import bd

registro = logging.getLogger("asistencia.migraciones")


# ── Excusas: tabla, tipos y permisos ───────────────────────────────────
# El docente presenta una justificación con su archivo; un administrativo la
# revisa. Sin esta tabla la pantalla de excusas no puede funcionar.

SENTENCIAS_EXCUSAS = (
    # Los tipos ENUM no aceptan IF NOT EXISTS: se comprueban con un DO vacío
    # que solo crea el que falta.
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'excuse_type') THEN
            CREATE TYPE "excuse_type" AS ENUM ('INCAPACIDAD', 'PERMISO', 'OTRO');
        END IF;
    END $$
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'excuse_status') THEN
            CREATE TYPE "excuse_status" AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
        END IF;
    END $$
    """,
    """
    CREATE TABLE IF NOT EXISTS "excuses" (
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
    )
    """,
    'CREATE INDEX IF NOT EXISTS "excuses_teacher_id_date_idx" ON "excuses"("teacher_id", "date")',
    'CREATE INDEX IF NOT EXISTS "excuses_status_idx" ON "excuses"("status")',
    'CREATE INDEX IF NOT EXISTS "excuses_date_idx" ON "excuses"("date")',
    'CREATE INDEX IF NOT EXISTS "excuses_deleted_at_idx" ON "excuses"("deleted_at")',
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE constraint_name = 'excuses_teacher_id_fkey'
        ) THEN
            ALTER TABLE "excuses"
                ADD CONSTRAINT "excuses_teacher_id_fkey"
                FOREIGN KEY ("teacher_id") REFERENCES "teachers"("id")
                ON DELETE RESTRICT ON UPDATE CASCADE;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE constraint_name = 'excuses_attendance_id_fkey'
        ) THEN
            ALTER TABLE "excuses"
                ADD CONSTRAINT "excuses_attendance_id_fkey"
                FOREIGN KEY ("attendance_id") REFERENCES "attendances"("id")
                ON DELETE SET NULL ON UPDATE CASCADE;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE constraint_name = 'excuses_reviewed_by_id_fkey'
        ) THEN
            ALTER TABLE "excuses"
                ADD CONSTRAINT "excuses_reviewed_by_id_fkey"
                FOREIGN KEY ("reviewed_by_id") REFERENCES "users"("id")
                ON DELETE SET NULL ON UPDATE CASCADE;
        END IF;
    END $$
    """,
    'ALTER TABLE "excuses" ALTER COLUMN "id" SET DEFAULT gen_random_uuid()',
)

# Permisos de excusas. El módulo los inserta para los roles que ya existen en
# la base; una instalación nueva los recibe por `database.sql`.
PERMISOS_EXCUSAS = (
    ("excuses.self", "Gestionar propias excusas", "Excusas"),
    ("excuses.read", "Consultar excusas", "Excusas"),
    ("excuses.review", "Revisar excusas", "Excusas"),
)

# Qué roles reciben cada permiso. El docente solo gestiona las suyas: puede
# presentar una excusa y verlas, pero no revisar las de nadie más.
PERMISOS_POR_ROL = {
    "DOCENTE": ("excuses.self",),
    "COORDINADOR": ("excuses.read", "excuses.review"),
    "ADMINISTRADOR": ("excuses.read", "excuses.review"),
    "SUPER_ADMIN": ("excuses.self", "excuses.read", "excuses.review"),
}


def aplicar_excusas() -> None:
    """Crea la estructura de excusas si el servidor aún no la tiene."""
    motor = bd.session.get_bind()
    inspector = inspect(motor)

    if not inspector.has_table("excuses"):
        registro.info("Migración: creando la tabla de excusas")

    for sentencia in SENTENCIAS_EXCUSAS:
        bd.session.execute(text(sentencia))

    bd.session.commit()
    _asignar_permisos()


def _asignar_permisos() -> None:
    """
    Inserta los permisos de excusas y los reparte entre los roles.

    `ON CONFLICT` hace que repetir el arranque no duplique nada. Los roles que
    no existan se saltan solos: la consulta no encuentra filas que repartir.
    """
    for codigo, etiqueta, modulo in PERMISOS_EXCUSAS:
        bd.session.execute(
            text(
                """
                INSERT INTO "permissions"
                    ("id", "code", "name", "module", "is_system", "status",
                     "created_at", "updated_at")
                VALUES
                    (gen_random_uuid(), :codigo, :etiqueta, :modulo, TRUE,
                     'ACTIVE'::"record_status", NOW(), NOW())
                ON CONFLICT ("code") DO NOTHING
                """
            ),
            {"codigo": codigo, "etiqueta": etiqueta, "modulo": modulo},
        )

    bd.session.commit()

    for rol, permisos in PERMISOS_POR_ROL.items():
        if not permisos:
            continue
        lista = ", ".join(f":p{i}" for i in range(len(permisos)))
        parametros = {f"p{i}": valor for i, valor in enumerate(permisos)}
        bd.session.execute(
            text(
                f"""
                INSERT INTO "role_permissions" ("role_id", "permission_id", "created_at")
                SELECT r."id", p."id", NOW()
                FROM "roles" r
                CROSS JOIN "permissions" p
                WHERE r."code" = :rol
                  AND p."code" IN ({lista})
                ON CONFLICT DO NOTHING
                """
            ),
            {"rol": rol, **parametros},
        )

    bd.session.commit()


def aplicar(app) -> None:
    """
    Punto de entrada desde la fábrica de la aplicación.

    Cada migración va en su propio `try`: si una falla no se pierden las demás.
    """
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        registro.info("Migraciones: sin base de datos configurada, se omiten")
        return

    with app.app_context():
        try:
            aplicar_excusas()
            registro.info("Migraciones: estructura al día")
        except SQLAlchemyError as error:
            bd.session.rollback()
            registro.warning("Migraciones: no se pudo aplicar la de excusas: %s", error)
        except Exception as error:  # noqa: BLE001 - una migración nunca debe tumbar el arranque
            bd.session.rollback()
            registro.warning("Migraciones: error inesperado: %s", error)
