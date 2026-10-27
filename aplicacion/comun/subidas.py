"""
Adjuntos: fotografías de docentes y documentos de justificación.

Sustituye a Multer y a sharp. Pillow hace el mismo tratamiento: respeta la
orientación de la cámara, recorta al centro en cuadrado, reduce a 512 px y
reescribe como WEBP.

El archivo no se guarda en el disco: se devuelve normalizado para que el módulo
que lo pide lo almacene en la base de datos. Así viaja con el respaldo, no
quedan archivos huérfanos al eliminar un docente y no hay que sincronizar una
carpeta aparte.

Normalizar siempre al mismo formato y tamaño evita que un archivo de 5 MB
acabe ocupando eso mismo en cada fila.

`normalizar_documento` es la variante para las excusas: allí no se recorta nada
porque el texto del soporte tiene que seguir siendo legible, y admite PDF,
que Pillow no abre.
"""

from __future__ import annotations

import io
import re

from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.datastructures import FileStorage

from .errores import SolicitudInvalida

LADO = 512
CALIDAD = 82
MAXIMO_BYTES = 5 * 1024 * 1024
TIPO_GUARDADO = "image/webp"

TIPOS_ADMITIDOS = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def normalizar_foto(archivo: FileStorage) -> tuple[bytes, str]:
    """
    Comprueba y normaliza la imagen recibida.

    Devuelve el contenido en WEBP y su tipo. El tipo que declara el navegador
    solo sirve de primer filtro: la comprobación real la hace Pillow al abrir
    el contenido, porque la extensión y la cabecera se pueden falsear.
    """
    if archivo is None or not archivo.filename:
        raise SolicitudInvalida("No se recibió ningún archivo")

    if archivo.mimetype not in TIPOS_ADMITIDOS:
        raise SolicitudInvalida(
            "Formato no admitido. Use una imagen JPG, PNG, WEBP o GIF de máximo 5 MB."
        )

    try:
        with Image.open(archivo.stream) as imagen:
            # Respeta la orientación EXIF de las fotos de celular
            imagen = ImageOps.exif_transpose(imagen)
            imagen = imagen.convert("RGB")
            # Recorte centrado al cuadrado, igual que `fit: cover`
            imagen = ImageOps.fit(imagen, (LADO, LADO), method=Image.LANCZOS, centering=(0.5, 0.4))

            memoria = io.BytesIO()
            imagen.save(memoria, format="WEBP", quality=CALIDAD)
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise SolicitudInvalida("El archivo no es una imagen válida o está dañado.") from error

    return memoria.getvalue(), TIPO_GUARDADO


# ── Documentos de justificación ───────────────────────────────────────
# Una excusa se apoya en un papel: una incapacidad, un permiso, un oficio. El
# texto importa, así que aquí no se recorta ni se reescala a un tamaño fijo.

MAXIMO_DOCUMENTO_BYTES = 5 * 1024 * 1024

TIPOS_DOCUMENTO = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

# Cuánto se reduce como máximo una imagen de Supporting. Un celular moderno
# entrega 12 megapíxeles; guardarlos tal cual ocuparía la fila sin que nadie
# imprima ese tamaño.
LADO_DOCUMENTO = 2000


def normalizar_documento(archivo: FileStorage) -> tuple[bytes, str, str, int]:
    """
    Comprueba el adjunto de una excusa.

    Devuelve el contenido, el nombre, el tipo y el tamaño. A diferencia de la
    fotografía, aquí el archivo puede ser un PDF: se comprueba por su firma
    (`%PDF`) y de paso se descarta, porque un PDF no es una imagen y no tiene
    nada que normalizar.
    """
    if archivo is None or not archivo.filename:
        raise SolicitudInvalida("Adjunte el documento que respalda la excusa")

    if archivo.mimetype not in TIPOS_DOCUMENTO:
        raise SolicitudInvalida(
            "Formato no admitido. Use un PDF o una imagen JPG, PNG o WEBP de máximo 5 MB."
        )

    contenido = archivo.read()

    if len(contenido) > MAXIMO_DOCUMENTO_BYTES:
        raise SolicitudInvalida("El documento supera el máximo de 5 MB")

    nombre = _nombre_seguro(archivo.filename)
    tipo = archivo.mimetype

    if tipo == "application/pdf":
        if not contenido.startswith(b"%PDF"):
            raise SolicitudInvalida("El archivo no es un PDF válido")
        return contenido, nombre, tipo, len(contenido)

    # Una imagen se abre de verdad: la extensión y la cabecera se pueden
    # falsear, el contenido no miente cuando lo lee Pillow.
    try:
        with Image.open(io.BytesIO(contenido)) as imagen:
            imagen = ImageOps.exif_transpose(imagen)

            # El alfa de un PNG transparente no tiene sentido en un documento
            # impreso: sobre negro deja zonas negras. Se compone sobre blanco.
            if imagen.mode in ("RGBA", "LA", "P"):
                fondo = Image.new("RGB", imagen.size, (255, 255, 255))
                fondo.paste(imagen.convert("RGBA"), mask=imagen.convert("RGBA").split()[-1])
                imagen = fondo
            else:
                imagen = imagen.convert("RGB")

            if max(imagen.size) > LADO_DOCUMENTO:
                imagen.thumbnail((LADO_DOCUMENTO, LADO_DOCUMENTO), Image.LANCZOS)

            memoria = io.BytesIO()
            imagen.save(memoria, format="JPEG", quality=CALIDAD, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise SolicitudInvalida("El documento no es una imagen válida o está dañado.") from error

    guardado = memoria.getvalue()
    return guardado, nombre, "image/jpeg", len(guardado)


def _nombre_seguro(original: str) -> str:
    """
    Deja solo el nombre del archivo, sin la ruta que declare el cliente.

    Un navegador puede enviar `C:\\Users\\...\\informe.pdf`; guardarlo tal
    cual escribiría fuera de donde se espera. Se quitan las separadoras y se
    limita la longitud.
    """
    nombre = original.replace("\\", "/").split("/")[-1].strip()
    nombre = re.sub(r"[^A-Za-z0-9._ -]", "_", nombre)
    if len(nombre) > 150:
        nombre = nombre[-150:]
    return nombre or "documento"
