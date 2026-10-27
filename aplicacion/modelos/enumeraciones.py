"""
Enumeraciones del dominio.

Sustituye a `common/enums.ts`. Los valores coinciden exactamente con las
etiquetas de los tipos ENUM nativos que ya existen en PostgreSQL, así que
SQLAlchemy lee y escribe sin necesidad de conversión alguna.

Heredan de `str` para que se serialicen solas al convertir a JSON, igual que
hacía Prisma.
"""

from __future__ import annotations

from enum import Enum


class EstadoRegistro(str, Enum):
    """Tipo `record_status`."""

    ACTIVO = "ACTIVE"
    INACTIVO = "INACTIVE"


class TipoMarcacion(str, Enum):
    """Tipo `attendance_type`."""

    ENTRADA = "CHECK_IN"
    SALIDA = "CHECK_OUT"


class EstadoMarcacion(str, Enum):
    """Tipo `attendance_status`."""

    PUNTUAL = "ON_TIME"          # RN008
    TARDE = "LATE"               # RN007
    SALIDA_ANTICIPADA = "EARLY_DEPARTURE"


class AccionAuditoria(str, Enum):
    """Tipo `audit_action`."""

    CREAR = "CREATE"
    ACTUALIZAR = "UPDATE"
    ELIMINAR = "DELETE"
    ACTIVAR = "ACTIVATE"
    DESACTIVAR = "DEACTIVATE"
    ENTRAR = "LOGIN"
    SALIR = "LOGOUT"
    ASISTENCIA = "ATTENDANCE"


class TipoAjuste(str, Enum):
    """Tipo `setting_type`."""

    TEXTO = "STRING"
    NUMERO = "NUMBER"
    BOOLEANO = "BOOLEAN"
    JSON = "JSON"


class TipoExcusa(str, Enum):
    """Tipo `excuse_type`."""

    INCAPACIDAD = "INCAPACIDAD"   # incapacidad médica
    PERMISO = "PERMISO"           # permisos o comisiones
    OTRO = "OTRO"                 # cualquier otro motivo


class EstadoExcusa(str, Enum):
    """Tipo `excuse_status`."""

    PENDIENTE = "PENDING"
    APROBADA = "APPROVED"
    RECHAZADA = "REJECTED"


class NivelEducativo(str, Enum):
    """
    Tipo `education_level`.

    Niveles del servicio educativo formal según la Ley 115 de 1994. Los
    valores conservan la denominación legal: no son etiquetas traducibles,
    son las categorías que define la norma.
    """

    PREESCOLAR = "PREESCOLAR"              # art. 15-18
    BASICA_PRIMARIA = "BASICA_PRIMARIA"    # art. 21, grados 1 a 5
    BASICA_SECUNDARIA = "BASICA_SECUNDARIA"  # art. 22, grados 6 a 9
    MEDIA = "MEDIA"                        # art. 27-35, grados 10 y 11


# ── Etiquetas en español, para la interfaz y las exportaciones ──────
# Se indexan por el valor almacenado, no por el miembro, porque es lo que
# llega desde la base y desde los parámetros de consulta.

ETIQUETA_ESTADO_MARCACION = {
    "ON_TIME": "Puntual",
    "LATE": "Tarde",
    "EARLY_DEPARTURE": "Salida anticipada",
}

ETIQUETA_TIPO_MARCACION = {
    "CHECK_IN": "Entrada",
    "CHECK_OUT": "Salida",
}

ETIQUETA_ACCION_AUDITORIA = {
    "CREATE": "Creación",
    "UPDATE": "Actualización",
    "DELETE": "Eliminación",
    "ACTIVATE": "Activación",
    "DEACTIVATE": "Inactivación",
    "LOGIN": "Inicio de sesión",
    "LOGOUT": "Cierre de sesión",
    "ATTENDANCE": "Asistencia",
}

ETIQUETA_ESTADO_REGISTRO = {
    "ACTIVE": "Activo",
    "INACTIVE": "Inactivo",
}

ETIQUETA_TIPO_EXCUSA = {
    "INCAPACIDAD": "Incapacidad",
    "PERMISO": "Permiso",
    "OTRO": "Otro motivo",
}

ETIQUETA_ESTADO_EXCUSA = {
    "PENDING": "En revisión",
    "APPROVED": "Aprobada",
    "REJECTED": "Rechazada",
}

ETIQUETA_NIVEL_EDUCATIVO = {
    "PREESCOLAR": "Preescolar",
    "BASICA_PRIMARIA": "Básica primaria",
    "BASICA_SECUNDARIA": "Básica secundaria",
    "MEDIA": "Educación media",
}
