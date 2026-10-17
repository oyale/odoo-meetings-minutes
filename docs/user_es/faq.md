# FAQ y resolución de problemas

Situaciones habituales, en la voz de quien las sufre.

## Acceso

**"Abro Odoo y no veo el menú Meetings."**
El menú raíz exige el grupo de usuario interno; si aun así no ves las reuniones
esperadas, no eres organizador/secretario/lector de ellas. Pide a un editor que te
añada en la pestaña **Access** de la reunión, o a un gestor que te conceda el rol de
Lector.

**"Soy asistente — ¿por qué no puedo abrir la reunión?"**
Los asistentes son contactos y no dan acceso. El acceso es por usuario: organizador,
secretario, lectores/editores asignados o gestores.

**"No puedo proponer puntos."**
O la organización restringió las propuestas a grupos concretos
([catálogos](admin/catalogs.md#grupos-de-proponentes-autorizados)) o la serie elegida
está inactiva o es de otra compañía.

## Preparación

**"Falta el botón Add Point en mi reunión."**
La política de *añadir puntos* de la serie dice que esta reunión ya no acepta puntos
(ver [políticas](admin/series.md#políticas)). El servidor también lo impide.

**"La agenda supera la duración de la reunión."**
La suma de estimaciones es mayor que la duración prevista. Amplía la duración, afina
las estimaciones o quita puntos. El aviso es informativo.

**"El cambio de serie está bloqueado."**
Las series pueden cambiarse solo en borrador/programada y antes de que empiece la
ejecución en vivo; además, los puntos compartidos con otras reuniones limitan la
serie de destino.

## Reunión en vivo

**"Mis notas han desaparecido."** No han desaparecido: con el seguimiento de tiempo
**activado**, las notas son de solo lectura cuando el cronómetro del punto está en
pausa y mientras la reunión está pausada. Reanuda el punto (o la reunión) para
seguir escribiendo. Todo se autoguarda — mira el estado en la barra superior.

**"Pulsé Finalizar reunión por error."** Un editor/aprobador puede reabrir el
contenido mientras el acta no esté aprobada: usa *Undo result* por punto o reabre
desde el formulario; si ya está Celebrada, el flujo continúa en acta en borrador.

**"No puedo completar un punto decisorio."** Registra primero el **acuerdo**
(aprobado/rechazado). Las decisiones exigen acuerdo; el botón Done sigue
deshabilitado hasta entonces.

**"No puedo completar un punto TODO."** Añade un seguimiento asignado — se exige
evidencia de responsabilidad antes de resolver.

**"Al añadir un punto dice que ya no está permitido."** La política de *añadir
puntos* de la serie/compañía venció para el estado de esta reunión. Opciones:
proponerlo para la próxima reunión o registrarlo como seguimiento.

## Actas

**"No aparece Approve Minutes."** Solo lo ven los **aprobadores**, y solo en estado
*Acta en borrador*.

**"Falta el PDF."** Las revisiones aprobadas generan su PDF al aprobar; si el
servidor no tiene los recursos PDF, la instantánea se conserva y el PDF puede
regenerarse después desde la revisión.

**"Alguien cambió un punto tras la aprobación."** Las actas aprobadas son
instantáneas inmutables; cambiar tras aprobar exige **Start Amendment** (aprobador)
y genera una nueva revisión.

## Seguimientos y tareas

**"El punto TODO está cerrado pero el trabajo no está hecho."** Esperado: la
resolución exige *evidencia de responsabilidad* (seguimiento asignado con
actividad/tarea), no trabajo terminado.

**"¿Por qué no puedo borrar esa tarea?"** Un TODO cerrado sigue dependiendo de ella
como evidencia. Cancela la tarea en lugar de borrarla, o reabre el punto.

**"El responsable de la tarea no ve la reunión."** Añádelo como lector en la pestaña
**Access** de la reunión — los vínculos de tarea no conceden acceso a la reunión.

## Calendario

**"El evento del calendario es de solo lectura."** Lo gestiona su reunión; edita la
reunión ([Calendario](integrations/calendar.md)).

## ¿Sigues atascado?

Consulta a un **gestor**; si parece un error del programa, describe la pantalla
exacta, el estado de la reunión y el mensaje mostrado — los gestores pueden revisar
los historiales de chatter en reuniones, puntos y seguimientos.
