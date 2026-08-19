# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What this project does

Daily automated pipeline that scrapes Argentine FX rates and macroeconomic indicators, stores them in Supabase, generates charts and an AI-written narrative via Gemini, and emails a styled HTML report to a subscriber list. A FastAPI wrapper (`app.py`) exposes a `/run` endpoint so the notebook can be triggered by n8n or any HTTP scheduler.

## Running the project

**Locally (notebook):** Open `Argentinian_Macroeconomic_Automatic_Mailing.ipynb` in VS Code and run all cells top to bottom. The kernel must use the venv Python — configured in `venv/share/jupyter/kernels/python3/kernel.json` with the full path to `venv/Scripts/python.exe`.

**Via Docker (production):**
```bash
docker build -t macro-mailing .
docker run --env-file .env -p 8000:8000 macro-mailing
# trigger execution:
curl -X POST http://localhost:8000/run -H "x-api-key: <API_KEY_EASY_PANEL>"
```

Scraping runs on Playwright (Chromium) in both environments — no more Edge/Chrome branching. The Dockerfile installs the browser via `playwright install --with-deps chromium` at build time; locally you need to run that once yourself (see below).

**Install dependencies:**
```bash
python -m venv venv
.\venv\Scripts\activate       # PowerShell
pip install -r requirements.txt
playwright install chromium   # required once, for the scrapers
pip install fastapi uvicorn nbconvert   # only needed for Docker/API mode
```

## Architecture

The entire pipeline lives in one notebook with this execution order:

1. **Imports** — all libraries, including `import scrapers` (the `scrapers/` package)
2. **Config** — loads `.env`, reads credentials, creates SQLAlchemy engine pointing to Supabase, sets seaborn visual style
3. **Historical load** — reads full `Fact_Mercado_Macro` table from Supabase; falls back to local CSV at `RUTA_BBDD` if Supabase fails
4. **API ingestion** — BCRA API (BADLAR rate id=140, inflation id=27), St. Louis FED API (EFFR rate), Yahoo Finance (BTC/USD via `yfinance`)
5. **Playwright scraping** — `scrapers.run_all_sync()` runs BNA (billetes + divisas tabs), DolarHoy (blue), and Ambito (MEP + riesgo país + euro blue) concurrently via `asyncio.gather()`, returning three dicts assembled into DataFrames
6. **DataFrame assembly** — concatenates today's row with historical df; calculates spreads, pct changes, Irving Fisher forward rates
7. **Pre-persistence validation** — validates the freshly built row with Pydantic before it is persisted. If a scraper returns invalid, non-positive, or malformed values, the run should stop and notify the developer instead of saving corrupted data.
8. **Supabase upsert** — deduplicates by `Fecha` PK, inserts new rows one by one defensively
9. **AI paragraph** — calls `ia_generator.procesar_y_guardar_parrafo(engine)`, which queries Supabase, computes 1-day and 25-session variations, prompts Gemini, saves result back via `UPDATE`
10. **Charts** — four matplotlib/seaborn figures saved to `Previews/`
11. **Email** — renders `templates/report_email.html` via Jinja2 with the computed values, two email variants (with/without CSV) sent in parallel via `threading`
12. **Git push** — auto-commits changed files in `Previews/` to the repo

## Key files

| File | Purpose |
|---|---|
| `Argentinian_Macroeconomic_Automatic_Mailing.ipynb` | Main pipeline (single source of truth) |
| `models.py` | Pydantic schema for the macro row; used as a validation contract before persistence |
| `ia_generator.py` | Gemini integration: queries Supabase → builds prompt → calls API with key failover → saves paragraph |
| `app.py` | FastAPI wrapper that executes the notebook via `jupyter nbconvert --execute` |
| `Dockerfile` | Linux/Chromium image for containerized execution |
| `scrapers/` | Playwright scrapers (`bna.py`, `dolarhoy.py`, `ambito.py`) plus `utils.py` (retry, error type, event-loop helper) and `__init__.py` (`run_all_sync()`, runs all three concurrently) |
| `templates/report_email.html` | Jinja2 template for the HTML email report — CSS + markup, rendered with computed values from the mailing cell |
| `sql_scripts/` | One-off SQL scripts for DB setup and historical data cleaning (not part of automated pipeline) |

## Environment variables (`.env`)

```
EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER, EMAIL_RECEIVER_CSV
SUPABASE_DB_URL          # PostgreSQL connection string
RUTA_BBDD                # Absolute path to fallback CSV
RUTA_REPO                # Absolute path to repo root (for git push step)
FED_API_KEY              # St. Louis FRED API key
GEMINI_API_KEY_1         # Primary Gemini key
GEMINI_API_KEY_2         # Failover Gemini key (rotated on HTTP 429)
API_KEY_EASY_PANEL       # Auth token for the /run FastAPI endpoint
```

## Supabase table: `Fact_Mercado_Macro`

Primary key: `Fecha` (date). Columns: `TCC_Blue`, `TCV_Blue`, `TCC_Billete`, `TCV_Billete`, `TCC_Divisas`, `TCV_Divisas`, `Solidario`, `TCV_MEP`, `riesgo_pais`, `TCC_Euro`, `TCV_Euro`, `fed_tea`, `bcra_tea`, `ai_paragraph`, `ai_model`.

## Important constraints

- **Scrapers depend on each site's HTML structure** — BNA, DolarHoy, and Ambito (`scrapers/`) use short CSS/id-based Playwright selectors, but still break if a site changes its markup. Unlike the old Selenium version, a broken selector now raises a `ScraperError` (site + step context) instead of silently leaving NaN columns in `fila_nueva`.
- **Validation gate before persistence** — if the newly built row does not satisfy the Pydantic schema, the process must fail fast and notify the developer instead of saving a bad record.
- **`fecha_inicio`** in the variaciones acumuladas chart (cell ~42) is hardcoded to `"2025-07-01"` — update this when the reference period changes.
- **`ia_generator` requires at least 26 rows** in Supabase to compute 25-session rolling variations; it raises an exception otherwise.
- **Jupyter's event loop can't run scraper coroutines directly** — `ipykernel` already runs its own asyncio loop, and on Windows that loop can't spawn subprocesses (which Playwright needs for its browser driver). Notebook cells call the sync wrapper `scrapers.run_all_sync()`, which runs the coroutines in a separate thread with its own event loop (`scrapers/utils.py:run_playwright`). Don't call `asyncio.run()` or bare `await` directly in a notebook cell for scraping.
