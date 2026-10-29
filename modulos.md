# Módulos más importantes del backend

Backend en Flask (migrado de NestJS). Módulos y archivos: `aplicacion/modulos/*`.

Los 3 módulos más importantes:

## 1. `asistencia` — el corazón del negocio

`aplicacion/modulos/asistencia/servicio.py` concentra las reglas de negocio
**RN001–RN009** del registro por QR. La función clave es `registrar()`:

```python
def registrar(tipo, docente_id_pedido, notas, actor, ctx, latitude=None, ...) -> dict:
    momento = ahora()
    zona = configuracion.texto(configuracion.CLAVES["ZONA_HORARIA"], "America/Bogota")
    docente_id = _resolver_docente(docente_id_pedido, actor)

    # RN001/R002 — docente y cuenta deben existir y estar activos
    docente = bd.session.execute(
        select(Docente).where(Docente.id == docente_id, Docente.deleted_at.is_(None))
    ).scalar_one_or_none()
    if docente is None:
        raise NoEncontrado("El docente no existe")
    if docente.status != EstadoRegistro.ACTIVO:
        raise Prohibido("RN002 · El docente se encuentra inactivo...")
    if docente.usuario and docente.usuario.status != EstadoRegistro.ACTIVO:
        raise Prohibido("RN002 · La cuenta de usuario del docente está inactiva...")

    # RN003 — debe existir horario aplicable para hoy
    horario = _resolver_horario(docente_id, momento, tipo, zona)

    # RN004/R005/R006 — secuencia: sin dos entradas ni dos salidas; sin salida sin entrada
    fecha = clave_fecha(momento, zona)
    _validar_secuencia(docente_id, tipo, fecha)

    # RN007/R008 — puntualidad contra la tolerancia del horario
    estado, diferencia, hora_esperada = _evaluar_puntualidad(horario, tipo, clave_hora(momento, zona))

    marcacion = Marcacion(id=nuevo_id(), teacher_id=docente_id, schedule_id=horario.id,
        type=tipo, status=estado, date=solo_fecha(fecha), registered_at=momento,
        expected_time=hora_esperada, minutes_diff=diferencia, ...)
    bd.session.add(marcacion); bd.session.flush()

    # RN009 — toda marcación queda auditada
    auditoria.anotar(AccionAuditoria.ASISTENCIA, MODULO, "...", entidad_id=marcacion.id, ...)
    bd.session.commit()
    return {**serializar(marcacion), "message": _mensaje(tipo, estado, diferencia)}
```

**Por qué importa:** aquí se decide quién puede marcar, contra qué horario, si llegó
tarde/puntual/salió anticipado, si secuencia entrada→salida es válida, y la validación
geográfica (radio del colegio). Cada función auxiliar (`_resolver_horario`,
`_validar_secuencia`, `_evaluar_puntualidad`) implementa una RN documentada.

---

## 2. `auth` — autenticación, tokens y bloqueos

`aplicacion/modulos/auth/servicio.py`. El login valida credenciales, bloquea por
intentos fallidos y emite el par de tokens:

```python
def entrar(email, clave, ctx) -> dict:
    usuario = bd.session.execute(
        select(Usuario).where(Usuario.email == email, Usuario.deleted_at.is_(None))
        .options(selectinload(Usuario.rol))
    ).scalar_one_or_none()

    if usuario is None:
        raise NoAutorizado(ERROR_GENERICO)  # respuesta uniforme: no revela si el correo existe

    if usuario.locked_until and usuario.locked_until > ahora:
        minutos = math.ceil(...)
        raise Prohibido(f"Cuenta bloqueada temporalmente... Intente en {minutos} minuto(s).")

    if not verificar_contrasena(clave, usuario.password):
        _anotar_intento_fallido(usuario)   # suma intento, bloquea al llegar al máximo
        raise NoAutorizado(ERROR_GENERICO)

    if usuario.status != EstadoRegistro.ACTIVO:
        raise Prohibido("El usuario se encuentra inactivo...")
    if usuario.rol.status != EstadoRegistro.ACTIVO:
        raise Prohibido("El rol asignado se encuentra inactivo.")

    permisos = _permisos_de(usuario.role_id)
    tokens = _emitir(usuario, ctx)   # access + refresh (guardado SOLO como huella SHA-256)
    auditoria.anotar(AccionAuditoria.ENTRAR, MODULO, ...)
    bd.session.commit()
    return {**tokens, "user": perfil(usuario, permisos)}
```

Además: `refrescar()` rota el refresh token (revoca el usado), `salir()` revoca todas
las sesiones y `cambiar_contrasena()` invalida sesiones abiertas.

---

## 3. `docentes` — gestión del docente (CRUD + foto + horarios)

`aplicacion/modulos/docentes/servicio.py` — una clase `ServicioDocentes(ServicioCRUD)`.
Lo distintivo:

```python
@classmethod
def serializar(cls, fila):
    return {
        **cls.campos_comunes(fila),
        "code": fila.code, "firstName": fila.first_name, "lastName": fila.last_name,
        "document": fila.document, "email": fila.email, "phone": fila.phone,
        "photoUrl": fila.photo_url, "userId": fila.user_id,
        "user": {...} if fila.usuario else None,
        "subjects": _asignaturas_de(fila.id),          # aplanadas, sin tabla puente
        "courses": _cursos_de(fila.id),
        "_count": {"schedules": _contar_horarios(fila.id), "attendances": _contar_marcaciones(fila.id)},
    }

@classmethod
def subir_foto(cls, identificador, archivo, actor, ctx):
    contenido, tipo = subidas.normalizar_foto(archivo)
    docente.photo = contenido            # la foto vive en la BD (desde v3.4)
    docente.photo_mime = tipo
    docente.photo_url = cls.ruta_foto(identificador)  # con ?v=tiempo para romper caché
    ...
```

**Por qué importa:** protege la integridad con reglas propias — no se puede inactivar
si tiene horarios activos, no se puede eliminar si tiene marcaciones (evidencia),
`liberar_claves_unicas()` libera código/documento/correo al borrar, y asigna/reemplaza
asignaturas y cursos que dicta (con validación anti-huérfanos).

---

## Bonus: control de acceso

Todo el control de acceso cuelga de `aplicacion/comun/seguridad.py` (`requiere_permisos`,
`requiere_roles`, `UsuarioAutenticado`), que valida en **cada petición** si el usuario/rol
siguen activos — no solo en el login.