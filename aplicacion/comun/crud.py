"""
Base común de los módulos CRUD.

Los servicios del sistema original repetían el mismo esqueleto: listar con
paginación y búsqueda, obtener por identificador, crear, actualizar, activar,
inactivar y eliminar de forma lógica, dejando siempre rastro en la auditoría.

Aquí ese esqueleto vive una sola vez. Cada módulo declara su modelo, sus
campos buscables y ordenables, y sobreescribe únicamente lo que difiere.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, ClassVar, Sequence

from sqlalchemy import Select, select
from sqlalchemy.orm import InstrumentedAttribute

from ..extensiones import bd
from ..modelos import AccionAuditoria, EstadoRegistro
from . import auditoria
from .consultas import Paginacion, aplicar_busqueda, aplicar_orden, paginar
from .errores import Conflicto, NoEncontrado, SolicitudInvalida
from .peticion import ContextoPeticion
from .respuestas import resultado_paginado
from .seguridad import UsuarioAutenticado
from .tiempo import iso
from .validaciones import exigir_identificador

TOPE_EXPORTACION = 1000


class ServicioCRUD:
    """
    Comportamiento compartido. Cada módulo lo concreta con sus datos.

    Los atributos de clase describen el módulo; los métodos `gancho_*` son los
    puntos donde cada uno añade sus propias reglas.
    """

    modelo: ClassVar[Any] = None
    modulo: ClassVar[str] = ""          # etiqueta que aparece en la auditoría
    articulo: ClassVar[str] = "el"      # "el horario", "la jornada"
    sustantivo: ClassVar[str] = "registro"
    campo_etiqueta: ClassVar[str] = "name"   # campo que identifica la fila en los mensajes
    ordenables: ClassVar[dict[str, Any]] = {}
    buscables: ClassVar[Sequence[InstrumentedAttribute]] = ()
    orden_defecto: ClassVar[str] = "createdAt"
    tope_exportacion: ClassVar[int] = TOPE_EXPORTACION

    # ── Textos ───────────────────────────────────────────────────────

    @classmethod
    def _no_existe(cls) -> str:
        return f"{cls.articulo.capitalize()} {cls.sustantivo} no existe"

    @classmethod
    def _etiqueta(cls, fila: Any) -> str:
        return str(getattr(fila, cls.campo_etiqueta, fila.id))

    # ── Consultas ────────────────────────────────────────────────────

    @classmethod
    def consulta_base(cls) -> Select:
        """Consulta de partida: solo filas vigentes."""
        return select(cls.modelo).where(cls.modelo.deleted_at.is_(None))

    @classmethod
    def aplicar_filtros(cls, consulta: Select, paginacion: Paginacion) -> Select:
        """Filtros propios del módulo. Por defecto, solo el estado."""
        if paginacion.estado in ("ACTIVE", "INACTIVE"):
            consulta = consulta.where(cls.modelo.status == EstadoRegistro(paginacion.estado))
        return consulta

    @classmethod
    def construir_consulta(cls, paginacion: Paginacion) -> Select:
        consulta = cls.consulta_base()
        consulta = cls.aplicar_filtros(consulta, paginacion)
        consulta = aplicar_busqueda(consulta, paginacion.busqueda, cls.buscables)
        return aplicar_orden(consulta, paginacion, cls.ordenables)

    @classmethod
    def listar(cls, paginacion: Paginacion) -> dict:
        elementos, total = paginar(cls.construir_consulta(paginacion), paginacion)
        return resultado_paginado(
            [cls.serializar(e) for e in elementos], total, paginacion.pagina, paginacion.limite
        )

    @classmethod
    def para_exportar(cls, paginacion: Paginacion) -> list[Any]:
        consulta = cls.construir_consulta(paginacion).limit(cls.tope_exportacion)
        return list(bd.session.execute(consulta).scalars().unique())

    @classmethod
    def buscar(cls, identificador: str) -> Any:
        """Fila vigente por identificador, o error 404."""
        exigir_identificador(identificador)

        fila = bd.session.execute(
            cls.consulta_base().where(cls.modelo.id == identificador)
        ).unique().scalar_one_or_none()
        if fila is None:
            raise NoEncontrado(cls._no_existe())
        return fila

    @classmethod
    def obtener(cls, identificador: str) -> dict:
        return cls.serializar(cls.buscar(identificador))

    # ── Serialización ────────────────────────────────────────────────

    @classmethod
    def campos_comunes(cls, fila: Any) -> dict:
        """Campos que llevan todas las entidades, con los nombres de la API."""
        datos = {
            "id": fila.id,
            "createdAt": iso(fila.created_at),
            "updatedAt": iso(fila.updated_at),
        }
        if hasattr(fila, "status"):
            datos["status"] = fila.status.value
        # El sistema original devolvía `deletedAt` explícito, siempre nulo en
        # los listados. Se conserva para que la respuesta sea idéntica.
        if hasattr(fila, "deleted_at"):
            datos["deletedAt"] = iso(fila.deleted_at)
        return datos

    @classmethod
    def serializar(cls, fila: Any) -> dict:
        """Convierte una fila al JSON que espera la interfaz."""
        raise NotImplementedError

    # ── Mutaciones ───────────────────────────────────────────────────

    @classmethod
    def crear(cls, datos: dict, actor: UsuarioAutenticado, ctx: ContextoPeticion) -> dict:
        cls.gancho_antes_de_crear(datos)

        fila = cls.construir(datos)
        bd.session.add(fila)
        bd.session.flush()          # asigna el identificador sin cerrar la transacción

        cls.gancho_despues_de_crear(fila, datos)

        auditoria.anotar(
            AccionAuditoria.CREAR,
            cls.modulo,
            f"Creó {cls.articulo} {cls.sustantivo} {cls._etiqueta(fila)}",
            entidad_id=fila.id,
            usuario=actor,
            ctx=ctx,
        )
        bd.session.commit()
        return cls.serializar(fila)

    @classmethod
    def actualizar(
        cls, identificador: str, datos: dict, actor: UsuarioAutenticado, ctx: ContextoPeticion
    ) -> dict:
        fila = cls.buscar(identificador)
        previo = {c.key: getattr(fila, c.key) for c in fila.__table__.columns}
        cls.gancho_antes_de_actualizar(fila, datos)

        cls.aplicar_cambios(fila, datos)

        cls.gancho_despues_de_actualizar(fila, datos, previo)

        auditoria.anotar(
            AccionAuditoria.ACTUALIZAR,
            cls.modulo,
            f"Actualizó {cls.articulo} {cls.sustantivo} {cls._etiqueta(fila)}",
            entidad_id=fila.id,
            detalle={"changes": datos} if datos else None,
            usuario=actor,
            ctx=ctx,
        )
        bd.session.commit()
        return cls.serializar(fila)

    @classmethod
    def cambiar_estado(
        cls,
        identificador: str,
        estado: EstadoRegistro,
        actor: UsuarioAutenticado,
        ctx: ContextoPeticion,
    ) -> dict:
        fila = cls.buscar(identificador)

        if estado == EstadoRegistro.INACTIVO:
            impedimento = cls.gancho_impide_inactivar(fila)
            if impedimento:
                raise SolicitudInvalida(impedimento)

        etiqueta = cls._etiqueta(fila)
        fila.status = estado

        activando = estado == EstadoRegistro.ACTIVO
        auditoria.anotar(
            AccionAuditoria.ACTIVAR if activando else AccionAuditoria.DESACTIVAR,
            cls.modulo,
            f"{'Activó' if activando else 'Inactivó'} {cls.articulo} {cls.sustantivo} {etiqueta}",
            entidad_id=fila.id,
            usuario=actor,
            ctx=ctx,
        )
        bd.session.commit()
        return cls.serializar(fila)

    @classmethod
    def eliminar(
        cls, identificador: str, actor: UsuarioAutenticado, ctx: ContextoPeticion
    ) -> dict:
        fila = cls.buscar(identificador)

        impedimento = cls.gancho_impide_eliminar(fila)
        if impedimento:
            raise SolicitudInvalida(impedimento)

        etiqueta = cls._etiqueta(fila)
        cls.gancho_antes_de_eliminar(fila)

        fila.deleted_at = datetime.now(timezone.utc)
        if hasattr(fila, "status"):
            fila.status = EstadoRegistro.INACTIVO
        cls.liberar_claves_unicas(fila)

        auditoria.anotar(
            AccionAuditoria.ELIMINAR,
            cls.modulo,
            f"Eliminó {cls.articulo} {cls.sustantivo} {etiqueta}",
            entidad_id=fila.id,
            usuario=actor,
            ctx=ctx,
        )
        bd.session.commit()
        return {"message": f"{cls.sustantivo.capitalize()} eliminad{cls.articulo[-1]} correctamente"}

    # ── Piezas que cada módulo concreta ──────────────────────────────

    @classmethod
    def construir(cls, datos: dict) -> Any:
        """Crea la instancia a partir de los datos validados."""
        raise NotImplementedError

    @classmethod
    def aplicar_cambios(cls, fila: Any, datos: dict) -> None:
        """Vuelca los campos presentes sobre la fila. Los ausentes no se tocan."""
        raise NotImplementedError

    @classmethod
    def liberar_claves_unicas(cls, fila: Any) -> None:
        """
        Renombra los campos únicos al eliminar.

        Sin esto, el código o el nombre quedarían ocupados para siempre por una
        fila que ya no está a la vista.
        """
        marca = int(time.time() * 1000)
        if hasattr(fila, "name"):
            sufijo = f" (elim. {marca})"
            espacio = 80 - len(sufijo)
            fila.name = fila.name[:max(espacio, 1)] + sufijo

    @classmethod
    def gancho_antes_de_crear(cls, datos: dict) -> None:
        """Validaciones previas al alta, como los duplicados."""

    @classmethod
    def gancho_despues_de_crear(cls, fila: Any, datos: dict) -> None:
        """Trabajo adicional tras el alta, como enlazar relaciones."""

    @classmethod
    def gancho_antes_de_actualizar(cls, fila: Any, datos: dict) -> None:
        """Validaciones previas a la modificación."""

    @classmethod
    def gancho_despues_de_actualizar(cls, fila: Any, datos: dict, _previo: dict) -> None:
        """Trabajo adicional tras la modificación."""

    @classmethod
    def gancho_impide_inactivar(cls, fila: Any) -> str | None:
        """Motivo por el que no puede inactivarse, o None si puede."""
        return None

    @classmethod
    def gancho_impide_eliminar(cls, fila: Any) -> str | None:
        """Motivo por el que no puede eliminarse, o None si puede."""
        return None

    @classmethod
    def gancho_antes_de_eliminar(cls, fila: Any) -> None:
        """
        Limpieza previa a la baja, una vez superadas las comprobaciones.

        Es donde se sueltan las relaciones auxiliares que no deben sobrevivir
        al registro, como los vínculos de una tabla puente.
        """

    # ── Ayuda para comprobar duplicados ──────────────────────────────

    @classmethod
    def exige_unico(
        cls, columna: InstrumentedAttribute, valor: str, mensaje: str, excluir: str | None = None
    ) -> None:
        """
        Comprueba que el valor no esté ya en uso, ignorando mayúsculas.

        Es la comparación que Prisma hacía con `mode: 'insensitive'`; PostgreSQL
        la resuelve en el motor con ILIKE, sin traer candidatos a memoria.
        """
        consulta = select(cls.modelo.id).where(
            columna.ilike(valor), cls.modelo.deleted_at.is_(None)
        )
        if excluir:
            consulta = consulta.where(cls.modelo.id != excluir)
        if bd.session.execute(consulta.limit(1)).scalar_one_or_none():
            raise Conflicto(mensaje)
