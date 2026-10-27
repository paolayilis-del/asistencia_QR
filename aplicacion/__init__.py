"""
Sistema Web de Asistencia Docente por QR.

Fábrica de la aplicación. Sustituye a `backend/src/main.ts` y a `AppModule`.

Un solo proceso sirve las tres cosas que antes estaban repartidas entre dos:
las páginas HTML, la API REST y los archivos subidos.
"""

from __future__ import annotations

import logging

from flask import Flask, request, send_from_directory
from flask_cors import CORS

from .comun.errores import registrar_manejadores
from .config import ORIGEN_ENTORNO, Config, obtener_config
from .extensiones import bd, limitador

__version__ = "3.7.0"


def crear_app(config: type[Config] | None = None) -> Flask:
    """Construye la aplicación con todo enlazado."""
    ajustes = config or obtener_config()

    app = Flask(
        __name__,
        template_folder="plantillas",
        static_folder="estaticos",
        static_url_path="/estaticos",
    )
    app.config.from_object(ajustes)
    app.config["PREFIJO_API"] = ajustes.PREFIJO_API

    _configurar_registro(app)

    problemas = ajustes.comprobar()
    if problemas:
        for problema in problemas:
            app.logger.error("Configuración: %s", problema)
        if not ajustes.SQLALCHEMY_DATABASE_URI:
            raise RuntimeError("; ".join(problemas))

    # ── Extensiones ──────────────────────────────────────────────────
    bd.init_app(app)
    limitador.init_app(app)

    CORS(
        app,
        resources={f"{ajustes.PREFIJO_API}/*": {"origins": ajustes.ORIGENES_CORS}},
        supports_credentials=True,
        expose_headers=["Content-Disposition"],
    )

    # ── Módulos ──────────────────────────────────────────────────────
    _registrar_modulos(app)

    # ── Estructura que le falta a la base ya desplegada ─────────────
    # `database.sql` sigue siendo la fuente para una instalación nueva; esto
    # solo pone al día una base que ya está en producción.
    from . import migraciones

    migraciones.aplicar(app)

    # ── Fotografías guardadas antes de la versión 3.4 ────────────────
    # Ahora las imágenes viven en la base de datos y se sirven desde el propio
    # módulo de docentes. Esta ruta solo atiende las que quedaran en el disco
    # de una instalación anterior; `herramientas/migrar_fotos.py` las traslada.
    if ajustes.CARPETA_SUBIDAS.is_dir():

        @app.route("/uploads/<path:recurso>")
        def archivos_subidos(recurso: str):
            return send_from_directory(ajustes.CARPETA_SUBIDAS, recurso, max_age=604_800)

    # ── Comprobación de estado ───────────────────────────────────────
    @app.route(f"{ajustes.PREFIJO_API}/health")
    @limitador.exempt
    def salud():
        from .comun.respuestas import responder

        return responder({"status": "ok", "version": __version__})

    # ── Cabeceras de protección ──────────────────────────────────────
    @app.after_request
    def _cabeceras(respuesta):
        respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
        respuesta.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        respuesta.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.path.startswith("/uploads/"):
            respuesta.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        return respuesta

    registrar_manejadores(app)

    app.logger.info("Configuración leída de %s", ORIGEN_ENTORNO or "(variables del sistema)")
    return app


def _configurar_registro(app: Flask) -> None:
    formato = logging.Formatter("  %(levelname)-7s %(message)s")
    consola = logging.StreamHandler()
    consola.setFormatter(formato)

    for registro in (app.logger, logging.getLogger("asistencia")):
        registro.handlers.clear()
        registro.addHandler(consola)
        registro.setLevel(logging.DEBUG if app.config.get("DEBUG") else logging.INFO)


# Módulos de la API, en el orden en que se registran. La lista crece a medida
# que se van portando; cada entrada es el paquete bajo `aplicacion.modulos`.
MODULOS_API = (
    "auth",
    "usuarios",
    "roles",
    "permisos",
    "docentes",
    "asignaturas",
    "grados",
    "cursos",
    "jornadas",
    "horarios",
    "asistencia",
    "excusas",
    "reportes",
    "auditoria",
    "configuracion",
)


def _registrar_modulos(app: Flask) -> None:
    """Engancha los blueprints. Equivale a los `imports` de `AppModule`."""
    from importlib import import_module

    prefijo = app.config["PREFIJO_API"]

    for nombre in MODULOS_API:
        modulo = import_module(f".modulos.{nombre}.rutas", package=__name__)
        app.register_blueprint(modulo.bp, url_prefix=prefijo)

    # Las páginas HTML cuelgan de la raíz, sin prefijo
    from .web.rutas import bp as bp_web

    app.register_blueprint(bp_web)

    app.logger.info("Módulos registrados: %s", ", ".join(MODULOS_API))
