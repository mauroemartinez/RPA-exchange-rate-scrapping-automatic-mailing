# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What this project does

Daily automated pipeline that scrapes Argentine FX rates and macroeconomic indicators, stores them in Supabase, generates charts and an AI-written narrative via Gemini, and emails a styled HTML report to a subscriber list. A FastAPI wrapper (`app.py`) exposes a `/run` endpoint so the notebook can be triggered by n8n or any HTTP scheduler.

## Running the project

**Locally (notebook):** Open `notebooks/Argentinian_Macroeconomic_Automatic_Mailing.ipynb` in VS Code and run all cells top to bottom. The first cell walks up to the project root (it looks for `config.py`) and `chdir`s there, so every relative path in the rest of the notebook resolves against the repo root regardless of where Jupyter started. The kernel must use the venv Python, configured in `venv/share/jupyter/kernels/python3/kernel.json` with the full path to `venv/Scripts/python.exe`.

Running the notebook has real side effects: it writes to Supabase, emails the whole subscriber list, and commits to git. Never run it end to end just to verify a code change.

**Via Docker (production):**
```bash
docker build -t macro-mailing .
docker run --env-file .env -p 8000:8000 macro-mailing
# trigger execution:
curl -X POST http://localhost:8000/run -H "x-api-key: <API_KEY_EASY_PANEL>"
```

Scraping runs on Playwright (Chromium) in both environments, with no Edge/Chrome branching. The Dockerfile installs the browser via `playwright install --with-deps chromium` at build time; locally you need to run that once yourself (see below).

**Install dependencies:**
```bash
python -m venv venv
.\venv\Scripts\activate       # PowerShell
pip install -r requirements.txt
playwright install chromium   # required once, for the scrapers
pip install fastapi uvicorn nbconvert   # only needed for Docker/API mode
```

**Resend today's report to one person:**
```bash
python scripts/reenvio_manual.py alguien@mail.com
python scripts/reenvio_manual.py alguien@mail.com --dry-run   # builds it, sends nothing
```
See "Manual resend" below.

## Architecture

The entire pipeline lives in one notebook with this execution order:

1. **Imports:** all libraries, including `import scrapers` (the `scrapers/` package)
2. **Config:** `config.py` loads and validates `.env` through Pydantic-Settings, then the notebook creates the SQLAlchemy engine pointing at Supabase and sets the seaborn visual style
3. **Historical load:** reads the full `Fact_Mercado_Macro` table from Supabase, newest row first; falls back to the local CSV at `RUTA_BBDD` if Supabase fails
4. **Ingestion:** `scrapers.run_all_sync()` runs all six sources concurrently via `asyncio.gather()` and returns their results in a fixed order: BNA (billetes + divisas tabs), DolarHoy (blue), Ambito (MEP + euro blue), riesgo país, BCRA (BADLAR id=140 and monthly inflation id=27), and the St. Louis FED (EFFR). The three HTTP sources share one `httpx.AsyncClient`. BTC/USD comes separately from Yahoo Finance via `yfinance`.
5. **DataFrame assembly:** concatenates today's row with the historical df; calculates spreads, pct changes, and Irving Fisher forward rates
6. **Pre-persistence validation:** validates the freshly built row with Pydantic before it is persisted. If a scraper returns invalid, non-positive, or malformed values, the run stops and notifies the developer instead of saving corrupted data.
7. **Supabase upsert:** deduplicates by `Fecha` PK, inserts new rows one by one defensively
8. **AI paragraph:** calls `ia_generator.procesar_y_guardar_parrafo(engine)`, which queries Supabase, computes 1-day and 25-session variations, prompts Gemini, and saves the result back via `UPDATE`
9. **Charts:** four matplotlib/seaborn figures saved to `Previews/`
10. **Email:** renders `templates/report_email.html` via Jinja2 with the computed values, then sends two variants (with and without the CSV attached) in parallel via `threading`
11. **Git push:** auto-commits changed files in `Previews/` to the repo

## Key files

| File | Purpose |
|---|---|
| `notebooks/Argentinian_Macroeconomic_Automatic_Mailing.ipynb` | Main pipeline (single source of truth) |
| `config.py` | Typed, validated settings loaded once from `.env`; import `settings` from here instead of reading `os.environ` |
| `models.py` | Pydantic schema for the macro row; the validation contract before persistence |
| `ia_generator.py` | Gemini integration: queries Supabase, builds the prompt, calls the API with key failover, saves the paragraph |
| `mailer.py` | Plain-text failure alerts over SMTP, so any module can report a broken run without depending on the notebook |
| `app.py` | FastAPI wrapper that executes the notebook via `jupyter nbconvert --execute` |
| `Dockerfile` | Linux/Chromium image for containerized execution |
| `scrapers/` | Playwright scrapers (`bna.py`, `dolarhoy.py`, `ambito.py`), async REST clients (`bcra.py`, `fed.py`, `riesgo_pais.py`), `utils.py` (retry, `ScraperError`, event-loop helper) and `__init__.py` (`run_all_sync()`, which runs all six concurrently) |
| `templates/report_email.html` | Jinja2 template for the HTML email report: CSS plus markup, rendered with computed values from the mailing cell |
| `scripts/backfill.py` | Repairs historical `riesgo_pais` and `bcra_tea` series against their source APIs. Dry-run by default, writes only with `--apply`. |
| `scripts/reenvio_manual.py` | Resends the latest report to arbitrary recipients without rerunning the pipeline |
| `sql/` | One-off SQL scripts for DB setup and historical data cleaning (not part of the automated pipeline) |

## Environment variables (`.env`)

All of these are declared and validated in `config.py`. A missing or malformed value fails at import time rather than midway through a run.

```
EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER, EMAIL_RECEIVER_CSV
SUPABASE_DB_URL          # PostgreSQL connection string
RUTA_BBDD                # Path to fallback CSV (relative paths resolve against the repo root)
RUTA_REPO                # Path to repo root (for the git push step)
FED_API_KEY              # St. Louis FRED API key
GEMINI_API_KEY_1         # Primary Gemini key
GEMINI_API_KEY_2         # Failover Gemini key (rotated on HTTP 429)
API_KEY_EASY_PANEL       # Auth token for the /run FastAPI endpoint (optional)
SERVICE_ROUTE            # Deployment URL (optional, currently unread)
```

`EMAIL_RECEIVER` and `EMAIL_RECEIVER_CSV` are comma-separated lists, each address validated individually.

## Supabase table: `Fact_Mercado_Macro`

Primary key: `Fecha` (date). Columns: `TCC_Blue`, `TCV_Blue`, `TCC_Billete`, `TCV_Billete`, `TCC_Divisas`, `TCV_Divisas`, `Solidario`, `TCV_MEP`, `riesgo_pais`, `TCC_Euro`, `TCV_Euro`, `fed_tea`, `bcra_tea`, `ai_paragraph`, `ai_model`.

## Manual resend

`scripts/reenvio_manual.py` sends the most recent report to whichever addresses you pass on the command line. Use it when someone joins the list mid-month, or when a subscriber did not get the mail.

```bash
python scripts/reenvio_manual.py alguien@mail.com
python scripts/reenvio_manual.py uno@mail.com otro@mail.com
python scripts/reenvio_manual.py alguien@mail.com --csv       # attaches the tracking CSV
python scripts/reenvio_manual.py alguien@mail.com --dry-run   # builds it, writes a preview, sends nothing
```

It does not rerun the pipeline: no scraping, no row validation, no upsert, no Gemini call, no git push. It replays what the daily run already produced, namely the newest `Fact_Mercado_Macro` row, the `ai_paragraph` stored on it, and the four JPGs in `Previews/`. The one input it must refetch is the BCRA monthly inflation series, which the table does not persist. Recipients go in Bcc so they cannot see each other, and the rendered HTML is byte-identical to the daily mail apart from the performance timing line.

Two guardrails worth knowing: it aborts if the newest row has no `ai_paragraph` (that means the pipeline did not finish), and it warns when that row is not from today or when the charts in `Previews/` are over 24 hours old. `--dry-run` writes its preview to the system temp directory, deliberately not to `Previews/`, because the notebook auto-commits anything that lands in that folder.

## Important constraints

- **Scrapers depend on each site's HTML structure.** BNA, DolarHoy, and Ambito (`scrapers/`) use short CSS and id-based Playwright selectors, but still break if a site changes its markup. Unlike the old Selenium version, a broken selector now raises a `ScraperError` carrying site and step context instead of silently leaving NaN columns in `fila_nueva`.
- **Validation gate before persistence.** If the newly built row does not satisfy the Pydantic schema, the process fails fast and notifies the developer instead of saving a bad record.
- **`fecha_inicio`** in the variaciones acumuladas chart (cell ~42) is hardcoded to `"2025-07-01"`. Update it when the reference period changes.
- **`ia_generator` requires at least 26 rows** in Supabase to compute 25-session rolling variations; it raises an exception otherwise.
- **Jupyter's event loop cannot run scraper coroutines directly.** `ipykernel` already runs its own asyncio loop, and on Windows that loop cannot spawn subprocesses, which Playwright needs for its browser driver. Notebook cells call the sync wrapper `scrapers.run_all_sync()`, which runs the coroutines in a separate thread with its own event loop (`run_async` in `scrapers/utils.py`). Do not call `asyncio.run()` or a bare `await` directly in a notebook cell for scraping.
- **Send failures are caught and printed, not raised.** A bad Gmail App Password surfaces as a `535` line in the output and nothing else, so the run still looks green. Test SMTP changes with an isolated script rather than a full notebook run.
- **Column order matters in the email.** The cotizaciones table is built with `df.iloc[:, :14]`, so it depends on the column order coming back from Supabase. Adding a column to the table in the wrong position silently reshuffles the mail.
- **Writing style for this repo: no em dashes,** in documentation, comments, or commit messages.
