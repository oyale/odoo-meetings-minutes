# Configuración general (gestor)

Todo en esta página requiere el rol **Gestor** y acceso a *Ajustes* de Odoo.
Ubicación: **Ajustes → Meetings** (desplázate dentro de la página de ajustes).

![Ajustes generales](img/settings-general.png)

La página de ajustes tiene cinco bloques. Todos los valores son **valores
predeterminados de la compañía**: cualquier serie puede sobrescribir los que
afectan a los puntos (ver [Series](series.md)).

## Estimación de puntos

| Ajuste | Significado |
|---|---|
| **Duración estimada predeterminada por punto (minutos)** | Minutos pre-rellenados para los puntos nuevos que no indiquen duración. |

*Cómo se resuelve:* la estimación de un punto es el valor que escriba el usuario,
si no la **serie**, si no este valor de la **compañía**.

## Nombres de rol

| Ajuste | Significado |
|---|---|
| **Nombre del rol de coordinación** | Etiqueta mostrada para el rol de coordinación (p. ej. "Organizer", "Presidencia"). |
| **Nombre del rol de secretaría** | Etiqueta mostrada para el rol de secretaría de actas. |

Son ajustes cosméticos: cada organización habla su propio idioma en formularios
e informes.

## Seguimiento de tiempo

| Ajuste | Significado |
|---|---|
| **Registrar el tiempo de reuniones y puntos** (sí/no) | **Activado** (por defecto): la reunión en vivo muestra *Iniciar / Pausar / Reanudar reunión*, los puntos tienen cronómetro, las notas de discusión solo se editan con el cronómetro del punto en marcha y se registran las duraciones reales. **Desactivado**: sin cronómetros — la reunión en vivo es editable desde el principio y simplemente se *finaliza* la reunión. |

> **Consejo:** desactiva el seguimiento de tiempo en organizaciones que no quieran
> cronómetros. El flujo de agenda (acuerdos, discrepancias, seguimientos, actas)
> funciona exactamente igual.

## Añadir puntos

| Ajuste | Significado |
|---|---|
| **Añadir puntos hasta** | El último momento en que se pueden añadir puntos nuevos a una reunión: |

| Valor | Los puntos se pueden añadir… |
|---|---|
| **Solo borrador** | Solo mientras la reunión es borrador. |
| **Antes de empezar** | En borrador, y una vez programada — hasta que comience. |
| **Mientras se realiza** *(por defecto)* | En borrador, programada y mientras la reunión está en curso. |

Después los botones **Añadir punto** desaparecen y el servidor también lo
impide. Cada serie puede sobrescribirlo (ver
[Series → Políticas](series.md#políticas)).

> **Nota:** nunca se añaden puntos a reuniones cuyo acta ya está redactada
> (Celebrada/Acta en borrador/Aprobada) — eso se registra como seguimiento o
> propuesta nueva.

## Seguimientos

| Ajuste | Significado |
|---|---|
| **Tipos de seguimiento permitidos** | Mecanismos de ejecución que pueden usar los puntos (actividad de Odoo, TODO nativo…). |
| **Tipo de seguimiento predeterminado** | Tipo preseleccionado al crear un seguimiento. |
| **Tipo de actividad de Odoo por defecto** | Tipo de actividad usado cuando el seguimiento es una actividad de Odoo. |

Con el módulo **Project** instalado aparece aquí también el bloque *política de tareas de Project* — ver [Integración con Project](../integrations/project.md#política-de-tareas).

## Dónde encajan las series

Cada ajuste anterior que diga "una serie puede sobrescribirlo" se edita en el
formulario de la serie, pestaña **Políticas** — leer
[Configuración de series](series.md).

## Catálogos relacionados

- [Tipos de reunión y de punto](catalogs.md#tipos-de-reunión)
- [Motivos de discrepancia](catalogs.md#motivos-de-discrepancia)
- [Grupos de proponentes autorizados](catalogs.md#grupos-de-proponentes-autorizados)
