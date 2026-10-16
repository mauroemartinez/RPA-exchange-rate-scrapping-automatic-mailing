# Fase 6: ejecución programada y monitoreo

Estado al 14 de octubre de 2026: **la corrida corre en GitHub Actions, en el plan gratis, y la orden la da un Worker de Cloudflare** (al final de esta guía). El horario propio de GitHub quedó como respaldo, apagado. Lo que sigue es la guía completa, con la historia de cómo se llegó a eso.

Antes de todo esto la corrida se lanzaba a mano desde el notebook. En los 90 días anteriores al 7 de octubre quedaron tres días hábiles sin fila que no eran feriados: el 19/08, el 24/09 y el 02/10.

## Qué quedó resuelto

| Pedido del roadmap | Cómo quedó |
|---|---|
| Evitar corridas duplicadas entre mecanismos | Advisory lock de Postgres durante toda la corrida (`data_access.candado_corrida`), el control de "la fila de hoy ya existe" y un INSERT que no pisa. Dos disparadores a la vez: uno corre y el otro termina como `omitida`. Uno detrás del otro: el segundo ve la fila y no repite el mail. Si igual se cruzaran (por ejemplo, uno que leyó el CSV de respaldo y no vio la fila), el INSERT encuentra la fila y la corrida termina como `omitida`, también sin mail. **El notebook no respeta nada de esto**: con un programador activo, dejalo de usar. |
| Operar de forma previsible | Los fines de semana y los feriados nacionales (API de ArgentinaDatos, puentes incluidos) la corrida se omite. Con `--forzar` corre igual. Si el calendario no responde, corre: un mail de más es menos grave que un día sin reporte. |
| Corridas que mueren a mitad de camino | Si una corrida insertó la fila y murió antes del párrafo y del mail (timeout, reinicio, la PC suspendida), la siguiente no la toma como día hecho: termina en error, con una alerta que dice cómo rehacer el día (`--forzar`). Cada llamada a Gemini tiene un timeout de 120 s, para que una respuesta colgada no se coma la hora de la corrida. |
| Registrar duración y resultado de cada etapa | Cada etapa queda con estado y segundos en el log (`--log-archivo`) y en un JSON (`--json`). El código de salida es 1 si alguna etapa terminó en error. |
| Alertas útiles | Un error en cualquier etapa manda un único mail con el resumen. `scripts/control_diario.py` cubre la corrida que nunca arrancó: si a la hora del control no está la fila de hoy, falla y alerta. Corriendo en GitHub Actions, cada falla además dispara el aviso por mail de GitHub, que no depende de la contraseña de Gmail del reporte. Las alertas van a `EMAIL_ALERTAS` (si está vacía, a `EMAIL_RECEIVER_CSV`); como llevan tracebacks, conviene que sea solo quien mantiene el proyecto. |
| Credenciales | Los logs tapan cada secreto del `.env` y cada dirección de destinatario (ver "Logs públicos", abajo). |
| CI sin efectos externos | `.github/workflows/ci.yml`: `ruff check` (incluye el orden de los imports), importa todos los módulos y corre los tests, que fallan si intentan salir a la red, abrir una conexión SMTP, bajar datos de Yahoo o lanzar un navegador. Corre en cada push a `main` (salvo los commits de `Previews/`) y en cada PR. |

Sobre "formato": el CI verifica el estilo con las reglas de `ruff check`, no con un formateador. Aplicar `ruff format` hoy cambiaría unas 800 líneas en 26 archivos, también en código que esta rama no tocó; conviene hacerlo en un commit aparte, solo de formato, y recién ahí sumar `ruff format --check` al CI.

## Elegir el programador

Hay dos opciones reales para correrla. No hace falta ningún servidor: la API y el `Dockerfile` que el repo traía para ese caso se sacaron en octubre de 2026, porque no había servidor y no iba a haberlo. Si algún día hace falta, alcanza con un cron que llame a `python pipeline.py`. Quién da la orden es otra decisión, y está al final de la guía.

| | GitHub Actions | Programador de tareas de Windows |
|---|---|---|
| Costo | Gratis (repo público) | Nada |
| Dónde corre | Servidores de GitHub, en EE.UU.: tu PC puede estar apagada | Tu PC, que tiene que estar prendida (no suspendida) a las 17 |
| Logs | **Públicos** (repo público), con los secretos tapados | Privados, en `logs/` |
| Gráficos en `Previews/` y PowerPoint en su rama | Sí: los commits salen a nombre del dueño del repo | Sí, como hoy |
| Aviso si falla | Mail de GitHub, además de la alerta propia | Solo la alerta propia |
| Puntualidad | El cron de GitHub puede atrasarse varios minutos | Exacta |
| Lo que falta | Mergear la rama, cargar los secretos y probar | Mergear la rama y crear la tarea |

La opción recomendada es **GitHub Actions**, con una condición: que las webs argentinas respondan desde los servidores de GitHub. Es lo único que no se puede saber sin probar, y se prueba en dos minutos con el paso 3 de abajo. Si BNA, DolarHoy o Ámbito bloquean esas IPs, la alternativa más simple es el Programador de tareas de Windows.

### GitHub Actions, paso a paso (plan gratis)

En un repo público, GitHub Actions no cobra los minutos de sus máquinas estándar, que son las que usan estos workflows. Cada corrida tarda unos pocos minutos.

1. **Mergear y subir.** Mergear `roadmap/implementacion` a `main` y pushear. GitHub solo muestra y programa los workflows que están en `main`.
2. **Cargar los secretos.** En el repo: Settings > Secrets and variables > Actions, pestaña *Secrets* > New repository secret. Uno por uno, con los mismos valores del `.env`: `EMAIL_SENDER`, `EMAIL_PASSWORD`, `EMAIL_RECEIVER`, `EMAIL_RECEIVER_CSV`, `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, `FED_API_KEY` y `SUPABASE_DB_URL`. Opcional: `EMAIL_ALERTAS`, para que las alertas te lleguen solo a vos.
3. **Probar sin efectos.** Actions > Corrida diaria > Run workflow, con modo `dry-run`. Scrapea y arma todo sin escribir ni mandar nada. Si las etapas `scraping`, `indicadores` y `graficos` terminan en `ok`, las fuentes responden desde los servidores de GitHub. Las etapas con advertencias o errores aparecen como avisos en la página de la corrida, junto con un resumen. Tildando *probar_mail*, el dry-run además manda el reporte de prueba solo a `EMAIL_ALERTAS` (o a `EMAIL_SENDER`): confirma que Gmail acepta el envío desde GitHub, sin tocar la base ni la lista.
4. **Una corrida real, a mano.** Un día que no hayas corrido el notebook: Run workflow con modo `real`. Escribe en Supabase, manda el mail, commitea los gráficos en `Previews/` y publica el PowerPoint en la rama `reporte-ejecutivo`. En GitHub, el commit de `Previews/` tiene que salir con la foto del dueño del repo (el push técnico lo hace el token automático de GitHub Actions, que es lo normal). Si no (pasa con algunas cuentas creadas antes de 2017), creá en la pestaña *Variables* la variable `EMAIL_COMMITS` con el mail de tus commits.
5. **Prender el horario.** En Settings > Secrets and variables > Actions, pestaña *Variables* > New repository variable: nombre `CORRIDA_AUTOMATICA`, valor `si` (vale también `sí`, con o sin mayúscula). Desde ahí corre solo de lunes a viernes a las 16:19 de Argentina, con dos reintentos a las 17:07 y a las 19:12 (no hacen nada si el día ya salió), y el control a las 19:43 (minutos no redondos a propósito: en el minuto cero de cada hora GitHub atrasa y hasta pierde las tareas programadas). Para apagarlo, cambiá el valor a `no`. **Hoy está en `no`** (desde el 13/10/2026): la orden la da la tarea de Windows de abajo, y el horario de GitHub quedó apagado por el episodio del 12/10 (más abajo).
6. **Dejar de correr el notebook.** Si corren los dos el mismo día, sale un mail duplicado.

Si un día el mail salió pero la fila no se guardó (la alerta de la corrida muestra la etapa `persistencia` en error), el modo `sin-mail` del mismo botón carga la fila y hace todo lo demás sin volver a mandar el mail. La corrida completa lo mandaría dos veces.

Tres cosas de GitHub para tener en cuenta:

- **Reglas de protección del repo.** Si `main` exige pull requests, o una regla bloquea los force push en todas las ramas, los commits diarios de la corrida y la publicación del PowerPoint fallan. Si el repo no tiene reglas de ese tipo, no hace falta tocar nada.
- **Las corridas programadas pueden atrasarse** unos minutos cuando GitHub está cargado. Por eso el horario está a los 13 minutos y no en punto, que es cuando más se atrasan.
- **En un repo público, GitHub apaga los horarios después de 60 días sin actividad.** Los commits diarios de `Previews/` cuentan como actividad, así que con la corrida andando no pasa. Si alguna vez pasa, GitHub te avisa por mail y se vuelve a prender desde la pestaña Actions.

### Logs públicos

En un repo público, cualquiera puede leer el log de un workflow. GitHub tapa los secretos completos, pero `EMAIL_RECEIVER` se carga entero como un solo secreto y una dirección suelta (por ejemplo, la de un destinatario rechazado en un error de SMTP) no coincidiría. Por eso `pipeline.py` reemplaza en cada línea de log, traceback incluido, cada secreto del `.env` por `***` y cada dirección de destinatario por `[destinatario]`; el JSON de `--json` pasa por el mismo filtro. Los workflows tampoco suben artefactos: la vista previa del mail y el detalle de los errores no quedan publicados.

### Programador de tareas de Windows, en resumen

Después de mergear, actualizar el venv una vez: `venv\Scripts\pip install -r requirements.txt` (entraron `python-pptx` y sus dependencias). Sin eso la corrida sigue, pero sin el PowerPoint.

Una tarea de lunes a viernes a las 17:00 que ejecute, con la carpeta del proyecto como directorio de inicio:

```
venv\Scripts\python.exe pipeline.py --log-archivo logs\pipeline.log
```

Y otra a las 19:30 con `venv\Scripts\python.exe scripts\control_diario.py`.

## Mandar el reporte desde una casilla del dominio

El remitente (`EMAIL_SENDER`) puede ser un alias del dominio propio, por ejemplo `reporte@globalaize.com`, sin cambiar de proveedor: Gmail sigue mandando, con su contraseña de aplicación, y el alias va en el From. Para eso hay una variable aparte, `EMAIL_LOGIN`, con la cuenta de Gmail con la que se entra al SMTP; vacía, se entra con `EMAIL_SENDER` como siempre.

Pasos, una sola vez:

1. **Recibir.** En Cloudflare, Email Routing (el dominio ya lo usa para `mauro@`): crear la dirección `reporte@globalaize.com` con destino la casilla de Gmail. Las respuestas al reporte llegan ahí, y hace falta para el paso 2.
2. **Enviar como.** En Gmail: Configuración > Cuentas e importación > "Enviar como" > Agregar otra dirección: `reporte@globalaize.com`, con "Tratar como un alias" marcado; servidor SMTP `smtp.gmail.com`, puerto 587, usuario la cuenta de Gmail y una contraseña de aplicación. Gmail manda un código a `reporte@`, que llega por el paso 1.
3. **DNS, para que no caiga en spam.** En Cloudflare, el registro TXT de SPF de `globalaize.com` tiene que incluir a Google además de a Cloudflare: `v=spf1 include:_spf.mx.cloudflare.net include:_spf.google.com ~all`. Y un registro `_dmarc.globalaize.com` TXT `v=DMARC1; p=none; rua=mailto:mauro@globalaize.com` para recibir los informes sin rechazar nada todavía.
4. **El pipeline.** En Settings > Secrets and variables > Actions: `EMAIL_SENDER` pasa a `reporte@globalaize.com` y se crea `EMAIL_LOGIN` con la cuenta de Gmail. Lo mismo en el `.env` local. `EMAIL_PASSWORD` no cambia.
5. **Probar sin la lista.** Actions > Corrida diaria > Run workflow, modo `dry-run` con *probar_mail*: manda el reporte de prueba solo a `EMAIL_ALERTAS`. Si llega con el From nuevo y sin aviso de spam, listo.

## Dos reglas para cualquier programador

**Reintentos, solo los del horario.** En GitHub Actions, los dos reintentos (17:07 y 19:12) son la misma corrida sin `--forzar`: omiten un día terminado y frenan con alerta en uno a medio hacer. No actives ningún otro (ni "Re-run failed jobs" en GitHub ni, en el Programador de tareas, "Si la tarea no se ejecuta correctamente, reiniciar cada"). Una corrida que falló después de insertar la fila no se puede repetir a ciegas: una de las dos variantes del mail puede haber salido. Con la alerta en la mano, el día se rehace con `--forzar` o se reenvía con `scripts/reenvio_manual.py`. Repetir sin `--forzar` es seguro en el otro sentido: omite un día terminado y frena con error en uno a medio hacer.

**`SUPABASE_DB_URL` en modo sesión.** El candado dura lo que la sesión de Postgres. Con una conexión directa, una corrida que muere no lo deja puesto, porque la sesión muere con ella; detrás de un pooler en modo sesión tampoco, siempre que el pooler limpie la conexión al recibirla de vuelta (`DISCARD ALL` suelta los advisory locks). Detrás del pooler de Supabase en modo transacción (puerto 6543), tomarlo y soltarlo pueden caer en conexiones distintas del servidor, y el candado quedaría tomado. Por eso la URL tiene que ir al pooler en modo sesión (puerto 5432, como hoy). La conexión directa también serviría en una PC, pero no en GitHub Actions: es solo IPv6 y las máquinas de GitHub no tienen IPv6. Si aun así quedara tomado, cada corrida terminaría como `omitida` sin escribir la fila, y eso es justamente lo que detecta `scripts/control_diario.py`.

## El disparo confiable: un Worker de Cloudflare da la orden

El horario propio de GitHub (schedule) es "best effort" en el plan gratis: el 08/10/2026 los disparos llegaron con unas 4 horas de atraso, el 09 y el 10 no llegaron, y el 12 llegaron seis horas tarde (al final). La orden manual (workflow_dispatch), en cambio, arranca en segundos. Desde el 14/10/2026 la manda un Worker de Cloudflare, `cloudflare/disparador.js`, con los horarios de `cloudflare/wrangler.toml`: de lunes a viernes a las 16:00 de Argentina pide la corrida en modo `real`, a las 17:07 y a las 19:12 la repite (si el día ya salió, termina como `omitida` sin mandar nada) y a las 19:43 pide el control, con su alerta. Los horarios de Cloudflare (Cron Triggers) son puntuales, gratis en el plan Free (hasta cinco por Worker, y el tope de 100.000 invocaciones por día ni se acerca) y no dependen de ninguna máquina propia. La corrida es la de siempre, en la nube de GitHub: el Worker solo aprieta el botón, con dos reintentos a 30 s si GitHub no responde.

### Ponerlo en marcha

Hace falta Node.js (trae `npx`) y una cuenta de Cloudflare, gratis y sin tarjeta. Un dominio no hace falta: el Worker no tiene URL pública (`workers_dev = false`), solo horarios. Todo se hace desde la carpeta `cloudflare/`.

1. **El token de GitHub.** En GitHub: Settings > Developer settings > Personal access tokens > Fine-grained tokens > Generate new token. Nombre `reporte-macro-disparador`, vencimiento de un año (anotá la fecha), *Repository access*: Only select repositories, este repo; *Permissions* > Repository permissions > Actions: Read and write (Metadata: Read-only se marca sola). Nada más. En *Expiration*, una cuenta personal permite *No expiration*: elegilo, así no hay que renovarlo. Copiá el token: GitHub no lo vuelve a mostrar.
2. **Entrar a Cloudflare desde la consola**, una vez: `npx wrangler@4 login` abre el navegador y pide autorizar (con `--browser=false` imprime el link para abrirlo a mano). La sesión queda en la PC; `npx wrangler@4 logout` la cierra.
3. **Subir el Worker:** `npx wrangler@4 deploy`. Crea el Worker `reporte-macro-disparador` con sus cuatro horarios. Cada cambio de horario en `wrangler.toml` se sube igual. En una cuenta nueva, el primer deploy sube el código pero falla al registrar los horarios con el error 10063, "You need a workers.dev subdomain": el subdominio se crea solo al abrir por primera vez Workers & Pages en el panel, y el segundo deploy entra. Pasó el 14/10/2026.
4. **Cargar el token:** `npx wrangler@4 secret put GITHUB_TOKEN` lo pide por consola, sin mostrarlo, y lo guarda cifrado en Cloudflare. También se puede desde el panel: Workers & Pages > reporte-macro-disparador > Settings > Variables and Secrets. El token no va en ningún archivo.
5. **Verificar, sin efectos.** Un día hábil con el reporte ya salido, el disparo de las 17:07 tiene que aparecer en Actions > Corrida diaria como una corrida `workflow_dispatch` que termina en `omitida`. En Cloudflare, Workers & Pages > reporte-macro-disparador > Logs muestra cada invocación con "disparado" o con el error.

**Si Cloudflare muestra la invocación con error "HTTP 403 Resource not accessible by personal access token"**, el token existe pero no tiene el repo ni el permiso: pasó el 14/10/2026 con el primer token sin vencimiento, que se creó sin marcar nada. Se arregla editando el token en GitHub (Repository access: Only select repositories, este repo; Permissions: Actions Read and write) y apretando Update: el valor del token no cambia, así que el secreto del Worker queda como está. Ese día el reporte salió con `gh workflow run corrida-diaria.yml --ref main -f modo=real` a mano, y el disparo de las 17:07 ya entró con el token corregido (corrida `workflow_dispatch`, `omitida` en 8 segundos).

El Worker tiene tests sin red en `cloudflare/disparador.test.js` (los dos workflows, el reintento ante un 5xx, el 401 que no se reintenta, el secreto ausente): `node --test` desde `cloudflare/`, o `npm test`; el CI los corre en cada push.

**Si un día hábil el Worker no aparece en sus logs**, revisar los días de sus horarios. En Cloudflare el 1 es el domingo, no el lunes como en el cron clásico (y en los workflows de GitHub): con `1-5`, el Worker disparaba de domingo a jueves, y el viernes 16/10/2026 no hubo corrida a las 16:00. Ese día el reporte salió a las 16:14 con `gh workflow run corrida-diaria.yml --ref main -f modo=real`, y los horarios pasaron a `MON-FRI`, que no deja lugar a dudas. Para ver qué disparó y qué no, además del panel, la API de analítica de Cloudflare (`workersInvocationsScheduled`) lista cada invocación programada con su horario y su estado.

### Diagnosticar el Worker desde la consola

Tres preguntas cubren casi todo: si los horarios están registrados, si el Worker corrió y si GitHub recibió la orden. Desde `cloudflare/`, con la sesión de wrangler (el login del paso 2):

```bash
npx wrangler@4 whoami        # además de mostrar la cuenta, renueva el token de la sesión, que vence cada hora
```

Ese token queda en `%APPDATA%\xdg.config\.wrangler\config\default.toml` (`oauth_token`). Con él, en Git Bash:

```bash
TOKEN=$(grep -E '^oauth_token' "$APPDATA/xdg.config/.wrangler/config/default.toml" | sed 's/.*= *"//;s/".*//')
CUENTA=2ff3e0a845fbe4619a9305300671790b

# 1. Los horarios registrados: tienen que decir MON-FRI
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.cloudflare.com/client/v4/accounts/$CUENTA/workers/scripts/reporte-macro-disparador/schedules"

# 2. Las invocaciones programadas desde una fecha, con su estado (success o error)
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  https://api.cloudflare.com/client/v4/graphql -d '{"query":"query { viewer { accounts(filter:{accountTag:\"'$CUENTA'\"}) { workersInvocationsScheduled(limit: 20, filter:{datetime_geq:\"2026-10-16T00:00:00Z\"}, orderBy:[datetime_DESC]) { cron status datetime } } } }"}'
```

Y la tercera, en GitHub: `gh run list --workflow corrida-diaria.yml --limit 5` tiene que mostrar una corrida `workflow_dispatch` por cada invocación con `success`. Cómo leer las respuestas:

| Lo que se ve | Qué pasó | Qué hacer |
|---|---|---|
| Ninguna invocación un día hábil | Los horarios no incluyen ese día (el caso del 16/10/2026) o no están registrados | Revisar los horarios del punto 1 y redesplegar con `npx wrangler@4 deploy` |
| Invocación con `error` | GitHub rechazó la orden: 401 es un token vencido o borrado, 403 un token sin el repo o sin permiso de Actions | En el panel, Workers > reporte-macro-disparador > Observability, el mensaje dice cuál; ver los párrafos de arriba |
| Invocación con `success` y ninguna corrida en GitHub | No debería pasar: el Worker solo marca éxito con un 204 de GitHub | Mirar la pestaña Actions del repo y el estado de GitHub |
| Corrida en GitHub que termina `omitida` | La orden llegó y la corrida decidió no hacer nada: el día ya estaba hecho, era feriado o fin de semana | Nada |

Si el día quedó sin reporte, primero el reporte y después el diagnóstico: `gh workflow run corrida-diaria.yml --ref main -f modo=real` lo manda en un par de minutos.

Si el token tuviera vencimiento y venciera (GitHub avisa por mail una semana antes), GitHub respondería 401, ninguna orden entraría y el control tampoco: el Worker figura fallido en el panel de Cloudflare y el día queda sin reporte hasta que alguien lo dispare a mano (`gh workflow run corrida-diaria.yml --ref main -f modo=real`). Se renueva con un token nuevo y `npx wrangler@4 secret put GITHUB_TOKEN`. Para apagar el Worker del todo: `npx wrangler@4 delete`.

### Por qué tres disparos de la corrida

Los de las 17:07 y las 19:12 son reintentos, no corridas nuevas. Si la de las 16:00 salió bien, cada uno encuentra la fila del día y termina como `omitida` en un minuto, sin tocar nada. Sirven cuando la de las 16:00 falló antes de guardar la fila (BNA o Ámbito caídos un rato, una máquina de GitHub que no arrancó): el reintento hace el día entero. Si falló después de guardar la fila, el reintento frena con error y alerta, nunca repite el mail. Los horarios de GitHub (16:19, 17:07, 19:12 y el control de las 19:43) están apagados (`CORRIDA_AUTOMATICA` en `no`); si se vuelven a prender, la corrida va con `--desde 14:00`.

### Antes del Worker: la tarea de Windows (09 al 14/10/2026)

Esos días la orden la dio la compu del mantenedor, con una tarea del Programador de tareas que ejecutaba `scripts/disparar_corrida.ps1` a las 16:00. Si la compu estaba apagada todo el día no había orden, y como el control era un horario de GitHub, nadie avisaba: pasó el viernes 10/10/2026. Por eso la orden pasó al Worker, y la tarea y el script se borraron el 14/10/2026.

**Por qué el horario de GitHub quedó apagado.** El lunes 12/10/2026, feriado, los tres disparos programados llegaron unas seis horas tarde: 22:25, 22:58 y 00:01. Los dos primeros vieron el feriado y terminaron como `omitida`; el tercero arrancó ya el martes 13, día hábil, y mandó el reporte del 13 a las 00:02 con los valores del cierre anterior (de madrugada ninguna fuente había abierto). La fila se borró a mano y el día se rehízo con una orden manual. Desde entonces el pipeline acepta `--desde HH:MM`: una corrida que arranca antes de esa hora de Argentina termina como `omitida`, igual que un feriado, salvo con `--forzar`. El workflow lo pasa solo en el evento `schedule` (`--desde 14:00`); la orden manual y la de Windows no tienen tope. Es la red de seguridad si el horario se vuelve a prender.
