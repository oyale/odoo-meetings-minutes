# Integración con Calendario (`community_meetings_calendar`)

Módulo opcional que refleja las reuniones programadas en el **Calendario** estándar
de Odoo para que todo el mundo las vea junto al resto de sus eventos.

![Evento de calendario vinculado](img/calendar-event.png)

## Qué hace

- **Programar** una reunión crea/actualiza un `calendar.event` vinculado con las
  mismas fechas, asistentes, lugar y enlace de videollamada.
- Finalizar o cancelar la reunión mantiene el evento coherente con ella.

## Qué puede hacer el usuario

- Ver la reunión en su calendario (vistas día/semana/mes) y en los recordatorios.
- Abrir la reunión desde el evento: el evento muestra un aviso informativo — *"This
  event is managed by its community meeting"* — y todos los campos gestionados por
  la reunión quedan en solo lectura.

## Qué no puede hacer

Todos los campos gestionados por la reunión son **de solo lectura en el evento**:
nombre, fechas, duración, recurrencia, asistentes, alarmas, privacidad, descripción,
categorías y los botones de envío/invitaciones están deshabilitados.

> **Nota:** para cambiar una reunión usa siempre la reunión (pantalla en vivo o
> formulario), nunca el evento de calendario. El evento es una proyección, no la
> fuente.

## Preguntas frecuentes

**¿Por qué no puedo invitar a más gente desde el evento?** Los asistentes se
gestionan en la reunión (cabecera → *Editar asistentes*), que mantiene la reunión como
única fuente de verdad.

**¿Sigo recibiendo recordatorios de Odoo?** Sí — el evento es un evento real de
calendario con alarmas y notificaciones normales.
