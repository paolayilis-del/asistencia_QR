"""
Servicio de asistencia.

Traducción de `modules/attendance/attendance.service.ts`, el módulo que
concentra las reglas de negocio del sistema:

    RN001 / RN002   el docente y su cuenta deben estar activos
    RN003           debe existir un horario aplicable
    RN004 / RN005   no se admiten dos entradas ni dos salidas seguidas
    RN006           no hay salida sin entrada previa
    RN007 / RN008   la puntualidad se mide contra la tolerancia del horario
    RN009           toda marcación queda auditada
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import request
from sqlalchemy import and_, func, select

from ...comun import auditoria
from ...comun.consultas import Paginacion, aplicar_busqueda, aplicar_orden, paginar
from ...comun.errores import Conflicto, NoEncontrado, Prohibido, SolicitudInvalida
from ...comun.peticion import ContextoPeticion
from ...comun.respuestas import resultado_paginado
from ...comun.seguridad import UsuarioAutenticado
from ...comun.validaciones import exigir_identificador, validar_ubicacion_colegio
from ...comun.tiempo import (
    DIAS,
    ahora,
    clave_fecha,
    clave_hora,
    diferencia_minutos,
    dia_semana,
    iso,
    rango_dias,
    solo_fecha,
)
from ...extensiones import bd
from ...modelos import (
    ETIQUETA_ESTADO_EXCUSA,
    ETIQUETA_ESTADO_MARCACION,
    ETIQUETA_TIPO_MARCACION,
    AccionAuditoria,
    Docente,
    EstadoExcusa,
    EstadoMarcacion,
    EstadoRegistro,
    Excusa,
    Horario,
    Jornada,
    Marcacion,
    TipoMarcacion,
    Usuario,
    nuevo_id,
)
from ..configuracion import servicio as configuracion

MODULO = "Asistencia"
TOPE_EXPORTACION = 10000

ORDENABLES = {
    "registeredAt": Marcacion.registered_at,
    "date": Marcacion.date,
    "type": Marcacion.type,
    "status": Marcacion.status,
    "minutesDiff": Marcacion.minutes_diff,
}


def etiqueta_estado(estado: str) -> str:
    return ETIQUETA_ESTADO_MARCACION.get(estado, estado)


def etiqueta_tipo(tipo: str) -> str:
    return ETIQUETA_TIPO_MARCACION.get(tipo, tipo)


# ──────────────────────── Registro de marcación ─────────────────────


def registrar(
    tipo: TipoMarcacion,
    docente_id_pedido: str | None,
    notas: str | None,
    actor: UsuarioAutenticado,
    ctx: ContextoPeticion,
    latitude: float | None = None,
    longitude: float | None = None,
    location_accuracy: float | None = None,
    location_source: str | None = None,
) -> dict:
    """Registra una entrada o salida aplicando las reglas RN001 a RN009."""
    momento = ahora()
    zona = configuracion.texto(configuracion.CLAVES["ZONA_HORARIA"], "America/Bogota")

    docente_id = _resolver_docente(docente_id_pedido, actor)

    # RN001 / RN002 — el docente debe existir y estar activo
    docente = bd.session.execute(
        select(Docente).where(Docente.id == docente_id, Docente.deleted_at.is_(None))
    ).scalar_one_or_none()
    if docente is None:
        raise NoEncontrado("El docente no existe")

    if docente.status != EstadoRegistro.ACTIVO:
        raise Prohibido(
            "RN002 · El docente se encuentra inactivo y no puede registrar asistencia"
        )
    if docente.usuario and docente.usuario.status != EstadoRegistro.ACTIVO:
        raise Prohibido(
            "RN002 · La cuenta de usuario del docente está inactiva y no puede registrar asistencia"
        )

    # RN003 — el docente debe tener un horario aplicable
    horario = _resolver_horario(docente_id, momento, tipo, zona)

    # ── Validación de ubicación geográfica ──
    ubicacion = configuracion.ubicacion_colegio()
    if ubicacion["required"] and ubicacion["configured"]:
        geo = validar_ubicacion_colegio(
            latitud=latitude,
            longitud=longitude,
            school_lat=ubicacion["latitude"],
            school_lng=ubicacion["longitude"],
            radio_metros=ubicacion["radiusMeters"],
        )
        if not geo["dentro"]:
            raise Prohibido(
                f"Ubicación fuera del rango permitido. "
                f"Distancia: {geo['distancia_metros']:.0f}m — "
                f"Máximo permitido: {ubicacion['radiusMeters']}m"
            )

    # RN004 / RN005 / RN006 — secuencia válida de marcaciones
    fecha = clave_fecha(momento, zona)
    _validar_secuencia(docente_id, tipo, fecha)

    # RN007 / RN008 — evaluación de puntualidad
    estado, diferencia, hora_esperada = _evaluar_puntualidad(
        horario, tipo, clave_hora(momento, zona)
    )

    marcacion = Marcacion(
        id=nuevo_id(),
        teacher_id=docente_id,
        schedule_id=horario.id,
        type=tipo,
        status=estado,
        date=solo_fecha(fecha),
        registered_at=momento,
        expected_time=hora_esperada,
        minutes_diff=diferencia,
        latitude=latitude,
        longitude=longitude,
        location_accuracy=location_accuracy,
        location_source=location_source,
        ip_address=ctx.ip,
        user_agent=ctx.agente,
        device=ctx.dispositivo,
        notes=notas or None,
        registered_by_id=actor.id,
        created_at=momento,
        updated_at=momento,
    )
    bd.session.add(marcacion)
    bd.session.flush()

    # RN009 — auditoría
    accion = "Registró entrada" if tipo == TipoMarcacion.ENTRADA else "Registró salida"
    auditoria.anotar(
        AccionAuditoria.ASISTENCIA,
        MODULO,
        f"{accion} de {docente.first_name} {docente.last_name} ({docente.code}) — "
        f"{etiqueta_estado(estado.value)}",
        entidad_id=marcacion.id,
        detalle={
            "type": tipo.value,
            "status": estado.value,
            "expectedTime": hora_esperada,
            "minutesDiff": diferencia,
            "scheduleId": horario.id,
            "onBehalf": actor.docente_id != docente_id,
        },
        usuario=actor,
        ctx=ctx,
    )
    bd.session.commit()

    ubicacion_info = None
    if ubicacion["configured"]:
        geo_check = validar_ubicacion_colegio(
            latitud=latitude,
            longitud=longitude,
            school_lat=ubicacion["latitude"],
            school_lng=ubicacion["longitude"],
            radio_metros=ubicacion["radiusMeters"],
        )
        ubicacion_info = {
            "withinSchool": geo_check["dentro"],
            "distanceMeters": geo_check["distancia_metros"],
            "schoolRadius": ubicacion["radiusMeters"],
            "message": geo_check["mensaje"],
        }

    return {
        **serializar(marcacion),
        "message": _mensaje(tipo, estado, diferencia),
        "locationValidation": ubicacion_info,
    }


def _resolver_docente(pedido: str | None, actor: UsuarioAutenticado) -> str:
    """Un docente solo puede registrar su propia asistencia."""
    autoservicio = "attendance.create" not in actor.permisos and not actor.es_super_admin

    if autoservicio:
        if not actor.docente_id:
            raise Prohibido(
                "Su usuario no está vinculado a un docente. Contacte al administrador."
            )
        if pedido and pedido != actor.docente_id:
            raise Prohibido("Solo puede registrar su propia asistencia")
        return actor.docente_id

    docente_id = pedido or actor.docente_id
    if not docente_id:
        raise SolicitudInvalida("Debe indicar el docente a registrar")
    return docente_id


def _resolver_horario(
    docente_id: str, momento: datetime, tipo: TipoMarcacion, zona: str
) -> Horario:
    """
    RN003 — Horario aplicable a la marcación.

    Se elige el horario activo del día cuya hora de referencia esté más cerca
    del momento actual, dentro de la ventana de marcación configurada.
    """
    dia = dia_semana(momento, zona)

    horarios = list(
        bd.session.execute(
            select(Horario)
            .join(Jornada, Jornada.id == Horario.shift_id)
            .where(
                Horario.teacher_id == docente_id,
                Horario.deleted_at.is_(None),
                Horario.status == EstadoRegistro.ACTIVO,
                (Horario.day_of_week == dia) | (Horario.day_of_week.is_(None)),
                Jornada.status == EstadoRegistro.ACTIVO,
                Jornada.deleted_at.is_(None),
            )
        ).scalars()
    )

    if not horarios:
        raise SolicitudInvalida(
            f"RN003 · No tiene un horario activo asignado para hoy ({DIAS[dia]}). "
            "Contacte al administrador."
        )

    hora_actual = clave_hora(momento, zona)
    ventana = configuracion.numero(configuracion.CLAVES["VENTANA"], 180)

    def distancia(h: Horario) -> int:
        referencia = h.check_in_time if tipo == TipoMarcacion.ENTRADA else h.check_out_time
        return abs(diferencia_minutos(hora_actual, referencia))

    mas_cercano = min(horarios, key=distancia)

    if distancia(mas_cercano) > ventana:
        referencia = (
            mas_cercano.check_in_time
            if tipo == TipoMarcacion.ENTRADA
            else mas_cercano.check_out_time
        )
        raise SolicitudInvalida(
            f"La marcación está fuera de la ventana permitida. Su horario más cercano es a "
            f"las {referencia} y la ventana configurada es de {ventana} minutos."
        )

    return mas_cercano


def _validar_secuencia(docente_id: str, tipo: TipoMarcacion, fecha: str) -> None:
    """RN004, RN005 y RN006 — coherencia de la secuencia del día."""
    ultima = bd.session.execute(
        select(Marcacion)
        .where(
            Marcacion.teacher_id == docente_id,
            Marcacion.date == solo_fecha(fecha),
            Marcacion.deleted_at.is_(None),
        )
        .order_by(Marcacion.registered_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if tipo == TipoMarcacion.ENTRADA:
        # RN004 — no se admiten dos entradas consecutivas
        if ultima is not None and ultima.type == TipoMarcacion.ENTRADA:
            raise Conflicto(
                "RN004 · Ya registró su entrada. Debe registrar la salida antes de una nueva entrada."
            )
        return

    # RN006 — no puede haber salida sin una entrada previa
    if ultima is None:
        raise Conflicto("RN006 · No puede registrar la salida sin haber registrado la entrada.")
    # RN005 — no se admiten dos salidas consecutivas
    if ultima.type == TipoMarcacion.SALIDA:
        raise Conflicto(
            "RN005 · Ya registró su salida. Debe registrar una nueva entrada primero."
        )


def _evaluar_puntualidad(
    horario: Horario, tipo: TipoMarcacion, hora_actual: str
) -> tuple[EstadoMarcacion, int, str]:
    """
    RN007 — si supera la tolerancia se marca TARDE.
    RN008 — dentro del horario, incluida la tolerancia, se marca PUNTUAL.
    """
    esperada = (
        horario.check_in_time if tipo == TipoMarcacion.ENTRADA else horario.check_out_time
    )
    diferencia = diferencia_minutos(hora_actual, esperada)

    if tipo == TipoMarcacion.ENTRADA:
        estado = (
            EstadoMarcacion.TARDE
            if diferencia > horario.tolerance_minutes
            else EstadoMarcacion.PUNTUAL
        )
        return estado, diferencia, esperada

    # Salida anticipada: es informativa, no bloquea el registro
    estado = (
        EstadoMarcacion.SALIDA_ANTICIPADA
        if diferencia < -horario.tolerance_minutes
        else EstadoMarcacion.PUNTUAL
    )
    return estado, diferencia, esperada


def _mensaje(tipo: TipoMarcacion, estado: EstadoMarcacion, diferencia: int) -> str:
    accion = "Entrada registrada" if tipo == TipoMarcacion.ENTRADA else "Salida registrada"

    if estado == EstadoMarcacion.TARDE:
        return f"{accion} con {diferencia} minuto(s) de retraso."
    if estado == EstadoMarcacion.SALIDA_ANTICIPADA:
        return f"{accion} con {abs(diferencia)} minuto(s) de anticipación."
    return f"{accion} a tiempo. ¡Gracias!"


# ─────────────────────────────── Consultas ──────────────────────────


def serializar(fila: Marcacion) -> dict:
    docente, horario = fila.docente, fila.horario
    excusa = getattr(fila, "excusa_vinculada", None)
    return {
        "id": fila.id,
        "teacherId": fila.teacher_id,
        "scheduleId": fila.schedule_id,
        "type": fila.type.value,
        "status": fila.status.value,
        "date": iso(fila.date),
        "registeredAt": iso(fila.registered_at),
        "expectedTime": fila.expected_time,
        "minutesDiff": fila.minutes_diff,
        "latitude": fila.latitude,
        "longitude": fila.longitude,
        "locationAccuracy": fila.location_accuracy,
        "locationSource": fila.location_source,
        "ipAddress": fila.ip_address,
        "userAgent": fila.user_agent,
        "device": fila.device,
        "notes": fila.notes,
        "registeredById": fila.registered_by_id,
        "createdAt": iso(fila.created_at),
        "updatedAt": iso(fila.updated_at),
        "deletedAt": iso(fila.deleted_at),
        "teacher": {
            "id": docente.id,
            "code": docente.code,
            "firstName": docente.first_name,
            "lastName": docente.last_name,
            "document": docente.document,
        },
        "schedule": (
            {
                "id": horario.id,
                "checkInTime": horario.check_in_time,
                "checkOutTime": horario.check_out_time,
                "toleranceMinutes": horario.tolerance_minutes,
                "dayOfWeek": horario.day_of_week,
                "shift": {"id": horario.jornada.id, "name": horario.jornada.name},
            }
            if horario
            else None
        ),
        "excuse": (
            {
                "id": excusa.id,
                "status": excusa.status.value,
                "statusLabel": ETIQUETA_ESTADO_EXCUSA.get(excusa.status.value),
            }
            if excusa
            else None
        ),
    }


def _consulta(paginacion: Paginacion):
    consulta = (
        select(Marcacion)
        .join(Docente, Docente.id == Marcacion.teacher_id)
        .where(Marcacion.deleted_at.is_(None))
    )

    docente_id = request.args.get("teacherId")
    if docente_id:
        consulta = consulta.where(Marcacion.teacher_id == docente_id)

    tipo = request.args.get("type")
    if tipo in ("CHECK_IN", "CHECK_OUT"):
        consulta = consulta.where(Marcacion.type == TipoMarcacion(tipo))

    estado = request.args.get("status")
    if estado in ("ON_TIME", "LATE", "EARLY_DEPARTURE"):
        consulta = consulta.where(Marcacion.status == EstadoMarcacion(estado))

    jornada_id = request.args.get("shiftId")
    if jornada_id:
        consulta = consulta.where(
            Marcacion.schedule_id.in_(
                select(Horario.id).where(Horario.shift_id == jornada_id)
            )
        )

    desde, hasta = rango_dias(request.args.get("dateFrom"), request.args.get("dateTo"))
    if desde:
        consulta = consulta.where(Marcacion.date >= desde)
    if hasta:
        consulta = consulta.where(Marcacion.date <= hasta)

    consulta = aplicar_busqueda(
        consulta,
        paginacion.busqueda,
        (Docente.first_name, Docente.last_name, Docente.code, Docente.document),
    )
    return aplicar_orden(consulta, paginacion, ORDENABLES)


def listar() -> dict:
    paginacion = Paginacion("registeredAt")
    elementos, total = paginar(_consulta(paginacion), paginacion)
    return resultado_paginado(
        [serializar(e) for e in elementos], total, paginacion.pagina, paginacion.limite
    )


def obtener(identificador: str) -> dict:
    exigir_identificador(identificador)
    fila = bd.session.execute(
        select(Marcacion).where(
            Marcacion.id == identificador, Marcacion.deleted_at.is_(None)
        )
    ).unique().scalar_one_or_none()
    if fila is None:
        raise NoEncontrado("El registro de asistencia no existe")
    return serializar(fila)


def para_exportar() -> list[Marcacion]:
    paginacion = Paginacion("registeredAt")
    return list(
        bd.session.execute(_consulta(paginacion).limit(TOPE_EXPORTACION)).scalars().unique()
    )


# ────────────────────────────── Eliminación ─────────────────────────


def borrar_seleccionadas(
    ids: list[str], motivo: str | None, actor: UsuarioAutenticado, ctx: ContextoPeticion
) -> dict:
    """
    Borrado lógico de las marcaciones seleccionadas.

    La fila permanece con su marca de baja, de modo que la auditoría sigue
    siendo verificable: se puede demostrar qué se eliminó y quién lo hizo.
    Reservado al SUPER_ADMIN.
    """
    filas = list(
        bd.session.execute(
            select(Marcacion).where(
                Marcacion.id.in_(ids), Marcacion.deleted_at.is_(None)
            )
        ).scalars().unique()
    )

    if not filas:
        raise NoEncontrado(
            "Las marcaciones seleccionadas no existen o ya fueron eliminadas"
        )

    zona = configuracion.texto(configuracion.CLAVES["ZONA_HORARIA"], "America/Bogota")
    momento = datetime.now(timezone.utc)

    # Se conserva el detalle de cada marcación: tras el borrado, la bitácora es
    # el único sitio donde queda constancia legible de lo eliminado.
    detalle = [
        {
            "id": f.id,
            "docente": f"{f.docente.first_name} {f.docente.last_name}",
            "codigo": f.docente.code,
            "fecha": clave_fecha(f.date, zona),
            "hora": clave_hora(f.registered_at, zona),
            "tipo": etiqueta_tipo(f.type.value),
            "estado": etiqueta_estado(f.status.value),
            "jornada": f.horario.jornada.name if f.horario else None,
        }
        for f in filas
    ]

    for fila in filas:
        fila.deleted_at = momento

    auditoria.anotar(
        AccionAuditoria.ELIMINAR,
        MODULO,
        f"Eliminó {len(filas)} marcación(es) de asistencia"
        + (f" · Motivo: {motivo}" if motivo else ""),
        entidad_id=filas[0].id if len(filas) == 1 else None,
        detalle={
            "cantidad": len(filas),
            "motivo": motivo,
            "solicitadas": len(ids),
            "marcaciones": detalle,
        },
        usuario=actor,
        ctx=ctx,
    )
    bd.session.commit()

    omitidas = len(ids) - len(filas)
    return {
        "deleted": len(filas),
        "message": f"Se eliminaron {len(filas)} marcación(es)."
        + (f" {omitidas} ya no estaban disponibles." if omitidas > 0 else ""),
    }


def borrar_por_docente(
    docentes_ids: list[str],
    desde: str | None,
    hasta: str | None,
    motivo: str | None,
    actor: UsuarioAutenticado,
    ctx: ContextoPeticion,
) -> dict:
    """Elimina todas las marcaciones de los docentes indicados en un periodo."""
    inicio, fin = rango_dias(desde, hasta)

    consulta = select(Marcacion).where(
        Marcacion.deleted_at.is_(None), Marcacion.teacher_id.in_(docentes_ids)
    )
    if inicio:
        consulta = consulta.where(Marcacion.date >= inicio)
    if fin:
        consulta = consulta.where(Marcacion.date <= fin)

    filas = list(bd.session.execute(consulta).scalars().unique())
    if not filas:
        raise NoEncontrado(
            "Los docentes seleccionados no tienen marcaciones en el periodo indicado"
        )

    docentes = list(
        bd.session.execute(select(Docente).where(Docente.id.in_(docentes_ids))).scalars()
    )

    momento = datetime.now(timezone.utc)
    for fila in filas:
        fila.deleted_at = momento

    por_docente = [
        {
            "docente": f"{d.first_name} {d.last_name}",
            "codigo": d.code,
            "eliminadas": sum(1 for f in filas if f.teacher_id == d.id),
        }
        for d in docentes
    ]

    if desde and hasta:
        periodo = f"{desde} a {hasta}"
    elif desde:
        periodo = f"desde {desde}"
    elif hasta:
        periodo = f"hasta {hasta}"
    else:
        periodo = "periodo completo"

    auditoria.anotar(
        AccionAuditoria.ELIMINAR,
        MODULO,
        f"Eliminó {len(filas)} marcación(es) de {len(docentes)} docente(s) — {periodo}"
        + (f" · Motivo: {motivo}" if motivo else ""),
        detalle={
            "cantidad": len(filas),
            "periodo": periodo,
            "motivo": motivo,
            "docentes": por_docente,
        },
        usuario=actor,
        ctx=ctx,
    )
    bd.session.commit()

    return {
        "deleted": len(filas),
        "message": f"Se eliminaron {len(filas)} marcación(es) de {len(docentes)} docente(s).",
    }


# ──────────────────────────── Panel del docente ─────────────────────


def estado_propio(actor: UsuarioAutenticado) -> dict:
    """Qué puede registrar ahora mismo el docente autenticado."""
    if not actor.docente_id:
        raise Prohibido("Su usuario no está vinculado a un docente")

    zona = configuracion.texto(configuracion.CLAVES["ZONA_HORARIA"], "America/Bogota")
    momento = ahora()
    fecha = clave_fecha(momento, zona)
    dia = dia_semana(momento, zona)

    docente = bd.session.execute(
        select(Docente).where(Docente.id == actor.docente_id, Docente.deleted_at.is_(None))
    ).scalar_one_or_none()

    del_dia = list(
        bd.session.execute(
            select(Marcacion)
            .where(
                Marcacion.teacher_id == actor.docente_id,
                Marcacion.date == solo_fecha(fecha),
                Marcacion.deleted_at.is_(None),
            )
            .order_by(Marcacion.registered_at.asc())
        ).scalars().unique()
    )

    horarios = list(
        bd.session.execute(
            select(Horario)
            .where(
                Horario.teacher_id == actor.docente_id,
                Horario.deleted_at.is_(None),
                Horario.status == EstadoRegistro.ACTIVO,
                (Horario.day_of_week == dia) | (Horario.day_of_week.is_(None)),
            )
            .order_by(Horario.check_in_time.asc())
        ).scalars().unique()
    )

    ultima = del_dia[-1] if del_dia else None
    tiene_horario = bool(horarios)

    return {
        "teacher": (
            {
                "id": docente.id,
                "code": docente.code,
                "firstName": docente.first_name,
                "lastName": docente.last_name,
                "status": docente.status.value,
            }
            if docente
            else None
        ),
        "date": fecha,
        "dayName": DIAS[dia],
        "currentTime": clave_hora(momento, zona),
        "timezone": zona,
        "schedules": [
            {
                "id": h.id,
                "dayOfWeek": h.day_of_week,
                "checkInTime": h.check_in_time,
                "checkOutTime": h.check_out_time,
                "toleranceMinutes": h.tolerance_minutes,
                "status": h.status.value,
                "shift": {"id": h.jornada.id, "name": h.jornada.name},
            }
            for h in horarios
        ],
        "todayRecords": [serializar(m) for m in del_dia],
        "lastRecord": serializar(ultima) if ultima else None,
        "canCheckIn": tiene_horario and (ultima is None or ultima.type != TipoMarcacion.ENTRADA),
        "canCheckOut": tiene_horario and ultima is not None and ultima.type == TipoMarcacion.ENTRADA,
        "blockedReason": (
            None
            if tiene_horario
            else f"RN003 · No tiene un horario activo asignado para hoy ({DIAS[dia]})"
        ),
    }


def historial_propio(actor: UsuarioAutenticado) -> dict:
    """
    Historial del docente autenticado, con sus filtros y un resumen del periodo.

    Los filtros de mes y de estado los aplica `_consulta`, que ya sabe leerlos.
    El resumen se calcula sobre todo lo filtrado, no sobre la página visible: de
    lo contrario el docente vería "2 tardanzas" un día y "17" al cambiar de
    página, y ninguna de las dos cifras quadraría con la tabla.
    """
    if not actor.docente_id:
        raise Prohibido("Su usuario no está vinculado a un docente")

    paginacion = Paginacion("registeredAt")
    consulta = (
        _consulta(paginacion)
        .where(Marcacion.teacher_id == actor.docente_id)
        .outerjoin(
            Excusa,
            and_(
                Excusa.attendance_id == Marcacion.id,
                Excusa.deleted_at.is_(None),
            ),
        )
        .options(*[])
    )
    # Traemos la excusa vinculada para mostrar el botón/estado sin consultas
    # extra: una marcación solo puede tener una excusa ligada por attendance_id.
    consulta = consulta.add_columns(Excusa).distinct()
    elementos = paginar(consulta, paginacion)
    filas = elementos[0]
    total = elementos[1]

    items = []
    for fila in filas:
        if isinstance(fila, tuple):
            marcacion = fila[0]
            excusa = fila[1]
        else:
            marcacion = fila
            excusa = None
        marcacion.excusa_vinculada = excusa
        items.append(serializar(marcacion))

    return resultado_paginado(
        items,
        total,
        paginacion.pagina,
        paginacion.limite,
        extra={"resumen": resumen_propio(actor, _filtros_de_consulta())},
    )


def _filtros_de_consulta() -> dict:
    """Los mismos filtros que se aplicaron, para resumirlos sin volver a leerlos."""
    tipo = request.args.get("type")
    estado = request.args.get("status")
    return {
        "type": tipo if tipo in ("CHECK_IN", "CHECK_OUT") else None,
        "status": estado if estado in ("ON_TIME", "LATE", "EARLY_DEPARTURE") else None,
        "dateFrom": request.args.get("dateFrom") or None,
        "dateTo": request.args.get("dateTo") or None,
    }


def resumen_propio(actor: UsuarioAutenticado, filtros: dict | None = None) -> dict:
    """
    Cifras del docente sobre el periodo que se está mirando.

    Sin filtros cuenta todo su historial. Con ellos, el periodo filtrado: así
    el detalle de un mes y el resumen de la pantalla de ese mes cuentan lo mismo.
    """
    if not actor.docente_id:
        raise Prohibido("Su usuario no está vinculado a un docente")

    filtros = filtros or {}
    consulta = select(
        func.count(Marcacion.id),
        func.count(Marcacion.id).filter(Marcacion.type == TipoMarcacion.ENTRADA),
        func.count(Marcacion.id).filter(Marcacion.type == TipoMarcacion.SALIDA),
        func.count(Marcacion.id).filter(Marcacion.status == EstadoMarcacion.PUNTUAL),
        func.count(Marcacion.id).filter(Marcacion.status == EstadoMarcacion.TARDE),
        func.count(Marcacion.id).filter(
            Marcacion.status == EstadoMarcacion.SALIDA_ANTICIPADA
        ),
        func.coalesce(func.sum(Marcacion.minutes_diff), 0),
    ).where(Marcacion.teacher_id == actor.docente_id, Marcacion.deleted_at.is_(None))

    if filtros.get("type") in ("CHECK_IN", "CHECK_OUT"):
        consulta = consulta.where(Marcacion.type == TipoMarcacion(filtros["type"]))
    if filtros.get("status") in ("ON_TIME", "LATE", "EARLY_DEPARTURE"):
        consulta = consulta.where(Marcacion.status == EstadoMarcacion(filtros["status"]))
    if filtros.get("dateFrom"):
        consulta = consulta.where(Marcacion.date >= solo_fecha(filtros["dateFrom"]))
    if filtros.get("dateTo"):
        consulta = consulta.where(Marcacion.date <= solo_fecha(filtros["dateTo"]))

    (
        total,
        entradas,
        salidas,
        puntuales,
        tardanzas,
        anticipadas,
        minutos,
    ) = bd.session.execute(consulta).one()

    # El porcentaje de puntualidad se mide sobre las entradas: una salida nunca
    # es "puntual" ni "tarde" en el mismo sentido que una entrada.
    base = puntos = (puntuales or 0) + (tardanzas or 0)
    pct_puntualidad = round((puntuales or 0) * 100 / base, 1) if base else 0.0

    # Los días con marcación cuentan dentro del mismo periodo que el resto de
    # cifras. Si se dejaran sin filtrar, el detalle de un mes mostraría, por
    # ejemplo, 22 días trabajados junto a las entradas de ese mes: dos números
    # que describen periodos distintos en la misma tarjeta.
    dias_consulta = select(func.count(func.distinct(Marcacion.date))).where(
        Marcacion.teacher_id == actor.docente_id, Marcacion.deleted_at.is_(None)
    )
    if filtros.get("dateFrom"):
        dias_consulta = dias_consulta.where(Marcacion.date >= solo_fecha(filtros["dateFrom"]))
    if filtros.get("dateTo"):
        dias_consulta = dias_consulta.where(Marcacion.date <= solo_fecha(filtros["dateTo"]))

    dias = bd.session.execute(dias_consulta).scalar_one()

    return {
        "total": total or 0,
        "checkIns": entradas or 0,
        "checkOuts": salidas or 0,
        "onTime": puntuales or 0,
        "late": tardanzas or 0,
        "earlyDeparture": anticipadas or 0,
        "punctualityRate": pct_puntualidad,
        "workedDays": dias or 0,
        "averageMinutesDiff": round((minutos or 0) / total, 1) if total else 0.0,
    }


def panel_propio(actor: UsuarioAutenticado) -> dict:
    """
    Dashboard del docente: sus propias cifras, no las de la institución.

    Deliberadamente no reutiliza `reportes.panel()`: aquel muestra el total de
    docentes y las tardanzas de todos, que es información de otra persona. Aquí
    solo entran los datos del docente autenticado, más lo que puede marcar
    ahora mismo para que la pantalla sirva también como acceso a la marcación.
    """
    if not actor.docente_id:
        raise Prohibido("Su usuario no está vinculado a un docente")

    zona = configuracion.texto(configuracion.CLAVES["ZONA_HORARIA"], "America/Bogota")
    momento = ahora()
    fecha = clave_fecha(momento, zona)
    hoy = solo_fecha(fecha)

    docente = bd.session.execute(
        select(Docente).where(Docente.id == actor.docente_id, Docente.deleted_at.is_(None))
    ).scalar_one_or_none()

    resumen = resumen_propio(actor)

    # Últimas marcaciones y las del mes en curso
    recientes = list(
        bd.session.execute(
            select(Marcacion)
            .where(Marcacion.teacher_id == actor.docente_id, Marcacion.deleted_at.is_(None))
            .order_by(Marcacion.registered_at.desc())
            .limit(8)
        ).scalars().unique()
    )

    del_mes = bd.session.execute(
        select(
            func.count(Marcacion.id),
            func.count(Marcacion.id).filter(Marcacion.status == EstadoMarcacion.TARDE),
        ).where(
            Marcacion.teacher_id == actor.docente_id,
            Marcacion.date >= hoy.replace(day=1),
            Marcacion.deleted_at.is_(None),
        )
    ).one()

    # Serie de las últimas 8 semanas, para la gráfica de barras
    serie = []
    for semanas in range(7, -1, -1):
        desde_mes = hoy.replace(day=1) - timedelta(days=7 * semanas)
        hasta_mes = desde_mes + timedelta(days=6)
        filas = bd.session.execute(
            select(
                func.count(Marcacion.id),
                func.count(Marcacion.id).filter(Marcacion.status == EstadoMarcacion.PUNTUAL),
                func.count(Marcacion.id).filter(Marcacion.status == EstadoMarcacion.TARDE),
            ).where(
                Marcacion.teacher_id == actor.docente_id,
                Marcacion.date >= desde_mes,
                Marcacion.date <= hasta_mes,
                Marcacion.deleted_at.is_(None),
            )
        ).one()
        serie.append(
            {
                "week": f"{desde_mes.strftime('%d/%m')}",
                "total": filas[0] or 0,
                "onTime": filas[1] or 0,
                "late": filas[2] or 0,
            }
        )

    # Días del mes que ya pasaron y en los que el docente no registró entrada
    dias_transcurridos = hoy.day
    entradas_mes = del_mes[0] or 0
    marcaciones_hoy = bd.session.execute(
        select(func.count(Marcacion.id)).where(
            Marcacion.teacher_id == actor.docente_id,
            Marcacion.date == hoy,
            Marcacion.deleted_at.is_(None),
        )
    ).scalar_one()

    return {
        "teacher": (
            {
                "id": docente.id,
                "code": docente.code,
                "firstName": docente.first_name,
                "lastName": docente.last_name,
                "document": docente.document,
                "status": docente.status.value,
            }
            if docente
            else None
        ),
        "date": fecha,
        "summary": resumen,
        "month": {
            "records": entradas_mes,
            "late": del_mes[1] or 0,
            "elapsedDays": dias_transcurridos,
        },
        "week": serie,
        "recent": [serializar(m) for m in recientes],
        "today": {"records": marcaciones_hoy or 0},
        # El estado de marcación se reutiliza tal cual: la misma lógica que
        # controla la pantalla de escaneo decide qué botón se muestra aquí.
        "estado": estado_propio(actor),
    }
