"""Rutas de excusas. Traducción de `modules/excuse/excuse.controller.ts`."""

from __future__ import annotations

from flask import Blueprint, Response, request
from pydantic import ValidationError

from ...comun.errores import SolicitudInvalida
from ...comun.peticion import contexto
from ...comun.respuestas import responder
from ...comun.seguridad import exigir_usuario, requiere_permisos, requiere_sesion
from . import servicio
from .esquemas import PresentarExcusa, RevisarExcusa

bp = Blueprint("excusas", __name__)


@bp.post("/excuses")
@requiere_permisos("excuses.self", "excuses.read")
def presentar():
    """Recibe la justificación con su documento adjunto."""
    # El archivo va multipart porque es un adjunto; el resto del formulario
    # llega como texto en el campo `payload`, en el mismo formato que la API
    # ya usa en JSON. Así el cliente no necesita dos rutas distintas.
    carga = request.form.get("payload")
    if not carga:
        raise SolicitudInvalida("No se recibieron los datos de la excusa")

    try:
        datos = PresentarExcusa.model_validate_json(carga)
    except ValidationError as error:
        raise SolicitudInvalida("Los datos de la excusa no son válidos") from error

    return responder(
        servicio.presentar(
            datos, request.files.get("file"), exigir_usuario(), contexto()
        ),
        201,
    )


@bp.get("/excuses/me")
@requiere_permisos("excuses.self", "excuses.read")
def listar_propias():
    return responder(servicio.listar_propias(exigir_usuario()))


@bp.get("/excuses/me/summary")
@requiere_permisos("excuses.self", "excuses.read")
def resumen_propio():
    return responder(servicio.resumen(exigir_usuario()))


@bp.get("/excuses/summary")
@requiere_permisos("excuses.read")
def resumen_general():
    """Cifras de toda la institución, para la pantalla de revisión."""
    return responder(servicio.resumen_global())


@bp.get("/excuses")
@requiere_permisos("excuses.read")
def listar():
    return responder(servicio.listar(exigir_usuario()))


@bp.get("/excuses/<identificador>")
@requiere_permisos("excuses.self", "excuses.read")
def obtener(identificador: str):
    return responder(servicio.obtener(identificador, exigir_usuario()))


@bp.get("/excuses/<identificador>/file")
@requiere_sesion
def descargar_archivo(identificador: str):
    """
    Sirve el documento adjunto.

    El permiso se comprueba contra la excusa concreta, no contra el módulo: el
    docente descarga la suya y un administrativo las que puede revisar. Por
    eso basta con tener sesión, igual que con la fotografía del docente.
    """
    contenido, tipo, nombre = servicio.leer_archivo(identificador, exigir_usuario())
    return Response(
        contenido,
        mimetype=tipo,
        headers={
            "Content-Disposition": f'inline; filename="{nombre}"',
            "Cache-Control": "private, max-age=3600",
            "Content-Length": str(len(contenido)),
        },
    )


@bp.post("/excuses/<identificador>/review")
@requiere_permisos("excuses.review")
def revisar(identificador: str):
    """Aprueba o rechaza una justificación."""
    datos = RevisarExcusa.model_validate(request.get_json(silent=True) or {})
    return responder(
        servicio.revisar(identificador, datos, exigir_usuario(), contexto())
    )
