# Pruebas de navegador de reuniones

`full_meeting_playwright.py` amplía los recorridos de `live_meeting_playwright.py`.
La extensión opcional Project reutiliza esa suite desde
`community_meetings_project/tests/browser/`. Usa Chromium real, interfaz inglesa y
un editor de reuniones. La preparación y comprobación persistida usan RPC; las
acciones contabilizadas se realizan en UI.

## Ejecutar en este contenedor de desarrollo

Con Python Playwright y su Chromium instalados:

```sh
python3 addons/community_meetings/tests/browser/run_development_suite.py --development
```

El lanzador usa `meeting-minutes.local`, la base existente `meeting_minutes` y
el virtualenv `odoo`. Crea usuarios exclusivos de editor/aprobador y proponente con
credenciales aleatorias. No crea ningún proyecto: la suite core no requiere Project
y no modifica la instalación de módulos. No imprime ni guarda credenciales.
El `finally` limpia sus reuniones, revisiones/PDF de prueba, propuestas, puntos,
series, arrastres, usuarios y contactos.
Para limpiar reuniones celebradas, restablece el estado y rompe las referencias circulares de arrastre **solo de
registros del usuario temporal exclusivo** mediante SQL; después los elimina por ORM. Este
lanzador es exclusivamente para desarrollo. No cambia las reglas del producto.

Acepta `--host`, `--base-url`, `--database` y filtros de nombre:

```sh
python3 addons/community_meetings/tests/browser/run_development_suite.py --development notes_autosave carryover
```

Un fallo de limpieza devuelve error; no se considera una ejecución correcta.
Una interrupción forzada del proceso/host puede impedir el `finally`.

## Extensión Project

`community_meetings_project/tests/browser/run_development_suite.py` reutiliza el
lanzador core y ejecuta `full_project_playwright.py`, que añade los escenarios de
tarea Project sobre los recorridos core. Exige que
`community_meetings_project` esté instalado (y por tanto `project`) en la base
usada; el lanzador lo comprueba y falla con un mensaje claro si no lo está. No
instala Project por sí mismo: la suite core debe seguir corriendo sin Project.

```sh
python3 addons/community_meetings_project/tests/browser/run_development_suite.py --development
```

## Ejecución con cuenta existente

Exportar `ODOO_BASE_URL`, `ODOO_LOGIN` y `ODOO_PASSWORD`, después:

```sh
python3 addons/community_meetings/tests/browser/full_meeting_playwright.py
```

La cuenta debe usar inglés y ser editor/aprobador. Para las propuestas, proporcionar
también `ODOO_PROPOSER_LOGIN` y `ODOO_PROPOSER_PASSWORD` de un usuario con el rol de
proponente. Para la suite Project, usar `full_project_playwright.py` con una cuenta
editora que además pueda administrar proyectos y una base con Project instalado. Este
modo no concede permisos ni modifica usuarios. Conserva las
reuniones celebradas y con historial de arrastre porque el producto impide su
borrado editorial: aparecen en `retained_records` del informe. También pueden
quedar fixtures si un caso falla antes de registrar sus IDs. Preferir el lanzador
con usuario desechable para garantizar limpieza administrativa de todo el run.

## Cobertura y evidencias

`--list-actions` imprime el inventario explícito de acciones. No es cobertura de
líneas ni una medición de frecuencia real de usuarios: no hay telemetría.

Cada acción cubierta exige que pase su escenario completo, incluidas aserciones
en UI y lecturas ORM donde corresponde. La suite incluye aprobación y descarga
del PDF conservado, y envío/revisión de propuestas con dos usuarios separados.
Incluye los wizards de preparación y puntos, sus defaults y metadatos, arrastres
automáticos y revisables, actividades y enlaces a tareas existentes. También prueba
confirmaciones y cancelaciones concurrentes mediante solicitudes reales.

Sin filtros, el comando falla si falla un test, si hay skips o si la cobertura del
inventario queda por debajo del 90 %. Un skip cuenta como pendiente, no como caso
superado. Con filtros no exige el porcentaje global y conserva los casos no
ejecutados como no cubiertos.

Cada ejecución escribe `coverage.json`, trazas Playwright y capturas en fallo en
`/tmp/meeting-playwright/<run>/` (configurable con `PLAYWRIGHT_ARTIFACTS`). Las trazas
permiten inspeccionar selectores, requests y estado visual. Con cuenta existente
pueden contener información de esa sesión; no deben añadirse a Git.

Se comprueban errores JavaScript en todos los escenarios de la suite full.
Se ejercitan escritorio 1440px y móvil 390px. Esto no sustituye pruebas ORM de
permisos/multiempresa, integridad de actas, concurrencia, accesibilidad completa,
ni el recorrido con Project desinstalado (que cubre la separación core).

Validación de desarrollo del 2026-10-17 (commit addons pendiente de publicar): 56
escenarios correctos, 0 fallos, 0 errores y 105/105 acciones del inventario
cubiertas (100 %). La evidencia Project queda pendiente: la base de desarrollo no
tiene `community_meetings_project` instalado y la suite core no debe instalarlo.
El informe de cada ejecución es la evidencia vigente.

Para ver el navegador, usar `PLAYWRIGHT_HEADFUL=1`. La suite corta sigue disponible
mediante `python3 live_meeting_playwright.py` con las mismas variables de acceso.
