"""
Seed idempotente de los docentes y sus usuarios de la IED Los Laureles.

Se ejecuta al arrancar la aplicación (servidor.py) y también durante el
build (init_db.py). Es seguro repetirlo: no inserta duplicados.

Usa psycopg2 directamente contra DATABASE_URL para que funcione fuera de
la sesión de SQLAlchemy. Adapta las columnas a lo que exista en la BD.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg2


def _url_bd() -> str:
    """DATABASE_URL lista para psycopg2 (sin parámetros incompatibles)."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        try:
            for linea in (Path(__file__).resolve().parent.parent.parent / ".env").read_text().splitlines():
                if linea.startswith("DATABASE_URL="):
                    url = linea.split("=", 1)[1].strip()
                    break
        except FileNotFoundError:
            pass
    if "?" in url:
        base, _, query = url.partition("?")
        resto = "&".join(p for p in query.split("&") if not p.startswith("schema="))
        url = base + ("?" + resto if resto else "")
    return url


def _columnas(cur, tabla: str) -> set[str]:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s",
        (tabla,),
    )
    return {fila[0] for fila in cur.fetchall()}


def _insertar(cur, tabla: str, fila: dict) -> None:
    cols = list(fila.keys())
    marcadores = []
    valores = []
    for c in cols:
        if fila[c] == "__now__":
            marcadores.append("NOW()")
        else:
            marcadores.append("%s")
            valores.append(fila[c])
    # Las columnas se unen aparte: una barra invertida dentro de una f-string
    # solo es válida desde Python 3.12 y el proyecto declara 3.10 como mínimo.
    columnas = '", "'.join(cols)
    sql = (
        f'INSERT INTO "{tabla}" ("{columnas}") '
        f"VALUES ({', '.join(marcadores)})"
    )
    cur.execute(sql, valores)


def _ejecutar_seed(cur) -> dict:
    """Inserta usuarios y docentes del archivo seed_docentes.json."""
    ruta = Path(__file__).resolve().parent / "seed_docentes.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    docentes = datos["docentes"]

    col_usuarios = _columnas(cur, "users")
    col_docentes = _columnas(cur, "teachers")

    if "id" not in col_usuarios or "email" not in col_usuarios:
        return {"error": "la tabla users no tiene las columnas esperadas"}
    if "id" not in col_docentes:
        return {"error": "la tabla teachers no tiene las columnas esperadas"}

    cur.execute("SELECT id FROM roles WHERE code = 'DOCENTE' AND deleted_at IS NULL")
    fila_rol = cur.fetchone()
    if fila_rol is None:
        return {"error": "no existe el rol DOCENTE"}
    rol_docente = fila_rol[0]

    creados_u = 0
    creados_d = 0
    errores = []

    for d in docentes:
        try:
            cur.execute(
                "SELECT 1 FROM users WHERE document=%s OR email=%s LIMIT 1",
                (d["document"], d["email"]),
            )
            if cur.fetchone() is None:
                fila_u = {c: v for c, v in d.items() if c in col_usuarios}
                fila_u.update(
                    {c: v for c, v in {
                        "id": d["usuario_id"],
                        "role_id": rol_docente,
                        "status": "ACTIVE",
                        "must_change_password": True,
                        "created_at": "__now__",
                        "updated_at": "__now__",
                    }.items() if c in col_usuarios}
                )
                _insertar(cur, "users", fila_u)
                creados_u += 1

            cur.execute(
                "SELECT 1 FROM teachers WHERE document=%s OR code=%s LIMIT 1",
                (d["document"], d["code"]),
            )
            if cur.fetchone() is None:
                fila_t = {c: v for c, v in d.items() if c in col_docentes}
                fila_t.update(
                    {c: v for c, v in {
                        "id": d["docente_id"],
                        "user_id": d["usuario_id"],
                        "status": "ACTIVE",
                        "created_at": "__now__",
                        "updated_at": "__now__",
                    }.items() if c in col_docentes}
                )
                _insertar(cur, "teachers", fila_t)
                creados_d += 1
        except Exception as e:  # noqa: BLE001
            errores.append(f"{d['code']}: {e}")

    _normalizar_correos(cur, col_usuarios, col_docentes)

    return {
        "usuarios_creados": creados_u,
        "docentes_creados": creados_d,
        "errores": errores,
    }


def _normalizar_correos(cur, col_usuarios, col_docentes) -> None:
    """Guarda los correos en minúsculas (el login los baja a minúsculas).

    Autocura registros previos guardados con mayúsculas, que de otro modo
    nunca coinciden en la comparación de PostgreSQL.
    """
    if "email" in col_usuarios:
        cur.execute("UPDATE users SET email = lower(email) WHERE email <> lower(email)")
    if "email" in col_docentes:
        cur.execute("UPDATE teachers SET email = lower(email) WHERE email <> lower(email)")


def ejecutar_seed(verbose: bool = True) -> dict:
    """Conecta, aplica el seed con commit por transacción y devuelve el resumen."""
    url = _url_bd()
    if not url:
        return {"error": "DATABASE_URL no configurada"}
    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        resultado = _ejecutar_seed(cur)
        cur.close()
    finally:
        conn.close()

    if verbose:
        if resultado.get("error"):
            print(f"[seed] {resultado['error']}")
        else:
            print(
                f"[seed] usuarios creados: {resultado['usuarios_creados']}, "
                f"docentes creados: {resultado['docentes_creados']}",
                end="",
            )
            if resultado["errores"]:
                print(f", errores: {len(resultado['errores'])}")
                for e in resultado["errores"][:5]:
                    print(f"[seed]   -> {e}")
            else:
                print()
    return resultado


if __name__ == "__main__":
    ejecutar_seed()