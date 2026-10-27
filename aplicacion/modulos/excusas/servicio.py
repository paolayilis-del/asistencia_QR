"""Excusas y justificaciones. Sustituye a `modules/excuse/excuse.service.ts`."""

from __future__ import annotations

from flask import current_app, request
from sqlalchemy import func, or_, select

from ...comun import auditoria
from ...comun.consultas import Paginacion, paginar
from ...comun.errores import Conflicto, NoEncontrado, Prohibido, SolicitudInvalida
from ...comun.peticion import ContextoPeticion
from ...comun.respuestas import resultado_paginado
from ...comun.seguridad import UsuarioAutenticado
from ...comun.subidas import normalizar_documento
from ...comun.validaciones import exigir_identificador
from ...comun.tiempo import ahora, iso, rango_dias, solo_fecha
from ...extensiones import bd
from ...modelos import (
    ETIQUETA_ESTADO_EXCUSA,
    ETIQUETA_TIPO_EXCUSA,
    AccionAuditoria,
    Docente,
    EstadoExcusa,
    Excusa,
    Marcacion,
    TipoExcusa,
)
from .esquemas import PresentarExcusa, RevisarExcusa

MODULO = "excusas"

ORDENABLES = {
    "createdAt": Excusa.created_at,
    "date": Excusa.date,
    "status": Excusa.status,
    "type": Excusa.type,
}


# ─────────────────────────────── Creación ────────────────────────────


def presentar(
    datos: PresentarExcusa, archivo, actor: UsuarioAutenticado, ctx: ContextoPeticion
) -> dict:
    """
    Registra la justificación de un docente.

    El archivo es obligatorio: una excusa sin soporte no es una excusa. Se
    guarda en la base de datos, no en el disco, para que viaje con el respaldo
    y no dependa de una carpeta que el despliegue pueda perder.
    """
    if not actor.docente_id:
        raise Prohibido("Su usuario no está vinculado a un docente")

    # Una justificación repetida del mismo día es casi siempre un doble clic.
    existente = bd.session.execute(
        select(Excusa).where(
            Excusa.teacher_id == actor.docente_id,
            Excusa.date == solo_fecha(datos.date),
            Excusa.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if existente is not None:
        raise Conflicto("Ya tiene una excusa registrada para esa fecha")

    contenido, nombre, tipo, tamano = normalizar_documento(archivo)

    fila = Excusa(
        teacher_id=actor.docente_id,
        attendance_id=_marcacion_del_dia(actor.docente_id, datos.date),
        type=datos.type,
        status=EstadoExcusa.PENDIENTE,
        date=solo_fecha(datos.date),
        reason=datos.reason,
        file_name=nombre,
        file_mime=tipo,
        file_size=tamano,
        file_data=contenido,
        created_by_id=actor.id,
    )
    bd.session.add(fila)

    auditoria.anotar(
        AccionAuditoria.CREAR,
        MODULO,
        f"Presentó una excusa de tipo {ETIQUETA_TIPO_EXCUSA.get(datos.type.value, datos.type.value)}",
        entidad_id=None,
        detalle={"date": datos.date, "tipo": datos.type.value, "tamano": tamano},
        usuario=actor,
        ctx=ctx,
    )
    bd.session.commit()
    return serializar(fila)


def _marcacion_del_dia(docente_id: str, fecha: str) -> str | None:
    """
    Vincula la excusa con la marcación de ese día, si la hubo.

    Así el historial del docente puede mostrar la justificación al lado de la
    entrada o la salida que explica. Si el día no tiene marcación, la excusa
    sirve igual: también justifica los días en que no se registró nada.
    """
    fila = bd.session.execute(
        select(Marcacion.id)
        .where(
            Marcacion.teacher_id == docente_id,
            Marcacion.date == solo_fecha(fecha),
            Marcacion.deleted_at.is_(None),
        )
        .order_by(Marcacion.registered_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    return fila


# ─────────────────────────────── Consulta ─────────────────────────────


def serializar(fila: Excusa) -> dict:
    docente = fila.docente
    prefijo = current_app.config["PREFIJO_API"]
    return {
        "id": fila.id,
        "teacherId": fila.teacher_id,
        "attendanceId": fila.attendance_id,
        "type": fila.type.value,
        "typeLabel": ETIQUETA_TIPO_EXCUSA.get(fila.type.value, fila.type.value),
        "status": fila.status.value,
        "statusLabel": ETIQUETA_ESTADO_EXCUSA.get(fila.status.value, fila.status.value),
        "date": iso(fila.date),
        "reason": fila.reason,
        # El nombre del archivo se expone, el contenido no: este último solo
        # se sirve por la ruta de descarga, que sí comprueba permisos.
        "fileName": fila.file_name,
        "fileMime": fila.file_mime,
        "fileSize": fila.file_size,
        "fileUrl": f"{prefijo}/excuses/{fila.id}/file" if fila.file_data else None,
        "reviewedById": fila.reviewed_by_id,
        "reviewedAt": iso(fila.reviewed_at),
        "reviewNotes": fila.review_notes,
        # Quién resolvió la solicitud. Se muestra en la pantalla de revisión
        # para que quede claro qué decisión tomó cada administrativo.
        "reviewedBy": (
            {
                "id": fila.revisor.id,
                "firstName": fila.revisor.first_name,
                "lastName": fila.revisor.last_name,
            }
            if fila.revisor
            else None
        ),
        "createdById": fila.created_by_id,
        "createdAt": iso(fila.created_at),
        "updatedAt": iso(fila.updated_at),
        "teacher": (
            {
                "id": docente.id,
                "code": docente.code,
                "firstName": docente.first_name,
                "lastName": docente.last_name,
                "document": docente.document,
            }
            if docente
            else None
        ),
    }


def listar_propias(actor: UsuarioAutenticado) -> dict:
    """Justificaciones presentadas por el docente autenticado."""
    if not actor.docente_id:
        raise Prohibido("Su usuario no está vinculado a un docente")

    paginacion = Paginacion("created_at")
    consulta = select(Excusa).where(
        Excusa.teacher_id == actor.docente_id, Excusa.deleted_at.is_(None)
    )

    tipo = request.args.get("type")
    if tipo in [t.value for t in TipoExcusa]:
        consulta = consulta.where(Excusa.type == TipoExcusa(tipo))

    estado = request.args.get("status")
    if estado in [e.value for e in EstadoExcusa]:
        consulta = consulta.where(Excusa.status == EstadoExcusa(estado))

    consulta = consulta.order_by(Excusa.date.desc(), Excusa.created_at.desc())
    elementos, total = paginar(consulta, paginacion)
    return resultado_paginado(
        [serializar(e) for e in elementos], total, paginacion.pagina, paginacion.limite
    )


def listar(actor: UsuarioAutenticado) -> dict:
    """Justificaciones de toda la institución, para quien puede revisarlas."""
    paginacion = Paginacion("created_at")
    consulta = select(Excusa).where(Excusa.deleted_at.is_(None))

    tipo = request.args.get("type")
    if tipo in [t.value for t in TipoExcusa]:
        consulta = consulta.where(Excusa.type == TipoExcusa(tipo))

    estado = request.args.get("status")
    if estado in [e.value for e in EstadoExcusa]:
        consulta = consulta.where(Excusa.status == EstadoExcusa(estado))

    docente_id = request.args.get("teacherId")
    if docente_id:
        consulta = consulta.where(Excusa.teacher_id == docente_id)

    desde, hasta = rango_dias(request.args.get("dateFrom"), request.args.get("dateTo"))
    if desde:
        consulta = consulta.where(Excusa.date >= desde)
    if hasta:
        consulta = consulta.where(Excusa.date <= hasta)

    busqueda = paginacion.busqueda
    if busqueda:
        # Se busca por código, nombre o documento del docente, igual que en
        # el resto de listados: quien revisa busca "por quién", no por UUID.
        consulta = consulta.where(
            Excusa.teacher_id.in_(
                select(Docente.id).where(
                    or_(
                        Docente.code.ilike(f"%{busqueda}%"),
                        Docente.first_name.ilike(f"%{busqueda}%"),
                        Docente.last_name.ilike(f"%{busqueda}%"),
                        Docente.document.ilike(f"%{busqueda}%"),
                    )
                )
            )
        )

    orden = ORDENABLES.get(paginacion.ordenar_por, Excusa.date)
    consulta = consulta.order_by(
        orden.asc() if paginacion.orden == "asc" else orden.desc()
    )

    elementos, total = paginar(consulta, paginacion)
    return resultado_paginado(
        [serializar(e) for e in elementos], total, paginacion.pagina, paginacion.limite
    )


def obtener(identificador: str, actor: UsuarioAutenticado) -> dict:
    fila = _buscar(identificador)
    _comprobar_acceso(fila, actor)
    return serializar(fila)


def _buscar(identificador: str) -> Excusa:
    exigir_identificador(identificador)
    fila = bd.session.execute(
        select(Excusa).where(Excusa.id == identificador, Excusa.deleted_at.is_(None))
    ).unique().scalar_one_or_none()
    if fila is None:
        raise NoEncontrado("La excusa no existe")
    return fila


def _comprobar_acceso(fila: Excusa, actor: UsuarioAutenticado) -> None:
    """
    El docente solo ve las suyas; quien tiene `excuses.read`, todas.
    """
    if actor.tiene("excuses.read"):
        return
    if actor.docente_id and fila.teacher_id == actor.docente_id:
        return
    raise Prohibido("No tiene acceso a esta excusa")


def leer_archivo(identificador: str, actor: UsuarioAutenticado) -> tuple[bytes, str, str]:
    """Contenido, tipo y nombre del adjunto, previa comprobación de acceso."""
    fila = _buscar(identificador)
    _comprobar_acceso(fila, actor)

    if fila.file_data is None:
        raise NoEncontrado("Esta excusa no tiene archivo adjunto")

    return bytes(fila.file_data), fila.file_mime or "application/octet-stream", fila.file_name or "excusa"


# ─────────────────────────────── Revisión ─────────────────────────────


def revisar(
    identificador: str, datos: RevisarExcusa, actor: UsuarioAutenticado, ctx: ContextoPeticion
) -> dict:
    """Aprueba o rechaza una justificación."""
    fila = _buscar(identificador)

    if fila.status != EstadoExcusa.PENDIENTE:
        raise Conflicto("Esta excusa ya fue revisada")

    # Un rechazo sin explicación no deja al docente saber qué corregir, así que
    # se exige motivo. Aprobar no lo necesita: basta con registrar la decisión.
    if datos.status == EstadoExcusa.RECHAZADA and not (datos.notas or "").strip():
        raise SolicitudInvalida("Explique por qué rechaza la justificación")

    fila.status = datos.status
    fila.review_notes = datos.notas
    fila.reviewed_by_id = actor.id
    fila.reviewed_at = ahora()

    auditoria.anotar(
        AccionAuditoria.ACTUALIZAR,
        MODULO,
        f"Revisó una excusa como {ETIQUETA_ESTADO_EXCUSA.get(datos.status.value, datos.status.value)}",
        entidad_id=identificador,
        detalle={"status": datos.status.value, "notas": datos.notas},
        usuario=actor,
        ctx=ctx,
    )
    bd.session.commit()
    return serializar(fila)


# ────────────────────────────── Resumen ───────────────────────────────


def resumen(actor: UsuarioAutenticado) -> dict:
    """Cifras de las excusas del docente para su pantalla."""
    if not actor.docente_id:
        raise Prohibido("Su usuario no está vinculado a un docente")

    total, pendientes, aprobadas, rechazadas = bd.session.execute(
        select(
            func.count(Excusa.id),
            func.count(Excusa.id).filter(Excusa.status == EstadoExcusa.PENDIENTE),
            func.count(Excusa.id).filter(Excusa.status == EstadoExcusa.APROBADA),
            func.count(Excusa.id).filter(Excusa.status == EstadoExcusa.RECHAZADA),
        ).where(Excusa.teacher_id == actor.docente_id, Excusa.deleted_at.is_(None))
    ).one()

    return {
        "total": total or 0,
        "pending": pendientes or 0,
        "approved": aprobadas or 0,
        "rejected": rechazadas or 0,
    }


def resumen_global() -> dict:
    """
    Cifras de toda la institución para la pantalla de revisión.

    No lleva docente: quien revisa necesita saber cuántas hay en total y cuántas
    lo esperan, no el desglose de cada uno. Además calcula la más antigua sin
    resolver, que es la que conviene atender primero.
    """
    total, pendientes, aprobadas, rechazadas = bd.session.execute(
        select(
            func.count(Excusa.id),
            func.count(Excusa.id).filter(Excusa.status == EstadoExcusa.PENDIENTE),
            func.count(Excusa.id).filter(Excusa.status == EstadoExcusa.APROBADA),
            func.count(Excusa.id).filter(Excusa.status == EstadoExcusa.RECHAZADA),
        ).where(Excusa.deleted_at.is_(None))
    ).one()

    antigua = bd.session.execute(
        select(func.min(Excusa.created_at)).where(
            Excusa.status == EstadoExcusa.PENDIENTE, Excusa.deleted_at.is_(None)
        )
    ).scalar_one_or_none()

    # Por tipo, para que quien revisa sepa de qué son las solicitudes que tiene.
    por_tipo = {
        tipo.value: (conteo or 0)
        for tipo, conteo in bd.session.execute(
            select(Excusa.type, func.count(Excusa.id))
            .where(Excusa.status == EstadoExcusa.PENDIENTE, Excusa.deleted_at.is_(None))
            .group_by(Excusa.type)
        ).all()
    }

    return {
        "total": total or 0,
        "pending": pendientes or 0,
        "approved": aprobadas or 0,
        "rejected": rechazadas or 0,
        "oldestPendingAt": iso(antigua),
        "pendingByType": {
            "INCAPACIDAD": por_tipo.get("INCAPACIDAD", 0),
            "PERMISO": por_tipo.get("PERMISO", 0),
            "OTRO": por_tipo.get("OTRO", 0),
        },
    }
