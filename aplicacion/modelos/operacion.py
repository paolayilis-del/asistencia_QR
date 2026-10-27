"""
Modelos de operación: marcaciones, auditoría y configuración.

Traducción de `Attendance`, `AuditLog` y `Setting`.
"""

from __future__ import annotations

from datetime import date as Fecha, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensiones import bd
from .base import BorradoLogico, MarcasTiempo, columna_uuid, enum_sql, nuevo_id
from .enumeraciones import (
    AccionAuditoria,
    EstadoExcusa,
    EstadoMarcacion,
    TipoAjuste,
    TipoExcusa,
    TipoMarcacion,
)


class Marcacion(bd.Model, MarcasTiempo, BorradoLogico):
    """Marcación de entrada o salida. Es la evidencia del sistema."""

    __tablename__ = "attendances"

    id: Mapped[str] = columna_uuid(primary_key=True, default=nuevo_id)

    # Restrict: una marcación no se pierde porque se elimine al docente
    teacher_id: Mapped[str] = columna_uuid(
        ForeignKey("teachers.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    docente: Mapped["Docente"] = relationship(back_populates="marcaciones", lazy="joined")

    schedule_id: Mapped[str | None] = columna_uuid(
        ForeignKey("schedules.id", ondelete="SET NULL", onupdate="CASCADE")
    )
    horario: Mapped["Horario | None"] = relationship(back_populates="marcaciones", lazy="joined")

    type: Mapped[TipoMarcacion] = enum_sql(TipoMarcacion, "attendance_type", nullable=False)
    status: Mapped[EstadoMarcacion] = enum_sql(EstadoMarcacion, "attendance_status", nullable=False)

    # Fecha local de la marcación, sin componente horario
    date: Mapped[Fecha] = mapped_column(Date, nullable=False)

    # Instante exacto del registro
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Hora esperada según el horario aplicado (HH:MM)
    expected_time: Mapped[str | None] = mapped_column(String(5))

    # Minutos de diferencia: positivo llegó tarde, negativo se anticipó
    minutes_diff: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)

    # Geolocalización del docente al momento de registrar
    latitude: Mapped[float | None] = mapped_column()
    longitude: Mapped[float | None] = mapped_column()
    location_accuracy: Mapped[float | None] = mapped_column()  # metros
    location_source: Mapped[str | None] = mapped_column(String(30))  # gps, network, user

    ip_address: Mapped[str | None] = mapped_column(String(60))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    device: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(String(400))

    # Quién ejecutó el registro: el propio docente o un administrativo
    registered_by_id: Mapped[str | None] = columna_uuid()

    __table_args__ = (
        Index("attendances_teacher_id_date_idx", "teacher_id", "date"),
        Index("attendances_date_type_idx", "date", "type"),
        Index("attendances_status_idx", "status"),
        Index("attendances_schedule_id_idx", "schedule_id"),
        Index("attendances_deleted_at_idx", "deleted_at"),
    )


class Excusa(bd.Model, MarcasTiempo, BorradoLogico):
    """
    Excusa o justificación presentada por un docente.

    El archivo no se guarda en el disco: viaja en la base de datos igual que la
    fotografía del docente, para que no queden adjuntos huérfanos ni dependa de
    una carpeta que el despliegue pueda perder.
    """

    __tablename__ = "excuses"

    id: Mapped[str] = columna_uuid(primary_key=True, default=nuevo_id)

    # Restrict: la evidencia de una ausencia no se pierde porque se borre el docente
    teacher_id: Mapped[str] = columna_uuid(
        ForeignKey("teachers.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    docente: Mapped["Docente"] = relationship(lazy="joined")

    # Marcación que justifica, cuando se sabe cuál. Nulo si la ausencia no
    # llegó a registrarse: la excusa también sirve para días sin marcación.
    attendance_id: Mapped[str | None] = columna_uuid(
        ForeignKey("attendances.id", ondelete="SET NULL", onupdate="CASCADE")
    )

    type: Mapped[TipoExcusa] = enum_sql(TipoExcusa, "excuse_type", nullable=False)
    status: Mapped[EstadoExcusa] = enum_sql(
        EstadoExcusa, "excuse_status", default=EstadoExcusa.PENDIENTE, nullable=False
    )

    # Día que justifica, en fecha local
    date: Mapped[Fecha] = mapped_column(Date, nullable=False)

    # Motivo escrito por el docente
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Adjunto de respaldo
    file_name: Mapped[str | None] = mapped_column(String(200))
    file_mime: Mapped[str | None] = mapped_column(String(80))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    file_data: Mapped[bytes | None] = mapped_column(LargeBinary)

    # Quién recibe y resuelve la solicitud
    reviewed_by_id: Mapped[str | None] = columna_uuid(
        ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE")
    )
    # Sin `back_populates`: la relación va en un solo sentido. Se usa `joined`
    # porque la pantalla de revisión siempre muestra quién resolvió cada una.
    revisor: Mapped["Usuario | None"] = relationship(lazy="joined")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)

    # Quién la presentó
    created_by_id: Mapped[str | None] = columna_uuid()

    __table_args__ = (
        Index("excuses_teacher_id_date_idx", "teacher_id", "date"),
        Index("excuses_status_idx", "status"),
        Index("excuses_date_idx", "date"),
        Index("excuses_deleted_at_idx", "deleted_at"),
    )


class Auditoria(bd.Model, MarcasTiempo, BorradoLogico):
    """Bitácora de toda acción del sistema (RN009)."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = columna_uuid(primary_key=True, default=nuevo_id)

    user_id: Mapped[str | None] = columna_uuid(
        ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE")
    )

    # Se conservan copiados: el evento debe seguir siendo legible aunque el
    # usuario se elimine más adelante.
    user_email: Mapped[str | None] = mapped_column(String(180))
    user_name: Mapped[str | None] = mapped_column(String(240))

    action: Mapped[AccionAuditoria] = enum_sql(AccionAuditoria, "audit_action", nullable=False)
    module: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    ip_address: Mapped[str | None] = mapped_column(String(60))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    device: Mapped[str | None] = mapped_column(String(120))

    # Detalle estructurado del evento, consultable con operadores JSON.
    # Nulo significa «sin detalle»; nunca se escribe el valor JSON `null`.
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)

    __table_args__ = (
        Index("audit_logs_user_id_idx", "user_id"),
        Index("audit_logs_action_idx", "action"),
        Index("audit_logs_module_idx", "module"),
        Index("audit_logs_created_at_idx", "created_at"),
    )


class Ajuste(bd.Model, MarcasTiempo, BorradoLogico):
    """Parámetros del sistema editables sin desplegar código."""

    __tablename__ = "settings"

    id: Mapped[str] = columna_uuid(primary_key=True, default=nuevo_id)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    type: Mapped[TipoAjuste] = enum_sql(
        TipoAjuste, "setting_type", default=TipoAjuste.TEXTO, nullable=False
    )

    group: Mapped[str] = mapped_column(String(60), default="general", nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(400))

    # Accesible sin autenticación (nombre institucional, zona horaria)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Su modificación exige además tocar la configuración del servidor
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (Index("settings_group_idx", "group"),)
