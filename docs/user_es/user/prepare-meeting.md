# Preparar una reunión (editor)

Dos puntos de entrada: el asistente **Nueva reunión** (guiado) o abrir una serie y
pulsar **Nueva reunión** allí (el mismo asistente, con la serie preseleccionada).

![Lista de reuniones](img/meetings-list.png)

## El asistente guiado

El asistente recorre seis pasos; *Atrás/Siguiente* son libres y tus cambios se
conservan al cambiar de serie.

1. **Serie** — elige una, o déjala vacía para una reunión independiente. El botón
   *Usar valores de la serie* carga duración y asistentes.
2. **Cuándo** — fecha/hora de inicio, título (pre-rellenado con el patrón
   `{date} {series}`) y duración. La hora de fin se calcula.
3. **Personas** — asistentes (pre-rellenados desde la serie).
4. **Puntos que continúan** — si la política de arrastre es *Revisión*, aquí
   aparecen los puntos arrastrados de reuniones anteriores: **Aceptar** para
   incluir, **Posponer** para ofrecerlos más adelante, **Descartar** para perderlos
   definitivamente. Con política *Automática* ya vienen incluidos.
5. **Agenda** — añade puntos ahora (o después). Reutiliza un punto existente de la
   serie con *Más opciones → Punto existente*.
6. **Revisión** — resumen de todo; **Crear reunión** termina.

> **Consejo:** el asistente copia los valores de la serie; no los enlaza. Cambiar
> la serie después no reescribe la reunión.

## Leer una reunión (itinerario lector)

Los lectores abren las reuniones desde **Meetings → Reuniones** (o el calendario).
Ven la agenda con resultados, notas de discusión, discrepancias publicadas,
acuerdos, seguimientos y — una vez aprobada — el acta con botón de **PDF** en la
pestaña *Revisiones aprobadas*. Todo en solo lectura.

## Añadir puntos

En el formulario de la reunión, **Añadir punto** abre un diálogo centrado:

- **Título** — una línea clara: es lo que leerán los asistentes.
- **Tipo de punto** — decide el comportamiento en vivo (ver
  [catálogos](../admin/catalogs.md#tipos-de-punto-de-agenda)).
- **Descripción** — texto enriquecido: contexto, enlaces, documentos.
- **Planificación** (prioridad, plazo, minutos estimados) y **Responsable**.
- **Más opciones** — reutilizar un punto existente, relacionar puntos, reglas de
  seguimiento.

Los **minutos estimados** vienen pre-rellenados con el valor de la serie (o de la
compañía). El botón **Añadir y continuar** encadena varios puntos rápido.

> **Nota:** la disponibilidad de *Añadir punto* depende del estado de la reunión y de
> la **política de añadir puntos** de su serie — desaparece al vencer el plazo y el
> servidor también lo impide.

El aviso el aviso de agenda sobre duración aparece cuando la suma de estimaciones
supera la duración prevista. Amplía la duración o recorta la agenda.

![Asistente de punto](img/point-wizard.png)

## Programación y cambios de serie

- **Programar** confirma la reunión (exige fecha de inicio) y publica el evento de
  calendario.
- La serie puede cambiarse mientras la reunión esté *en borrador o programada* y no
  haya comenzado la ejecución en vivo. Los puntos compartidos con otras reuniones
  limitan el cambio.
- **Cancelar** está disponible en borrador/programada.

## Pestaña Access

Los editores pueden conceder acceso de **lector**/**editor** en las reuniones que
organizan; los gestores también pueden cambiar organizador, secretaría y acceso de
cualquier reunión.

Siguiente: celebrarla → [Reunión en vivo](live-meeting.md).
