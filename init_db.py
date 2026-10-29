#!/usr/bin/env python3
"""
Inicializa la base de datos ejecutando database.sql.
Se ejecuta durante el build de Render.
"""
import os
import sys
import psycopg2
from pathlib import Path

def _ejecutar_archivo(cur, ruta: Path, descripcion: str) -> bool:
    """Ejecuta un archivo SQL si existe. Devuelve True si se aplicó."""
    if not ruta.exists():
        print(f"{descripcion} no encontrado, saltando")
        return False
    cur.execute(ruta.read_text(encoding="utf-8"))
    print(f"{descripcion} aplicado correctamente")
    return True

def _existe_tabla(cur, nombre: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=%s",
        (nombre,),
    )
    return cur.fetchone()[0] > 0

def _existe_columna(cur, tabla: str, columna: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s AND column_name=%s",
        (tabla, columna),
    )
    return cur.fetchone()[0] > 0

def _existe_setting(cur, clave: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='settings'"
    )
    if cur.fetchone()[0] == 0:
        return True  # no hay tabla settings: no hay nada que migrar
    cur.execute("SELECT COUNT(*) FROM settings WHERE key = %s", (clave,))
    return cur.fetchone()[0] > 0

def init_database():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("DATABASE_URL no configurada, saltando init")
        return

    # psycopg2 no entiende `?schema=public` (lo añade Prisma): se descarta,
    # igual que hace `aplicacion/config.py` al preparar SQLAlchemy.
    if "?" in db_url:
        base, _, consulta = db_url.partition("?")
        resto = "&".join(
            parametro
            for parametro in consulta.split("&")
            if not parametro.startswith("schema=")
        )
        db_url = base + ("?" + resto if resto else "")

    sql_file = Path(__file__).parent / "database.sql"
    if not sql_file.exists():
        print("database.sql no encontrado, saltando")
        return

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
        )
        count = cur.fetchone()[0]

        if count > 0:
            print(f"Base de datos ya tiene {count} tablas, saltando init")
            _run_migrations(cur)
            _run_seed(cur)
            cur.close()
            conn.close()
            return

        print("Inicializando base de datos...")
        _ejecutar_archivo(cur, sql_file, "Base de datos")
        _run_seed(cur)
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error inicializando BD: {e}")

def _run_migrations(cur):
    """Ejecuta migraciones incrementales sobre la base existente."""
    base = Path(__file__).parent

    # Geolocalización de marcaciones (columnas en attendances)
    if _existe_tabla(cur, "attendances") and not _existe_columna(cur, "attendances", "latitude"):
        _ejecutar_archivo(cur, base / "migracion_geo.sql", "migracion_geo.sql")
    else:
        print("Columnas de geolocalización ya existen, migracion_geo.sql saltando")

    # Configuración de ubicación del colegio (settings)
    if _existe_tabla(cur, "settings") and not _existe_setting(cur, "school.location_latitude"):
        _ejecutar_archivo(cur, base / "migracion_ubicacion_colegio.sql",
                          "migracion_ubicacion_colegio.sql")
    else:
        print("Configuración de ubicación del colegio ya existe, migracion_ubicacion_colegio.sql saltando")

    # Ubicación de la IED Los Laureles (solo si la latitud sigue vacía)
    if _existe_tabla(cur, "settings"):
        _ejecutar_archivo(cur, base / "migracion_ubicacion_ied.sql",
                          "migracion_ubicacion_ied.sql")

    # Permisos mínimos del rol DOCENTE (idempotente)
    if _existe_tabla(cur, "role_permissions") and _existe_tabla(cur, "roles"):
        _ejecutar_archivo(cur, base / "migracion_permisos_docente.sql",
                          "migracion_permisos_docente.sql")

def _run_seed(cur):
    """Sincroniza los docentes y sus usuarios en la base existente."""
    if not _existe_tabla(cur, "users") or not _existe_tabla(cur, "teachers"):
        print("seed saltado: no existen tablas users/teachers")
        return
    try:
        import importlib.util

        ruta = Path(__file__).parent / "seed_sincronizacion.py"
        spec = importlib.util.spec_from_file_location("seed_sincronizacion", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        modulo.ejecutar_seed()
    except Exception as e:
        print(f"Error ejecutando el seed: {e}")


if __name__ == "__main__":
    init_database()
