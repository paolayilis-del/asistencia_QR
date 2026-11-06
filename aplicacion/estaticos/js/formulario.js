/**
 * Diálogo de alta y edición.
 *
 * Sustituye a los formularios en React Hook Form + Zod del proyecto original.
 * Se construye a partir de la definición que envía el servidor, valida en el
 * navegador antes de enviar y reparte sobre sus campos los errores que
 * devuelve la API.
 */
const Formulario = (() => {

  const esc = Interfaz.escapar;

  const ANCHOS = {
    completo: 'sm:col-span-6',
    mitad: 'sm:col-span-3',
    tercio: 'sm:col-span-2',
  };

  const CLASE_CAMPO =
    'h-11 w-full rounded-lg border border-input bg-card px-3 text-sm text-foreground ' +
    'transition placeholder:text-muted-foreground/60 ' +
    'focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring/30';

  // ── Construcción de cada tipo de campo ──────────────────────────

  function control(definicion, valor) {
    const { campo, tipo } = definicion;
    const v = valor ?? definicion.defecto ?? '';

    // Los campos automáticos no se escriben a mano: los asigna el sistema
    // siguiendo la numeración. Se muestran para que se vean, pero bloqueados.
    if (definicion.automatico) {
      return `<div class="relative">
          <input type="text" name="${campo}" value="${esc(v)}" readonly tabindex="-1"
                 class="${CLASE_CAMPO} cursor-not-allowed bg-muted pr-10 text-muted-foreground">
          <span class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground">
            <svg viewBox="0 0 24 24" fill="none" class="h-4 w-4" aria-hidden="true">
              <rect x="4" y="10" width="16" height="10" rx="2" stroke="currentColor" stroke-width="1.6"/>
              <path d="M8 10V7a4 4 0 118 0v3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
            </svg>
          </span>
        </div>`;
    }

    switch (tipo) {
      case 'parrafo':
        return `<textarea name="${campo}" rows="3"
                  class="${CLASE_CAMPO.replace('h-11', 'min-h-[84px] py-2')}">${esc(v)}</textarea>`;

      case 'numero':
        return `<input type="number" name="${campo}" value="${esc(v)}"
                  ${definicion.minimo != null ? `min="${definicion.minimo}"` : ''}
                  ${definicion.maximo != null ? `max="${definicion.maximo}"` : ''}
                  class="${CLASE_CAMPO}">`;

      case 'hora':
        return `<input type="time" name="${campo}" value="${esc(v)}" class="${CLASE_CAMPO}">`;

      case 'correo':
        return `<input type="email" name="${campo}" value="${esc(v)}"
                  placeholder="usuario@institucion.edu.co" class="${CLASE_CAMPO}">`;

      case 'telefono':
        return `<input type="tel" name="${campo}" value="${esc(v)}" class="${CLASE_CAMPO}">`;

      case 'clave':
        return `<div class="relative">
            <input type="password" name="${campo}" autocomplete="new-password"
                   class="${CLASE_CAMPO} pr-11">
            <button type="button" data-ver-clave
                    class="absolute inset-y-0 right-0 flex items-center px-3 text-muted-foreground
                           transition hover:text-foreground" aria-label="Mostrar contraseña">
              <svg viewBox="0 0 24 24" fill="none" class="h-4 w-4" aria-hidden="true">
                <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"
                      stroke="currentColor" stroke-width="1.6"/>
                <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.6"/>
              </svg>
            </button>
          </div>`;

      case 'color':
        return `<div class="flex items-center gap-2">
            <input type="color" name="${campo}" value="${esc(v || '#4F46E5')}"
                   class="h-11 w-14 cursor-pointer rounded-lg border border-input bg-card p-1">
            <input type="text" data-espejo="${campo}" value="${esc(v || '#4F46E5')}"
                   class="${CLASE_CAMPO}">
          </div>`;

      case 'casilla':
        return `<label class="flex items-center gap-2.5">
            <input type="checkbox" name="${campo}" ${v ? 'checked' : ''}
                   class="h-4 w-4 rounded border-input text-primary focus:ring-2 focus:ring-ring/40">
            <span class="text-sm text-foreground">${esc(definicion.etiqueta)}</span>
          </label>`;

      case 'opciones':
        return `<select name="${campo}" class="${CLASE_CAMPO}">
            ${definicion.opciones
              .map(
                ([valorOpcion, texto]) =>
                  `<option value="${esc(valorOpcion)}" ${
                    String(v) === String(valorOpcion) ? 'selected' : ''
                  }>${esc(texto)}</option>`,
              )
              .join('')}
          </select>`;

      case 'catalogo':
        return `<select name="${campo}" data-catalogo="${definicion.recurso}"
                  data-elegido="${esc(v)}"
                  ${definicion.depende_de ? `data-depende="${definicion.depende_de}" data-parametro="${definicion.parametro}"` : ''}
                  class="${CLASE_CAMPO}">
            <option value="">${esc(definicion.vacio || 'Seleccione…')}</option>
          </select>`;

      case 'multiple':
        return `<div data-multiple="${campo}" data-recurso="${definicion.recurso}"
                     class="max-h-52 space-y-1.5 overflow-y-auto rounded-lg border border-input bg-card p-3">
            <p class="text-sm text-muted-foreground">Cargando…</p>
          </div>`;

      case 'permisos':
        return `<div data-permisos="${campo}"
                     class="max-h-72 space-y-3 overflow-y-auto rounded-lg border border-input bg-card p-3">
            <p class="text-sm text-muted-foreground">Cargando…</p>
          </div>`;

      default:
        return `<input type="text" name="${campo}" value="${esc(v)}" class="${CLASE_CAMPO}">`;
    }
  }

  function bloque(definicion, registro) {
    // Los campos ocultos no se muestran: el sistema los completa solo.
    if (definicion.oculto) {
      const valorOculto = registro?.[definicion.campo] ?? definicion.defecto ?? '';
      return `<input type="hidden" name="${definicion.campo}" value="${esc(valorOculto)}">`;
    }

    if (definicion.tipo === 'casilla') {
      return `<div class="${ANCHOS[definicion.ancho] || ANCHOS.completo}">
          ${control(definicion, registro?.[definicion.campo])}
          ${definicion.ayuda ? `<p class="mt-1 text-xs text-muted-foreground">${esc(definicion.ayuda)}</p>` : ''}
          <p class="hidden text-xs text-destructive" data-error="${definicion.campo}"></p>
        </div>`;
    }

    return `<div class="${ANCHOS[definicion.ancho] || ANCHOS.completo}">
        <label class="mb-1.5 block text-sm font-medium text-foreground">
          ${esc(definicion.etiqueta)}
          ${definicion.obligatorio ? '<span class="text-destructive">*</span>' : ''}
        </label>
        ${control(definicion, registro?.[definicion.campo])}
        ${definicion.ayuda ? `<p class="mt-1 text-xs text-muted-foreground">${esc(definicion.ayuda)}</p>` : ''}
        <p class="hidden text-xs text-destructive" data-error="${definicion.campo}"></p>
      </div>`;
  }

  // ── Carga de catálogos y listas ─────────────────────────────────

  const nombreDe = (opcion) =>
    opcion.name ||
    opcion.fullName ||
    `${opcion.firstName || ''} ${opcion.lastName || ''}`.trim() ||
    opcion.code ||
    opcion.id;

  async function llenarCatalogo(select) {
    const parametros = new URLSearchParams();
    if (select.dataset.depende) {
      const padre = select.form.querySelector(`[name="${select.dataset.depende}"]`);
      if (!padre || !padre.value) {
        // Sin el campo del que depende, el catálogo no tiene sentido todavía
        select.innerHTML = `<option value="">Elija primero ${select.dataset.depende === 'teacherId' ? 'el docente' : 'el campo anterior'}</option>`;
        select.disabled = true;
        return;
      }
      parametros.set(select.dataset.parametro, padre.value);
    }

    select.disabled = false;
    const elegido = select.dataset.elegido;
    const recurso = select.dataset.catalogo;

    try {
      let opciones;
      try {
        opciones = await Api.get(
          `/${recurso}/options${parametros.toString() ? '?' + parametros : ''}`,
        );
      } catch (sinCatalogo) {
        // No todos los módulos ofrecen `/options`: usuarios, por ejemplo, solo
        // expone el listado paginado, y ahí «options» se interpreta como un
        // identificador. Se recurre al listado con un tope amplio.
        if (![400, 404].includes(sinCatalogo.codigo)) throw sinCatalogo;
        parametros.set('limit', '100');
        parametros.set('status', 'ACTIVE');
        const pagina = await Api.get(`/${recurso}?${parametros}`);
        opciones = pagina.items || [];
      }

      const primera = select.querySelector('option');
      select.innerHTML = '';
      if (primera) select.appendChild(primera);

      (opciones || []).forEach((opcion) => {
        const nodo = document.createElement('option');
        nodo.value = opcion.id;
        nodo.textContent = opcion.code
          ? `${opcion.code} · ${nombreDe(opcion)}`
          : opcion.email
            ? `${nombreDe(opcion)} · ${opcion.email}`
            : nombreDe(opcion);
        if (opcion.id === elegido) nodo.selected = true;
        select.appendChild(nodo);
      });
    } catch (error) {
      select.innerHTML = '<option value="">No fue posible cargar el catálogo</option>';
    }
  }

  async function llenarMultiple(caja, elegidos) {
    try {
      const opciones = await Api.get(`/${caja.dataset.recurso}/options`);
      if (!opciones || !opciones.length) {
        caja.innerHTML = '<p class="text-sm text-muted-foreground">No hay opciones disponibles.</p>';
        return;
      }
      caja.innerHTML = opciones
        .map(
          (opcion) => `
          <label class="flex items-center gap-2.5 rounded-md px-1.5 py-1 transition hover:bg-muted/60">
            <input type="checkbox" value="${esc(opcion.id)}"
                   ${(elegidos || []).includes(opcion.id) ? 'checked' : ''}
                   class="h-4 w-4 rounded border-input text-primary focus:ring-2 focus:ring-ring/40">
            <span class="text-sm text-foreground">
              ${opcion.color ? `<span class="mr-1 inline-block h-2 w-2 rounded-full align-middle" style="background:${esc(opcion.color)}"></span>` : ''}
              ${esc(nombreDe(opcion))}
              ${opcion.code ? `<span class="ml-1 text-xs text-muted-foreground">${esc(opcion.code)}</span>` : ''}
            </span>
          </label>`,
        )
        .join('');
    } catch (error) {
      caja.innerHTML = `<p class="text-sm text-destructive">${esc(error.mensaje)}</p>`;
    }
  }

  async function llenarPermisos(caja, elegidos) {
    try {
      const grupos = await Api.get('/permissions/grouped');
      caja.innerHTML = (grupos || [])
        .map(
          (grupo) => `
          <div>
            <div class="flex items-center justify-between gap-2 border-b border-border pb-1">
              <p class="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                ${esc(grupo.module)}
              </p>
              <button type="button" data-grupo="${esc(grupo.module)}"
                      class="text-xs font-medium text-primary transition hover:underline">
                Todos
              </button>
            </div>
            <div class="mt-1.5 grid gap-1 sm:grid-cols-2" data-permisos-grupo="${esc(grupo.module)}">
              ${grupo.permissions
                .map(
                  (permiso) => `
                <label class="flex items-start gap-2 rounded-md px-1.5 py-1 transition hover:bg-muted/60">
                  <input type="checkbox" value="${esc(permiso.id)}"
                         ${(elegidos || []).includes(permiso.id) ? 'checked' : ''}
                         class="mt-0.5 h-4 w-4 rounded border-input text-primary focus:ring-2 focus:ring-ring/40">
                  <span class="min-w-0">
                    <span class="block truncate text-sm text-foreground">${esc(permiso.name)}</span>
                    <code class="block truncate text-[11px] text-muted-foreground">${esc(permiso.code)}</code>
                  </span>
                </label>`,
                )
                .join('')}
            </div>
          </div>`,
        )
        .join('');

      // «Todos» marca o desmarca el grupo entero
      caja.querySelectorAll('[data-grupo]').forEach((boton) =>
        boton.addEventListener('click', () => {
          const casillas = caja.querySelectorAll(
            `[data-permisos-grupo="${boton.dataset.grupo}"] input`,
          );
          const faltaAlguna = [...casillas].some((c) => !c.checked);
          casillas.forEach((c) => (c.checked = faltaAlguna));
        }),
      );
    } catch (error) {
      caja.innerHTML = `<p class="text-sm text-destructive">${esc(error.mensaje)}</p>`;
    }
  }

  // ── Lectura de los valores ──────────────────────────────────────

  function leer(formulario, definicion, esEdicion) {
    const cuerpo = {};
    const relaciones = [];

    definicion.campos.forEach((d) => {
      if (d.solo_crear && esEdicion) return;
      if (d.solo_editar && !esEdicion) return;

      // Las relaciones viajan a su propio punto de la API
      if (d.relacion) {
        const caja = formulario.querySelector(
          `[data-multiple="${d.campo}"], [data-permisos="${d.campo}"]`,
        );
        if (caja) {
          const valores = [...caja.querySelectorAll('input:checked')].map((c) => c.value);
          relaciones.push({ ruta: d.relacion, clave: d.clave_relacion, valores });
        }
        return;
      }

      const control = formulario.querySelector(`[name="${d.campo}"]`);
      if (!control) return;

      if (d.tipo === 'casilla') {
        cuerpo[d.campo] = control.checked;
        return;
      }

      const bruto = control.value.trim();

      if (bruto === '') {
        // Al crear se omite; al editar se envía vacío para poder borrarlo
        if (esEdicion && !d.obligatorio) cuerpo[d.campo] = null;
        return;
      }

      if (d.tipo === 'numero') {
        cuerpo[d.campo] = Number(bruto);
      } else if (d.campo === 'dayOfWeek') {
        cuerpo[d.campo] = Number(bruto);
      } else {
        cuerpo[d.campo] = bruto;
      }
    });

    return { cuerpo, relaciones };
  }

  function validar(formulario, definicion, esEdicion) {
    Interfaz.limpiarErrores(formulario);
    let valido = true;

    definicion.campos.forEach((d) => {
      if (!d.obligatorio) return;
      if (d.solo_crear && esEdicion) return;
      if (d.solo_editar && !esEdicion) return;

      const control = formulario.querySelector(`[name="${d.campo}"]`);
      if (!control || control.value.trim() !== '') return;

      const destino = formulario.querySelector(`[data-error="${d.campo}"]`);
      if (destino) {
        destino.textContent = 'Este campo es obligatorio';
        destino.classList.remove('hidden');
      }
      control.setAttribute('aria-invalid', 'true');
      control.classList.add('border-destructive');
      valido = false;
    });

    return valido;
  }

  // ── Diálogo ─────────────────────────────────────────────────────

  function cerrar() {
    const nodo = document.getElementById('dialogo-formulario');
    if (nodo) nodo.remove();
  }

  /**
   * Abre el formulario. Sin `registro` es un alta; con él, una edición.
   * Devuelve una promesa que resuelve a true si se guardó.
   */
  async function abrir(definicion, registro = null) {
    const esEdicion = Boolean(registro);
    const articulo = definicion.genero === 'la' ? 'Nueva' : 'Nuevo';
    const titulo = definicion.titulo
      ? definicion.titulo
      : esEdicion
        ? `Editar ${definicion.singular}`
        : `${articulo} ${definicion.singular}`;

    cerrar();

    const nodo = document.createElement('div');
    nodo.id = 'dialogo-formulario';
    // Misma superficie que el resto de la interfaz. En pantallas pequeñas se
    // abre desde abajo, como hacían los diálogos del sistema original.
    nodo.className =
      'fixed inset-0 z-50 flex items-end justify-center overflow-y-auto bg-slate-900/40 ' +
      'backdrop-blur-sm sm:items-start sm:p-4';
    nodo.setAttribute('role', 'dialog');
    nodo.setAttribute('aria-modal', 'true');

    nodo.innerHTML = `
      <div class="w-full max-w-2xl rounded-t-2xl border border-border bg-card shadow-elevated
                  animate-slide-up sm:my-8 sm:rounded-xl">
        <div class="flex items-center justify-between gap-3 border-b border-border px-6 py-4">
          <h2 class="text-lg font-semibold text-foreground">${esc(titulo)}</h2>
          <button type="button" data-cerrar
                  class="inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground
                         transition hover:bg-muted hover:text-foreground" aria-label="Cerrar">
            <svg viewBox="0 0 24 24" fill="none" class="h-4 w-4" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
          </button>
        </div>

        <form id="campos-formulario" class="px-6 py-5" novalidate>
          ${definicion.foto ? bloqueFoto(registro) : ''}
          <div class="grid gap-4 sm:grid-cols-6">
            ${definicion.campos
              .filter((d) => !(d.solo_crear && esEdicion) && !(d.solo_editar && !esEdicion))
              .map((d) => bloque(d, registro))
              .join('')}
          </div>
        </form>

        <div class="flex flex-col-reverse gap-2 border-t border-border px-6 py-4 sm:flex-row sm:justify-end">
          <button type="button" data-cerrar
                  class="inline-flex h-10 items-center justify-center rounded-lg border border-border
                         bg-card px-4 text-sm font-medium text-foreground transition hover:bg-muted">
            Cancelar
          </button>
          <button type="button" data-guardar
                  class="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-5
                         text-sm font-semibold text-primary-foreground shadow-glow transition
                         hover:bg-primary-hover disabled:opacity-70">
            <span data-texto>${esEdicion ? 'Guardar cambios' : 'Crear'}</span>
          </button>
        </div>
      </div>`;

    document.body.appendChild(nodo);
    const formulario = nodo.querySelector('#campos-formulario');

    // ── Fotografía ─────────────────────────────────────────────────
    // Al editar se sube en el momento. Al crear todavía no hay a quién
    // asignarla, así que se guarda aquí y se envía en cuanto el registro
    // existe: si el alta falla, no queda ninguna imagen suelta.
    let fotoPendiente = null;
    const foto = definicion.foto ? conectarFoto(definicion, registro, (f) => (fotoPendiente = f)) : null;

    // ── Rellenar catálogos y listas ────────────────────────────────
    formulario.querySelectorAll('[data-catalogo]').forEach((select) => {
      llenarCatalogo(select);
      // Un catálogo que depende de otro se recarga al cambiar el padre
      if (select.dataset.depende) {
        const padre = formulario.querySelector(`[name="${select.dataset.depende}"]`);
        if (padre) {
          padre.addEventListener('change', () => {
            select.dataset.elegido = '';
            llenarCatalogo(select);
          });
        }
      }
    });

    // Al vincular una cuenta de usuario, los datos personales del docente se
    // toman de ella: no hace falta volver a escribirlos.
    const cuentaDocente = formulario.querySelector('[data-catalogo="users"]');
    if (cuentaDocente) {
      const derivados = ['firstName', 'lastName', 'document', 'email', 'phone'];
      const tomarDelUsuario = async () => {
        if (!cuentaDocente.value) return;
        try {
          const usuario = await Api.get(`/users/${cuentaDocente.value}`);
          derivados.forEach((nombre) => {
            const input = formulario.querySelector(`[name="${nombre}"]`);
            if (input && usuario[nombre] != null) input.value = usuario[nombre];
          });
        } catch (sinUsuario) {
          // Si no se puede leer la cuenta, los campos quedan editables a mano
        }
      };
      cuentaDocente.addEventListener('change', tomarDelUsuario);
      if (cuentaDocente.dataset.elegido) tomarDelUsuario();
    }

    for (const caja of formulario.querySelectorAll('[data-multiple]')) {
      const campo = caja.dataset.multiple;
      const elegidos = (registro?.[campo] || registro?.[campo.replace('Ids', 's')] || []).map(
        (x) => (typeof x === 'string' ? x : x.id),
      );
      llenarMultiple(caja, elegidos);
    }

    for (const caja of formulario.querySelectorAll('[data-permisos]')) {
      llenarPermisos(caja, registro?.permissionIds || []);
    }

    // El campo de color y su texto se mantienen en sintonía
    formulario.querySelectorAll('input[type="color"]').forEach((selector) => {
      const espejo = formulario.querySelector(`[data-espejo="${selector.name}"]`);
      if (!espejo) return;
      selector.addEventListener('input', () => (espejo.value = selector.value));
      espejo.addEventListener('change', () => {
        if (/^#[0-9A-Fa-f]{6}$/.test(espejo.value.trim())) selector.value = espejo.value.trim();
      });
    });

    // Código asignado automáticamente al dar de alta
    if (!esEdicion && definicion.sugerir_codigo) {
      const campoCodigo = formulario.querySelector('[name="code"]');
      if (campoCodigo && !campoCodigo.value) {
        campoCodigo.value = 'Asignando…';
        Api.get(definicion.sugerir_codigo)
          .then((datos) => {
            campoCodigo.value = datos ? datos.code : '';
          })
          .catch(() => {
            // Sin número no se puede continuar: se muestra para escribirlo a mano
            campoCodigo.value = '';
            if (campoCodigo.type === 'hidden') {
              campoCodigo.type = 'text';
              campoCodigo.className =
                'h-11 w-full rounded-lg border border-input bg-card px-3 text-sm text-foreground ' +
                'transition placeholder:text-muted-foreground/60 sm:col-span-6 ' +
                'focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring/30';
              const etiqueta = document.createElement('label');
              etiqueta.className = 'mb-1.5 block text-sm font-medium text-foreground sm:col-span-6';
              etiqueta.textContent = 'Código';
              campoCodigo.parentNode.insertBefore(etiqueta, campoCodigo);
            }
            campoCodigo.readOnly = false;
            campoCodigo.classList.remove('cursor-not-allowed', 'bg-muted', 'text-muted-foreground');
            Interfaz.aviso('No se pudo asignar el código automáticamente; escríbalo a mano', 'aviso');
          });
      }
    }

    // ── Cierre ─────────────────────────────────────────────────────
    return new Promise((resolver) => {
      const terminar = (guardado) => {
        document.removeEventListener('keydown', alTeclado);
        cerrar();
        resolver(guardado);
      };

      const alTeclado = (e) => {
        if (e.key === 'Escape') terminar(false);
      };
      document.addEventListener('keydown', alTeclado);

      nodo.querySelectorAll('[data-cerrar]').forEach((boton) =>
        boton.addEventListener('click', () => terminar(false)),
      );
      nodo.addEventListener('click', (e) => {
        if (e.target === nodo) terminar(false);
      });

      // ── Guardar ──────────────────────────────────────────────────
      const guardar = nodo.querySelector('[data-guardar]');
      const texto = guardar.querySelector('[data-texto]');

      guardar.addEventListener('click', async () => {
        if (!validar(formulario, definicion, esEdicion)) {
          Interfaz.aviso('Revise los campos marcados', 'aviso');
          return;
        }

        const { cuerpo, relaciones } = leer(formulario, definicion, esEdicion);

        guardar.disabled = true;
        texto.textContent = 'Guardando…';

        try {
          let resultado;

          if (definicion.envio) {
            // Punto de la API propio, como el reinicio de contraseña
            resultado = await Api[definicion.envio.metodo.toLowerCase()](
              definicion.envio.ruta,
              cuerpo,
            );
          } else if (esEdicion) {
            resultado = await Api.patch(`/${definicion.recurso}/${registro.id}`, cuerpo);
          } else {
            try {
              resultado = await Api.post(`/${definicion.recurso}`, cuerpo);
            } catch (choque) {
              // Si otra persona tomó ese número mientras se rellenaba el
              // formulario, se pide el siguiente y se reintenta una vez.
              const codigoOcupado =
                choque.codigo === 409 && definicion.sugerir_codigo && cuerpo.code;
              if (!codigoOcupado) throw choque;

              const siguiente = await Api.get(definicion.sugerir_codigo);
              cuerpo.code = siguiente.code;
              formulario.querySelector('[name="code"]').value = siguiente.code;
              resultado = await Api.post(`/${definicion.recurso}`, cuerpo);
            }
          }

          // Las relaciones y la fotografía se envían después, ya con el
          // identificador del registro recién creado
          const id = esEdicion ? registro.id : resultado?.id;
          if (id) {
            for (const relacion of relaciones) {
              await Api.patch(relacion.ruta.replace('{id}', id), {
                [relacion.clave]: relacion.valores,
              });
            }

            if (fotoPendiente) {
              texto.textContent = 'Subiendo la fotografía…';
              const datos = new FormData();
              datos.append('file', fotoPendiente);
              await Api.subir(`/${definicion.recurso}/${id}/photo`, datos);
            }
          }

          Interfaz.aviso(
            definicion.envio
              ? resultado?.message || 'Listo'
              : esEdicion
                ? 'Cambios guardados'
                : `${definicion.singular} creado correctamente`,
            'exito',
          );
          terminar(true);
        } catch (error) {
          Interfaz.mostrarErrores(formulario, error);
          Interfaz.aviso(error.mensaje, 'error', 6000);
          guardar.disabled = false;
          texto.textContent = esEdicion ? 'Guardar cambios' : 'Crear';
        }
      });

      formulario.addEventListener('keydown', (e) => {
        // Enter envía, salvo dentro de un área de texto
        if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') {
          e.preventDefault();
          guardar.click();
        }
      });

      const primero = formulario.querySelector('input:not([type="hidden"]), select, textarea');
      if (primero) primero.focus();
    });
  }

  // ── Fotografía del docente ──────────────────────────────────────

  function bloqueFoto(registro) {
    const iniciales = registro
      ? ((registro.firstName || '?')[0] + (registro.lastName || '')[0] || '').toUpperCase()
      : '';

    const vista = registro?.photoUrl
      ? `<img src="${esc(registro.photoUrl)}" alt="" class="h-16 w-16 rounded-full object-cover">`
      : `<div class="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10
                     text-lg font-semibold text-primary">${esc(iniciales || '—')}</div>`;

    return `
      <div class="mb-5 flex items-center gap-4 rounded-lg border border-border bg-muted/40 p-4">
        <div id="vista-foto" class="shrink-0">${vista}</div>
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium text-foreground">Fotografía</p>
          <p class="mt-0.5 text-xs text-muted-foreground">
            JPG, PNG, WEBP o GIF, máximo 5 MB. Se recorta a 512 × 512 y se guarda
            en la base de datos.
          </p>
          <div class="mt-2 flex flex-wrap items-center gap-2">
            <label class="inline-flex h-9 cursor-pointer items-center rounded-lg border border-border
                          bg-card px-3 text-sm font-medium transition hover:bg-muted">
              ${registro?.photoUrl ? 'Cambiar' : 'Elegir imagen'}
              <input type="file" id="archivo-foto" accept="image/*" class="hidden">
            </label>
            <button type="button" id="quitar-foto"
                    class="${registro?.photoUrl ? '' : 'hidden '}inline-flex h-9 items-center rounded-lg px-3
                           text-sm font-medium text-destructive transition hover:bg-destructive/10">
              Quitar
            </button>
            <span id="estado-foto" class="text-xs text-muted-foreground"></span>
          </div>
        </div>
      </div>`;
  }

  /**
   * Conecta el bloque de fotografía del formulario abierto.
   *
   * Editando se sube en el momento, porque el docente ya existe. Creando se
   * guarda la elección y se avisa al formulario, que la enviará cuando tenga
   * el identificador.
   */
  function conectarFoto(definicion, registro, alElegir) {
    const archivo = document.getElementById('archivo-foto');
    const quitar = document.getElementById('quitar-foto');
    const vista = document.getElementById('vista-foto');
    const estado = document.getElementById('estado-foto');
    if (!archivo) return null;

    const esEdicion = Boolean(registro);
    let objeto = null;

    const marcador = () =>
      `<div class="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10
                   text-lg font-semibold text-primary">—</div>`;

    const mostrar = (origen) => {
      vista.innerHTML = `<img src="${origen}" alt="" class="h-16 w-16 rounded-full object-cover">`;
    };

    archivo.addEventListener('change', async () => {
      const fichero = archivo.files[0];
      if (!fichero) return;

      if (fichero.size > 5 * 1024 * 1024) {
        Interfaz.aviso('La imagen supera los 5 MB', 'error');
        archivo.value = '';
        return;
      }

      // Vista previa inmediata, antes de enviar nada
      if (objeto) URL.revokeObjectURL(objeto);
      objeto = URL.createObjectURL(fichero);
      mostrar(objeto);
      quitar.classList.remove('hidden');

      if (!esEdicion) {
        // Se guarda para enviarla cuando el docente exista
        if (alElegir) alElegir(fichero);
        estado.textContent = 'Se guardará al crear el docente';
        return;
      }

      estado.textContent = 'Subiendo…';
      const datos = new FormData();
      datos.append('file', fichero);

      try {
        const actualizado = await Api.subir(`/${definicion.recurso}/${registro.id}/photo`, datos);
        mostrar(actualizado.photoUrl);
        estado.textContent = 'Guardada en la base de datos';
        Interfaz.aviso('Fotografía actualizada', 'exito');
      } catch (error) {
        estado.textContent = '';
        Interfaz.aviso(error.mensaje, 'error');
      } finally {
        archivo.value = '';
      }
    });

    quitar.addEventListener('click', async () => {
      if (objeto) {
        URL.revokeObjectURL(objeto);
        objeto = null;
      }

      if (!esEdicion) {
        if (alElegir) alElegir(null);
        archivo.value = '';
        vista.innerHTML = marcador();
        quitar.classList.add('hidden');
        estado.textContent = '';
        return;
      }

      try {
        await Api.delete(`/${definicion.recurso}/${registro.id}/photo`);
        vista.innerHTML = marcador();
        quitar.classList.add('hidden');
        estado.textContent = '';
        archivo.value = '';
        Interfaz.aviso('Fotografía retirada', 'exito');
      } catch (error) {
        Interfaz.aviso(error.mensaje, 'error');
      }
    });

    return { limpiar: () => objeto && URL.revokeObjectURL(objeto) };
  }

  return { abrir };
})();
