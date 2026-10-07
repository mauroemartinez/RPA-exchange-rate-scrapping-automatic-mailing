# Fase 6: ejecución programada y monitoreo

Estado al 7 de octubre de 2026: **todo lo de esta fase está listo menos la elección del programador, que es tuya.** Nada queda programado por el solo hecho de mergear: los workflows de GitHub se disparan a mano hasta que descomentes su `schedule`.

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

| | GitHub Actions | EasyPanel (contenedor + `/run`) | Programador de tareas de Windows |
|---|---|---|---|
| Costo | Gratis (repo público) | El servidor de EasyPanel | Nada |
| Dónde corre | Servidores de GitHub, en EE.UU. | Tu servidor | Tu PC, que tiene que estar prendida |
| Logs | **Públicos** (repo público) | Privados | Privados |
| `Previews/` en GitHub | Sí, el workflow commitea y pushea | No: el contenedor no tiene git | Sí, como hoy |
| Aviso si falla | Mail de GitHub, además de la alerta propia | Solo la alerta propia (mismo Gmail) | Solo la alerta propia |
| Puntualidad | El cron de GitHub puede atrasarse varios minutos | Exacta | Exacta |
| Lo que falta | Cargar secretos y probar | Desplegar la imagen, poner `API_KEY_EASY_PANEL` y un cron (n8n u otro) que llame a `/run` | Crear la tarea |

Mi recomendación es **GitHub Actions**, con una condición: que las webs argentinas respondan desde los servidores de GitHub. Es lo único que no se puede saber sin probar, y se prueba en dos minutos con el paso 2 de abajo. Si BNA, DolarHoy o Ámbito bloquean esas IPs, la alternativa más simple es el Programador de tareas de Windows.

### GitHub Actions, paso a paso

1. En el repo: Settings > Secrets and variables > Actions > New repository secret. Cargar `EMAIL_SENDER`, `EMAIL_PASSWORD`, `EMAIL_RECEIVER`, `EMAIL_RECEIVER_CSV`, `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, `FED_API_KEY` y `SUPABASE_DB_URL`, con los mismos valores del `.env`. Opcional: `EMAIL_ALERTAS`.
2. Actions > Corrida diaria > Run workflow, con modo `dry-run`. Scrapea y arma todo sin escribir ni mandar nada. Si la etapa `scraping` termina en `ok`, las webs responden desde GitHub.
3. Un día que no hayas corrido el notebook: Run workflow con modo `real`. Es la corrida completa: escribe en Supabase, manda el mail y pushea `Previews/`.
4. En `.github/workflows/corrida-diaria.yml`, descomentar el bloque `schedule` (17:00 de Argentina, de lunes a viernes) y hacer lo mismo en `control-diario.yml` (19:30). Commitear en `main`.
5. Dejar de correr el notebook.

### Logs públicos

En un repo público, cualquiera puede leer el log de un workflow. GitHub tapa los secretos completos, pero `EMAIL_RECEIVER` se carga entero como un solo secreto y una dirección suelta (por ejemplo, la de un destinatario rechazado en un error de SMTP) no coincidiría. Por eso `pipeline.py` reemplaza en cada línea de log, traceback incluido, cada secreto del `.env` por `***` y cada dirección de destinatario por `[destinatario]`; el JSON de `--json` pasa por el mismo filtro. Los workflows tampoco suben artefactos: la vista previa del mail y el detalle de los errores no quedan publicados.

### EasyPanel, en resumen

Construir la imagen desde el repo con el `Dockerfile`, cargar las variables del `.env` (más `API_KEY_EASY_PANEL`) y programar un POST a `https://<servicio>/run` con el header `x-api-key`, por ejemplo con el Schedule Trigger de n8n. Para probar sin efectos: `POST /run?dry_run=true`. El control diario se puede correr en el mismo contenedor con `python scripts/control_diario.py` desde otro cron.

### Programador de tareas de Windows, en resumen

Una tarea de lunes a viernes a las 17:00 que ejecute, con la carpeta del proyecto como directorio de inicio:

```
venv\Scripts\python.exe pipeline.py --log-archivo logs\pipeline.log
```

Y otra a las 19:30 con `venv\Scripts\python.exe scripts\control_diario.py`.

## Dos reglas para cualquier programador

**Sin reintentos automáticos.** No actives los reintentos del programador (el "Retry On Fail" de un nodo de n8n, o el "Si la tarea no se ejecuta correctamente, reiniciar cada" del Programador de tareas; GitHub Actions no reintenta solo). Una corrida que falló después de insertar la fila no se puede repetir a ciegas: una de las dos variantes del mail puede haber salido. Con la alerta en la mano, el día se rehace con `--forzar` o se reenvía con `scripts/reenvio_manual.py`. Repetir sin `--forzar` es seguro en el otro sentido: omite un día terminado y frena con error en uno a medio hacer.

**`SUPABASE_DB_URL` en modo sesión.** El candado dura lo que la sesión de Postgres. Con una conexión directa, una corrida que muere no lo deja puesto, porque la sesión muere con ella; detrás de un pooler en modo sesión tampoco, siempre que el pooler limpie la conexión al recibirla de vuelta (`DISCARD ALL` suelta los advisory locks). Detrás del pooler de Supabase en modo transacción (puerto 6543), tomarlo y soltarlo pueden caer en conexiones distintas del servidor, y el candado quedaría tomado. Por eso la URL tiene que ir al pooler en modo sesión (puerto 5432, como hoy) o a la conexión directa. Si aun así quedara tomado, cada corrida terminaría como `omitida` sin escribir la fila, y eso es justamente lo que detecta `scripts/control_diario.py`.
