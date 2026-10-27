"""
Formato uniforme de las respuestas de la API.

Sustituye a `TransformInterceptor` y a `PaginatedResultDto`.

El sobre debe ser idéntico al del sistema anterior, porque el JavaScript de la
interfaz y cualquier consumidor externo ya dependen de esa forma exacta:

    { "success": true, "statusCode": 200, "data": ..., "timestamp": "..." }
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from flask import jsonify


def _ahora() -> str:
    """Marca de tiempo en ISO 8601 con milisegundos, como la de JavaScript."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def responder(datos: Any = None, codigo: int = 200):
    """Envuelve una respuesta correcta."""
    cuerpo = {
        "success": True,
        "statusCode": codigo,
        "data": datos,
        "timestamp": _ahora(),
    }
    return jsonify(cuerpo), codigo


def responder_error(
    mensaje: str,
    codigo: int = 400,
    errores: list[str] | None = None,
    ruta: str = "",
):
    """Envuelve una respuesta de error, con el mismo cuerpo que el sistema anterior."""
    cuerpo: dict[str, Any] = {
        "success": False,
        "statusCode": codigo,
        "message": mensaje,
    }
    if errores:
        cuerpo["errors"] = errores
    cuerpo["path"] = ruta
    cuerpo["timestamp"] = _ahora()
    return jsonify(cuerpo), codigo


def resultado_paginado(
    elementos: list[Any],
    total: int,
    pagina: int,
    limite: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Estructura de listado. Réplica de `buildPaginatedResult`.

    La clave es `items`, no `data`: la interfaz ya la consume así.

    `extra` añade claves al nivel superior, no dentro de `meta`. Lo usa el
    historial del docente, que devuelve un resumen del periodo filtrado junto
    con los registros: son datos hermanos, no parte de la paginación.
    """
    total_paginas = max(1, math.ceil(total / limite)) if limite else 1
    resultado: dict[str, Any] = {
        "items": elementos,
        "meta": {
            "page": pagina,
            "limit": limite,
            "total": total,
            "totalPages": total_paginas,
            "hasNextPage": pagina < total_paginas,
            "hasPreviousPage": pagina > 1,
        },
    }
    if extra:
        resultado.update(extra)
    return resultado
