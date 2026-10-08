# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What this project does

Daily automated pipeline that scrapes Argentine FX rates and macroeconomic indicators, stores them in Supabase, generates charts (monetary aggregates and public debt in USD among them), an AI-written narrative via Gemini and an executive PowerPoint deck, and emails a styled HTML report to a subscriber list. The daily run lives in `pipeline.py`, a plain Python entry point with no Jupyter dependency, scheduled on GitHub Actions (free plan). A FastAPI wrapper (`app.py`) exposes a `/run` endpoint that executes the same pipeline, for the day the report runs on a server.

## Running the project

**Locally (CLI):**
```bash
python pipeline.py --dry-run                          # scrapes and builds everything, writes and sends nothing
python pipeline.py --dry-run --enviar-a yo@mail.com   # same, but the mail goes only to that address
python pipeline.py                                    # the real daily run
```

A real run has side effects: it writes to Supabase, emails the whole subscriber list, commits and pushes the charts in `Previews/`, and publishes the deck to the `reporte-ejecutivo` branch. To verify a code change use `--dry-run`, optionally with `--enviar-a`, never a plain run. `--dry-run --con-ia` also asks Gemini for the per-chart comments (one structured request, plus its retries) to preview them, without saving them. `--enviar-a` and `--con-ia` only go with `--dry-run`, and `--enviar-a` never with `--sin-mail`; the CLI rejects those combinations. Other flags: `--sin-mail` (everything except the email), `--sin-push` (no git), `--forzar` (redo today even if its row already exists: it overwrites the row and emails again; it is also how to finish a day whose previous run died halfway), `--salida DIR`, `--log-archivo FILE` and `--json FILE` (machine-readable result). The exit code is 1 when any stage ends in error, so a scheduler can tell a failed run from a good one.

`--dry-run` scrapes the live sources and reads Supabase, but does not write to Supabase, does not call Gemini, does not send the mail and does not touch git. It leaves the six charts, the deck, `mail_preview.html` (opens in a browser) and `mail.eml` (opens in a mail client) in a temp folder, or in `--salida`. It never writes anywhere inside `Previews/`, because that folder gets auto-committed.

**Notebook (retired):** `notebooks/Argentinian_Macroeconomic_Automatic_Mailing.ipynb` is retired: GitHub Actions runs the daily report, and running the notebook as well would mail the list twice. It stays only as a historical reference and no longer runs as is: it imports the modules from the root, where they lived before they moved into `reporte/`. The kernel must use the venv Python, configured in `venv/share/jupyter/kernels/python3/kernel.json` with the full path to `venv/Scripts/python.exe`.

**Via Docker (optional, only if the report ever runs on a server):**
```bash
docker build -t macro-mailing .
docker run --env-file .env -p 8000:8000 macro-mailing
# trigger execution:
curl -X POST http://localhost:8000/run -H "x-api-key: <API_KEY_EASY_PANEL>"
# end-to-end check of a deployment, with no side effects:
curl -X POST "http://localhost:8000/run?dry_run=true" -H "x-api-key: <API_KEY_EASY_PANEL>"
```

`/run` executes `pipeline.py` in a child process, so a hung run can be killed by the timeout and every run starts from a clean interpreter. The response carries the state and duration of each stage but no error details, which stay in the container log. There is no server today: the daily run is meant for GitHub Actions or the Windows Task Scheduler (see "Scheduling and monitoring"), and `API_KEY_EASY_PANEL` is only the `/run` key, with a historical name.

Scraping runs on Playwright (Chromium) in both environments, with no Edge/Chrome branching. The Dockerfile installs the browser via `playwright install --with-deps chromium` at build time; locally you need to run that once yourself (see below).

**Install dependencies:**
```bash
python -m venv venv
.\venv\Scripts\activate                # PowerShell
pip install -r requirements-dev.txt    # production dependencies plus notebook, pytest and ruff
playwright install chromium            # required once, for the scrapers
```

`requirements.txt` holds only what production imports, and it is what the Docker image installs. The three lock files (`requirements.txt`, `requirements-dev.txt` and `dashboard/requirements.txt`) are generated from their `.in` with `uv pip compile` (the command is in the header of each `.in`); the dashboard's is constrained by the other two, so one venv can hold all three. Do not regenerate them with `pip freeze > requirements.txt` from PowerShell 5: it writes UTF-16 and pins whatever happens to be installed.

**Tests and lint:**
```bash
pytest         # offline: no network, no Supabase, no SMTP
ruff check .
```

The test suite loads fake credentials over any real `.env`, and fails any test that tries to open a real SMTP connection, make a real HTTP request, download from Yahoo or launch a browser, so it is always safe to run. It covers the transformations, charts, email assembly, the pipeline orchestration through fake dependencies, the idempotent insert, `preview_git` against temporary git repos, the Gemini failover, the API and the manual resend. `tests/test_html_golden.py` pins the mail's HTML byte for byte against `tests/datos/`: when a change to the HTML is intended, regenerate those files with `ACTUALIZAR_GOLDEN=1 pytest tests/test_html_golden.py` and commit the diff together with the change.

**Scheduling and monitoring:** `.github/workflows/` holds the CI (lint, imports, tests; runs on push and PR) and two scheduled workflows: `corrida-diaria.yml` (the daily run, 16:00 in Argentina, Monday to Friday) and `control-diario.yml` (fails when a business day has no row, 17:00). Their schedules only run when the repository variable `CORRIDA_AUTOMATICA` is `si` (Settings > Secrets and variables > Actions > Variables), so they are switched on and off without editing YAML and a merge cannot start them by surprise; manual dispatch always works, in dry-run by default. The setup steps, and the comparison with the Windows Task Scheduler, are in `docs/programacion-y-monitoreo.md`. Commits made by the workflow carry the repo owner's name and GitHub noreply address (or the address in the `EMAIL_COMMITS` variable), never a bot's. `python scripts/control_diario.py --sin-alerta` checks today's row without sending the alert email.

**Resend today's report to one person:**
```bash
python scripts/reenvio_manual.py alguien@mail.com
python scripts/reenvio_manual.py alguien@mail.com --dry-run   # builds it, sends nothing
```
See "Manual resend" below.

## Architecture

`pipeline.py` runs these stages in order. Each one is recorded with its state (`ok`, `advertencia`, `error` or `omitida`) and its duration, and the whole run returns a `ResultadoCorrida`:

1. **Control:** takes a Postgres advisory lock (`data_access.candado_corrida`) so two triggers cannot run at once (the second one ends as `omitida`), then skips weekends and national holidays (`reporte/scrapers/feriados.py`, ArgentinaDatos, bridge days included; if the calendar API fails, the run goes ahead)
2. **historico:** `data_access.leer_historico()` reads the full `Fact_Mercado_Macro` table, newest row first; falls back to the local CSV at `RUTA_BBDD` if Supabase fails. With the history in hand the day is checked: if today's row already exists the run ends as `omitida`, unless that row has no `ai_paragraph`, which means the run that inserted it died before the AI and the mail; that is an `error`, with an alert that says to rerun with `--forzar`. `--forzar` overrides the calendar and the existing-row checks
3. **scraping:** `reporte.scrapers.run_all_sync()` runs all six sources concurrently via `asyncio.gather()` and returns their results in a fixed order: BNA (billetes + divisas tabs), DolarHoy (blue), Ambito (MEP + euro blue), riesgo país, BCRA (BADLAR id=140 and monthly inflation id=27), and the St. Louis FED (EFFR). The three HTTP sources share one `httpx.AsyncClient`. A `ScraperError` emails an alert and stops the run
4. **validacion:** `transformations.armar_fila_nueva()` builds today's row and `models.FilaMacro` validates it. If a scraper returned invalid, non-positive, or malformed values, the run emails the developer and stops before anything is persisted
5. **persistencia:** `data_access.guardar_fila()`, one atomic `INSERT ... ON CONFLICT ("Fecha") DO NOTHING` (`DO UPDATE` under `--forzar`). If the insert finds the row anyway (another trigger wrote it in between), the run stops as `omitida` instead of mailing the list a second time
6. **ia:** once the `ai_secciones` column exists, one structured Gemini call returns a summary (the AI box at the top) plus a comment per chart block (parallel rates, official rates, country risk, BTC); `models.SeccionesIA` validates it and `ia_generator.guardar_secciones` saves the summary to `ai_paragraph` and the comments to `ai_secciones`. Without the column, or if anything in the structured path fails (the call, the validation or the save), it falls back to `ia_generator.procesar_y_guardar_parrafo(engine, fecha_esperada=hoy)`, the original single paragraph, which refuses to write when the newest row is not today's; the fallback also clears `ai_secciones`, so a `--forzar` rerun cannot keep comments written for the previous values. Every Gemini call has a 120 s timeout. BTC is downloaded just before this stage because its comment needs it
7. **indicadores:** downloads two years (plus a margin) of the BCRA series behind the two new charts: monetary aggregates, inflation, BCRA letters in pesos and in foreign currency, transitory advances to the Treasury, loans to the private sector, and the A3500 wholesale rate; plus the Treasury's gross debt from the Secretaría de Finanzas monthly Excel (`reporte/scrapers/finanzas.py`, read by labels, with provisional months flagged). Each series is validated on its own: a broken one is dropped, a stale one is used with a notice. It only reads, so it also runs in a dry run; a source that fails is a warning and the mail goes without the chart that needs it
8. **graficos:** `reporte/charts.py` draws six JPGs: the four of the notebook plus `Agregados Monetarios.jpg` and `Deuda en Dólares.jpg`. Debt is always shown in USD: series published in pesos are converted, only for display, with the A3500 rate of each day. BTC/USD comes from Yahoo Finance through `reporte/scrapers/btc.py`; if Yahoo fails, the mail goes out without that chart instead of the whole run dying
9. **mail:** `reporte/email_report.py` renders `reporte/templates/report_email.html` with Jinja2 and sends the two variants in parallel: one to `EMAIL_RECEIVER`, and one to `EMAIL_RECEIVER_CSV` with the full history attached as CSV, generated at send time from the same data as the report. The two new charts carry a plain-language explanation plus one sentence computed in Python with the latest figures and their dates (`reporte/indicadores.py`); Gemini does not write those. A failed send marks the run as failed
10. **presentacion:** `reporte/presentacion.py` builds the eight-slide executive deck, `Reporte Ejecutivo.pptx`, from today's data, the AI texts of this run and the charts generated in this run; a missing chart gets a placeholder slide. It saves to a temporary file and replaces the deck only when the save finished. A failure here is only a warning: the mail has already gone out
11. **previews:** `reporte/preview_git.py` commits and pushes the six charts in `Previews/` on `main` (only from `main`, checking every git exit code), and publishes the deck to the `reporte-ejecutivo` branch: a parentless commit holding only the file, force-pushed, so that branch always has a single commit with the latest deck and versions never accumulate. Only a deck built in this run is published; a failed publication is a warning
12. **series:** upserts what `indicadores` downloaded into `Fact_Series_Macro` (daily series: the last 120 days; monthly: whole), each series on its own, so a discontinued one does not stop the rest. Without the table the stage is skipped with a notice, and a failure here is only a warning

Any stage in `error` sets exit code 1 and triggers one summary alert email, unless the failure already sent its own (scraper down, validation). The calculations (spreads, daily changes, Irving Fisher forwards, inflation accumulations) live in `reporte/transformations.py` as pure functions with no I/O.

The pipeline is a faithful port of the notebook: fed the same inputs, the four JPGs, the HTML and both MIME messages come out byte-identical, except for three intentional changes made afterwards: the accumulated inflation line in `Variaciones.jpg`, one decimal on the right axis of `Gráficos Inflación.jpg`, and the CSV attachment, now built from the same data as the report instead of the local file.

## Key files

| File | Purpose |
|---|---|
| `pipeline.py` | Daily run and its CLI: stage orchestration, result per stage, alerts |
| `reporte/` | The package with every module the run uses (below); `pipeline.py` and `app.py` are the only Python files at the root. Imports are absolute: `from reporte import charts`, `from reporte.config import settings` |
| `reporte/data_access.py` | Supabase engine, historical read (with the CSV fallback), idempotent insert of today's row, run lock |
| `reporte/transformations.py` | Today's row, validation, spreads and daily changes, Fisher forwards, inflation series |
| `reporte/charts.py` | Data preparation and drawing of the six charts |
| `reporte/email_report.py` | Tables, HTML rendering, MIME assembly and sending through `mailer.enviar_smtp`; shared with the manual resend |
| `reporte/presentacion.py` | The daily executive `.pptx`: cover, indicators, AI summary, three chart slides with their comments, and the aggregates and debt slides with their explanations |
| `reporte/preview_git.py` | Commit and push of the charts in `Previews/`, and publication of the deck on its own branch |
| `reporte/indicadores.py` | Plain-language explanations of the aggregates and debt charts, plus the sentence with the latest figures, computed in Python |
| `reporte/fechas.py` | Today's date in Argentina time and Spanish month names, independent of the machine's timezone and locale |
| `reporte/config.py` | Typed, validated settings loaded once from `.env`; import `settings` from here instead of reading `os.environ` |
| `reporte/models.py` | The row's columns in table order (`COLUMNAS_*`), its Pydantic schema (the validation contract before persistence) and `SeccionesIA`, which validates Gemini's structured answer. It does not import `config`, so the calculation modules load without a `.env` |
| `reporte/ia_generator.py` | Gemini integration: queries Supabase, builds the prompts, calls the API with key and model failover, saves the paragraph or the per-chart sections |
| `reporte/mailer.py` | The only SMTP code: `enviar_smtp`, which the report uses too, and the plain-text failure alerts, sent to `EMAIL_ALERTAS` |
| `app.py` | FastAPI wrapper whose `/run` executes `pipeline.py` |
| `Dockerfile` | Linux/Chromium image for containerized execution |
| `reporte/scrapers/` | Playwright scrapers (`bna.py`, `dolarhoy.py`, `ambito.py`), async REST clients (`bcra.py`, `fed.py`, `riesgo_pais.py`), `btc.py` (Yahoo Finance), `finanzas.py` (the Secretaría de Finanzas debt Excel), `utils.py` (retry, `ScraperError`, event-loop helper) and `__init__.py` (`run_all_sync()`, which runs the first six concurrently) |
| `reporte/templates/report_email.html` | Jinja2 template for the HTML email report: CSS plus markup, rendered by `reporte/email_report.py` |
| `notebooks/Argentinian_Macroeconomic_Automatic_Mailing.ipynb` | The original pipeline, kept as a reference during the transition |
| `scripts/backfill.py` | Repairs historical `riesgo_pais` and `bcra_tea` series against their source APIs. Dry-run by default, writes only with `--apply`. |
| `scripts/reenvio_manual.py` | Resends the latest report to arbitrary recipients without rerunning the pipeline |
| `scripts/agregados_monetarios.py` | Summary and preview charts of the aggregates and debt series; `--guardar` loads their full history into `Fact_Series_Macro` |
| `scripts/control_diario.py` | Dead man's switch: on a business day without today's row, exits 1 and emails an alert (`--sin-alerta` only reports). Read-only |
| `reporte/scrapers/feriados.py` | National holidays from ArgentinaDatos, used to skip non-business days |
| `.github/workflows/` | CI, plus the daily run and the daily control, scheduled but switched on only by the `CORRIDA_AUTOMATICA` repository variable |
| `scripts/presentacion_ejecutiva.py` | Builds the same deck by hand from the stored row and `Previews/` (a thin CLI over `reporte/presentacion.py`). Read-only |
| `dashboard/app.py` | Prototype (roadmap phase 5), to be reviewed later: Streamlit dashboard over the full history, with its own `dashboard/requirements.txt`. Read-only, does not import `reporte/config.py` |
| `notebooks/laboratorio_sql.ipynb` | Read-only SQL lab: every query run through its `consulta()` goes inside a `READ ONLY` transaction |
| `reporte/scrapers/agregados.py` | Catalog of the stored series (key, source id, frequency, unit, source): BCRA aggregates, inflation, debt-related series and the A3500 rate, plus the Treasury's gross debt; paginated BCRA download |
| `docs/` | Roadmap notes in Spanish: the cache evaluation, phase 3 (aggregates and debt, with the debt definition chosen), the PowerPoint and Streamlit evaluation, and the scheduling and monitoring guide (GitHub Actions setup) |
| `Assets/` | The README architecture diagrams; `Assets/arquitectura/construir.py` regenerates both from HTML with Chromium, keeping the style |
| `sql/` | SQL scripts applied by hand in Supabase: DB setup, historical data cleaning, and the migrations `06_series_macro.sql` and `07_ai_secciones.sql`, each with a plain-Spanish header (what it does, how to apply, verify and undo it) |
| `tests/` | Offline test suite; `tests/datos/` holds the golden HTML of the mail |
| `pyproject.toml` | pytest and ruff configuration |

## Environment variables (`.env`)

All of these are declared and validated in `reporte/config.py`. A missing or malformed value fails at import time rather than midway through a run.

```
EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER, EMAIL_RECEIVER_CSV
EMAIL_ALERTAS            # Who gets the technical alerts (optional; empty means EMAIL_RECEIVER_CSV)
SUPABASE_DB_URL          # PostgreSQL connection string, in session mode (see "Important constraints")
RUTA_BBDD                # Path to the CSV read when Supabase is down (relative paths resolve against the repo root)
RUTA_REPO                # Path to repo root (for the git push step)
FED_API_KEY              # St. Louis FRED API key
GEMINI_API_KEY_1         # Primary Gemini key
GEMINI_API_KEY_2         # Failover Gemini key (rotated on HTTP 429)
API_KEY_EASY_PANEL       # Key for POST /run in app.py, only if the API runs on a server (blank: /run answers 503)
SERVICE_ROUTE            # Deployment URL (optional, currently unread)
```

`EMAIL_RECEIVER` and `EMAIL_RECEIVER_CSV` are comma-separated lists, each address validated individually. The git step only runs when `RUTA_REPO` is the folder that holds the code, so a checkout elsewhere never commits into another repo. Alerts carry tracebacks, so `EMAIL_ALERTAS` is best set to the maintainer alone; the log redaction covers it like the report's recipients.

Two GitHub repository variables (not in `.env`) control the workflows: `CORRIDA_AUTOMATICA` (`si` turns the schedules on) and, optionally, `EMAIL_COMMITS` (the address for the workflow's commits). The secrets the workflows need are the `.env` values above, loaded under Settings > Secrets and variables > Actions.

The dashboard does not read `reporte/config.py`. It takes `DASHBOARD_DB_URL`, a read-only user (without it, it falls back to `SUPABASE_DB_URL` and says so on screen), or `DASHBOARD_CSV`, from Streamlit secrets or the environment.

## Supabase table: `Fact_Mercado_Macro`

Primary key: `Fecha` (date). Columns: `TCC_Blue`, `TCV_Blue`, `TCC_Billete`, `TCV_Billete`, `TCC_Divisas`, `TCV_Divisas`, `Solidario`, `TCV_MEP`, `riesgo_pais`, `TCC_Euro`, `TCV_Euro`, `fed_tea`, `bcra_tea`, `ai_paragraph`, `ai_model`, and once `sql/07_ai_secciones.sql` is applied, `ai_secciones` (jsonb with the per-chart comments and the model). New columns go at the end of the table: the email takes the first 14 by position. Applying `sql/07_ai_secciones.sql` while the notebook is still in daily use is safe: the notebook reads `SELECT *` but builds the email table from those first 14 columns, and its insert sends a fixed column list that does not include `ai_secciones`.

## Supabase table: `Fact_Series_Macro`

Long format, one row per series and date: `serie`, `Fecha`, `valor`, `frecuencia` (`D`, `M`, `T`, `A`), `unidad`, `fuente`, `id_fuente`, `actualizado_en`. Primary key `(serie, Fecha)`. Values keep the unit and the dates of their source (the BCRA publishes the base in millions of ARS and M3 in thousands; the Secretaría de Finanzas, gross debt in millions of USD at month end); convert only for display. Stored series: the monetary aggregates (`base_monetaria`, `circulacion_monetaria`, `billetes_publico`, `m2`, `m2_transaccional_privado`, `m3`), inflation (`inflacion_mensual`, `inflacion_interanual`), debt (`letras_bcra_pesos`, `letras_bcra_moneda_extranjera`, `adelantos_transitorios`, `prestamos_sector_privado`, `deuda_bruta_tesoro`) and `tipo_cambio_mayorista` (A3500, for the USD conversion). The table is created by `sql/06_series_macro.sql`, applied by hand, never by the code. Its upsert only rewrites values that changed, so `actualizado_en` marks the last real revision.

## Manual resend

`scripts/reenvio_manual.py` sends the most recent report to whichever addresses you pass on the command line. Use it when someone joins the list mid-month, or when a subscriber did not get the mail.

```bash
python scripts/reenvio_manual.py alguien@mail.com
python scripts/reenvio_manual.py uno@mail.com otro@mail.com
python scripts/reenvio_manual.py alguien@mail.com --csv       # attaches the tracking CSV
python scripts/reenvio_manual.py alguien@mail.com --dry-run   # builds it, writes a preview, sends nothing
```

It does not rerun the pipeline: no scraping, no row validation, no upsert, no Gemini call, no git push. It replays what the daily run already produced, namely the newest `Fact_Mercado_Macro` row, the `ai_paragraph` and per-chart comments (`ai_secciones`) stored on it, and the six JPGs in `Previews/`. It refetches only what the table does not hold: the BCRA monthly inflation, and the series behind the sentences under the aggregates and debt charts (recomputed with the latest published data). It dates each chart by its last commit when the file has no local changes, so with the daily run on GitHub Actions, run `git pull` first; otherwise the charts look old and are left out. It renders through `reporte/email_report.py`, the same code as the daily run, so its HTML is identical to the daily mail apart from the performance timing line. With several recipients they go in Bcc so they cannot see each other.

Three guardrails worth knowing: it aborts if the newest row has no `ai_paragraph` (the pipeline did not finish, or Gemini returned nothing that day); it warns when that row is not from today; and it leaves out any chart in `Previews/` older than the row's date, as the daily mail does with a chart that failed, instead of attaching a previous day's image. `--dry-run` writes its preview to the system temp directory, deliberately not to `Previews/`, because the pipeline auto-commits anything that lands in that folder.

## Important constraints

- **Scrapers depend on each site's HTML structure.** BNA, DolarHoy, and Ambito (`reporte/scrapers/`) use short CSS and id-based Playwright selectors, but still break if a site changes its markup. A broken selector raises a `ScraperError` carrying site and step context instead of silently leaving NaN columns in the new row.
- **Validation gate before persistence.** If the newly built row does not satisfy the Pydantic schema, the run fails fast and notifies the developer instead of saving a bad record.
- **Today's date comes from `fechas.hoy()`,** computed in America/Argentina/Buenos_Aires. Never use `datetime.today()` or `date.today()` for the row date: the container runs in UTC, and a run after 21:00 would stamp the next day.
- **No `locale.setlocale()`.** Spanish month names come from `fechas.MESES_ABREV`. The slim Docker image has no Spanish locale (the call raises there), and the locale is process-wide state.
- **Charts never use pyplot's global state.** Each one is drawn on its own `matplotlib.figure.Figure` inside an `rc_context` that starts from the same base style, so a chart cannot leak its style into the next one or into the next run.
- **`charts.FECHA_INICIO_VARIACIONES`,** the start of the variaciones acumuladas chart, is hardcoded to `"2025-07-01"`. Update it when the reference period changes. The chart must receive the full inflation series, not the 12 months of the table: with only 12 months, the inflation line starts later than the dollar lines once the period is longer than a year.
- **`ia_generator` requires at least 26 rows** in Supabase to compute 25-session rolling variations; it raises an exception otherwise.
- **Jupyter's event loop cannot run scraper coroutines directly.** `ipykernel` already runs its own asyncio loop, and on Windows that loop cannot spawn subprocesses, which Playwright needs for its browser driver. Callers use the sync wrapper `reporte.scrapers.run_all_sync()`, which runs the coroutines in a separate thread with its own event loop (`run_async` in `reporte/scrapers/utils.py`). Do not call `asyncio.run()` or a bare `await` directly in a notebook cell for scraping.
- **Send failures.** In the pipeline a failed send marks the run as failed (exit code 1) and is logged with the SMTP error. The notebook still catches and prints them, so there a bad Gmail App Password surfaces as a `535` line and nothing else. Since alerts use the same credentials, they fail with it; the exit code is the signal that survives. Test SMTP changes with `python pipeline.py --dry-run --enviar-a <your address>`.
- **Gemini only writes; Python computes.** Every figure in the prompts is calculated beforehand, and the structured answer must pass `models.SeccionesIA` before it reaches the email. The schema sent to the API carries only types and required fields; the length limits live in the Pydantic model.
- **Keep the `httpx` logger at WARNING or above.** It logs full request URLs at INFO, and the FRED request carries the API key in its query string.
- **Logs can be public.** On GitHub Actions in this public repo, anyone can read a run's log. `pipeline.configurar_logging` installs a formatter that replaces every secret from `.env` with `***` and every recipient address with `[destinatario]`, tracebacks included, and `--json` output goes through the same `redactar()`. Keep new output inside `logging`, and never upload the mail preview or error details as workflow artifacts.
- **Anything that can send mail is verified with the sending stubbed or disabled.** `pipeline.py --dry-run`, `scripts/reenvio_manual.py --dry-run`, `scripts/control_diario.py --sin-alerta`. A real run of the control before the day's run sends a real (false) alert.
- **No automatic retries in the scheduler.** A run that fails after inserting the row is not safe to repeat blindly: one of the two mail variants may already be out. Let it fail, read the alert, and redo the day with `--forzar` or resend with `scripts/reenvio_manual.py`. A plain rerun is safe the other way around: it skips a finished day and stops with an error on an unfinished one.
- **The run lock needs a session-mode connection.** `pg_try_advisory_lock` holds until the session ends or is reset. On a direct connection a killed run does not leave it behind, and behind a session-mode pooler neither, as long as the pooler resets the connection it gets back (`DISCARD ALL` releases advisory locks). Behind Supabase's pooler in transaction mode (port 6543) the lock and its release can land on different server connections and the lock would stay held; keep `SUPABASE_DB_URL` on the session pooler (port 5432). A direct connection also works from a PC, but not from GitHub Actions: Supabase's direct host is IPv6-only and GitHub's runners have no IPv6. If it ever stayed held, every run would end as `omitida` without writing the row, which is exactly what `scripts/control_diario.py` catches.
- **The deck never goes into `main`.** `Previews/*.pptx` is ignored; the deck lives only on the `reporte-ejecutivo` branch, rebuilt as a single commit every day. Do not add it to the `Previews/` commit: every daily version would stay in the history.
- **Debt is always shown in USD.** Stored values keep the source unit; the conversion with the A3500 rate of each date happens only for charts and texts.
- **Reinstall the requirements after pulling dependency changes.** `python-pptx` (deck) and `openpyxl` (debt Excel) are production dependencies. A venv without `python-pptx` still sends the mail, and the deck stage warns; without `openpyxl`, the debt chart goes out without the Treasury's gross debt.
- **Column order matters in the email.** The cotizaciones table is built with `df.iloc[:, :14]`, so it depends on the column order coming back from Supabase. Adding a column to the table in the wrong position silently reshuffles the mail.
- **Analysis tools only read.** The SQL lab and the dashboard never write to Supabase and never reimplement the report: they consume the warehouse and the existing modules. The executive deck is built inside the pipeline from the same in-memory data as the mail. The dashboard must not get the pipeline's credentials; if it is ever published, give it a read-only role (`docs/evaluacion-powerpoint-y-streamlit.md` has the SQL, including the RLS policy that role needs).
- **Writing style for this repo: no em dashes,** in documentation, comments, or commit messages.
