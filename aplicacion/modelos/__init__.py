"""
Modelos de datos.

Sustituye a `backend/prisma/schema.prisma` y al cliente generado por Prisma.

Los 13 modelos se mapean contra las tablas que ya existen en PostgreSQL. No se
crean ni se alteran estructuras: `database.sql` sigue siendo la única fuente
de la definición de la base.
"""

from .academico import (
    Asignatura,
    Curso,
    Docente,
    DocenteAsignatura,
    DocenteCurso,
    Grado,
    Horario,
    Jornada,
)
from .acceso import Permiso, Rol, RolPermiso, SesionRefresco, Usuario
from .base import BorradoLogico, ConEstado, MarcasTiempo, nuevo_id
from .enumeraciones import (
    ETIQUETA_ACCION_AUDITORIA,
    ETIQUETA_ESTADO_EXCUSA,
    ETIQUETA_ESTADO_MARCACION,
    ETIQUETA_ESTADO_REGISTRO,
    ETIQUETA_NIVEL_EDUCATIVO,
    ETIQUETA_TIPO_EXCUSA,
    ETIQUETA_TIPO_MARCACION,
    AccionAuditoria,
    EstadoExcusa,
    EstadoMarcacion,
    EstadoRegistro,
    NivelEducativo,
    TipoAjuste,
    TipoExcusa,
    TipoMarcacion,
)
from .operacion import Ajuste, Auditoria, Excusa, Marcacion

__all__ = [
    # Acceso
    "Usuario",
    "SesionRefresco",
    "Rol",
    "Permiso",
    "RolPermiso",
    # Académico
    "Docente",
    "Asignatura",
    "DocenteAsignatura",
    "Grado",
    "Curso",
    "DocenteCurso",
    "Jornada",
    "Horario",
    # Operación
    "Marcacion",
    "Excusa",
    "Auditoria",
    "Ajuste",
    # Enumeraciones
    "EstadoRegistro",
    "TipoMarcacion",
    "EstadoMarcacion",
    "EstadoExcusa",
    "TipoExcusa",
    "AccionAuditoria",
    "TipoAjuste",
    "NivelEducativo",
    "ETIQUETA_ESTADO_MARCACION",
    "ETIQUETA_TIPO_MARCACION",
    "ETIQUETA_ESTADO_EXCUSA",
    "ETIQUETA_TIPO_EXCUSA",
    "ETIQUETA_ACCION_AUDITORIA",
    "ETIQUETA_ESTADO_REGISTRO",
    "ETIQUETA_NIVEL_EDUCATIVO",
    # Base
    "MarcasTiempo",
    "BorradoLogico",
    "ConEstado",
    "nuevo_id",
]
