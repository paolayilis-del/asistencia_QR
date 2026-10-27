"""Validación de excusas. Sustituye a `dto/excuse.dto.ts`."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...modelos import EstadoExcusa, TipoExcusa


class PresentarExcusa(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: TipoExcusa
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    reason: str = Field(min_length=10, max_length=1000)
    attendanceId: str | None = None


class RevisarExcusa(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: EstadoExcusa
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("status")
    @classmethod
    def _solo_estados_finales(cls, valor: EstadoExcusa) -> EstadoExcusa:
        """
        Descarta `PENDING` como resultado de una revisión.

        Aceptarlo dejaría "revisada" una solicitud que en realidad sigue sin
        decidirse, y el servicio solo protege contra el estado anterior, no
        contra el nuevo.
        """
        if valor not in (EstadoExcusa.APROBADA, EstadoExcusa.RECHAZADA):
            raise ValueError("La justificación solo puede quedar aprobada o rechazada")
        return valor
