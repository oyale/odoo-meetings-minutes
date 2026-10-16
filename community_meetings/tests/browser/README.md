# Pruebas de navegador de reuniones

`full_meeting_playwright.py` amplía los recorridos de `live_meeting_playwright.py`.
Usa Chromium real, interfaz inglesa y un editor de reuniones. La preparación y
comprobación persistida usan RPC; las acciones contabilizadas se realizan en UI.

## Ejecutar en este contenedor de desarrollo

Con Python Playwright y su Chromium instalados:

```sh
python3 addons/community_meetings/tests/browser/run_development_suite.py --development
```

El lanzador usa `meeting-minutes.local`, la base existente `meeting_minutes` y
el virtualenv `odoo`. Crea usuarios exclusivos de editor/aprobador y proponente con credenciales
aleatorias y, si Project está instalado, un proyecto de prueba. El editor tiene
permisos de administración Project para probar la creación de proyectos. No imprime ni guarda credenciales.
El `finally` limpia sus reuniones, revisiones/PDF de prueba, propuestas, puntos,
series, arrastres, proyecto, usuarios y contactos.
Para limpiar reuniones celebradas, restablece el estado y rompe las referencias circulares de arrastre **solo de
registros del usuario temporal exclusivo** mediante SQL; después los elimina por ORM. Este
lanzador es exclusivamente para desarrollo. No cambia las reglas del producto.

Acepta `--host`, `--base-url`, `--database` y filtros de nombre:

```sh
python3 addons/community_meetings/tests/browser/run_development_suite.py --development notes_autosave carryover
```

Un fallo de limpieza devuelve error; no se considera una ejecución correcta.
Una interrupción forzada del proceso/host puede impedir el `finally`.

## Ejecución con cuenta existente

Exportar `ODOO_BASE_URL`, `ODOO_LOGIN`, `ODOO_PASSWORD` y, con Project instalado,
`ODOO_TEST_PROJECT` (nombre único de un proyecto accesible), después:

```sh
python3 addons/community_meetings/tests/browser/full_meeting_playwright.py
```

La cuenta debe usar inglés, ser editor/aprobador y poder administrar proyectos si Project está
instalado. Para las propuestas, proporcionar también `ODOO_PROPOSER_LOGIN` y
`ODOO_PROPOSER_PASSWORD` de un usuario con el rol de proponente. Este modo no concede permisos ni modifica usuarios. Conserva las
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

Sin filtros, el comando falla si falla un test o si la cobertura del inventario
queda por debajo del 90 %. Con filtros no exige el porcentaje global y conserva
los casos no ejecutados como no cubiertos.

Cada ejecución escribe `coverage.json`, trazas Playwright y capturas en fallo en
`/tmp/meeting-playwright/<run>/` (configurable con `PLAYWRIGHT_ARTIFACTS`). Las trazas
permiten inspeccionar selectores, requests y estado visual. Con cuenta existente
pueden contener información de esa sesión; no deben añadirse a Git.

Se comprueban errores JavaScript en todos los escenarios de la suite full.
Se ejercitan escritorio 1440px y móvil 390px. Esto no sustituye pruebas ORM de
permisos/multiempresa, integridad de actas, concurrencia, accesibilidad completa,
ni el recorrido con Project desinstalado.

Validación de desarrollo del 2026-10-16: 37 escenarios correctos y 88/88 acciones
del inventario cubiertas. El informe de cada ejecución es la evidencia vigente.

Para ver el navegador, usar `PLAYWRIGHT_HEADFUL=1`. La suite corta sigue disponible
mediante `python3 live_meeting_playwright.py` con las mismas variables de acceso.
