/**
 * Tabla de listado.
 *
 * Sustituye al componente DataTable en React: paginación en el servidor,
 * ordenación por columna, selección por casillas, tarjetas en móvil y
 * exportación. Los datos vienen de la misma API que ya está verificada.
 */
(() => {
  const vista = JSON.parse(document.getElementById('definicion-vista').textContent);

  const cuerpo = document.getElementById('cuerpo-tabla');
  const tarjetas = document.getElementById('tarjetas');
  const vacio = document.getElementById('vacio');
  const cargando = document.getElementById('cargando');
  const resumen = document.querySelector('[data-resumen]');
  const indicador = document.querySelector('[data-indicador]');
  const barra = document.getElementById('barra-seleccion');

  const parametros = new URLSearchParams(location.search);
  let pagina = Number(parametros.get('page')) || 1;
  let ordenarPor = parametros.get('sortBy') || vista.ordenar || '';
  let orden = parametros.get('sortOrder') || 'desc';

  // ── Presentación de cada tipo de columna ────────────────────────

  const ESTADOS = {
    ACTIVE: ['Activo', 'bg-success/10 text-emerald-700 border-success/20'],
    INACTIVE: ['Inactivo', 'bg-muted text-muted-foreground border-border'],
  };

  const ESTADOS_MARCACION = {
    ON_TIME: ['Puntual', 'bg-success/10 text-emerald-700 border-success/20'],
    LATE: ['Tarde', 'bg-warning/10 text-amber-700 border-warning/20'],
    EARLY_DEPARTURE: ['Salida anticipada', 'bg-destructive/10 text-red-700 border-destructive/20'],
  };

  // Los cuatro niveles de la Ley 115 de 1994, en el orden de la escalera
  // educativa. El color los distingue de un vistazo en el listado.
  const NIVELES = {
    PREESCOLAR: ['Preescolar', 'bg-accent text-accent-foreground border-primary/20'],
    BASICA_PRIMARIA: ['Básica primaria', 'bg-primary/10 text-indigo-700 border-primary/20'],
    BASICA_SECUNDARIA: ['Básica secundaria', 'bg-warning/10 text-amber-700 border-warning/20'],
    MEDIA: ['Educación media', 'bg-success/10 text-emerald-700 border-success/20'],
  };

  const ACCIONES = {
    CREATE: 'Creación', UPDATE: 'Actualización', DELETE: 'Eliminación',
    ACTIVATE: 'Activación', DEACTIVATE: 'Inactivación', LOGIN: 'Inicio de sesión',
    LOGOUT: 'Cierre de sesión', ATTENDANCE: 'Asistencia',
  };

  const esc = Interfaz.escapar;

  /** Lee una ruta con puntos, como `role.name`, sin romperse si falta un tramo. */
  const leer = (objeto, ruta) =>
    ruta.split('.').reduce((valor, parte) => (valor == null ? undefined : valor[parte]), objeto);

  const insignia = (texto, clases) =>
    `<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${clases}">${esc(texto)}</span>`;

  const fecha = (valor) =>
    valor ? new Date(valor).toLocaleDateString('es-CO', { timeZone: 'UTC' }) : '—';

  const fechaHora = (valor) =>
    valor
      ? new Date(valor).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' })
      : '—';

  const hora = (valor) =>
    valor ? new Date(valor).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' }) : '—';

  function avatar(fila) {
    const nombre = `${fila.firstName || ''} ${fila.lastName || ''}`.trim();
    const iniciales = ((fila.firstName || '?')[0] + (fila.lastName || '')[0] || '').toUpperCase();
    const imagen = fila.photoUrl
      ? `<img src="${esc(fila.photoUrl)}" alt="" class="h-9 w-9 rounded-full object-cover"
              onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary',textContent:'${esc(iniciales)}'}))">`
      : `<div class="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">${esc(iniciales)}</div>`;

    return `<div class="flex items-center gap-3">
      ${imagen}
      <div class="min-w-0">
        <p class="truncate font-medium text-foreground">${esc(nombre)}</p>
        <p class="truncate text-xs text-muted-foreground">${esc(fila.email || '')}</p>
      </div>
    </div>`;
  }

  function celda(fila, columna) {
    const bruto = leer(fila, columna.campo);

    switch (columna.tipo) {
      case 'docente':
        return avatar(fila);

      case 'usuario':
        return `<div class="min-w-0">
            <p class="truncate font-medium text-foreground">${esc(fila.firstName)} ${esc(fila.lastName)}</p>
            <p class="truncate text-xs text-muted-foreground">${esc(fila.email)}</p>
          </div>`;

      case 'docente_anidado':
        return `<div class="min-w-0">
            <p class="truncate font-medium text-foreground">${esc(fila.teacher?.firstName)} ${esc(fila.teacher?.lastName)}</p>
            <p class="truncate text-xs text-muted-foreground">${esc(fila.teacher?.code)}</p>
          </div>`;

      case 'asignatura':
        return `<div class="flex items-center gap-2">
            <span class="h-2.5 w-2.5 shrink-0 rounded-full" style="background:${esc(fila.color || '#4F46E5')}"></span>
            <div class="min-w-0">
              <p class="truncate font-medium text-foreground">${esc(fila.name)}</p>
              <p class="truncate text-xs text-muted-foreground">${esc(fila.code)}</p>
            </div>
          </div>`;

      case 'asignatura_anidada':
        return fila.subject
          ? `<span class="inline-flex items-center gap-1.5 text-foreground">
               <span class="h-2 w-2 rounded-full" style="background:${esc(fila.subject.color || '#4F46E5')}"></span>
               ${esc(fila.subject.name)}</span>`
          : '<span class="text-muted-foreground">—</span>';

      case 'asignaturas': {
        const lista = fila.subjects || [];
        if (!lista.length) return '<span class="text-muted-foreground">—</span>';
        return `<div class="flex flex-wrap gap-1">${lista
          .map(
            (a) =>
              `<span class="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                 <span class="h-1.5 w-1.5 rounded-full" style="background:${esc(a.color || '#4F46E5')}"></span>
                 ${esc(a.name)}</span>`,
          )
          .join('')}</div>`;
      }

      case 'cursos': {
        const lista = fila.courses || [];
        if (!lista.length) return '<span class="text-muted-foreground">—</span>';
        return `<div class="flex flex-wrap gap-1">${lista
          .map(
            (c) =>
              `<span class="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs
                            ${c.isHomeroom ? 'border-primary/30 bg-primary/10 text-indigo-700' : 'border-border bg-muted'}"
                     title="${esc(c.gradeName)}${c.isHomeroom ? ' · Director de grupo' : ''}">
                 ${esc(c.name)}${c.isHomeroom ? ' ★' : ''}</span>`,
          )
          .join('')}</div>`;
      }

      case 'estado': {
        const [texto, clases] = ESTADOS[bruto] || ['—', 'bg-muted text-muted-foreground border-border'];
        return insignia(texto, clases);
      }

      case 'estado_marcacion': {
        const [texto, clases] = ESTADOS_MARCACION[bruto] || ['—', 'bg-muted text-muted-foreground border-border'];
        return insignia(texto, clases);
      }

      case 'tipo_marcacion':
        return insignia(
          bruto === 'CHECK_IN' ? 'Entrada' : 'Salida',
          bruto === 'CHECK_IN'
            ? 'bg-primary/10 text-indigo-700 border-primary/20'
            : 'bg-secondary/10 text-slate-700 border-border',
        );

      case 'accion':
        return insignia(ACCIONES[bruto] || bruto, 'bg-accent text-accent-foreground border-primary/20');

      case 'evento':
        return `<div class="min-w-0">
            <p class="truncate font-medium text-foreground">${esc(fila.description)}</p>
            <p class="truncate text-xs text-muted-foreground">${esc(fila.userName || 'Sistema')} · ${esc(fila.userEmail || '')}</p>
          </div>`;

      case 'nivel': {
        const [texto, clases] = NIVELES[bruto] || ['—', 'bg-muted text-muted-foreground border-border'];
        return insignia(texto, clases);
      }

      case 'docente_director':
        return fila.homeroomTeacher
          ? `<div class="min-w-0">
               <p class="truncate text-foreground">${esc(fila.homeroomTeacher.firstName)} ${esc(fila.homeroomTeacher.lastName)}</p>
               <p class="truncate text-xs text-muted-foreground">${esc(fila.homeroomTeacher.code)}</p>
             </div>`
          : '<span class="text-muted-foreground">Sin asignar</span>';

      case 'cupo':
        return bruto
          ? `<span class="whitespace-nowrap">${bruto} estudiantes</span>`
          : '<span class="text-muted-foreground">—</span>';

      case 'insignia':
        return insignia(bruto ?? '—', 'bg-muted text-foreground border-border');

      case 'insignia_anidada':
        return insignia(bruto ?? '—', 'bg-accent text-accent-foreground border-primary/20');

      case 'codigo':
        return `<code class="rounded bg-muted px-1.5 py-0.5 text-xs text-foreground">${esc(bruto)}</code>`;

      case 'destacado':
        return `<span class="font-medium text-foreground">${esc(bruto ?? '—')}</span>`;

      case 'contador':
        return `<span class="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-muted px-2 text-xs font-medium">${bruto ?? 0}</span>`;

      case 'contador_exito':
        return `<span class="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-success/10 px-2 text-xs font-medium text-emerald-700">${bruto ?? 0}</span>`;

      case 'contador_alerta':
        return `<span class="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-warning/10 px-2 text-xs font-medium text-amber-700">${bruto ?? 0}</span>`;

      case 'porcentaje': {
        const valor = Number(bruto ?? 0);
        const color = valor >= 90 ? 'text-emerald-700' : valor >= 70 ? 'text-amber-700' : 'text-red-700';
        return `<span class="font-semibold ${color}">${valor}%</span>`;
      }

      case 'horas':
        return bruto ? `${bruto} h` : '<span class="text-muted-foreground">—</span>';

      case 'horas_rango':
        return `<span class="whitespace-nowrap font-medium text-foreground">${esc(fila.checkInTime)} – ${esc(fila.checkOutTime)}</span>`;

      case 'minutos':
        return `${bruto ?? 0} min`;

      case 'diferencia': {
        const valor = Number(bruto ?? 0);
        if (valor === 0) return '<span class="text-muted-foreground">A tiempo</span>';
        const color = valor > 0 ? 'text-amber-700' : 'text-emerald-700';
        return `<span class="${color}">${valor > 0 ? '+' : ''}${valor} min</span>`;
      }

      case 'si_no':
        return bruto ? 'Sí' : 'No';

      case 'fecha':
        return fecha(bruto);

      case 'fecha_hora':
        return fechaHora(bruto);

      case 'hora':
        return hora(bruto);

      case 'anidado':
      case 'texto':
      default:
        return bruto ? esc(bruto) : '<span class="text-muted-foreground">—</span>';
    }
  }

  // ── Pintado ─────────────────────────────────────────────────────

  // ── Acciones de fila, como iconos ───────────────────────────────

  const ICONOS_ACCION = {
    editar:
      '<path d="M4 16.5V20h3.5L18 9.5 14.5 6 4 16.5z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>' +
      '<path d="M13.5 7l3.5 3.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
    clave:
      '<rect x="4" y="10" width="16" height="10" rx="2" stroke="currentColor" stroke-width="1.7"/>' +
      '<path d="M8 10V7a4 4 0 118 0v3" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
    inactivar:
      '<circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.7"/>' +
      '<path d="M9 12h6" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>',
    activar:
      '<circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.7"/>' +
      '<path d="M8.5 12.2l2.4 2.4 4.6-4.8" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>',
    eliminar:
      '<path d="M5 7h14M10 11v6M14 11v6M6 7l1 12a2 2 0 002 2h6a2 2 0 002-2l1-12M9 7V5a2 2 0 012-2h2a2 2 0 012 2v2" ' +
      'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
  };

  /**
   * Botón de acción con icono.
   *
   * El texto no desaparece: viaja en `aria-label` para los lectores de
   * pantalla y en `title` para quien pase el ratón por encima.
   */
  function iconoAccion(accion, etiqueta, id, color) {
    return `<button type="button" data-accion="${accion}" data-id="${esc(id)}"
        title="${esc(etiqueta)}" aria-label="${esc(etiqueta)}"
        class="inline-flex h-8 w-8 items-center justify-center rounded-lg transition ${color}">
        <svg viewBox="0 0 24 24" fill="none" class="h-4 w-4" aria-hidden="true">
          ${ICONOS_ACCION[accion]}
        </svg>
      </button>`;
  }

  function botonesFila(fila) {
    if (
      !vista.puede.editar &&
      !vista.puede.activar &&
      !vista.puede.reiniciar_clave &&
      !vista.puede.eliminar
    )
      return '';

    const activo = fila.status === 'ACTIVE';
    const neutro = 'text-muted-foreground hover:bg-muted hover:text-foreground';
    const partes = [];

    if (vista.puede.editar) {
      partes.push(iconoAccion('editar', 'Editar', fila.id, 'text-primary hover:bg-primary/10'));
    }
    if (vista.puede.reiniciar_clave) {
      partes.push(iconoAccion('clave', 'Reiniciar contraseña', fila.id, neutro));
    }
    if (vista.puede.activar && fila.status) {
      partes.push(
        iconoAccion(
          activo ? 'inactivar' : 'activar',
          activo ? 'Inactivar' : 'Activar',
          fila.id,
          activo ? neutro : 'text-emerald-600 hover:bg-success/10',
        ),
      );
    }
    // Los grados de la Ley 115 no se eliminan: se inactivan. El botón se
    // oculta para no ofrecer una acción que el servidor rechazaría.
    if (vista.puede.eliminar && fila.isSystem !== true) {
      partes.push(
        iconoAccion(
          'eliminar',
          'Eliminar',
          fila.id,
          'text-destructive hover:bg-destructive/10',
        ),
      );
    }

    return `<td class="whitespace-nowrap px-4 py-3">
        <div class="flex items-center justify-end gap-0.5">${partes.join('')}</div>
      </td>`;
  }

  // En Asistencia cada fila es una marcación y se identifica por `id`; en
  // Reportes cada fila es un docente y lo que se envía es su `teacherId`.
  const claveFila = (fila) => fila[vista.borrado?.clave_fila || 'id'];

  function pintar(elementos) {
    cuerpo.innerHTML = elementos
      .map((fila) => {
        const casilla = vista.puede.borrado_multiple
          ? `<td class="px-4 py-3"><input type="checkbox" data-seleccion="fila" value="${esc(claveFila(fila))}"
               class="h-4 w-4 rounded border-input text-primary focus:ring-2 focus:ring-ring/40"></td>`
          : '';
        const celdas = vista.columnas
          .map((c) => `<td class="px-4 py-3 align-middle">${celda(fila, c)}</td>`)
          .join('');
        return `<tr data-fila class="transition hover:bg-muted/40">${casilla}${celdas}${botonesFila(fila)}</tr>`;
      })
      .join('');

    // En móvil se muestran las tres primeras columnas, que son las que
    // identifican el registro; el resto obligaría a desplazar en horizontal.
    tarjetas.innerHTML = elementos
      .map((fila) => {
        const casilla = vista.puede.borrado_multiple
          ? `<input type="checkbox" data-seleccion="fila" value="${esc(claveFila(fila))}"
               class="mt-1 h-4 w-4 shrink-0 rounded border-input text-primary">`
          : '';
        const detalle = vista.columnas
          .slice(1, 4)
          .map(
            (c) =>
              `<div class="flex items-center justify-between gap-3 text-sm">
                 <span class="text-muted-foreground">${esc(c.etiqueta)}</span>
                 <span class="min-w-0 text-right">${celda(fila, c)}</span>
               </div>`,
          )
          .join('');
        return `<div data-fila class="flex gap-3 p-4">
            ${casilla}
            <div class="min-w-0 flex-1 space-y-2">
              ${celda(fila, vista.columnas[0])}
              ${detalle}
              <div class="flex justify-end gap-1 pt-1">${botonesFila(fila).replace(/<\/?td[^>]*>/g, '')}</div>
            </div>
          </div>`;
      })
      .join('');

    if (vista.puede.borrado_multiple) {
      const cfg = vista.borrado || {};
      const seleccion = Interfaz.conectarSeleccion(document, (elegidas) => {
        barra.classList.toggle('hidden', elegidas.length === 0);
        barra.classList.toggle('flex', elegidas.length > 0);

        const unidad = elegidas.length === 1 ? cfg.unidad : cfg.unidades;
        const concordancia = elegidas.length === 1 ? 'seleccionado' : 'seleccionados';
        barra.querySelector('[data-cuenta]').textContent =
          `${elegidas.length} ${unidad || 'elemento(s)'} ${concordancia}`;
      });
      barra.__seleccion = seleccion;
    }
  }

  // ── Carga ───────────────────────────────────────────────────────

  function consulta() {
    const p = new URLSearchParams(location.search);
    p.set('page', pagina);
    p.set('limit', 10);
    if (ordenarPor && !vista.sin_ordenar) {
      p.set('sortBy', ordenarPor);
      p.set('sortOrder', orden);
    }
    return p.toString();
  }

  async function cargar() {
    cargando.classList.remove('hidden');
    vacio.classList.add('hidden');

    try {
      const datos = await Api.get(`/${vista.recurso}?${consulta()}`);
      if (!datos) return;

      const elementos = datos.items || [];
      pintar(elementos);

      const meta = datos.meta || { total: 0, page: 1, totalPages: 1 };
      vacio.classList.toggle('hidden', elementos.length > 0);
      resumen.textContent = elementos.length
        ? `Mostrando ${(meta.page - 1) * meta.limit + 1}–${(meta.page - 1) * meta.limit + elementos.length} de ${meta.total} registro(s)`
        : '';
      indicador.textContent = `${meta.page} / ${meta.totalPages}`;

      document.querySelector('[data-pagina="anterior"]').disabled = !meta.hasPreviousPage;
      document.querySelector('[data-pagina="siguiente"]').disabled = !meta.hasNextPage;

      document.querySelectorAll('[data-flecha]').forEach((nodo) => {
        const suyo = nodo.dataset.flecha === ordenarPor;
        nodo.textContent = suyo ? (orden === 'asc' ? '↑' : '↓') : '↕';
        nodo.classList.toggle('opacity-60', !suyo);
      });
    } catch (error) {
      Interfaz.aviso(error.mensaje, 'error');
      vacio.classList.remove('hidden');
    } finally {
      cargando.classList.add('hidden');
    }
  }

  // ── Catálogos de los filtros ────────────────────────────────────

  async function cargarCatalogos() {
    for (const select of document.querySelectorAll('[data-catalogo]')) {
      try {
        const opciones = await Api.get(`/${select.dataset.catalogo}/options`);
        (opciones || []).forEach((opcion) => {
          const nodo = document.createElement('option');
          nodo.value = opcion.id;
          nodo.textContent =
            opcion.name || `${opcion.firstName || ''} ${opcion.lastName || ''}`.trim();
          if (opcion.id === select.dataset.elegido) nodo.selected = true;
          select.appendChild(nodo);
        });
      } catch (_) {
        // Un catálogo que no carga deja el filtro vacío, sin romper la página
      }
    }
  }

  // ── Interacción ─────────────────────────────────────────────────

  document.querySelectorAll('[data-ordenar]').forEach((boton) =>
    boton.addEventListener('click', () => {
      const campo = boton.dataset.ordenar;
      orden = ordenarPor === campo && orden === 'asc' ? 'desc' : 'asc';
      ordenarPor = campo;
      pagina = 1;
      cargar();
    }),
  );

  document.querySelector('[data-pagina="anterior"]').addEventListener('click', () => {
    if (pagina > 1) { pagina -= 1; cargar(); }
  });
  document.querySelector('[data-pagina="siguiente"]').addEventListener('click', () => {
    pagina += 1; cargar();
  });

  document.querySelectorAll('[data-exportar]').forEach((boton) =>
    boton.addEventListener('click', async () => {
      const ruta = boton.dataset.exportar || `/${vista.recurso}/export`;
      const separador = ruta.includes('?') ? '&' : '?';
      try {
        await Api.descargar(`${ruta}${separador}${consulta()}`, `${vista.nombre}.xlsx`);
        Interfaz.aviso('Descarga generada', 'exito');
      } catch (error) {
        Interfaz.aviso(error.mensaje, 'error');
      }
    }),
  );

  // Editar, contraseña, activar, inactivar y eliminar
  document.addEventListener('click', async (evento) => {
    const boton = evento.target.closest('[data-accion]');
    if (!boton) return;

    const { accion, id } = boton.dataset;

    // ── Editar ────────────────────────────────────────────────────
    if (accion === 'editar') {
      try {
        // Se pide el detalle: trae las relaciones que el listado no incluye
        const registro = await Api.get(`/${vista.recurso}/${id}`);
        await Formulario.abrir(vista.formulario, registro);
        // Se recarga siempre, no solo al guardar: la fotografía se sube dentro
        // del propio diálogo y puede haber cambiado aunque se cierre sin más.
        cargar();
      } catch (error) {
        Interfaz.aviso(error.mensaje, 'error');
      }
      return;
    }

    // ── Reiniciar contraseña ──────────────────────────────────────
    if (accion === 'clave') {
      await reiniciarClave(id);
      return;
    }

    // ── Eliminar ──────────────────────────────────────────────────
    if (accion === 'eliminar') {
      const confirmado = await Interfaz.confirmar({
        titulo: `Eliminar ${vista.singular}`,
        texto: 'Esta acción marca el registro como eliminado y queda constancia en la auditoría. ¿Desea continuar?',
        etiqueta: 'Eliminar',
      });
      if (!confirmado) return;
    }

    try {
      if (accion === 'eliminar') await Api.delete(`/${vista.recurso}/${id}`);
      else await Api.patch(`/${vista.recurso}/${id}/${accion === 'activar' ? 'activate' : 'deactivate'}`);

      Interfaz.aviso('Cambio aplicado', 'exito');
      cargar();
    } catch (error) {
      // Cuando una regla del sistema impide la acción, el motivo es lo
      // importante: se muestra más tiempo para que dé tiempo a leerlo.
      Interfaz.aviso(error.mensaje, 'error', error.codigo === 400 ? 8000 : 5000);
    }
  });

  /** Diálogo corto para asignar una contraseña nueva a un usuario. */
  async function reiniciarClave(id) {
    const definicion = {
      recurso: 'users',
      singular: 'contraseña',
      campos: [
        {
          campo: 'newPassword',
          etiqueta: 'Contraseña nueva',
          tipo: 'clave',
          obligatorio: true,
          ancho: 'completo',
          ayuda: 'Mínimo 8 caracteres, con mayúscula, minúscula y número. El usuario deberá cambiarla al entrar.',
        },
      ],
    };

    // Se reutiliza el diálogo, pero enviando al punto de reinicio
    const nodo = await Formulario.abrir(
      { ...definicion, envio: { ruta: `/users/${id}/reset-password`, metodo: 'PATCH' } },
      null,
    );
    if (nodo) cargar();
  }

  // ── Borrado múltiple ────────────────────────────────────────────

  const borrar = document.getElementById('borrar-seleccion');
  if (borrar && vista.borrado) {
    borrar.addEventListener('click', async () => {
      const elegidos = barra.__seleccion.seleccionadas();
      if (!elegidos.length) return;

      const cfg = vista.borrado;
      const unidad = elegidos.length === 1 ? cfg.unidad : cfg.unidades;

      // El periodo sale de los filtros que están puestos en pantalla
      const filtros = new URLSearchParams(location.search);
      const desde = filtros.get('dateFrom');
      const hasta = filtros.get('dateTo');

      let periodo = 'todo el histórico';
      if (desde && hasta) periodo = `del ${desde} al ${hasta}`;
      else if (desde) periodo = `desde el ${desde}`;
      else if (hasta) periodo = `hasta el ${hasta}`;

      const texto = cfg.con_periodo
        ? `Se eliminarán todas las marcaciones de ${elegidos.length} ${unidad} en el periodo ${periodo}.`
        : `Va a eliminar ${elegidos.length} ${unidad}.`;

      const detalle =
        '<p class="font-medium text-foreground">Qué ocurre exactamente</p>' +
        '<ul class="mt-1 list-disc space-y-0.5 pl-4">' +
        '<li>Los registros quedan marcados como eliminados, no se borran de la base.</li>' +
        '<li>La auditoría guarda el detalle y su nombre como responsable.</li>' +
        '<li>Esta acción está reservada al rol con control total.</li>' +
        '</ul>' +
        (cfg.con_periodo && !desde && !hasta
          ? '<p class="mt-2 font-medium text-destructive">No hay filtro de fechas: se eliminará el histórico completo de esos docentes.</p>'
          : '');

      const confirmado = await Interfaz.confirmar({
        titulo: cfg.titulo,
        texto,
        detalle,
        etiqueta: `Sí, eliminar`,
      });
      if (!confirmado) return;

      const cuerpo = { [cfg.campo]: elegidos };
      if (cfg.con_periodo) {
        if (desde) cuerpo.dateFrom = desde;
        if (hasta) cuerpo.dateTo = hasta;
      }

      try {
        const resultado = await Api.post(cfg.ruta, cuerpo);
        Interfaz.aviso(resultado.message, 'exito', 6000);
        cargar();
      } catch (error) {
        Interfaz.aviso(error.mensaje, 'error', 7000);
      }
    });
  }

  const nuevo = document.querySelector('[data-nuevo]');
  if (nuevo) {
    nuevo.addEventListener('click', async () => {
      const guardado = await Formulario.abrir(vista.formulario, null);
      if (guardado) {
        pagina = 1;
        cargar();
      }
    });
  }

  Interfaz.conectarFiltros(document.getElementById('filtros'));
  cargarCatalogos();
  cargar();
})();
