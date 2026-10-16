# Corrección de los siete concerns

Plan aprobado: implementar los siete bloques del análisis de MODELO_TECNICO.md.
Interpretación de la política core: actividad, To-do o ambas opciones disponibles,
con una opción predeterminada. Un seguimiento crea el tipo elegido, sin duplicarlo.

1. Capacidades live: lectura del aprobador sin permisos editoriales; aprobación
   independiente de edición y carga sin información privada.
2. Snapshot v2: serie destino, compatibilidad de revisiones anteriores e integridad.
3. Preparación común: candidatos de participaciones, solicitudes y puntos promovidos;
   exclusión temporal sin descarte definitivo; revalidación e idempotencia.
4. Pausa: proteger contenido editorial en servidor, mantener preparación de agenda,
   redacción posterior y avance operativo de tareas; serializar pausa y guardados.
5. Fechas: zona por serie, fecha y hora explícitas, recurrencia en hora local.
6. Seguimientos: política empresa → serie → punto; actividades nativas con varios
   responsables y tarea Project sin actividad duplicada.
7. Validación: servidor core/Project, navegador completo, revisión y commits atómicos.

El usuario excluye expresamente la migración: entorno de desarrollo, se permite
reiniciar datos si es necesario. No se borran registros de usuario para probar;
las suites crean y eliminan únicamente sus fixtures identificadas.
No reescribir snapshots/PDF aprobados. Los cambios de política
no deben invalidar evidencias de cierre históricas ni convertir silenciosamente
seguimientos existentes al editar campos ajenos a su tipo.

La política del punto es persistente (topic); sus participaciones conservan el
contenido de sesión. «Ambas» habilita dos opciones, con una elegida por seguimiento.
La finalización de todos los responsables completa el seguimiento; la finalización
parcial se conserva y la reapertura vuelve a programar las actividades.

Revisión de dos ejes aplicada: se corrigieron bloqueo concurrente de cronómetros,
defaults de contexto en creaciones editoriales, permisos del responsable lector,
carga de puntos por topic_id, autoría de disensos y edición de responsables múltiples.
