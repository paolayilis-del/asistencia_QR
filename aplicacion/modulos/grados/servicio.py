"""
Servicio de grados.

Los grados los fija la Ley 115 de 1994, así que no se crean ni se eliminan
desde la aplicación: vienen cargados. Lo que la institución decide es cuáles
ofrece —activándolos o inactivándolos— y cómo los llama.
"""

from __future__ import annotations

from flask import request
from sqlalchemy import func, select

from ...comun.consultas import Paginacion
from ...comun.crud import ServicioCRUD
from ...extensiones import bd
from ...modelos import (
    ETIQUETA_NIVEL_EDUCATIVO,
    Curso,
    EstadoRegistro,
    Grado,
    NivelEducativo,
)


def _contar_cursos(grado_id: str, solo_activos: bool = False) -> int:
    consulta = select(func.count()).select_from(Curso).where(
        Curso.grade_id == grado_id, Curso.deleted_at.is_(None)
    )
    if solo_activos:
        consulta = consulta.where(Curso.status == EstadoRegistro.ACTIVO)
    return bd.session.execute(consulta).scalar_one()


class ServicioGrados(ServicioCRUD):
    modelo = Grado
    modulo = "Grados"
    articulo = "el"
    sustantivo = "grado"
    campo_etiqueta = "name"
    orden_defecto = "position"

    ordenables = {
        "createdAt": Grado.created_at,
        "position": Grado.position,
        "code": Grado.code,
        "name": Grado.name,
        "level": Grado.level,
        "status": Grado.status,
    }
    buscables = (Grado.code, Grado.name, Grado.description)

    # ── Consultas ────────────────────────────────────────────────────

    @classmethod
    def aplicar_filtros(cls, consulta, paginacion: Paginacion):
        consulta = super().aplicar_filtros(consulta, paginacion)

        nivel = request.args.get("level")
        if nivel in {n.value for n in NivelEducativo}:
            consulta = consulta.where(Grado.level == NivelEducativo(nivel))
        return consulta

    @classmethod
    def serializar(cls, fila: Grado) -> dict:
        return {
            **cls.campos_comunes(fila),
            "code": fila.code,
            "name": fila.name,
            "level": fila.level.value,
            "levelName": ETIQUETA_NIVEL_EDUCATIVO.get(fila.level.value, fila.level.value),
            "position": fila.position,
            "description": fila.description,
            "isSystem": fila.is_system,
            "_count": {"courses": _contar_cursos(fila.id)},
        }

    @classmethod
    def opciones(cls) -> list[dict]:
        """Grados activos, en el orden de la escalera educativa."""
        filas = bd.session.execute(
            select(Grado)
            .where(Grado.deleted_at.is_(None), Grado.status == EstadoRegistro.ACTIVO)
            .order_by(Grado.position.asc())
        ).scalars()
        return [
            {
                "id": f.id,
                "code": f.code,
                "name": f.name,
                "level": f.level.value,
                "levelName": ETIQUETA_NIVEL_EDUCATIVO.get(f.level.value, f.level.value),
            }
            for f in filas
        ]

    @classmethod
    def por_nivel(cls) -> list[dict]:
        """
        Los grados agrupados por nivel educativo.

        Es como los presenta la ley y como los entiende cualquiera del centro:
        preescolar, primaria, secundaria y media.
        """
        filas = bd.session.execute(
            select(Grado)
            .where(Grado.deleted_at.is_(None))
            .order_by(Grado.position.asc())
        ).scalars()

        niveles: dict[str, dict] = {}
        for grado in filas:
            clave = grado.level.value
            if clave not in niveles:
                niveles[clave] = {
                    "level": clave,
                    "levelName": ETIQUETA_NIVEL_EDUCATIVO.get(clave, clave),
                    "grades": [],
                }
            niveles[clave]["grades"].append(
                {
                    "id": grado.id,
                    "code": grado.code,
                    "name": grado.name,
                    "position": grado.position,
                    "status": grado.status.value,
                    "courses": _contar_cursos(grado.id, solo_activos=True),
                }
            )

        return list(niveles.values())

    # ── Mutaciones ───────────────────────────────────────────────────

    @classmethod
    def construir(cls, datos: dict) -> Grado:
        return Grado(
            code=datos["code"],
            name=datos["name"],
            level=datos["level"],
            position=datos["position"],
            description=datos.get("description") or None,
            status=datos.get("status") or EstadoRegistro.ACTIVO,
            is_system=False,
        )

    @classmethod
    def gancho_antes_de_actualizar(cls, fila: Grado, datos: dict) -> None:
        if fila.is_system:
            # Los grados de la ley no cambian de código, nivel ni orden
            return
        codigo = datos.get("code")
        if codigo and codigo != fila.code:
            cls.exige_unico(
                Grado.code, codigo, "Ya existe un grado con ese código", excluir=fila.id
            )

    @classmethod
    def aplicar_cambios(cls, fila: Grado, datos: dict) -> None:
        # El código, el nivel y la posición de los grados de la ley no se tocan.
        if not fila.is_system:
            if datos.get("code") is not None:
                fila.code = datos["code"]
            if datos.get("level") is not None:
                fila.level = datos["level"]
            if datos.get("position") is not None:
                fila.position = datos["position"]
        if datos.get("name") is not None:
            fila.name = datos["name"]
        if "description" in datos:
            fila.description = datos["description"] or None
        if datos.get("status") is not None:
            fila.status = datos["status"]

    @classmethod
    def liberar_claves_unicas(cls, fila: Grado) -> None:
        """
        Deja libre el código para poder volver a crear ese grado.

        El código de un grado son diez caracteres contados, así que aquí no
        cabe la marca de tiempo que usan los demás módulos: truncada pierde
        los dígitos que la hacen distinta y dos bajas del mismo grado
        chocarían. Se usa el identificador, que ya es único por definición.
        """
        fila.code = f"{fila.code[:1]}.{fila.id[:8]}"

    # ── Reglas propias ───────────────────────────────────────────────

    @classmethod
    def gancho_impide_inactivar(cls, fila: Grado) -> str | None:
        activos = _contar_cursos(fila.id, solo_activos=True)
        if activos:
            return (
                f"No es posible inactivar el grado: tiene {activos} curso(s) activo(s). "
                "Inactive primero sus cursos."
            )
        return None

    @classmethod
    def gancho_impide_eliminar(cls, fila: Grado) -> str | None:
        if fila.is_system:
            return (
                "Los grados los establece la Ley 115 de 1994 y no se eliminan. "
                "Si la institución no lo ofrece, inactívelo."
            )
        cursos = _contar_cursos(fila.id)
        if cursos:
            return f"No es posible eliminar el grado: tiene {cursos} curso(s) asociado(s)"
        return None
