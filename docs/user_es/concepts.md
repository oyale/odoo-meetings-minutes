# Conceptos y vocabulario

Toda la guía usa el vocabulario siguiente. Las palabras se muestran en minúsculas
en la interfaz, pero aquí se definen en cursiva.

<div class="concept-map" id="mapa-conceptual" role="group" aria-label="Relación entre series, reuniones, puntos, actas y seguimientos">
  <div class="concept-setup-map">
    <div class="concept-origins">
      <article class="concept-node">
        <span class="concept-map-label">Reuniones recurrentes</span>
        <strong>Serie</strong>
        <p>Valores y políticas que se copian a cada reunión nueva.</p>
      </article>
      <article class="concept-node concept-standalone">
        <span class="concept-map-label">Una reunión</span>
        <strong>Una reunión puntual</strong>
        <p>Sin serie.</p>
      </article>
    </div>
    <div class="concept-map-arrow"><span>crea</span><b aria-hidden="true">→</b></div>
    <article class="concept-node concept-meeting-node">
      <span class="concept-map-label">Evento programado</span>
      <strong>Reunión</strong>
      <div class="concept-meeting-meta"><span>Fecha y personas</span><span>Orden del día</span></div>
    </article>
  </div>

  <div class="concept-map-rule"><span>Orden del día</span></div>
  <div class="concept-point-map">
    <div class="concept-case">
      <article class="concept-node concept-identity-node">
        <span class="concept-map-label">Una participación</span>
        <strong>Punto X</strong>
        <p>Título · descripción · responsable</p>
      </article>
      <div class="concept-map-arrow concept-case-arrow"><b aria-hidden="true">→</b></div>
      <article class="concept-node concept-participation">
        <span class="concept-map-label">Reunión A</span>
        <strong>Participación</strong>
        <p>Discusión, resultado y tiempo.</p>
      </article>
    </div>
    <div class="concept-case">
      <article class="concept-node concept-identity-node">
        <span class="concept-map-label">Varias participaciones</span>
        <strong>Punto Y</strong>
        <p>Título · descripción · responsable</p>
      </article>
      <div class="concept-map-arrow concept-case-arrow"><b aria-hidden="true">→</b></div>
      <div class="concept-case-participations">
        <article class="concept-node concept-participation">
          <span class="concept-map-label">Reunión A</span>
          <strong>Participación</strong>
          <p>Discusión y resultado.</p>
        </article>
        <article class="concept-node concept-participation">
          <span class="concept-map-label">Reunión B</span>
          <strong>Participación</strong>
          <p>Nueva discusión y resultado.</p>
        </article>
      </div>
    </div>
  </div>

  <div class="concept-map-outputs">
    <article class="concept-output">
      <span class="concept-map-label">Registro de la reunión</span>
      <strong>Acta → revisión aprobada + PDF</strong>
      <p>Las notas y resultados de la reunión forman su propio registro formal.</p>
    </article>
    <article class="concept-output">
      <span class="concept-map-label">Tarea pendiente</span>
      <strong>Seguimiento → personas asignadas</strong>
      <p>Un punto abierto puede arrastrarse a un orden del día posterior; la nueva participación tendrá su propio registro.</p>
    </article>
  </div>
</div>

## Objetos básicos

### Reunión
Un evento concreto con fecha, duración, asistentes y orden del día. Sigue un
ciclo de vida (ver [Estados](#estados-de-la-reunión)). Cada reunión pertenece a
una **compañía** y, opcionalmente, a una **serie**.

<div class="object-diagram" role="img" aria-label="Una reunión contiene puntos del orden del día y produce un acta aprobada">
  <div class="object-diagram-node"><strong>Reunión</strong><small>Fecha · asistentes</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-branches">
    <div class="object-diagram-node"><strong>Puntos del orden del día</strong><small>Temas de esta reunión</small></div>
    <div class="object-diagram-node"><strong>Acta</strong><small>Revisión aprobada</small></div>
  </div>
</div>

### Serie
Plantilla de reunión recurrente: quién coordina, asistentes habituales,
duración, zona horaria, patrón de nombre y — sobre todo — sus **políticas**
(cómo continúan los puntos, si se registra el tiempo, cuándo se pueden añadir
puntos, reglas de seguimiento). Los valores de la serie **se copian** en cada
reunión nueva: cambiar la serie después nunca reescribe las reuniones existentes.

<div class="object-diagram" role="img" aria-label="Los valores de la serie se copian en cada reunión nueva">
  <div class="object-diagram-node"><strong>Serie</strong><small>Valores · políticas</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-branches">
    <div class="object-diagram-node"><strong>Reunión A</strong><small>Valores copiados al crearla</small></div>
    <div class="object-diagram-node"><strong>Reunión B</strong><small>Valores copiados al crearla</small></div>
  </div>
</div>

### Punto
Un asunto con identidad propia que puede tratarse en **varias reuniones**. El
punto guarda la información durable: título, descripción, ponente, prioridad,
plazo, vínculos con otros puntos. Mantiene su propio estado (`abierto`,
tratado, cerrado, propuesto…) que sobrevive entre reuniones.

<div class="object-diagram" role="img" aria-label="Un punto conserva su identidad y estado">
  <div class="object-diagram-node object-diagram-record"><strong>Punto X</strong><small>Título · responsable</small><small>Prioridad · plazo</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node"><strong>Estado del punto</strong><small>Abierto · tratado · cerrado</small></div>
</div>

### Participación (punto del orden del día)
Una participación vincula un punto con una reunión concreta. Registra lo
que ocurrió *aquel día*: sus notas de discusión, su resultado, el tiempo dedicado.
Cuando esta guía dice "un punto en la agenda" se refiere a una participación.

<div class="object-diagram" role="img" aria-label="Un punto y una reunión forman una participación del orden del día">
  <div class="object-diagram-node"><strong>Punto X</strong></div>
  <span class="object-diagram-arrow" aria-hidden="true">+</span>
  <div class="object-diagram-node"><strong>Reunión A</strong></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node object-diagram-record"><strong>Participación</strong><small>Notas · resultado · tiempo</small></div>
</div>

### Acuerdo
Una decisión documentada producida en una reunión. En los puntos **decisorios**
el acuerdo lleva el resultado *aprobado/rechazado*. Los acuerdos tienen cuerpo
en texto enriquecido y pueden retirarse durante la reunión en vivo.

<div class="object-diagram" role="img" aria-label="Un punto decisorio se documenta mediante un acuerdo con su resultado">
  <div class="object-diagram-node"><strong>Punto decisorio</strong></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node object-diagram-record"><strong>Acuerdo</strong><small>Texto de la decisión</small><small>Aprobado / rechazado</small></div>
</div>

### Discrepancias y reservas
Una objeción o reserva registrada, con un motivo del catálogo y la persona que
la expresa. Todas las discrepancias registradas aparecen en el acta; las notas
editoriales privadas son un registro independiente.

<div class="object-diagram" role="img" aria-label="Todas las discrepancias registradas aparecen en el acta">
  <div class="object-diagram-node object-diagram-record"><strong>Discrepancia</strong><small>Autoría · motivo · texto</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node"><strong>Acta aprobada</strong></div>
</div>

### Seguimiento
El registro durable de "quién tiene que hacer qué": responsables, plazo y un
mecanismo de ejecución — una **actividad** de Odoo, un **TODO** nativo o (con el
módulo Project) una **tarea de proyecto**. Los seguimientos nacen de puntos y
conservan la trazabilidad con su origen.

<div class="object-diagram" role="img" aria-label="Un punto puede generar un seguimiento asignado a responsables y gestionado en una herramienta">
  <div class="object-diagram-node"><strong>Punto</strong></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node object-diagram-record"><strong>Seguimiento</strong><small>Responsables · plazo</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node"><strong>Actividad / TODO / tarea de Project</strong></div>
</div>

### Acta
El registro escrito de la reunión. Durante la reunión la construye la *pantalla
en vivo*; al pasar la reunión a **Celebrada** se formaliza, y un **aprobador**
la congela en una **revisión** inmutable (con PDF).

<div class="object-diagram" role="img" aria-label="El contenido de la reunión forma un borrador que se congela en una revisión aprobada y un PDF">
  <div class="object-diagram-node"><strong>Contenido de la reunión</strong><small>Notas · resultados</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node"><strong>Acta en borrador</strong></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node object-diagram-record"><strong>Revisión aprobada</strong><small>Instantánea · PDF</small></div>
</div>

### Arrastre
Incluir un punto ya existente en una reunión posterior para continuar su
tratamiento o revisar su seguimiento. Los arrastres pueden proponerse
automáticamente por la política de la serie o solicitarse manualmente.

<div class="object-diagram" role="img" aria-label="El arrastre conserva el origen y crea un punto nuevo en el orden del día de una reunión posterior">
  <div class="object-diagram-node"><strong>Registro de origen</strong><small>Punto · acuerdo · seguimiento</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node object-diagram-record"><strong>Arrastre</strong><small>Motivo · destino</small></div>
  <span class="object-diagram-arrow" aria-hidden="true">→</span>
  <div class="object-diagram-node"><strong>Nuevo punto de agenda</strong><small>Reunión posterior</small></div>
</div>

## Estados de la reunión

| Estado | Significado |
|---|---|
| **Borrador** | En preparación. Se pueden añadir puntos (según la política de la serie). |
| **Programada** | Fecha confirmada. Aparece en calendarios. |
| **En curso** *(visual)* | La reunión programada ha comenzado de verdad. No es un estado almacenado: la insignia y la pantalla en vivo lo reflejan. |
| **Celebrada** | La reunión tuvo lugar; toca redactar el acta formal. |
| **Acta en borrador** | El acta se está escribiendo/ajustando antes de aprobar. |
| **Aprobada** | El acta está congelada. El contenido pasa a solo lectura; cambiarlo exige una nueva **revisión** por enmienda. |
| **Cancelada** | La reunión no se celebrará. |

> **Nota:** con el **seguimiento de tiempo desactivado** (ver
> [políticas de serie](admin/series.md#políticas)) no hay paso "Iniciar reunión":
> una reunión programada va directa a **Finalizar**, y la pantalla en vivo es
> editable desde el principio.

## Resultados de un punto

Cada participación termina con un resultado:

| Resultado | Origen |
|---|---|
| **Tratado** | Puntos informativos/de discusión cubiertos. |
| **Acuerdo (aprobado / rechazado)** | Puntos decisorios con acuerdo registrado. |
| **Pospuesto** | No tratado; opcionalmente movido a otra reunión (arrastre). |
| **Cerrado (resuelto)** | Puntos de discusión/TODO finalizados. |
| **Se revisará en la próxima reunión** | Marca explícita, típica de seguimientos. |

## Dos puntos especiales

Las series pueden añadir automáticamente dos puntos estructurales a cada reunión:

- **Aprobación del acta** (primer punto): lista las reuniones anteriores con el
  acta pendiente de aprobar. Reserva 5 minutos por acta pendiente.
- **Próxima reunión** (último punto): propone la siguiente fecha con la regla de
  la serie (día de la semana, día del mes o cada N días). Reserva 5 minutos.
