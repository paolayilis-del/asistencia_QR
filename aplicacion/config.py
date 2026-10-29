"""
Configuración de la aplicación.

Sustituye a la configuración del sistema anterior y a `@nestjs/config`.

Ninguna credencial vive en el código: todo se lee de variables de entorno,
del archivo `.env` de la raíz del proyecto.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent


def _cargar_entorno() -> Path | None:
    """Carga el `.env` de la raíz, si existe."""
    candidato = RAIZ / ".env"
    if candidato.is_file():
        load_dotenv(candidato, override=False)
        return candidato
    return None


ORIGEN_ENTORNO = _cargar_entorno()


def _texto(clave: str, defecto: str) -> str:
    valor = os.getenv(clave)
    return valor if valor not in (None, "") else defecto


def _entero(clave: str, defecto: int) -> int:
    try:
        return int(os.getenv(clave, ""))
    except (TypeError, ValueError):
        return defecto


def _duracion_a_segundos(texto: str, defecto: int) -> int:
    """
    Convierte `15m`, `7d`, `30s` o `2h` a segundos.

    El proyecto original usaba el formato de `@nestjs/jwt`; se mantiene el
    mismo para que los valores de `.env` sigan sirviendo tal cual.
    """
    coincidencia = re.fullmatch(r"\s*(\d+)\s*([smhd])?\s*", texto or "")
    if not coincidencia:
        return defecto
    cantidad = int(coincidencia.group(1))
    unidad = coincidencia.group(2) or "s"
    return cantidad * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unidad]


def _normalizar_url(url: str) -> str:
    """
    Adapta la cadena de conexión de Prisma a la que espera SQLAlchemy.

    Prisma añade `?schema=public`, que no es un parámetro de PostgreSQL: si se
    envía tal cual, la conexión falla. Se traduce al equivalente real y se
    declara el controlador de forma explícita.
    """
    if not url:
        return ""

    partes = urlsplit(url)
    esquema = partes.scheme
    if esquema in ("postgres", "postgresql"):
        esquema = "postgresql+psycopg2"

    parametros = dict(parse_qsl(partes.query))
    espacio = parametros.pop("schema", None)
    if espacio and espacio != "public":
        # En PostgreSQL el equivalente es la ruta de búsqueda de esquemas
        parametros["options"] = f"-csearch_path={espacio}"

    return urlunsplit((esquema, partes.netloc, partes.path, urlencode(parametros), partes.fragment))


class Config:
    """Valores compartidos por todos los entornos."""

    # ── Aplicación ───────────────────────────────────────────────────
    ENTORNO = _texto("NODE_ENV", "development")
    ZONA_HORARIA = _texto("APP_TIMEZONE", "America/Bogota")
    PREFIJO_API = "/" + _texto("API_PREFIX", "api/v1").strip("/")
    # Render (y otros PaaS) publican el puerto en `PORT`; se prefiere ese
    # valor para no tener que mantener `API_PORT` sincronizado con la
    # plataforma.
    PUERTO = _entero("PORT", 0) or _entero("API_PORT", 4000)

    # ── Base de datos ────────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = _normalizar_url(_texto("DATABASE_URL", ""))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,   # descarta conexiones muertas antes de usarlas
        "pool_recycle": 1800,
    }

    # ── Sesiones y tokens ────────────────────────────────────────────
    JWT_ACCESO_SECRETO = _texto("JWT_ACCESS_SECRET", "dev-access-secret-change-me-please-32")
    JWT_REFRESCO_SECRETO = _texto("JWT_REFRESH_SECRET", "dev-refresh-secret-change-me-please-32")
    JWT_ACCESO_TEXTO = _texto("JWT_ACCESS_EXPIRES_IN", "15m")
    JWT_REFRESCO_TEXTO = _texto("JWT_REFRESH_EXPIRES_IN", "7d")
    JWT_ACCESO_SEGUNDOS = _duracion_a_segundos(JWT_ACCESO_TEXTO, 900)
    JWT_REFRESCO_SEGUNDOS = _duracion_a_segundos(JWT_REFRESCO_TEXTO, 604_800)

    # Clave de las sesiones de navegador (las páginas HTML)
    SECRET_KEY = _texto("SESSION_SECRET", JWT_ACCESO_SECRETO)

    # La cookie de sesión no existía en el sistema anterior, que solo usaba
    # cabecera Authorization. Al introducirla aparece la posibilidad de que
    # un sitio ajeno provoque peticiones autenticadas desde el navegador, así
    # que se restringe: no viaja en peticiones que vengan de otro sitio, ni
    # es accesible desde JavaScript.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = ENTORNO == "production"
    PERMANENT_SESSION_LIFETIME = JWT_REFRESCO_SEGUNDOS

    # ── Seguridad ────────────────────────────────────────────────────
    BCRYPT_RONDAS = _entero("BCRYPT_ROUNDS", 12)
    LOGIN_INTENTOS_MAXIMOS = _entero("LOGIN_MAX_ATTEMPTS", 5)
    LOGIN_BLOQUEO_MINUTOS = _entero("LOGIN_LOCK_MINUTES", 15)
    LOGIN_LIMITE = _entero("LOGIN_RATE_LIMIT", 5)
    LOGIN_VENTANA = _entero("LOGIN_RATE_TTL", 60)

    ORIGENES_CORS = [
        o.strip()
        for o in _texto("CORS_ORIGINS", "http://localhost:3000").split(",")
        if o.strip()
    ]

    # ── Archivos subidos ─────────────────────────────────────────────
    # Las rutas guardadas en la base son públicas (`/uploads/teachers/…`),
    # así que mover la carpeta no invalida ninguna fotografía existente.
    CARPETA_SUBIDAS = RAIZ / "uploads"
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB, igual que el límite anterior

    # ── Usuario inicial ──────────────────────────────────────────────
    SEED_ADMIN_EMAIL = _texto("SEED_ADMIN_EMAIL", "admin@datly.local")

    @classmethod
    def comprobar(cls) -> list[str]:
        """Devuelve los problemas de configuración que impedirían arrancar."""
        problemas: list[str] = []

        if not cls.SQLALCHEMY_DATABASE_URI:
            problemas.append(
                "Falta DATABASE_URL en el archivo .env. "
                "Ejecute CONFIGURAR-BASE-DE-DATOS.bat para generarlo."
            )
        elif not cls.SQLALCHEMY_DATABASE_URI.startswith("postgresql"):
            problemas.append("DATABASE_URL no apunta a PostgreSQL.")

        if cls.ENTORNO == "production":
            for nombre, valor in (
                ("JWT_ACCESS_SECRET", cls.JWT_ACCESO_SECRETO),
                ("JWT_REFRESH_SECRET", cls.JWT_REFRESCO_SECRETO),
                ("SESSION_SECRET", cls.SECRET_KEY),
            ):
                if "change-me" in valor or len(valor) < 32:
                    problemas.append(f"{nombre} debe cambiarse antes de publicar en producción.")

        return problemas


class Desarrollo(Config):
    DEBUG = True


class Produccion(Config):
    DEBUG = False


def obtener_config() -> type[Config]:
    return Produccion if Config.ENTORNO == "production" else Desarrollo
