# Configuración de series (gestor / editor)

Una **serie** es la plantilla de una reunión recurrente. Todo lo configurado aquí
se copia en las reuniones nuevas al crearse — las ediciones posteriores no afectan
a las reuniones existentes.

Ubicación: **Meetings → Meeting Series**. El asistente de creación (*Nuevo* en la
lista de series) pide lo mismo por pasos: básicos → programación → estructura →
revisión.

![Formulario de serie](img/series-form.png)

## Cabecera: Qué y Personas

| Campo | Significado |
|---|---|
| **Tipo** | Clase de reuniones que celebra esta serie (del catálogo Tipos de reunión). |
| **Compañía** | Compañía propietaria (solo multicompañía). |
| **Activo** | Las series archivadas conservan sus reuniones pero desaparecen de listas y menús. |
| **Coordinadores** | Usuarios responsables de preparar las reuniones de la serie. |
| **Asistentes habituales** | Personas invitadas a cada reunión nueva; siguen siendo modificables por reunión. |

## Propósito

Descripción en texto enriquecido, útil para quien llega nuevo. Se muestra en solo
lectura en cada reunión como *Descripción de la serie*.

## Programación

| Campo | Significado |
|---|---|
| **Duración prevista** | Duración planificada de cada reunión. |
| **Zona horaria** | Se usa para proponer la próxima fecha sin ambigüedad. |
| **Patrón de nombre** | P. ej. `{date} {series}` → "2026-11-08 Coordinación semanal". Tokens: `{date}`, `{series}`. |

## Estructura de la agenda

| Campo | Significado |
|---|---|
| **Punto de aprobación del acta** | Añade un primer punto para aprobar las actas anteriores. Solo aparece si hay actas pendientes. Reserva 5 minutos por acta. |
| **Punto de próxima reunión** | Añade un último punto para fijar la próxima fecha. Reserva 5 minutos. |
| **Regla de próxima reunión** | Regla para proponer esa fecha: *día de la semana* (siempre martes), *día del mes* o *cada N días*. |

## Políticas

Esta pestaña decide el comportamiento de la serie. Todo puede quedarse en
**Predeterminado de la compañía**.

### Puntos sin terminar (arrastre)

| Valor | Comportamiento |
|---|---|
| **Revisión** *(por defecto)* | Los puntos sin terminar se ofrecen a la siguiente reunión; un editor acepta o descarta cada uno. |
| **Automática** | Los puntos sin terminar continúan en la siguiente reunión sin preguntar. |
| **Manual** | Nadie ofrece nada automáticamente; alguien mueve cada punto explícitamente (*Mover a otra reunión*). |

### Seguimiento de tiempo

| Valor | Comportamiento |
|---|---|
| **Predeterminado de la compañía** | Lo que digan los Ajustes; el valor efectivo se muestra al lado. |
| **Activado** | Cronómetros y duraciones reales en las reuniones de esta serie. |
| **Desactivado** | Sin cronómetros: la reunión en vivo es editable desde el principio; solo se registra la finalización. |

### Añadir puntos

| Valor | Comportamiento |
|---|---|
| **Predeterminado de la compañía** | Sigue *Ajustes → Añadir puntos*. |
| **Solo borrador** | Los puntos solo se añaden preparando la reunión. |
| **Antes de empezar** | También programada, hasta que comience. |
| **Mientras se realiza** | También mientras está en curso, hasta que termine. |

### Estimaciones de puntos

| Campo | Significado |
|---|---|
| **Default point estimate (minutes)** | Estimación pre-rellenada para los puntos nuevos de esta serie. Vacío → valor de la compañía (se muestra al lado). |

Los puntos estructurales (aprobación de acta y próxima reunión) ignoran este
valor: reservan 5 minutos cada uno (5 por acta pendiente en las aprobaciones).

### Nombres de rol

Sobrescrituras opcionales de las etiquetas de coordinación y secretaría solo para
esta serie.

### Seguimientos

| Campo | Significado |
|---|---|
| **Tipos de seguimiento permitidos** | Tipos que pueden usar los puntos nuevos de esta serie. |
| **Tipo de seguimiento por defecto** | Tipo preseleccionado. |
| **Tipo de actividad por defecto** | Para seguimientos registrados como actividades de Odoo. |

Con el módulo Project se añade aquí una página **Follow-up and Task Policy** —
ver [Project](../integrations/project.md#política-de-tareas).

## Botones y propuestas

- **Nueva reunión** — abre el asistente de creación de reuniones con esta serie
  preseleccionada.
- **Proponer un punto** — abre el asistente de propuestas dirigido a esta serie.
- El aviso **Propuestas por revisar** (solo editores) aparece bajo el título cuando
  hay propuestas pendientes, con botones Aceptar/Rechazar — ver
  [Proponer un punto](../user/propose-a-point.md).

## Pestaña Meetings

Lista de solo lectura con las reuniones de la serie, de más reciente a más
antigua, con insignias de estado. Abre una para trabajar con ella.
