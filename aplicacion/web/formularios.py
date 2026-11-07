"""
Definición de los formularios de alta y edición.

Sustituye a los formularios en React Hook Form del proyecto original. Aquí se
declara qué campos tiene cada módulo y una sola pieza de JavaScript los pinta,
valida y envía.

Cada campo indica:

    campo        nombre que espera la API
    etiqueta     texto visible
    tipo         cómo se pinta y se valida
    obligatorio  si no puede quedar vacío
    solo_crear   aparece únicamente al dar de alta (por ejemplo la contraseña)
    solo_editar  aparece únicamente al modificar
    relacion     se envía aparte, a su propio punto de la API

Los campos con `relacion` no viajan en el cuerpo principal: el sistema
original los gestionaba con endpoints propios (`/teachers/:id/subjects`,
`/roles/:id/permissions`) y aquí se respeta esa separación.
"""

from __future__ import annotations

from typing import Any


def campo(
    nombre: str,
    etiqueta: str,
    tipo: str = "texto",
    *,
    obligatorio: bool = False,
    ayuda: str = "",
    ancho: str = "completo",
    **extra: Any,
) -> dict:
    return {
        "campo": nombre,
        "etiqueta": etiqueta,
        "tipo": tipo,
        "obligatorio": obligatorio,
        "ayuda": ayuda,
        "ancho": ancho,
        **extra,
    }


ESTADO = campo(
    "status",
    "Estado",
    "opciones",
    ancho="mitad",
    opciones=[("ACTIVE", "Activo"), ("INACTIVE", "Inactivo")],
    defecto="ACTIVE",
)

DIAS_SEMANA = [
    ("", "Todos los días"),
    ("0", "Domingo"),
    ("1", "Lunes"),
    ("2", "Martes"),
    ("3", "Miércoles"),
    ("4", "Jueves"),
    ("5", "Viernes"),
    ("6", "Sábado"),
]


FORMULARIOS: dict[str, dict] = {
    "docentes": {
        "recurso": "teachers",
        "singular": "docente",
        "genero": "el",
        "sugerir_codigo": "/teachers/next-code",
        "campos": [
            campo("code", "Código", obligatorio=True, ancho="mitad", automatico=True,
                  oculto=True,
                  ayuda="Se asigna automáticamente, siguiendo la numeración"),
            campo("userId", "Cuenta de acceso (usuario)", "catalogo", recurso="users",
                  ancho="completo", vacio="Sin cuenta vinculada",
                  ayuda="Al vincular una cuenta, nombres, documento, correo y teléfono se toman del usuario. Con ella el docente entra a marcar su asistencia."),
            campo("document", "Documento", ancho="mitad",
                  ayuda="Se completa desde la cuenta vinculada"),
            campo("firstName", "Nombres", ancho="mitad"),
            campo("lastName", "Apellidos", ancho="mitad"),
            campo("email", "Correo", "correo", ancho="mitad"),
            campo("phone", "Teléfono", "telefono", ancho="mitad"),
            ESTADO,
            campo("subjectIds", "Asignaturas que dicta", "multiple", recurso="subjects",
                  relacion="/teachers/{id}/subjects", clave_relacion="subjectIds",
                  ayuda="Un horario solo puede usar asignaturas que el docente dicte"),
            campo("courseIds", "Cursos que atiende", "multiple", recurso="courses",
                  relacion="/teachers/{id}/courses", clave_relacion="courseIds",
                  ayuda="Un docente puede atender uno o varios cursos"),
        ],
        "foto": True,
    },
    "asignaturas": {
        "recurso": "subjects",
        "singular": "asignatura",
        "genero": "la",
        "sugerir_codigo": "/subjects/next-code",
        "campos": [
            campo("code", "Código", obligatorio=True, ancho="mitad", automatico=True,
                  ayuda="Se asigna automáticamente, siguiendo la numeración"),
            campo("name", "Nombre", obligatorio=True, ancho="mitad"),
            campo("description", "Descripción", "parrafo"),
            campo("weeklyHours", "Horas por semana", "numero", ancho="mitad",
                  minimo=1, maximo=60),
            campo("color", "Color", "color", ancho="mitad", defecto="#4F46E5",
                  ayuda="Identifica la asignatura en listados y horarios"),
            ESTADO,
            campo("teacherIds", "Docentes que la dictan", "multiple", recurso="teachers",
                  relacion="/subjects/{id}/teachers", clave_relacion="teacherIds",
                  solo_editar=True),
        ],
    },
    "grados": {
        "recurso": "grades",
        "singular": "grado",
        "genero": "el",
        "campos": [
            campo("code", "Código", obligatorio=True, solo_crear=True, ancho="mitad",
                  ayuda="Código corto y único (máx. 10), por ejemplo ADULTO1"),
            campo("level", "Nivel educativo", "opciones", obligatorio=True,
                  solo_crear=True, ancho="mitad",
                  opciones=[("PREESCOLAR", "Preescolar"),
                            ("BASICA_PRIMARIA", "Básica primaria"),
                            ("BASICA_SECUNDARIA", "Básica secundaria"),
                            ("MEDIA", "Educación media")]),
            campo("position", "Orden en la escalera", "numero", obligatorio=True,
                  solo_crear=True, ancho="mitad", minimo=1, maximo=30,
                  ayuda="Lugar que ocupa (1 = prejardín … 14 = undécimo)"),
            campo("name", "Nombre", obligatorio=True, ancho="mitad"),
            campo("description", "Descripción", "parrafo"),
            campo("status", "¿La institución lo ofrece?", "opciones", ancho="mitad",
                  opciones=[("ACTIVE", "Sí, se ofrece"), ("INACTIVE", "No se ofrece")],
                  defecto="ACTIVE"),
        ],
    },
    "cursos": {
        "recurso": "courses",
        "singular": "curso",
        "genero": "el",
        "campos": [
            campo("gradeId", "Grado", "catalogo", recurso="grades",
                  obligatorio=True, ancho="mitad"),
            campo("letter", "Grupo", obligatorio=True, ancho="mitad",
                  ayuda="La letra del grupo: A, B, C… El nombre se compone solo"),
            campo("shiftId", "Jornada", "catalogo", recurso="shifts",
                  ancho="mitad", vacio="Sin jornada asignada"),
            campo("capacity", "Cupo", "numero", ancho="mitad", minimo=1, maximo=100,
                  ayuda="Número máximo de estudiantes"),
            campo("homeroomTeacherId", "Director de grupo", "catalogo", recurso="teachers",
                  vacio="Sin director asignado"),
            ESTADO,
            campo("teacherIds", "Docentes que lo atienden", "multiple", recurso="teachers",
                  relacion="/courses/{id}/teachers", clave_relacion="teacherIds"),
        ],
    },
    "jornadas": {
        "recurso": "shifts",
        "singular": "jornada",
        "genero": "la",
        "campos": [
            campo("name", "Nombre", obligatorio=True),
            campo("description", "Descripción", "parrafo"),
            ESTADO,
        ],
    },
    "horarios": {
        "recurso": "schedules",
        "singular": "horario",
        "genero": "el",
        "campos": [
            campo("teacherId", "Docente", "catalogo", recurso="teachers",
                  obligatorio=True, ancho="mitad", dispara="subjectId"),
            campo("shiftId", "Jornada", "catalogo", recurso="shifts",
                  obligatorio=True, ancho="mitad"),
            campo("subjectId", "Asignatura", "catalogo", recurso="subjects",
                  ancho="mitad", vacio="Sin asignatura",
                  depende_de="teacherId", parametro="teacherId",
                  ayuda="Solo aparecen las que dicta el docente elegido"),
            campo("courseId", "Curso", "catalogo", recurso="courses",
                  ancho="mitad", vacio="Sin curso",
                  depende_de="teacherId", parametro="teacherId",
                  ayuda="Solo aparecen los que atiende el docente elegido"),
            campo("dayOfWeek", "Día", "opciones", ancho="mitad", opciones=DIAS_SEMANA),
            campo("checkInTime", "Hora de entrada", "hora", obligatorio=True, ancho="tercio"),
            campo("checkOutTime", "Hora de salida", "hora", obligatorio=True, ancho="tercio"),
            campo("toleranceMinutes", "Tolerancia", "numero", ancho="tercio",
                  minimo=0, maximo=120, defecto=10,
                  ayuda="Minutos antes de considerar la entrada como tarde (RN007)"),
            ESTADO,
        ],
    },
    "usuarios": {
        "recurso": "users",
        "singular": "usuario",
        "genero": "el",
        "campos": [
            campo("firstName", "Nombres", obligatorio=True, ancho="mitad"),
            campo("lastName", "Apellidos", obligatorio=True, ancho="mitad"),
            campo("document", "Documento", obligatorio=True, ancho="mitad"),
            campo("phone", "Teléfono", "telefono", ancho="mitad"),
            campo("email", "Correo", "correo", obligatorio=True),
            campo("password", "Contraseña", "clave", obligatorio=True, solo_crear=True,
                  ayuda="Mínimo 8 caracteres, con mayúscula, minúscula y número"),
            campo("roleId", "Rol", "catalogo", recurso="roles",
                  obligatorio=True, ancho="mitad"),
            ESTADO,
            campo("mustChangePassword", "Obligar a cambiar la contraseña al entrar",
                  "casilla"),
        ],
    },
    "roles": {
        "recurso": "roles",
        "singular": "rol",
        "genero": "el",
        "campos": [
            campo("name", "Nombre", obligatorio=True),
            campo("description", "Descripción", "parrafo"),
            ESTADO,
            campo("permissionIds", "Permisos", "permisos",
                  relacion="/roles/{id}/permissions", clave_relacion="permissionIds",
                  ayuda="El rol con control total los tiene todos por definición y no se editan"),
        ],
    },
}


def para(nombre: str) -> dict | None:
    """Definición del formulario de un módulo, o None si no tiene."""
    definicion = FORMULARIOS.get(nombre)
    if definicion is None:
        return None
    return {**definicion, "nombre": nombre}
