# Catálogos (gestor)

Listas breves que alimentan los desplegables de toda la aplicación. Ubicación:
**Meetings → Configuration**. Todas las listas admiten ordenación por arrastre y
archivado (los elementos archivados siguen legibles en registros antiguos pero
desaparecen de los nuevos).

## Tipos de reunión

*Configuration → Meeting Kinds*

Una clasificación breve para series y reuniones (p. ej. *Operational*, *Board*,
*Assembly*). El **código** queda fijo una vez usado. Cada serie y reunión exige
un tipo; las reuniones independientes usan por defecto *Operational*.

## Tipos de punto de agenda

*Configuration → Agenda Point Types*

El **comportamiento** de un tipo decide cómo se trata el punto en la reunión en vivo:

| Comportamiento | Comportamiento en vivo |
|---|---|
| **Information** | Tratado → listo. No exige acuerdos. |
| **Discussion** | Puede cerrarse como resuelto o posponerse. |
| **Decision** | Exige un **acuerdo** (aprobado/rechazado) antes de completarse. |
| **To-do (TODO)** | Exige un seguimiento asignado con evidencia antes de resolverse. |
| **Minutes approval** | Lista las actas anteriores pendientes; estructural. |
| **Next meeting** | Fija la próxima fecha; estructural. |
| **Follow-up** | Revisión de un seguimiento existente. |

Cada tipo tiene un icono que se muestra en los selectores. Los tipos se comparten
entre todas las reuniones de la compañía; una vez usado, el comportamiento queda
fijo (archivar es la vía de escape).

> **Consejo:** mantén el catálogo corto. La mayoría de organizaciones necesita
> 4–6 tipos.

![Tipos de punto de agenda](img/agenda-types.png)

## Motivos de discrepancia

*Configuration → Dissent Reasons*

Catálogo de motivos para los registros de discrepancia/reserva (p. ej. "Objeción
procesal", "Conflicto de interés"). Archivar un motivo mantiene legibles las
discrepancias existentes.

## Grupos de proponentes autorizados

*Configuration → Authorized Proposer Groups*

Por defecto **cualquier usuario interno** puede proponer puntos. Añade aquí grupos
para restringir la propuesta a sus miembros (los gestores siempre conservan el
derecho). Deja la lista vacía para volver a abrirlo a todo el mundo.

## Dónde aparecen

- *Tipo de reunión* → formulario de series y de reuniones.
- *Tipo de punto* → asistente de puntos y listas de agenda (con iconos).
- *Motivos de discrepancia* → formularios de discrepancia en la reunión en vivo.
- *Grupos de proponentes* → comprobación de acceso del asistente de propuestas.
