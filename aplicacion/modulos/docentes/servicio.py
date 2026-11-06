"""
Servicio de docentes.

Traducción de `modules/teachers/teachers.service.ts`. Incluye la gestión de la
fotografía y el vínculo con las asignaturas que dicta.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from flask import request
from sqlalchemy import delete, func, select
from werkzeug.datastructures import FileStorage

from flask import current_app

from ...comun import auditoria, codigos, subidas
from ...comun.consultas import Paginacion
from ...comun.crud import ServicioCRUD
from ...comun.errores import SolicitudInvalida
from ...comun.peticion import ContextoPeticion
from ...comun.seguridad import UsuarioAutenticado
from ...comun.tiempo import iso
from ...comun.validaciones import exigir_identificador
from ...extensiones import bd
from ...modelos import (
    ETIQUETA_NIVEL_EDUCATIVO,
    AccionAuditoria,
    Asignatura,
    Curso,
    Docente,
    DocenteAsignatura,
    DocenteCurso,
    EstadoRegistro,
    Grado,
    Horario,
    Marcacion,
    Usuario,
    nuevo_id,
)


def _contar_horarios(docente_id: str, solo_activos: bool = False) -> int:
    consulta = select(func.count()).select_from(Horario).where(
        Horario.teacher_id == docente_id, Horario.deleted_at.is_(None)
    )
    if solo_activos:
        consulta = consulta.where(Horario.status == EstadoRegistro.ACTIVO)
    return bd.session.execute(consulta).scalar_one()


def _contar_marcaciones(docente_id: str) -> int:
    return bd.session.execute(
        select(func.count())
        .select_from(Marcacion)
        .where(Marcacion.teacher_id == docente_id, Marcacion.deleted_at.is_(None))
    ).scalar_one()


def _asignaturas_de(docente_id: str) -> list[dict]:
    filas = bd.session.execute(
        select(Asignatura)
        .join(DocenteAsignatura, DocenteAsignatura.subject_id == Asignatura.id)
        .where(DocenteAsignatura.teacher_id == docente_id)
        .order_by(DocenteAsignatura.created_at.asc())
    ).scalars()
    return [{"id": a.id, "code": a.code, "name": a.name, "color": a.color} for a in filas]


def _cursos_de(docente_id: str) -> list[dict]:
    """Cursos que atiende el docente, en el orden de la escalera educativa."""
    filas = bd.session.execute(
        select(Curso)
        .join(DocenteCurso, DocenteCurso.course_id == Curso.id)
        .join(Grado, Grado.id == Curso.grade_id)
        .where(DocenteCurso.teacher_id == docente_id, Curso.deleted_at.is_(None))
        .order_by(Grado.position.asc(), Curso.letter.asc())
    ).scalars()
    return [
        {
            "id": c.id,
            "name": c.name,
            "letter": c.letter,
            "gradeId": c.grade_id,
            "gradeName": c.grado.name,
            "level": c.grado.level.value,
            "levelName": ETIQUETA_NIVEL_EDUCATIVO.get(
                c.grado.level.value, c.grado.level.value
            ),
            "isHomeroom": c.homeroom_teacher_id == docente_id,
        }
        for c in filas
    ]


class ServicioDocentes(ServicioCRUD):
    modelo = Docente
    modulo = "Docentes"
    articulo = "el"
    sustantivo = "docente"
    campo_etiqueta = "code"
    tope_exportacion = 5000

    ordenables = {
        "createdAt": Docente.created_at,
        "code": Docente.code,
        "firstName": Docente.first_name,
        "lastName": Docente.last_name,
        "document": Docente.document,
        "email": Docente.email,
        "status": Docente.status,
    }
    buscables = (
        Docente.code,
        Docente.first_name,
        Docente.last_name,
        Docente.document,
        Docente.email,
        Docente.phone,
    )

    # ── Consultas ────────────────────────────────────────────────────

    @classmethod
    def aplicar_filtros(cls, consulta, paginacion: Paginacion):
        consulta = super().aplicar_filtros(consulta, paginacion)

        jornada_id = request.args.get("shiftId")
        if jornada_id:
            consulta = consulta.where(
                Docente.id.in_(
                    select(Horario.teacher_id).where(
                        Horario.shift_id == jornada_id, Horario.deleted_at.is_(None)
                    )
                )
            )

        asignatura_id = request.args.get("subjectId")
        if asignatura_id:
            consulta = consulta.where(
                Docente.id.in_(
                    select(DocenteAsignatura.teacher_id).where(
                        DocenteAsignatura.subject_id == asignatura_id
                    )
                )
            )

        curso_id = request.args.get("courseId")
        if curso_id:
            consulta = consulta.where(
                Docente.id.in_(
                    select(DocenteCurso.teacher_id).where(DocenteCurso.course_id == curso_id)
                )
            )

        grado_id = request.args.get("gradeId")
        if grado_id:
            consulta = consulta.where(
                Docente.id.in_(
                    select(DocenteCurso.teacher_id)
                    .join(Curso, Curso.id == DocenteCurso.course_id)
                    .where(Curso.grade_id == grado_id, Curso.deleted_at.is_(None))
                )
            )
        return consulta

    @classmethod
    def serializar(cls, fila: Docente) -> dict:
        usuario = fila.usuario
        return {
            **cls.campos_comunes(fila),
            "code": fila.code,
            "firstName": fila.first_name,
            "lastName": fila.last_name,
            "document": fila.document,
            "email": fila.email,
            "phone": fila.phone,
            "photoUrl": fila.photo_url,
            "userId": fila.user_id,
            "user": (
                {
                    "id": usuario.id,
                    "email": usuario.email,
                    "status": usuario.status.value,
                    "role": {"name": usuario.rol.name},
                }
                if usuario
                else None
            ),
            # La relación muchos a muchos se aplana: el cliente recibe las
            # asignaturas directamente, sin la tabla puente.
            "subjects": _asignaturas_de(fila.id),
            # Un docente puede pertenecer a uno o varios cursos: los de
            # asignatura y, si es director de grupo, el suyo propio.
            "courses": _cursos_de(fila.id),
            "_count": {
                "schedules": _contar_horarios(fila.id),
                "attendances": _contar_marcaciones(fila.id),
            },
        }

    @classmethod
    def obtener(cls, identificador: str) -> dict:
        """El detalle añade los horarios vigentes del docente."""
        fila = cls.buscar(identificador)

        horarios = bd.session.execute(
            select(Horario)
            .where(Horario.teacher_id == identificador, Horario.deleted_at.is_(None))
            .order_by(Horario.day_of_week.asc())
        ).scalars()

        return {
            **cls.serializar(fila),
            "schedules": [
                {
                    "id": h.id,
                    "teacherId": h.teacher_id,
                    "shiftId": h.shift_id,
                    "subjectId": h.subject_id,
                    "dayOfWeek": h.day_of_week,
                    "checkInTime": h.check_in_time,
                    "checkOutTime": h.check_out_time,
                    "toleranceMinutes": h.tolerance_minutes,
                    "status": h.status.value,
                    "createdAt": iso(h.created_at),
                    "updatedAt": iso(h.updated_at),
                    "deletedAt": iso(h.deleted_at),
                    "shift": {"id": h.jornada.id, "name": h.jornada.name},
                    "subject": (
                        {
                            "id": h.asignatura.id,
                            "code": h.asignatura.code,
                            "name": h.asignatura.name,
                        }
                        if h.asignatura
                        else None
                    ),
                }
                for h in horarios
            ],
        }

    @classmethod
    def opciones(cls) -> list[dict]:
        filas = bd.session.execute(
            select(Docente)
            .where(Docente.deleted_at.is_(None), Docente.status == EstadoRegistro.ACTIVO)
            .order_by(Docente.last_name.asc(), Docente.first_name.asc())
        ).scalars()
        return [
            {"id": f.id, "code": f.code, "firstName": f.first_name, "lastName": f.last_name}
            for f in filas
        ]

    @classmethod
    def sugerir_codigo(cls) -> dict:
        """Siguiente código disponible con el formato DOC-0000."""
        return {"code": codigos.siguiente(Docente.code, "DOC-", 4)}

    # ── Mutaciones ───────────────────────────────────────────────────

    @classmethod
    def construir(cls, datos: dict) -> Docente:
        if not datos.get("userId"):
            faltantes = [k for k in ("firstName", "lastName", "document", "email") if not datos.get(k)]
            if faltantes:
                raise SolicitudInvalida(
                    "Debe vincular una cuenta de usuario o completar nombres, apellidos, documento y correo"
                )
        return Docente(
            id=nuevo_id(),
            code=datos["code"],
            first_name=datos.get("firstName") or "",
            last_name=datos.get("lastName") or "",
            document=datos.get("document") or "",
            email=datos.get("email") or "",
            phone=datos.get("phone") or None,
            user_id=datos.get("userId") or None,
            status=datos.get("status") or EstadoRegistro.ACTIVO,
        )

    @classmethod
    def gancho_despues_de_crear(cls, fila: Docente, datos: dict) -> None:
        for asignatura_id in dict.fromkeys(datos.get("subjectIds") or []):
            bd.session.add(
                DocenteAsignatura(
                    teacher_id=fila.id,
                    subject_id=asignatura_id,
                    created_at=datetime.now(timezone.utc),
                )
            )
        for curso_id in dict.fromkeys(datos.get("courseIds") or []):
            bd.session.add(
                DocenteCurso(
                    teacher_id=fila.id,
                    course_id=curso_id,
                    created_at=datetime.now(timezone.utc),
                )
            )

    @classmethod
    def aplicar_cambios(cls, fila: Docente, datos: dict) -> None:
        if datos.get("code") is not None:
            fila.code = datos["code"]
        if datos.get("firstName") is not None:
            fila.first_name = datos["firstName"]
        if datos.get("lastName") is not None:
            fila.last_name = datos["lastName"]
        if datos.get("document") is not None:
            fila.document = datos["document"]
        if datos.get("email") is not None:
            fila.email = datos["email"]
        if "phone" in datos:
            fila.phone = datos["phone"] or None
        if "userId" in datos:
            fila.user_id = datos["userId"] or None
        if datos.get("status") is not None:
            fila.status = datos["status"]

    @classmethod
    def liberar_claves_unicas(cls, fila: Docente) -> None:
        marca = int(time.time() * 1000)
        fila.code = f"{fila.code}.DEL.{marca}"[:40]
        fila.document = f"{fila.document}.DEL.{marca}"[:40]
        fila.email = f"{fila.email}.DEL.{marca}"[:200]

    # ── Reglas propias ───────────────────────────────────────────────

    @classmethod
    def _usuario_disponible(cls, usuario_id: str, excluir: str | None = None) -> None:
        usuario = bd.session.execute(
            select(Usuario).where(Usuario.id == usuario_id, Usuario.deleted_at.is_(None))
        ).scalar_one_or_none()
        if usuario is None:
            raise SolicitudInvalida("La cuenta de usuario seleccionada no existe")

        consulta = select(Docente.code).where(
            Docente.user_id == usuario_id, Docente.deleted_at.is_(None)
        )
        if excluir:
            consulta = consulta.where(Docente.id != excluir)
        ocupada = bd.session.execute(consulta).scalar_one_or_none()
        if ocupada:
            raise SolicitudInvalida(
                f"Esa cuenta ya está vinculada al docente {ocupada}"
            )

    @classmethod
    def gancho_antes_de_crear(cls, datos: dict) -> None:
        if datos.get("userId"):
            usuario = cls._usuario_disponible(datos["userId"])
            cls._aplicar_datos_usuario(datos, usuario)
        faltantes = [
            k for k in ("firstName", "lastName", "document", "email") if not datos.get(k)
        ]
        if faltantes:
            raise SolicitudInvalida(
                "Debe vincular una cuenta de usuario o completar nombres, apellidos, documento y correo"
            )
        cls.exige_unico(Docente.code, datos["code"], "Ya existe un docente con ese código")
        cls.exige_unico(
            Docente.document, datos["document"], "Ya existe un docente con ese documento"
        )
        cls.exige_unico(Docente.email, datos["email"], "Ya existe un docente con ese correo")

    @classmethod
    def gancho_antes_de_actualizar(cls, fila: Docente, datos: dict) -> None:
        if datos.get("userId"):
            usuario = cls._usuario_disponible(datos["userId"], excluir=fila.id)
            cls._aplicar_datos_usuario(datos, usuario)
        elif "userId" in datos and datos.get("userId") in (None, ""):
            datos["userId"] = None
        if datos.get("code") and datos["code"] != fila.code:
            cls.exige_unico(
                Docente.code, datos["code"], "Ya existe un docente con ese código", excluir=fila.id
            )
        if datos.get("document") and datos["document"] != fila.document:
            cls.exige_unico(
                Docente.document,
                datos["document"],
                "Ya existe un docente con ese documento",
                excluir=fila.id,
            )
        if datos.get("email") and datos["email"].lower() != fila.email.lower():
            cls.exige_unico(
                Docente.email,
                datos["email"],
                "Ya existe un docente con ese correo",
                excluir=fila.id,
            )

    @classmethod
    def gancho_impide_inactivar(cls, fila: Docente) -> str | None:
        activos = _contar_horarios(fila.id, solo_activos=True)
        if activos:
            return f"No es posible inactivar el docente: tiene {activos} horario(s) activo(s)"
        return None

    @classmethod
    def gancho_impide_eliminar(cls, fila: Docente) -> str | None:
        marcaciones = _contar_marcaciones(fila.id)
        if marcaciones:
            return (
                f"No es posible eliminar el docente: tiene {marcaciones} marcación(es) "
                "registrada(s). La asistencia es evidencia y no se descarta."
            )

        dirigidos = bd.session.execute(
            select(Curso.name)
            .where(Curso.homeroom_teacher_id == fila.id, Curso.deleted_at.is_(None))
            .order_by(Curso.name.asc())
        ).scalars().all()
        if dirigidos:
            return (
                "No es posible eliminar el docente: es director de grupo de "
                f"{', '.join(dirigidos)}. Nombre primero otro director."
            )
        return None

    @classmethod
    def gancho_antes_de_eliminar(cls, fila: Docente) -> None:
        bd.session.execute(
            delete(DocenteAsignatura).where(DocenteAsignatura.teacher_id == fila.id)
        )
        bd.session.execute(delete(DocenteCurso).where(DocenteCurso.teacher_id == fila.id))

    # ── Asignaturas que dicta ────────────────────────────────────────

    @classmethod
    def asignar_asignaturas(
        cls,
        identificador: str,
        asignaturas_ids: list[str],
        actor: UsuarioAutenticado,
        ctx: ContextoPeticion,
    ) -> dict:
        """Reemplaza el listado de asignaturas que dicta el docente."""
        docente = cls.buscar(identificador)

        validas = bd.session.execute(
            select(func.count())
            .select_from(Asignatura)
            .where(Asignatura.id.in_(asignaturas_ids), Asignatura.deleted_at.is_(None))
        ).scalar_one()
        if validas != len(set(asignaturas_ids)):
            raise SolicitudInvalida("Una o más asignaturas seleccionadas no existen")

        # Un horario no puede quedar apuntando a una asignatura que el docente
        # deja de dictar.
        consulta = select(func.count()).select_from(Horario).where(
            Horario.teacher_id == identificador,
            Horario.deleted_at.is_(None),
            Horario.subject_id.is_not(None),
        )
        if asignaturas_ids:
            consulta = consulta.where(Horario.subject_id.notin_(asignaturas_ids))
        huerfanos = bd.session.execute(consulta).scalar_one()
        if huerfanos:
            raise SolicitudInvalida(
                f"No es posible retirar esas asignaturas: {huerfanos} horario(s) del docente "
                "siguen usándolas"
            )

        bd.session.execute(
            delete(DocenteAsignatura).where(DocenteAsignatura.teacher_id == identificador)
        )
        for asignatura_id in dict.fromkeys(asignaturas_ids):
            bd.session.add(
                DocenteAsignatura(
                    teacher_id=identificador,
                    subject_id=asignatura_id,
                    created_at=datetime.now(timezone.utc),
                )
            )

        auditoria.anotar(
            AccionAuditoria.ACTUALIZAR,
            cls.modulo,
            f"Asignó {len(asignaturas_ids)} asignatura(s) al docente {docente.code}",
            entidad_id=identificador,
            detalle={"subjectIds": asignaturas_ids},
            usuario=actor,
            ctx=ctx,
        )
        bd.session.commit()
        return cls.obtener(identificador)

    # ── Cursos que atiende ───────────────────────────────────────────

    @classmethod
    def asignar_cursos(
        cls,
        identificador: str,
        cursos_ids: list[str],
        actor: UsuarioAutenticado,
        ctx: ContextoPeticion,
    ) -> dict:
        """Reemplaza el listado de cursos que atiende el docente."""
        docente = cls.buscar(identificador)

        validos = bd.session.execute(
            select(func.count())
            .select_from(Curso)
            .where(Curso.id.in_(cursos_ids), Curso.deleted_at.is_(None))
        ).scalar_one()
        if validos != len(set(cursos_ids)):
            raise SolicitudInvalida("Uno o más cursos seleccionados no existen")

        # Un docente no puede dejar de atender el curso que dirige: sería
        # director de un grupo con el que ya no tiene vínculo.
        consulta = select(Curso.name).where(
            Curso.homeroom_teacher_id == identificador, Curso.deleted_at.is_(None)
        )
        if cursos_ids:
            consulta = consulta.where(Curso.id.notin_(cursos_ids))
        dirigidos = bd.session.execute(consulta.order_by(Curso.name.asc())).scalars().all()
        if dirigidos:
            raise SolicitudInvalida(
                f"El docente dirige {', '.join(dirigidos)}: no puede retirarse de "
                "esos cursos mientras sea su director de grupo"
            )

        bd.session.execute(delete(DocenteCurso).where(DocenteCurso.teacher_id == identificador))
        for curso_id in dict.fromkeys(cursos_ids):
            bd.session.add(
                DocenteCurso(
                    teacher_id=identificador,
                    course_id=curso_id,
                    created_at=datetime.now(timezone.utc),
                )
            )

        auditoria.anotar(
            AccionAuditoria.ACTUALIZAR,
            cls.modulo,
            f"Asignó {len(cursos_ids)} curso(s) al docente {docente.code}",
            entidad_id=identificador,
            detalle={"courseIds": cursos_ids},
            usuario=actor,
            ctx=ctx,
        )
        bd.session.commit()
        return cls.obtener(identificador)

    # ── Fotografía ───────────────────────────────────────────────────

    @classmethod
    def ruta_foto(cls, identificador: str) -> str:
        """
        Dirección pública desde la que se sirve la fotografía.

        Lleva la marca del momento en que se subió para que el navegador no
        muestre la anterior tras un cambio: sin ella, la imagen queda en la
        caché y parece que la subida no hizo nada.
        """
        prefijo = current_app.config["PREFIJO_API"]
        return f"{prefijo}/teachers/{identificador}/photo?v={int(time.time())}"

    @classmethod
    def subir_foto(
        cls,
        identificador: str,
        archivo: FileStorage,
        actor: UsuarioAutenticado,
        ctx: ContextoPeticion,
    ) -> dict:
        docente = cls.buscar(identificador)

        contenido, tipo = subidas.normalizar_foto(archivo)
        docente.photo = contenido
        docente.photo_mime = tipo
        docente.photo_url = cls.ruta_foto(identificador)

        auditoria.anotar(
            AccionAuditoria.ACTUALIZAR,
            cls.modulo,
            f"Actualizó la fotografía del docente {docente.code}",
            entidad_id=identificador,
            detalle={"tamano": len(contenido), "tipo": tipo},
            usuario=actor,
            ctx=ctx,
        )
        bd.session.commit()
        return cls.serializar(docente)

    @classmethod
    def quitar_foto(
        cls, identificador: str, actor: UsuarioAutenticado, ctx: ContextoPeticion
    ) -> dict:
        docente = cls.buscar(identificador)

        docente.photo = None
        docente.photo_mime = None
        docente.photo_url = None

        auditoria.anotar(
            AccionAuditoria.ACTUALIZAR,
            cls.modulo,
            f"Quitó la fotografía del docente {docente.code}",
            entidad_id=identificador,
            usuario=actor,
            ctx=ctx,
        )
        bd.session.commit()
        return cls.serializar(docente)

    @classmethod
    def leer_foto(cls, identificador: str) -> tuple[bytes, str] | None:
        """Contenido de la fotografía, o None si el docente no tiene."""
        exigir_identificador(identificador)

        fila = bd.session.execute(
            select(Docente.photo, Docente.photo_mime).where(Docente.id == identificador)
        ).one_or_none()

        if fila is None or fila.photo is None:
            return None
        return bytes(fila.photo), fila.photo_mime or "image/webp"
