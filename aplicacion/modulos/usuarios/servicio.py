"""
Servicio de usuarios.

Traducción de `modules/users/users.service.ts`.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import select

from ...comun import auditoria
from ...comun.consultas import Paginacion
from ...comun.crud import ServicioCRUD
from ...comun.errores import Prohibido, SolicitudInvalida
from ...comun.peticion import ContextoPeticion
from ...comun.seguridad import UsuarioAutenticado, cifrar_contrasena
from ...comun.tiempo import iso
from ...extensiones import bd
from ...modelos import (
    AccionAuditoria,
    Docente,
    EstadoRegistro,
    Rol,
    SesionRefresco,
    Usuario,
    nuevo_id,
)
from flask import request


class ServicioUsuarios(ServicioCRUD):
    modelo = Usuario
    modulo = "Usuarios"
    articulo = "el"
    sustantivo = "usuario"
    campo_etiqueta = "email"
    tope_exportacion = 5000

    ordenables = {
        "createdAt": Usuario.created_at,
        "firstName": Usuario.first_name,
        "lastName": Usuario.last_name,
        "email": Usuario.email,
        "document": Usuario.document,
        "status": Usuario.status,
        "role.name": Rol.name,
    }
    buscables = (
        Usuario.first_name,
        Usuario.last_name,
        Usuario.email,
        Usuario.document,
        Usuario.phone,
    )

    # ── Consultas ────────────────────────────────────────────────────

    @classmethod
    def consulta_base(cls):
        # La unión con el rol permite ordenar por `role.name`
        return select(Usuario).join(Rol, Rol.id == Usuario.role_id).where(
            Usuario.deleted_at.is_(None)
        )

    @classmethod
    def aplicar_filtros(cls, consulta, paginacion: Paginacion):
        consulta = super().aplicar_filtros(consulta, paginacion)
        rol_id = request.args.get("roleId")
        if rol_id:
            consulta = consulta.where(Usuario.role_id == rol_id)
        return consulta

    @classmethod
    def serializar(cls, fila: Usuario) -> dict:
        docente = bd.session.execute(
            select(Docente).where(Docente.user_id == fila.id, Docente.deleted_at.is_(None))
        ).scalar_one_or_none()

        # No se exponen ni el hash de la contraseña ni el estado del bloqueo
        # por intentos fallidos: el sistema original tampoco los devolvía.
        return {
            "id": fila.id,
            "firstName": fila.first_name,
            "lastName": fila.last_name,
            "document": fila.document,
            "email": fila.email,
            "phone": fila.phone,
            "status": fila.status.value,
            "lastLoginAt": iso(fila.last_login_at),
            "mustChangePassword": fila.must_change_password,
            "createdAt": iso(fila.created_at),
            "updatedAt": iso(fila.updated_at),
            "roleId": fila.role_id,
            "role": {
                "id": fila.rol.id,
                "name": fila.rol.name,
                "description": fila.rol.description,
            },
            "teacher": {"id": docente.id, "code": docente.code} if docente else None,
        }

    # ── Mutaciones ───────────────────────────────────────────────────

    @classmethod
    def construir(cls, datos: dict) -> Usuario:
        return Usuario(
            id=nuevo_id(),
            first_name=datos["firstName"],
            last_name=datos["lastName"],
            document=datos["document"],
            email=datos["email"],
            phone=datos.get("phone") or None,
            password=cifrar_contrasena(datos["password"]),
            role_id=datos["roleId"],
            status=datos.get("status") or EstadoRegistro.ACTIVO,
            must_change_password=bool(datos.get("mustChangePassword", False)),
        )

    @classmethod
    def aplicar_cambios(cls, fila: Usuario, datos: dict) -> None:
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
        if datos.get("roleId") is not None:
            fila.role_id = datos["roleId"]
        if datos.get("status") is not None:
            fila.status = datos["status"]
        if datos.get("mustChangePassword") is not None:
            fila.must_change_password = datos["mustChangePassword"]

    @classmethod
    def liberar_claves_unicas(cls, fila: Usuario) -> None:
        marca = int(time.time() * 1000)
        fila.email = f"{fila.email}.DEL.{marca}"[:180]
        fila.document = f"{fila.document}.DEL.{marca}"[:40]

    # ── Reglas propias ───────────────────────────────────────────────

    @classmethod
    def _rol_valido(cls, rol_id: str) -> Rol:
        rol = bd.session.execute(
            select(Rol).where(Rol.id == rol_id, Rol.deleted_at.is_(None))
        ).scalar_one_or_none()
        if rol is None:
            raise SolicitudInvalida("El rol seleccionado no existe")
        if rol.status != EstadoRegistro.ACTIVO:
            raise SolicitudInvalida("El rol seleccionado está inactivo")
        return rol

    @classmethod
    def gancho_antes_de_crear(cls, datos: dict) -> None:
        cls.exige_unico(Usuario.email, datos["email"], "Ya existe un usuario con ese correo")
        cls.exige_unico(
            Usuario.document, datos["document"], "Ya existe un usuario con ese documento"
        )
        cls._rol_valido(datos["roleId"])

    @classmethod
    def gancho_antes_de_actualizar(cls, fila: Usuario, datos: dict) -> None:
        correo = datos.get("email")
        if correo and correo.lower() != fila.email.lower():
            cls.exige_unico(
                Usuario.email, correo, "Ya existe un usuario con ese correo", excluir=fila.id
            )
        documento = datos.get("document")
        if documento and documento != fila.document:
            cls.exige_unico(
                Usuario.document,
                documento,
                "Ya existe un usuario con ese documento",
                excluir=fila.id,
            )
        if datos.get("roleId"):
            cls._rol_valido(datos["roleId"])

    @classmethod
    def gancho_despues_de_actualizar(cls, fila: Usuario, datos: dict, _previo: dict) -> None:
        # Si se desactiva, las sesiones abiertas dejan de valer
        if datos.get("status") == EstadoRegistro.INACTIVO:
            ahora = datetime.now(timezone.utc)
            for sesion in bd.session.execute(
                select(SesionRefresco).where(
                    SesionRefresco.user_id == fila.id, SesionRefresco.revoked_at.is_(None)
                )
            ).scalars():
                sesion.revoked_at = ahora
        # Sincronizar datos personales con el docente vinculado
        docente = bd.session.execute(
            select(Docente).where(Docente.user_id == fila.id, Docente.deleted_at.is_(None))
        ).scalar_one_or_none()
        if docente:
            docente.first_name = fila.first_name
            docente.last_name = fila.last_name
            docente.document = fila.document
            docente.email = fila.email
            if fila.phone:
                docente.phone = fila.phone

    @classmethod
    def gancho_impide_eliminar(cls, fila: Usuario) -> str | None:
        vinculado = bd.session.execute(
            select(Docente.code).where(Docente.user_id == fila.id, Docente.deleted_at.is_(None))
        ).scalar_one_or_none()
        if vinculado:
            return (
                f"No es posible eliminar el usuario: está vinculado al docente {vinculado}. "
                "Desvincúlelo primero desde la ficha del docente."
            )
        return None

    @classmethod
    def gancho_antes_de_eliminar(cls, fila: Usuario) -> None:
        # Las sesiones abiertas del usuario dejan de valer
        ahora = datetime.now(timezone.utc)
        for sesion in bd.session.execute(
            select(SesionRefresco).where(
                SesionRefresco.user_id == fila.id, SesionRefresco.revoked_at.is_(None)
            )
        ).scalars():
            sesion.revoked_at = ahora

    # ── Reinicio de contraseña ───────────────────────────────────────

    @classmethod
    def reiniciar_clave(
        cls,
        identificador: str,
        nueva: str,
        actor: UsuarioAutenticado,
        ctx: ContextoPeticion,
    ) -> dict:
        """Un administrador asigna una contraseña nueva y obliga a cambiarla."""
        usuario = cls.buscar(identificador)

        if usuario.id == actor.id:
            raise Prohibido(
                "Para cambiar su propia contraseña use la opción de cambio de contraseña"
            )

        usuario.password = cifrar_contrasena(nueva)
        usuario.must_change_password = True
        usuario.failed_login_attempts = 0
        usuario.locked_until = None

        # Todas las sesiones abiertas dejan de valer
        ahora = datetime.now(timezone.utc)
        for sesion in bd.session.execute(
            select(SesionRefresco).where(
                SesionRefresco.user_id == usuario.id, SesionRefresco.revoked_at.is_(None)
            )
        ).scalars():
            sesion.revoked_at = ahora

        auditoria.anotar(
            AccionAuditoria.ACTUALIZAR,
            cls.modulo,
            f"Reinició la contraseña de {usuario.nombre_completo}",
            entidad_id=usuario.id,
            usuario=actor,
            ctx=ctx,
        )
        bd.session.commit()
        return {
            "message": "Contraseña reiniciada. El usuario deberá cambiarla al iniciar sesión."
        }
