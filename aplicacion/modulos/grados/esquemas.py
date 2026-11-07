"""Validación de grados."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ...modelos import EstadoRegistro, NivelEducativo


class CrearGrado(BaseModel):
    """
    Alta de un grado.

    Los catorce de la Ley 115 vienen cargados; esto queda para los casos que
    la propia ley contempla aparte, como los ciclos de educación de adultos.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=2, max_length=60)
    level: NivelEducativo
    position: int = Field(ge=1, le=30)
    description: str | None = Field(default=None, max_length=300)
    status: EstadoRegistro | None = None


class ActualizarGrado(BaseModel):
    """
    Modificación de un grado.

    En los grados del sistema (Ley 115) solo cambian el nombre visible, la
    descripción y si se ofrece. En los grados propios de la institución
    también se pueden corregir el código, el nivel y el orden.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str | None = Field(default=None, min_length=1, max_length=10)
    name: str | None = Field(default=None, min_length=2, max_length=60)
    level: NivelEducativo | None = None
    position: int | None = Field(default=None, ge=1, le=30)
    description: str | None = Field(default=None, max_length=300)
    status: EstadoRegistro | None = None
