"""
Páginas HTML.

Sustituye al enrutado de Next.js. Cada pantalla se genera en el servidor con
Jinja2 y los mismos datos que antes pedía el frontend a la API; el JavaScript
propio se encarga de la interacción.

Las direcciones son las mismas que tenía la aplicación en React, para que
cualquier enlace guardado siga funcionando.
"""

from __future__ import annotations

import re
from functools import wraps
from urllib.parse import quote

from flask import Blueprint, redirect, render_template, request, url_for

from ..comun.seguridad import usuario_actual
from ..modelos.acceso import ROL_CONTROL_TOTAL
from ..modulos.configuracion import servicio as configuracion
from . import navegacion

bp = Blueprint("web", __name__)

# Identidad por defecto (se puede cambiar desde la configuración institucional)
INSTITUCION_POR_DEFECTO = "IED Los Laureles"
LEMA = "Puntualidad y compromiso con un solo código QR"


def con_sesion(permiso: str | None = None):
    """
    Exige sesión para ver la página.

    A diferencia de la API, aquí no se devuelve 401: se lleva al acceso
    recordando a dónde se quería ir.
    """

    def decorador(funcion):
        @wraps(funcion)
        def envoltura(*args, **kwargs):
            usuario = usuario_actual()
            if usuario is None:
                destino = quote(request.full_path.rstrip("?"))
                return redirect(f"/login?redirect={destino}")
            if permiso and not usuario.tiene(permiso):
                return render_template("sin-permiso.html", **_contexto("Sin acceso")), 403
            return funcion(*args, **kwargs)

        return envoltura

    return decorador


def _contexto(titulo: str) -> dict:
    """Datos que necesitan todas las pantallas administrativas."""
    usuario = usuario_actual()
    return {
        "titulo_pagina": titulo,
        "menu": navegacion.construir(usuario, request.path) if usuario else [],
        "usuario": {
            "nombre": usuario.nombre_completo if usuario else "",
            "correo": usuario.email if usuario else "",
            "rol": usuario.rol_nombre if usuario else "",
            "iniciales": navegacion.iniciales(usuario.nombre_completo if usuario else ""),
        },
        "permisos": {
            "marcar": bool(usuario and usuario.tiene("attendance.self", "attendance.create")),
            "excusas": bool(usuario and usuario.tiene("excuses.self")),
            "revisar_excusas": bool(usuario and usuario.tiene("excuses.review")),
            "borrar_asistencia": bool(usuario and usuario.rol_codigo == ROL_CONTROL_TOTAL),
            "editar_ajustes": bool(usuario and usuario.tiene("settings.update")),
            "reportes": bool(usuario and usuario.tiene("reports.read")),
            "asistencia": bool(usuario and usuario.tiene("attendance.read")),
        },
        "institucion": configuracion.texto(
            configuracion.CLAVES["NOMBRE_CORTO"], INSTITUCION_POR_DEFECTO
        ),
        "lema": LEMA,
    }


# ── Acceso ───────────────────────────────────────────────────────────


def _portada() -> dict:
    """Datos de la portada pública: identidad, lema y el QR institucional."""
    institucion = configuracion.texto(
        configuracion.CLAVES["NOMBRE_CORTO"], INSTITUCION_POR_DEFECTO
    )
    url = configuracion.texto(configuracion.CLAVES["QR_URL"], "")

    qr_svg = ""
    if url:
        try:
            from io import BytesIO

            import segno

            memoria = BytesIO()
            segno.make(url, error="h").save(
                memoria, kind="svg", scale=6, dark="#0F172A", border=2
            )
            crudo = memoria.getvalue().decode("utf-8")
            # Se incrusta en el HTML: fuera la declaración XML
            svg = crudo[crudo.find("<svg"):]
            # segno emite width/height fijos y sin viewBox: al cambiarle el
            # tamaño desde CSS el dibujo se recorta. El área se conserva como
            # viewBox y se quitan las medidas para que escale centrado.
            ancho = re.search(r'width="(\d+(?:\.\d+)?)"', svg)
            alto = re.search(r'height="(\d+(?:\.\d+)?)"', svg)
            if ancho and alto:
                svg = re.sub(r'\s(?:width|height)="\d+(?:\.\d+)?"', "", svg, count=2)
                svg = svg.replace(
                    "<svg ", f'<svg viewBox="0 0 {ancho.group(1)} {alto.group(1)}" ', 1
                )
            qr_svg = svg
        except Exception:  # noqa: BLE001 - la portada nunca debe romperse por el QR
            qr_svg = ""

    return {
        "institucion": institucion,
        "lema": LEMA,
        "qr_svg": qr_svg,
        "qr_url": url,
    }


@bp.get("/")
def inicio():
    if usuario_actual():
        return redirect("/dashboard")
    return render_template("inicio.html", **_portada())


@bp.get("/login")
def login():
    if usuario_actual():
        return redirect(request.args.get("redirect") or "/dashboard")
    return render_template("login.html", **_contexto("Acceso"))


# ── Pantallas ────────────────────────────────────────────────────────


@bp.get("/dashboard")
@con_sesion("dashboard.read")
def dashboard():
    """
    Dashboard del docente y dashboard de la institución.

    Son dos pantallas distintas con la misma dirección. La del docente muestra
    sus propias cifras; la institucional, el panorama completo. Se decide por
    el permiso: quien puede consultar la asistencia de todo el colegio recibe
    el panel general, y el resto recibe el suyo.
    """
    usuario = usuario_actual()

    if usuario and usuario.tiene("attendance.read", "teachers.read"):
        from ..modulos.reportes import servicio as reportes

        return render_template(
            "dashboard.html", panel=reportes.panel(), **_contexto("Dashboard")
        )

    from ..modulos.asistencia import servicio as asistencia

    return render_template(
        "mi-dashboard.html", panel=asistencia.panel_propio(usuario), **_contexto("Mi dashboard")
    )


@bp.get("/mi-asistencia")
@con_sesion("attendance.self")
def mi_asistencia():
    """
    Asistencia del docente: el detalle de sus marcaciones y la acción de marcar.

    Vive aparte de `/asistencia`, que es el listado administrativo de todo el
    colegio. Aquí solo hay una fila de datos, la del usuario que entró, pero
    hace falta pantalla propia para que ese dato no compita con la vista
    institucional.
    """
    from ..modulos.asistencia import servicio as asistencia

    usuario = usuario_actual()
    return render_template(
        "mi-asistencia.html",
        estado=asistencia.estado_propio(usuario),
        **_contexto("Mi asistencia"),
    )


@bp.get("/excusas")
@con_sesion("excuses.self")
def excusas():
    """
    Justificaciones del docente: presentar una nueva y seguir las que ya envía.

    La lista y la revisión se cargan por la API desde la propia página, igual
    que el resto de listados, para que un filtro no obligue a recargar todo el
    HTML.
    """
    return render_template("excusas.html", **_contexto("Mis excusas"))


@bp.get("/revision-excusas")
@con_sesion("excuses.read")
def revision_excusas():
    """
    Revisión de justificaciones de toda la institución.

    Es la contraparte de `/excusas`: el docente presenta y sigue las suyas, y
    quien tiene `excuses.read` decide sobre todas. La decisión se toma con
    `excuses.review`, que es un permiso aparte de poder consultarlas: poder ver
    la bandeja no implica poder resolverla.
    """
    return render_template("revision-excusas.html", **_contexto("Revisión de excusas"))


# Cada listado se resuelve con la misma plantilla: cambia la definición de
# columnas y el módulo del que salen los datos.
LISTADOS = {
    "docentes": ("Docentes", "teachers.read"),
    "asignaturas": ("Asignaturas", "subjects.read"),
    "grados": ("Grados", "grades.read"),
    "cursos": ("Cursos", "courses.read"),
    "jornadas": ("Jornadas", "shifts.read"),
    "horarios": ("Horarios", "schedules.read"),
    "asistencia": ("Asistencia", "attendance.read"),
    "usuarios": ("Usuarios", "users.read"),
    "roles": ("Roles", "roles.read"),
    "reportes": ("Reportes", "reports.read"),
}


def _registrar_listado(nombre: str, titulo: str, permiso: str) -> None:
    @bp.get(f"/{nombre}", endpoint=f"listado_{nombre}")
    @con_sesion(permiso)
    def vista(nombre=nombre, titulo=titulo):
        from . import listados

        return render_template(
            "listado.html", vista=listados.construir(nombre), **_contexto(titulo)
        )


for _nombre, (_titulo, _permiso) in LISTADOS.items():
    _registrar_listado(_nombre, _titulo, _permiso)


@bp.get("/qr")
@con_sesion("settings.read")
def codigo_qr():
    from flask import current_app

    from ..comun import red

    datos = configuracion.qr()
    return render_template(
        "qr.html",
        qr=datos,
        # Un QR con «localhost» se escanea bien pero no lleva a ninguna parte
        # desde un teléfono: se avisa y se ofrece la dirección correcta.
        sugerida=red.url_sugerida(current_app.config["PUERTO"]),
        alcanzable=red.es_alcanzable_desde_fuera(datos.get("publicUrl", "")),
        **_contexto("Código QR"),
    )


@bp.get("/qr/imagen.<formato>")
@con_sesion("settings.read")
def imagen_qr(formato: str):
    """
    Genera el código QR.

    Sustituye a la librería `qrcode` que usaba el frontend en React. Se genera
    en el servidor con segno, así que la imagen no depende de JavaScript y
    puede imprimirse directamente.
    """
    import segno
    from flask import Response

    if formato not in ("svg", "png"):
        return render_template("sin-permiso.html", **_contexto("Formato no válido")), 404

    destino = request.args.get("url") or configuracion.qr()["publicUrl"]
    if not destino:
        return Response("", status=204)

    # Corrección de errores alta: el código sigue leyéndose impreso y con uso
    codigo = segno.make(destino, error="h")

    from io import BytesIO

    memoria = BytesIO()
    if formato == "svg":
        codigo.save(memoria, kind="svg", scale=8, dark="#0F172A", border=2)
        tipo = "image/svg+xml"
    else:
        codigo.save(memoria, kind="png", scale=12, dark="#0F172A", border=2)
        tipo = "image/png"

    cabeceras = {"Cache-Control": "no-store"}
    if request.args.get("descargar"):
        cabeceras["Content-Disposition"] = f'attachment; filename="qr-institucional.{formato}"'

    return Response(memoria.getvalue(), mimetype=tipo, headers=cabeceras)


@bp.get("/configuracion")
@con_sesion("settings.read")
def configuracion_pagina():
    """
    Ajustes institucionales.

    Aquí se fija la ubicación del colegio: el punto medio, el radio y si la
    marcación exige estar dentro de ese rango. También se controla el
    seguimiento permanente de la ubicación del docente.
    """
    return render_template(
        "configuracion.html",
        ubicacion=configuracion.ubicacion_colegio(),
        **_contexto("Configuración"),
    )


@bp.get("/marcar")
@con_sesion()
def marcar():
    from ..modulos.asistencia import servicio as asistencia

    usuario = usuario_actual()
    estado = asistencia.estado_propio(usuario) if usuario.docente_id else None
    return render_template("marcar.html", estado=estado, **_contexto("Marcar asistencia"))


@bp.get("/escanear")
@con_sesion()
def escanear():
    """Página de escaneo QR con geolocalización para docentes."""
    from ..modulos.asistencia import servicio as asistencia

    usuario = usuario_actual()
    estado = asistencia.estado_propio(usuario) if usuario.docente_id else None
    return render_template("escanear.html", estado=estado, **_contexto("Escanear QR"))
