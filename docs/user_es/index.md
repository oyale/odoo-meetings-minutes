# Community Meetings — Guía de uso y administración

<div class="guide-hero">
  <div class="guide-hero-copy">
    <p class="guide-eyebrow">Preparación · reunión en vivo · seguimiento</p>
    <h2>Reuniones más fáciles de llevar, con acuerdos y seguimientos claros.</h2>
    <p>Mantén conectados el orden del día, la conversación, las decisiones y los siguientes pasos. Reutiliza puntos entre reuniones, registra los acuerdos al tomarlos y revisa y aprueba un acta clara.</p>
    <p><a class="guide-cta" href="user/prepare-meeting.md">Prepara tu primera reunión →</a></p>
  </div>
  <img src="img/meetings-list.png" alt="Lista de reuniones de Odoo con fechas, series, organizadores y estado" />
</div>

<div class="guide-features">
  <article>
    <img src="img/meeting-review.png" alt="Asistente de preparación que permite revisar el orden del día elegido" />
    <h3>Prepara la reunión con contexto</h3>
    <p>Organiza el orden del día desde una serie o para una reunión puntual. Recupera los puntos abiertos y comparte un plan claro con las personas convocadas.</p>
    <a href="user/prepare-meeting.md">Cómo preparar una reunión →</a>
  </article>
  <article>
    <img src="img/live-meeting.png" alt="Pantalla de reunión en vivo con puntos, notas y controles" />
    <h3>Mantén el ritmo de la reunión</h3>
    <p>Trabaja un punto cada vez. Anota la conversación, los acuerdos y seguimientos, y aplaza lo que necesite más tiempo.</p>
    <a href="user/live-meeting.md">Descubre la reunión en vivo →</a>
  </article>
  <article>
    <img src="img/minutes-preview.png" alt="Vista previa cuidada de un borrador de acta" />
    <h3>Cierra con un acta útil</h3>
    <p>Revisa el borrador, aprueba el acta y retoma las tareas en la siguiente reunión. Las revisiones aprobadas quedan como registro.</p>
    <a href="user/minutes-and-approval.md">Actas y aprobación →</a>
  </article>
</div>

<aside class="integration-note">
  <strong>Conexiones opcionales.</strong> Si utilizas Odoo Calendar o Project, puedes vincular las reuniones programadas con eventos del calendario y los seguimientos con tareas. Consulta las guías de <a href="integrations/calendar.md">Calendario</a> y <a href="integrations/project.md">Project</a>.
</aside>

<section class="guide-section" id="roles">
  <div class="guide-section-head">
    <p class="guide-eyebrow">Empieza por tu papel</p>
    <div>
      <h2>Encuentra tu lugar en la reunión</h2>
      <p>Elige el trabajo que haces y empieza por el paso que te resulte útil.</p>
    </div>
  </div>
  <div class="role-list">
    <a class="role-row" href="user/prepare-meeting.md#leer-una-reunion">
      <span class="role-number">01</span><span class="role-copy"><strong>Lector</strong><small>Consulta agendas, vistas previas de borradores y actas aprobadas.</small></span><span class="role-action">Abrir una reunión <span aria-hidden="true">→</span></span>
    </a>
    <a class="role-row" href="user/propose-a-point.md">
      <span class="role-number">02</span><span class="role-copy"><strong>Proponente</strong><small>Sugiere un asunto para un próximo orden del día.</small></span><span class="role-action">Proponer un punto <span aria-hidden="true">→</span></span>
    </a>
    <a class="role-row" href="user/prepare-meeting.md">
      <span class="role-number">03</span><span class="role-copy"><strong>Editor</strong><small>Prepara el orden del día y guía la reunión en vivo.</small></span><span class="role-action">Preparar una reunión <span aria-hidden="true">→</span></span>
    </a>
    <a class="role-row" href="user/minutes-and-approval.md">
      <span class="role-number">04</span><span class="role-copy"><strong>Aprobador</strong><small>Revisa y aprueba el acta de la reunión.</small></span><span class="role-action">Revisar el acta <span aria-hidden="true">→</span></span>
    </a>
    <a class="role-row" href="admin/configuration.md">
      <span class="role-number">05</span><span class="role-copy"><strong>Gestor</strong><small>Configura el módulo para la organización.</small></span><span class="role-action">Configurar reuniones <span aria-hidden="true">→</span></span>
    </a>
  </div>
  <p class="role-note"><strong>Los roles se acumulan.</strong> Los Editores también pueden leer; el rol Gestor incluye Editor y Aprobador. Consulta <a href="roles-and-permissions.md">roles y permisos</a>.</p>
</section>

<section class="guide-section journey-section" id="flujo-reunion">
  <div class="guide-section-head">
    <p class="guide-eyebrow">Un registro conectado</p>
    <div>
      <h2>Un mismo hilo, desde la preparación hasta el seguimiento</h2>
      <p>La serie sirve de base para las reuniones recurrentes. Cada reunión conserva su agenda y su propio registro; los puntos abiertos pueden retomarse más adelante.</p>
    </div>
  </div>
  <div class="workflow-illustration" role="group" aria-label="Flujo de una reunión desde su preparación hasta el seguimiento">
    <div class="workflow-entry">
      <div class="workflow-sources">
        <article class="workflow-source">
          <span class="workflow-kicker">Reuniones recurrentes</span>
          <strong>Serie</strong>
          <p>Asistentes habituales, plantillas de agenda y reglas de reunión.</p>
        </article>
        <article class="workflow-source standalone">
          <span class="workflow-kicker">Una sola reunión</span>
          <strong>Puntual</strong>
          <p>Prepárala sin crear una serie.</p>
        </article>
      </div>
      <span class="workflow-merge" aria-hidden="true">→</span>
      <article class="workflow-meeting-card">
        <div class="workflow-card-head">
          <span class="workflow-kicker">Se prepara la reunión</span>
          <strong>Fecha · personas · orden del día</strong>
        </div>
        <div class="workflow-agenda">
          <span class="workflow-agenda-title">Orden del día</span>
          <div><b>01</b><span>Punto para esta reunión</span></div>
          <div><b>02</b><span>Punto abierto que se retoma</span></div>
        </div>
      </article>
    </div>

    <ol class="workflow-stages">
      <li><span class="workflow-step-number">01</span><span class="workflow-kicker">Durante la reunión</span><strong>Trabaja cada punto</strong><p>Guarda las notas, los acuerdos y los seguimientos junto a cada punto.</p></li>
      <li><span class="workflow-step-number">02</span><span class="workflow-kicker">Al terminar</span><strong>Prepara el acta</strong><p>Reúne las notas de la reunión y los resultados de los puntos en un borrador legible.</p></li>
      <li><span class="workflow-step-number">03</span><span class="workflow-kicker">Aprobación</span><strong>Deja un registro oficial</strong><p>La aprobación guarda una revisión inmutable y su PDF.</p></li>
      <li><span class="workflow-step-number">04</span><span class="workflow-kicker">Siguientes pasos</span><strong>Continúa el trabajo</strong><p>Asigna tareas y decide qué puntos abiertos necesitan otra reunión.</p></li>
    </ol>

    <div class="workflow-continuity">
      <div class="workflow-continuity-copy">
        <span class="workflow-kicker">Entre reuniones</span>
        <strong>El punto puede continuar; cada reunión conserva su propio registro.</strong>
      </div>
      <div class="workflow-meeting-pair">
        <article class="workflow-occurrence">
          <span class="workflow-kicker">Reunión 1</span>
          <strong>Punto compartido</strong>
          <p>Discusión y resultado de esta reunión</p>
        </article>
        <div class="workflow-carry" aria-hidden="true"><span>Se retoma</span><b>→</b></div>
        <article class="workflow-occurrence">
          <span class="workflow-kicker">Reunión 2</span>
          <strong>El mismo punto</strong>
          <p>Nueva discusión y resultado</p>
        </article>
      </div>
    </div>
  </div>
</section>

<section class="guide-section guide-library" id="indice-guia">
  <div class="guide-section-head">
    <p class="guide-eyebrow">Para volver cuando lo necesites</p>
    <div>
      <h2>Ve directamente a la guía que buscas</h2>
      <p>Primero los pasos prácticos; después, la configuración y las referencias.</p>
    </div>
  </div>
  <div class="guide-library-grid">
    <section>
      <h3>Preparar y participar</h3>
      <ul>
        <li><a href="user/prepare-meeting.md">Preparar una reunión</a></li>
        <li><a href="user/propose-a-point.md">Proponer un punto</a></li>
        <li><a href="user/live-meeting.md">Llevar la reunión en vivo</a></li>
        <li><a href="user/minutes-and-approval.md">Revisar y aprobar el acta</a></li>
        <li><a href="user/followups.md">Registrar seguimientos</a></li>
        <li><a href="user/carryovers.md">Retomar un punto</a></li>
      </ul>
    </section>
    <section>
      <h3>Configurar las reuniones</h3>
      <ul>
        <li><a href="roles-and-permissions.md">Roles y permisos</a></li>
        <li><a href="admin/configuration.md">Configuración general</a></li>
        <li><a href="admin/series.md">Series de reuniones</a></li>
        <li><a href="admin/catalogs.md">Catálogos de puntos y acuerdos</a></li>
      </ul>
    </section>
    <section>
      <h3>Consultar referencias</h3>
      <ul>
        <li><a href="concepts.md">Conceptos y vocabulario</a></li>
        <li><a href="integrations/calendar.md">Integración con Calendario</a></li>
        <li><a href="integrations/project.md">Integración con Project</a></li>
        <li><a href="release-notes.md">Notas de versión</a></li>
        <li><a href="faq.md">Preguntas frecuentes</a></li>
      </ul>
    </section>
  </div>
</section>
