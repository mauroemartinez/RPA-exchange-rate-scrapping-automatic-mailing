# Fase 6: ejecución programada y monitoreo

Estado al 7 de octubre de 2026: **el programador elegido es GitHub Actions, en el plan gratis, y todo está listo.** Faltan los pasos de abajo, que se hacen a mano porque usan las credenciales del repo. Nada queda programado por el solo hecho de mergear: el horario se prende con una variable del repo (paso 5).

Hoy la corrida se lanza a mano desde el notebook. En los últimos 90 días quedaron tres días hábiles sin fila que no eran feriados: el 19/08, el 24/09 y el 02/10.

## Qué quedó resuelto

| Pedido del roadmap | Cómo quedó |
|---|---|
| Evitar corridas duplicadas entre mecanismos | Advisory lock de Postgres durante toda la corrida (`data_access.candado_corrida`), el control de "la fila de hoy ya existe" y un INSERT que no pisa. Dos disparadores a la vez: uno corre y el otro termina como `omitida`. Uno detrás del otro: el segundo ve la fila y no repite el mail. Si igual se cruzaran (por ejemplo, uno que leyó el CSV de respaldo y no vio la fila), el INSERT encuentra la fila y la corrida termina como `omitida`, también sin mail. **El notebook no respeta nada de esto**: con un programador activo, dejalo de usar. |
| Operar de forma previsible | Los fines de semana y los feriados nacionales (API de ArgentinaDatos, puentes incluidos) la corrida se omite. Con `--forzar` corre igual. Si el calendario no responde, corre: un mail de más es menos grave que un día sin reporte. |
| Corridas que mueren a mitad de camino | Si una corrida insertó la fila y murió antes del párrafo y del mail (timeout, reinicio, la PC suspendida), la siguiente no la toma como día hecho: termina en error, con una alerta que dice cómo rehacer el día (`--forzar`). Cada llamada a Gemini tiene un timeout de 120 s, para que una respuesta colgada no se coma la hora de la corrida. |
| Registrar duración y resultado de cada etapa | Cada etapa queda con estado y segundos en el log (`--log-archivo`) y en un JSON (`--json`). El código de salida es 1 si alguna etapa terminó en error. |
| Alertas útiles | Un error en cualquier etapa manda un único mail con el resumen. `scripts/control_diario.py` cubre la corrida que nunca arrancó: si a la hora del control no está la fila de hoy, falla y alerta. Corriendo en GitHub Actions, cada falla además dispara el aviso por mail de GitHub, que no depende de la contraseña de Gmail del reporte. Las alertas van a `EMAIL_ALERTAS` (si está vacía, a `EMAIL_RECEIVER_CSV`); como llevan tracebacks, conviene que sea solo quien mantiene el proyecto. |
| Endpoints y credenciales | `/run` compara la key con `secrets.compare_digest` y no se habilita sin key. Los logs tapan cada secreto del `.env` y cada dirección de destinatario (ver "Logs públicos", abajo). |
| CI sin efectos externos | `.github/workflows/ci.yml`: `ruff check` (incluye el orden de los imports), importa todos los módulos y corre los tests, que fallan si intentan salir a la red, abrir una conexión SMTP, bajar datos de Yahoo o lanzar un navegador. Corre en cada push a `main` (salvo los commits de `Previews/`) y en cada PR. |

Sobre "formato": el CI verifica el estilo con las reglas de `ruff check`, no con un formateador. Aplicar `ruff format` hoy cambiaría unas 800 líneas en 26 archivos, también en código que esta rama no tocó; conviene hacerlo en un commit aparte, solo de formato, y recién ahí sumar `ruff format --check` al CI.

## Elegir el programador

Hay dos opciones reales. No hace falta ningún servidor (ni EasyPanel ni otro): el `Dockerfile` y la API `/run` de `app.py` quedan para el día que haya uno (ver al final).

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
5. **Prender el horario.** En Settings > Secrets and variables > Actions, pestaña *Variables* > New repository variable: nombre `CORRIDA_AUTOMATICA`, valor `si` (vale también `sí`, con o sin mayúscula). Desde ahí corre solo de lunes a viernes a las 16:19 de Argentina, y el control a las 17:07 (minutos no redondos a propósito: en el minuto cero de cada hora GitHub atrasa y hasta pierde las tareas programadas). Para apagarlo, cambiá el valor a `no`.
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

### Docker y `/run`, solo si algún día hay un servidor

El repo trae un `Dockerfile` y una API (`app.py`, `POST /run`) para correr el reporte en un servidor propio y dispararlo desde afuera. Sin servidor no se usan, y no hace falta tocarlos. `API_KEY_EASY_PANEL` es solo la clave de esa API (el nombre es histórico): sin ella, `/run` no se habilita.

## Dos reglas para cualquier programador

**Sin reintentos automáticos.** No actives los reintentos del programador (en el Programador de tareas, no tildes "Si la tarea no se ejecuta correctamente, reiniciar cada"; GitHub Actions no reintenta solo). Una corrida que falló después de insertar la fila no se puede repetir a ciegas: una de las dos variantes del mail puede haber salido. Con la alerta en la mano, el día se rehace con `--forzar` o se reenvía con `scripts/reenvio_manual.py`. Repetir sin `--forzar` es seguro en el otro sentido: omite un día terminado y frena con error en uno a medio hacer.

**`SUPABASE_DB_URL` en modo sesión.** El candado dura lo que la sesión de Postgres. Con una conexión directa, una corrida que muere no lo deja puesto, porque la sesión muere con ella; detrás de un pooler en modo sesión tampoco, siempre que el pooler limpie la conexión al recibirla de vuelta (`DISCARD ALL` suelta los advisory locks). Detrás del pooler de Supabase en modo transacción (puerto 6543), tomarlo y soltarlo pueden caer en conexiones distintas del servidor, y el candado quedaría tomado. Por eso la URL tiene que ir al pooler en modo sesión (puerto 5432, como hoy). La conexión directa también serviría en una PC, pero no en GitHub Actions: es solo IPv6 y las máquinas de GitHub no tienen IPv6. Si aun así quedara tomado, cada corrida terminaría como `omitida` sin escribir la fila, y eso es justamente lo que detecta `scripts/control_diario.py`.
