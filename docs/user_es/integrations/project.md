# Integración con Project (`community_meetings_project`)

Módulo opcional que conecta los seguimientos de las reuniones con las tareas de
**Project** de Odoo. Requiere `project` y `community_meetings`.

![Seguimiento con tarea de proyecto](img/project-task.png)

## Crear una tarea desde un seguimiento

En cualquier acción de seguimiento (tarjeta de la reunión en vivo, pestaña del
formulario o el propio formulario del seguimiento) pulsa **Crear tarea**:

1. Elige **vincular una tarea existente** o **crear una nueva**.
2. Para una nueva: elige el proyecto (pre-rellenado según la política, ver abajo) y
   el nombre.
3. **Create and Link** — la tarea aparece como etiqueta en el seguimiento/línea de
   agenda.

Requisitos: permisos de creación de tareas de Project; la tarea debe pertenecer a un
proyecto de compañía compatible. Una tarea existente se vincula, nunca se duplica.

## Política de tareas

Dos niveles configuran cómo tratan los puntos TODO las tareas — ajustes de compañía
(*Ajustes → Reuniones → Política de tareas de Project*) y la página **Follow-up and Task
Policy** de la serie:

| Ajuste | Opciones |
|---|---|
| **Proyecto de las tareas** | Sin proyecto por defecto · un proyecto de compañía · un proyecto por serie (se crea al primer uso). |
| **Evidencia para resolver un TODO** | Solo seguimiento básico · seguimiento **o** tarea vinculada · tarea obligatoria. |
| **Ámbito de selección de tareas** | Cualquier proyecto accesible · solo el proyecto configurado. |

> **Nota:** por defecto, instalar el módulo no cambia nada: los seguimientos
> asignados del núcleo siguen siendo evidencia suficiente para los TODOs.

## Reglas que protegen la historia

- Los **detalles de las tareas no forman parte de las instantáneas del acta
  aprobada** — los cambios posteriores en la tarea nunca reescriben actas históricas.
- El cierre registra la política vigente en ese momento; los cambios posteriores de
  política afectan solo a resoluciones futuras.
- Mientras un TODO resuelto dependa de una tarea, eliminar la tarea o sacarla del
  ámbito queda rechazado.

## Encontrar los vínculos desde una tarea

Una tarea de Project muestra el botón **Meeting Agenda Links** que lista los puntos
de agenda, acuerdos y seguimientos vinculados a ella — filtrados por el acceso del
usuario actual.

## Arrastres con tareas

El asistente de arrastres permite a los editores seleccionar explícitamente las
tareas de proyecto vinculadas para continuarlas en la reunión de destino — ver
[Arrastres](../user/carryovers.md).
