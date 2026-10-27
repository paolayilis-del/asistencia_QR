"""
Menú de navegación.

Cada opción se muestra solo si el usuario tiene el permiso que la respalda,
igual que hacía la barra lateral del frontend en React.
"""

from __future__ import annotations

from ..comun.seguridad import UsuarioAutenticado


def _icono(trazado: str) -> str:
    return (
        '<svg viewBox="0 0 24 24" fill="none" class="h-4 w-4" aria-hidden="true">'
        f'{trazado}</svg>'
    )


ICONOS = {
    "panel": _icono(
        '<rect x="3" y="3" width="7" height="9" rx="1.6" stroke="currentColor" stroke-width="1.6"/>'
        '<rect x="14" y="3" width="7" height="5" rx="1.6" stroke="currentColor" stroke-width="1.6"/>'
        '<rect x="14" y="12" width="7" height="9" rx="1.6" stroke="currentColor" stroke-width="1.6"/>'
        '<rect x="3" y="16" width="7" height="5" rx="1.6" stroke="currentColor" stroke-width="1.6"/>'
    ),
    "docentes": _icono(
        '<circle cx="9" cy="8" r="3.2" stroke="currentColor" stroke-width="1.6"/>'
        '<path d="M3 20a6 6 0 0112 0" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
        '<path d="M16 11a3 3 0 100-6M17 20a5.5 5.5 0 00-1.5-3.8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    ),
    "asignaturas": _icono(
        '<path d="M4 5.5A1.5 1.5 0 015.5 4H19v15H5.5A1.5 1.5 0 004 20.5z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
        '<path d="M8 8h7M8 11.5h7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    ),
    "grados": _icono(
        '<path d="M12 4L2.5 8.5 12 13l9.5-4.5L12 4z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
        '<path d="M6 10.5V16c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-5.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    ),
    "cursos": _icono(
        '<rect x="3" y="4" width="18" height="13" rx="2" stroke="currentColor" stroke-width="1.6"/>'
        '<path d="M8 20h8M12 17v3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
        '<path d="M7 8.5h6M7 12h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    ),
    "jornadas": _icono(
        '<circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6"/>'
        '<path d="M12 7.5V12l3 2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    ),
    "horarios": _icono(
        '<rect x="3.5" y="5" width="17" height="15" rx="2" stroke="currentColor" stroke-width="1.6"/>'
        '<path d="M3.5 9.5h17M8 3.5v3M16 3.5v3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    ),
    "asistencia": _icono(
        '<rect x="4" y="3.5" width="16" height="17" rx="2" stroke="currentColor" stroke-width="1.6"/>'
        '<path d="M8.5 11.5l2.2 2.2 4.3-4.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "qr": _icono(
        '<rect x="3" y="3" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.6"/>'
        '<rect x="14" y="3" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.6"/>'
        '<rect x="3" y="14" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.6"/>'
        '<path d="M14 14h3v3h-3zM19 19h2v2h-2z" stroke="currentColor" stroke-width="1.6"/>'
    ),
    "reportes": _icono(
        '<path d="M5 19V9M12 19V5M19 19v-7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'
    ),
    "usuarios": _icono(
        '<circle cx="12" cy="8" r="3.5" stroke="currentColor" stroke-width="1.6"/>'
        '<path d="M5 20a7 7 0 0114 0" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    ),
    "roles": _icono(
        '<path d="M12 3l2.6 5.4 5.9.8-4.3 4.1 1 5.9-5.2-2.8-5.2 2.8 1-5.9L3.5 9.2l5.9-.8z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
    ),
    "ajustes": _icono(
        '<circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.6"/>'
        '<path d="M19 12a7 7 0 00-.1-1.2l2-1.5-2-3.5-2.3.9a7 7 0 00-2-1.2L14.5 3h-5l-.1 2.5a7 7 0 00-2 1.2L5 5.8 3 9.3l2 1.5A7 7 0 005 12c0 .4 0 .8.1 1.2L3 14.7l2 3.5 2.3-.9a7 7 0 002 1.2L9.5 21h5l.1-2.5a7 7 0 002-1.2l2.3.9 2-3.5-2-1.5c.1-.4.1-.8.1-1.2z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>'
    ),
    # Los tres iconos siguientes son para las pantallas del docente.
    "historial": _icono(
        '<circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6"/>'
        '<path d="M12 7.5V12l3 2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    ),
    "excusas": _icono(
        '<path d="M7 3.5h7.5L19 8v12.5a1 1 0 01-1 1H7a1 1 0 01-1-1v-16a1 1 0 011-1z"'
        ' stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
        '<path d="M14 3.5V8h4.5" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
        '<path d="M9 13.5l2 2 4-4.2" stroke="currentColor" stroke-width="1.8"'
        ' stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    # Bandeja de revisión: documento con un sello de aprobación encima.
    "revisar": _icono(
        '<path d="M7 3.5h7.5L19 8v12.5a1 1 0 01-1 1H7a1 1 0 01-1-1v-16a1 1 0 011-1z"'
        ' stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
        '<path d="M14 3.5V8h4.5" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
        '<circle cx="12" cy="14" r="3.2" stroke="currentColor" stroke-width="1.6"/>'
        '<path d="M14.4 16.4l2.1 2.1" stroke="currentColor" stroke-width="1.6"'
        ' stroke-linecap="round"/>'
    ),
}


# (ruta, etiqueta, icono, permiso que la habilita)
ESTRUCTURA = (
    (
        "Operación",
        (
            ("/dashboard", "Dashboard", "panel", "dashboard.read"),
            ("/asistencia", "Asistencia", "asistencia", "attendance.read"),
            ("/mi-asistencia", "Mi asistencia", "historial", "attendance.self"),
            ("/escanear", "Escanear QR", "qr", "attendance.self"),
            ("/reportes", "Reportes", "reportes", "reports.read"),
            ("/qr", "Código QR", "qr", "settings.read"),
        ),
    ),
    (
        "Académico",
        (
            ("/docentes", "Docentes", "docentes", "teachers.read"),
            ("/asignaturas", "Asignaturas", "asignaturas", "subjects.read"),
            ("/grados", "Grados", "grados", "grades.read"),
            ("/cursos", "Cursos", "cursos", "courses.read"),
            ("/jornadas", "Jornadas", "jornadas", "shifts.read"),
            ("/horarios", "Horarios", "horarios", "schedules.read"),
        ),
    ),
    (
        "Administración",
        (
            # La primera entrada es la del docente: presentar una justificación
            # es una gestión propia, no una tarea administrativa. Aparece aquí
            # porque la pidió así, pero la resuelve `excuses.self`, no el rol.
            ("/excusas", "Mis excusas", "excusas", "excuses.self"),
            ("/revision-excusas", "Revisión de excusas", "revisar", "excuses.review"),
            ("/usuarios", "Usuarios", "usuarios", "users.read"),
            ("/roles", "Roles", "roles", "roles.read"),
            ("/configuracion", "Configuración", "ajustes", "settings.read"),
        ),
    ),
)


def construir(usuario: UsuarioAutenticado, ruta_actual: str) -> list[dict]:
    """Menú filtrado por los permisos del usuario."""
    menu = []
    for titulo, opciones in ESTRUCTURA:
        visibles = [
            {
                "ruta": ruta,
                "etiqueta": etiqueta,
                "icono": ICONOS[icono],
                "activa": ruta_actual == ruta or ruta_actual.startswith(ruta + "/"),
            }
            for ruta, etiqueta, icono, permiso in opciones
            if usuario.tiene(permiso)
        ]
        if visibles:
            menu.append({"titulo": titulo, "opciones": visibles})
    return menu


def iniciales(nombre: str) -> str:
    """Dos letras a partir del nombre, para el avatar de la cabecera."""
    partes = [p for p in (nombre or "").split() if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()
