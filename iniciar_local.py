#!/usr/bin/env python3
"""
Arranca el Sistema de Asistencia Docente por QR en localhost.

    python iniciar_local.py

La primera vez prepara todo y las siguientes solo arranca:

  1. Crea el entorno virtual `.venv` e instala `requirements.txt`.
  2. Localiza PostgreSQL, crea la base `asistencia_qr` si no existe y aplica
     `database.sql` (después el propio arranque sincroniza docentes y usuarios).
  3. Escribe `.env` con la conexión y los secretos de desarrollo.
  4. Levanta la aplicación y abre el navegador.

Opciones:

    --puerto 4000          puerto de escucha (por defecto 4000, o el siguiente libre)
    --base-datos URL       conexión concreta, p. ej.
                           postgresql://postgres@localhost:5432/asistencia_qr
    --reinstalar           vuelve a instalar las dependencias
    --no-navegador         no abre el navegador

Si PostgreSQL pide contraseña, se solicita aquí y solo se guarda en `.env`.
También puede definirla antes con la variable de entorno `PGPASSWORD`.
"""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

RAIZ = Path(__file__).resolve().parent
VENV = RAIZ / ".venv"
PYTHON_VENV = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
ARCHIVO_ENV = RAIZ / ".env"
BASE = "asistencia_qr"
PUERTO_POR_DEFECTO = 4000
PUERTOS_POSTGRES = (5432, 5433, 5434)

# La consola de Windows usa cp1252 y no puede escribir acentos ni caracteres de
# recuadro: se pasa a UTF-8 antes de imprimir nada, igual que en servidor.py.
if os.name == "nt":
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:  # consola redirigida o sin permisos: no es grave
        pass

for _flujo in (sys.stdout, sys.stderr):
    if hasattr(_flujo, "reconfigure"):
        _flujo.reconfigure(encoding="utf-8", errors="replace")


# ── Presentación ─────────────────────────────────────────────────────

def aviso(texto: str) -> None:
    print(f"  · {texto}", flush=True)


def bien(texto: str) -> None:
    print(f"  OK {texto}", flush=True)


def error(texto: str) -> None:
    print(f"\n  x  {texto}\n", flush=True)


def titulo() -> None:
    print()
    print("  Sistema de Asistencia Docente por QR")
    print("  " + "─" * 46)
    print()


# ── Entorno virtual ──────────────────────────────────────────────────

def dentro_del_venv() -> bool:
    try:
        return Path(sys.prefix).resolve() == VENV.resolve()
    except OSError:
        return False


def preparar_entorno(forzar: bool) -> None:
    """Crea el `.venv` e instala las dependencias si hace falta."""
    if not PYTHON_VENV.exists():
        aviso("creando el entorno virtual .venv")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])

    requisitos = RAIZ / "requirements.txt"
    marca = VENV / ".dependencias-instaladas"

    desactualizado = (
        forzar
        or not marca.exists()
        or (requisitos.exists() and requisitos.stat().st_mtime > marca.stat().st_mtime)
    )
    if not desactualizado:
        return

    aviso("instalando dependencias (solo la primera vez tarda)")
    subprocess.check_call([str(PYTHON_VENV), "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
    subprocess.check_call([str(PYTHON_VENV), "-m", "pip", "install", "-r", str(requisitos), "--quiet"])
    marca.write_text("ok\n", encoding="utf-8")
    bien("dependencias instaladas")


def reactivar_en_venv(argumentos: list[str], forzar: bool) -> None:
    """Vuelve a lanzar este mismo script con el Python del `.venv`."""
    if dentro_del_venv():
        return

    preparar_entorno(forzar)

    if os.name == "nt":
        os.execv(str(PYTHON_VENV), [str(PYTHON_VENV), str(Path(__file__).resolve()), *argumentos])
    else:  # pragma: no cover - Windows es el objetivo, pero no rompe en otros
        os.execv(str(PYTHON_VENV), [str(PYTHON_VENV), str(Path(__file__).resolve()), *argumentos])


# ── Archivo .env ─────────────────────────────────────────────────────

def leer_env() -> dict[str, str]:
    datos: dict[str, str] = {}
    if not ARCHIVO_ENV.is_file():
        return datos
    for linea in ARCHIVO_ENV.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        datos[clave.strip()] = valor.strip()
    return datos


def guardar_env(datos: dict[str, str]) -> None:
    contenido = f"""# ─────────────────────────────────────────────
# Configuración local del Sistema de Asistencia Docente por QR
#
# Generado por iniciar_local.py. No se sube a GitHub: .env está en .gitignore.
# ─────────────────────────────────────────────

# ── Base de datos ────────────────────────────
DATABASE_URL={datos["DATABASE_URL"]}

# ── Servidor ─────────────────────────────────
NODE_ENV=development
API_PORT={datos["API_PORT"]}
API_PREFIX=api/v1
CORS_ORIGINS=http://localhost:{datos["API_PORT"]}

# ── Sesiones y tokens ────────────────────────
JWT_ACCESS_SECRET={datos["JWT_ACCESS_SECRET"]}
JWT_ACCESS_EXPIRES_IN=15m
JWT_REFRESH_SECRET={datos["JWT_REFRESH_SECRET"]}
JWT_REFRESH_EXPIRES_IN=7d
SESSION_SECRET={datos["SESSION_SECRET"]}

# ── Seguridad ────────────────────────────────
BCRYPT_ROUNDS=12
LOGIN_RATE_TTL=60
LOGIN_RATE_LIMIT=5
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCK_MINUTES=15

# ── Institución ──────────────────────────────
APP_TIMEZONE=America/Bogota
SEED_ADMIN_EMAIL=admin@datly.local
"""
    ARCHIVO_ENV.write_text(contenido, encoding="utf-8")


# ── PostgreSQL ───────────────────────────────────────────────────────

def dsn(host: str, puerto: int, usuario: str, clave: str, base: str) -> str:
    credencial = f":{quote(clave, safe='')}" if clave else ""
    return f"postgresql://{usuario}{credencial}@{host}:{puerto}/{base}"


def partes(url: str) -> dict[str, str | int]:
    """Separa una URL de conexión, ignorando parámetros como `?schema=public`."""
    limpia = url.split("?", 1)[0]
    p = urlsplit(limpia)
    return {
        "host": p.hostname or "localhost",
        "puerto": p.port or 5432,
        "usuario": unquote(p.username or "postgres"),
        "clave": unquote(p.password or ""),
        "base": (p.path or f"/{BASE}").lstrip("/") or BASE,
    }


def conectar(host: str, puerto: int, usuario: str, clave: str, base: str):
    import psycopg2

    return psycopg2.connect(
        host=host, port=puerto, user=usuario, password=clave,
        dbname=base, connect_timeout=5,
    )


def detectar_postgres() -> dict[str, str | int]:
    """Encuentra un servidor PostgreSQL local y devuelve sus datos."""
    import psycopg2

    for puerto in PUERTOS_POSTGRES:
        try:
            conexion = conectar("localhost", puerto, "postgres", "", "postgres")
            conexion.close()
            return {"host": "localhost", "puerto": puerto, "usuario": "postgres", "clave": "", "base": BASE}
        except psycopg2.OperationalError as exc:
            ultimo = exc

    # Puede que exija contraseña (la de la instalación de PostgreSQL).
    print()
    aviso("PostgreSQL no aceptó la conexión sin contraseña.")
    clave = os.environ.get("PGPASSWORD") or getpass.getpass("  Contraseña del usuario postgres: ")
    for puerto in PUERTOS_POSTGRES:
        try:
            conexion = conectar("localhost", puerto, "postgres", clave, "postgres")
            conexion.close()
            return {"host": "localhost", "puerto": puerto, "usuario": "postgres", "clave": clave, "base": BASE}
        except psycopg2.OperationalError as exc:
            ultimo = exc

    error(
        "No pude conectar con PostgreSQL. Compruebe que el servicio esté encendido "
        f"(Servicios de Windows → postgresql-x64-16).\n     Detalle: {ultimo}"
    )
    raise SystemExit(1)


def asegurar_base(datos: dict[str, str | int]) -> None:
    """Crea la base si todavía no existe."""
    import psycopg2

    try:
        conexion = conectar(
            str(datos["host"]), int(datos["puerto"]),
            str(datos["usuario"]), str(datos["clave"]), "postgres",
        )
    except psycopg2.OperationalError as exc:
        error(f"No pude conectar con PostgreSQL: {exc}")
        raise SystemExit(1)

    conexion.autocommit = True
    try:
        with conexion.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (datos["base"],))
            if cur.fetchone() is None:
                aviso(f"creando la base de datos {datos['base']}")
                from psycopg2 import sql

                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(str(datos["base"]))))
                bien(f"base {datos['base']} creada")
    finally:
        conexion.close()


def esquema_aplicado(url: str) -> bool:
    try:
        conexion = conectar(*[partes(url)[k] for k in ("host", "puerto", "usuario", "clave", "base")])
    except Exception:  # noqa: BLE001
        return False
    try:
        with conexion.cursor() as cur:
            cur.execute("SELECT to_regclass('public.users') IS NOT NULL")
            return bool(cur.fetchone()[0])
    finally:
        conexion.close()


def preparar_base(url: str) -> None:
    """Aplica `database.sql` la primera vez, usando el propio `init_db.py`."""
    if esquema_aplicado(url):
        bien("base de datos lista")
        return

    aviso("creando las tablas de la base de datos")
    os.environ["DATABASE_URL"] = url

    import importlib.util

    ruta = RAIZ / "init_db.py"
    especificacion = importlib.util.spec_from_file_location("init_db", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    modulo.init_database()

    if not esquema_aplicado(url):
        error(
            "No se pudo crear el esquema. Revise el mensaje de init_db.py de arriba;\n"
            "     lo más habitual es que falte la extensión pgcrypto/unaccent."
        )
        raise SystemExit(1)
    bien("base de datos creada")


# ── Arranque ─────────────────────────────────────────────────────────

def puerto_libre(preferido: int) -> int:
    for puerto in range(preferido, preferido + 30):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", puerto)) != 0:
                return puerto
    return preferido


def abrir_navegador(url: str) -> None:
    threading.Timer(2.5, lambda: webbrowser.open(url)).start()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Arranca el Sistema de Asistencia Docente por QR en localhost.",
    )
    parser.add_argument("--puerto", type=int, default=None, help="puerto de escucha (4000 por defecto)")
    parser.add_argument("--base-datos", default=None, help="URL de conexión a PostgreSQL")
    parser.add_argument("--reinstalar", action="store_true", help="vuelve a instalar las dependencias")
    parser.add_argument("--no-navegador", action="store_true", help="no abre el navegador")
    argumentos = parser.parse_args()

    titulo()

    # 1. Ejecutarse dentro del entorno virtual (instalándolo si hace falta).
    reactivar_en_venv(sys.argv[1:], argumentos.reinstalar)

    # 2. Decidir la conexión: argumento → variable de entorno → .env → detección.
    entorno = leer_env()
    configurada = (
        argumentos.base_datos
        or os.environ.get("DATABASE_URL")
        or entorno.get("DATABASE_URL")
    )

    if configurada:
        datos = partes(configurada)
        bien(f"usando la base {datos['base']} en {datos['host']}:{datos['puerto']}")
    else:
        aviso("buscando PostgreSQL")
        datos = detectar_postgres()
        bien(f"PostgreSQL encontrado en el puerto {datos['puerto']}")

    asegurar_base(datos)
    url = dsn(str(datos["host"]), int(datos["puerto"]), str(datos["usuario"]), str(datos["clave"]), str(datos["base"]))
    preparar_base(url)

    # 3. Puerto y configuración persistente.
    puerto = argumentos.puerto or int(entorno.get("API_PORT", PUERTO_POR_DEFECTO))
    libre = puerto_libre(puerto)
    if libre != puerto:
        aviso(f"el puerto {puerto} está ocupado; se usará el {libre}")
        puerto = libre

    guardar_env({
        "DATABASE_URL": url,
        "API_PORT": str(puerto),
        "JWT_ACCESS_SECRET": entorno.get("JWT_ACCESS_SECRET") or secrets.token_urlsafe(48),
        "JWT_REFRESH_SECRET": entorno.get("JWT_REFRESH_SECRET") or secrets.token_urlsafe(48),
        "SESSION_SECRET": entorno.get("SESSION_SECRET") or secrets.token_urlsafe(48),
    })
    bien(f"configuración guardada en {ARCHIVO_ENV.name}")

    # 4. Arrancar.
    if not argumentos.no_navegador:
        abrir_navegador(f"http://localhost:{puerto}")

    os.environ["DATABASE_URL"] = url
    os.environ["API_PORT"] = str(puerto)
    os.environ.setdefault("NODE_ENV", "development")
    os.environ.setdefault("CORS_ORIGINS", f"http://localhost:{puerto}")

    print()
    print(f"  Aplicación   http://localhost:{puerto}")
    print(f"  API          http://localhost:{puerto}/api/v1")
    print(f"  Usuario      admin@datly.local  ·  Admin123*")
    print()
    print("  Deténgala con Ctrl+C.")
    print()

    servidor = RAIZ / "servidor.py"

    entorno_hijo = os.environ.copy()
    entorno_hijo["DATABASE_URL"] = url
    entorno_hijo["API_PORT"] = str(puerto)
    entorno_hijo.setdefault("NODE_ENV", "development")
    entorno_hijo.setdefault("CORS_ORIGINS", f"http://localhost:{puerto}")

    try:
        subprocess.call([str(PYTHON_VENV), str(servidor)], cwd=str(RAIZ), env=entorno_hijo)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Aplicación detenida.\n")
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        error(f"Falló el arranque: {exc}")
        raise SystemExit(1)
