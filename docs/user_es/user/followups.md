# Seguimientos (editor / responsable)

Un **seguimiento** es el registro durable de "quién hace qué" que nace de un punto
de agenda. Sobrevive entre reuniones y mantiene la trazabilidad con su punto de
origen.

![Tarea de seguimiento](img/followup-task.png)

## Crear uno

En la reunión en vivo, dentro de un punto: **Añadir seguimiento** →

- **Título** — la acción en sí ("Enviar el acta a legal").
- **Tipo** — *actividad de Odoo* o *TODO nativo* (con el módulo Project: también
  tarea de proyecto) — limitado a los tipos permitidos por la serie.
- **Asignado a** — una persona por defecto; *varias personas responsables* en
  opciones avanzadas crea una actividad por persona.
- **Fecha límite**.

Al crearlo se avisa al responsable mediante las actividades estándar de Odoo
(reloj de la bandeja del sistema).

## La regla del TODO

Un punto **TODO** no puede resolverse hasta que tenga un seguimiento asignado
**con evidencia**:

| Tipo de seguimiento | Cuenta como evidencia cuando… |
|---|---|
| Actividad de Odoo / TODO | La actividad existe y está pendiente o completada para el responsable. |
| Tarea de Project *(módulo Project)* | Hay una tarea válida, asignada y no cancelada vinculada. |

> **Nota:** "tener evidencia" no significa que el trabajo esté terminado — significa
> que la responsabilidad está registrada. La evidencia no puede eliminarse mientras
> un punto cerrado la necesite.

## Vivir con un seguimiento

- **Estado** — Abierto / En curso / Hecho / Cancelado, editable desde la reunión en
  vivo, la pestaña *Acciones de seguimiento* del formulario o el propio formulario del
  seguimiento.
- **Cambios de responsable** — editar la lista de responsables re-sincroniza las
  actividades.
- **Convertir el tipo** — el menú ⋯ convierte p. ej. una actividad en TODO,
  conservando el historial.
- **Completar la actividad** actualiza el seguimiento durable en lugar de borrar la
  evidencia.

## Revisar en la próxima reunión

Marca **Revisar en la próxima reunión** (o pospone el punto) y el seguimiento se convierte
en un punto de *revisión* en la próxima reunión de la serie: misma identidad del
punto, espacio de discusión fresco y enlace de origen **Desde un seguimiento** en la
tarjeta.

## Tareas de Project

Con `community_meetings_project` instalado, *Crear tarea* convierte un seguimiento
en una tarea de Project (o vincula una existente). Ver
[Integración con Project](../integrations/project.md).

## Los responsables necesitan acceso

Un responsable del seguimiento que no es lector de la reunión no puede ver su
contexto. Los editores deberían añadirlo en la pestaña **Acceso** de la reunión.
