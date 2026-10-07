# 🤖 Argentinian Macroeconomic Automatic Mailing System
> **An Analytics Engineering, Data Pipeline, and AI Automation infrastructure designed to systematically untangle, model, and monitor Argentina's volatile macroeconomic chaos with an automated mailing report.**

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![Playwright](https://img.shields.io/badge/Playwright-async-2EAD33?style=flat&logo=playwright&logoColor=white)](https://playwright.dev)
[![httpx](https://img.shields.io/badge/httpx-async_REST-0B7285?style=flat)](https://www.python-httpx.org)
[![pandas](https://img.shields.io/badge/pandas-150458?style=flat&logo=pandas&logoColor=white)](https://pandas.pydata.org)
[![Supabase](https://img.shields.io/badge/Supabase_PostgreSQL-3FCF8E?style=flat&logo=supabase&logoColor=white)](https://supabase.com)
[![Gemini API](https://img.shields.io/badge/Gemini_API-1A73E8?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)](https://docs.docker.com/)
[![Pydantic](https://img.shields.io/badge/Pydantic-validated-E92063?style=flat&logo=pydantic&logoColor=white)](https://docs.pydantic.dev)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org)
[![Status](https://img.shields.io/badge/Status-Running_in_Production-28a745?style=flat)](https://github.com/mauroemartinez/RPA-exchange-rate-scrapping-automatic-mailing)

[![Last commit](https://img.shields.io/github/last-commit/mauroemartinez/RPA-exchange-rate-scrapping-automatic-mailing?style=flat&color=6c757d)](https://github.com/mauroemartinez/RPA-exchange-rate-scrapping-automatic-mailing/commits/main)
[![Top language](https://img.shields.io/github/languages/top/mauroemartinez/RPA-exchange-rate-scrapping-automatic-mailing?style=flat&color=6c757d)](https://github.com/mauroemartinez/RPA-exchange-rate-scrapping-automatic-mailing)
[![Repo size](https://img.shields.io/github/repo-size/mauroemartinez/RPA-exchange-rate-scrapping-automatic-mailing?style=flat&color=6c757d)](https://github.com/mauroemartinez/RPA-exchange-rate-scrapping-automatic-mailing)

---

### 🏗️ System Architecture & Data Pipeline Blueprint
Below is the end-to-end blueprint of the production data life cycle.

<p align="center">
  <img src="https://raw.githubusercontent.com/mauroemartinez/RPA-exchange-rate-scrapping-automatic-mailing/main/Assets/Architecture.png" width="900" alt="Project Architecture">
</p>

### 🗓️ A Business Day, Step by Step
GitHub Actions runs `pipeline.py` every business day: twelve stages, from the run lock to the warehouse, each one reporting its state and duration.

<p align="center">
  <img src="https://raw.githubusercontent.com/mauroemartinez/RPA-exchange-rate-scrapping-automatic-mailing/main/Assets/Architecture_opcion2.png" width="900" alt="Daily run on GitHub Actions">
</p>

Both diagrams are generated from `Assets/arquitectura/construir.py`, so they can be updated without redrawing them.

---

## 📋 Project Overview

This repository features a robust, portfolio-grade Robotic Process Automation (RPA) and Data Engineering pipeline tailored to track, store, and analyze the complex Argentine economic and exchange rate landscape.

The system automates the ingestion of highly volatile financial variables, ensures data integrity within a centralized data warehouse, runs mathematical macro-projections, and distributes dynamic, highly-styled financial reports to a private subscriber list.

Every business day the report brings official and parallel FX rates with their spreads, country risk, inflation, Irving Fisher forward rates, Bitcoin, the monetary aggregates and Argentina's public and private debt in US dollars, with an AI-written narrative and plain-language explanations for non-specialists. The same data feeds an executive PowerPoint deck. The whole run is built to work unattended on GitHub Actions' free plan, once its schedule is switched on.

### 🛠️ Core Tech Stack & Frameworks
* **Data Ingestion (ETL):** httpx (REST APIs), Playwright (async Web Scraping), openpyxl (the Treasury's monthly debt workbook).
* **Processing & Relational Mapping:** Pandas (Data Manipulation), SQLAlchemy (ORM).
* **Data Validation:** Pydantic for strict schema validation before data is persisted.
* **Configuration Management:** Pydantic-Settings for typed, fail-fast environment configuration.
* **Data Warehouse:** **Supabase PostgreSQL** for cloud-hosted analytics and persistency. Before Supabase, I used Microsoft SQL Server 2022, Microsoft SQL Server 2019.
* **Generative AI:** Google Gemini Flash models with structured JSON output, validated with Pydantic, with multi-key and model failover (Contextual Macro Narrative Generation).
* **Data Visualization & Delivery:** Matplotlib, Seaborn, Jinja2 HTML/CSS templates, tabulate, python-pptx (executive deck), SMTP Service.
* **Orchestration & CI:** GitHub Actions on the free plan: the daily run, a daily control and the test suite on every push.

---

## 🧭 Project Evolution & Historical Milestones

Since its inception in 2022, this infrastructure evolved from a single scraping script into a multi-layered analytical system, systematically overcoming technical debts and expanding data coverage:

* **The Inception & Ingestion Core (2022):** Developed the foundational Web Scraping layer to capture unstructured, highly volatile FX rates from dynamic portals (DolarHoy, Banco Nación), resolving manual ingestion bottlenecks for cross-border international trade documentation.
* **Pipeline Consolidation:** Consolidated disparate, heterogeneous data streams into uniform Pandas structures. Engineered the core automated mailing script to distribute analytical structures seamlessly.
* **Visualization Layer & Advanced Analytics:** Implemented visualization pipelines using Matplotlib and Seaborn, mastering complex timeseries formatting. Added calculated financial layers including spreads, variance metrics, and performance indicators.
* **Presentation Refactoring:** Introduced dynamic HTML5 (2023) and semantic CSS3 (2025) formatting to replace plain text outputs, utilizing `tabulate` libraries to ensure robust, responsive data matrices across multiple client viewports.
* **Macro Indicators Expansion:** Expanded the ingestion spectrum to track sovereign country risk indices, central bank interest rates, and multi-tier historical timelines (BNA, MEP). Integrated Federal Reserve rates to execute forward-rate projections based on the *Irving Fisher* hypothesis.
* **Relational Enterprise Architecture (2025-2026):** Deprecated flat-file persistence in favor of a permanent data warehouse model leveraging **Microsoft SQL Server 2022**. Engineered robust Upsert mechanisms using **SQLAlchemy** to guarantee strict data integrity and eliminate duplicate records.
* **Cloud Migration Milestone:** Successfully migrated the data warehouse from **SQL Server 2022 to Supabase PostgreSQL**, completing the planned transition to cloud-hosted analytics.
* **Data Validation Gate with Pydantic (2026):** Began validating incoming macro rows with **Pydantic** before persisting new records. When a scraper produces invalid or suspicious values, the write path is blocked and surfaced to the developer for correction, preventing bad data from reaching the warehouse.
* **Automated Repository Preview Synchronization (2026):** Implemented automated Git versioning workflows directly from the Python orchestration layer. The system now detects modified visualization assets inside the `/Previews` directory and automatically executes staged Git commits and pushes to GitHub, ensuring the repository always reflects the latest generated analytical outputs without manual intervention.
* **Generative AI Narrative Layer (2026):** Shipped a production-grade AI insights module powered by **Google Gemini 2.5 Flash**. The engine queries the SQL Server data warehouse, computes daily and 25-session rolling variations for all key macro indicators (FX rates, country risk, BCRA & FED effective rates), and dynamically composes a contextualized financial narrative paragraph injected directly into the HTML email report. The module features multi-API-key failover logic with automatic rotation on quota exhaustion (HTTP 429), persists the generated output back to the data warehouse via `UPDATE` for historical auditability, and is fully decoupled from the orchestration layer as an independent `ia_generator` module.
* **Threading Milestone (2026):** Added a threading piece of script so both email variants (with and without attached CSV) are sent in parallel. This reduces total send time significantly, since email delivery is the heaviest part of the project.
* **Scraping Performance Optimization (2026):** Replaced the per-request browser lifecycle (open → scrape → close, repeated for each site) with a single persistent WebDriver instance shared across all scrapers. This eliminated redundant browser startup overhead and reduced total scraping time by ~50%.
* **HTTP Client Modernization (2026):** Migrated from `requests` to `httpx` for all REST API calls (BCRA, St. Louis FED). `httpx` is the modern standard, offering native async support and HTTP/2 compatibility while maintaining a fully compatible API surface.
* **Automated WebDriver Version Management (2026):** Replaced the manually managed `msedgedriver` binary with `webdriver-manager`. The library auto-detects the installed Edge version, downloads the matching driver on first run, and caches it locally, eliminating manual updates on every browser upgrade.
* **Selenium to Playwright Migration (2026):** Migrated the entire web scraping layer (BNA, DolarHoy, Ambito MEP/riesgo país/euro) from Selenium to Playwright's async API, replacing brittle, deep XPath chains with short, semantic CSS/id-based selectors. All four scrapers now run concurrently via `asyncio.gather()` instead of sequentially through a single shared WebDriver, further reducing total scraping time. Each scraper raises a structured `ScraperError` with site and step context on failure, so a broken selector fails loudly through the existing Pydantic validation gate instead of silently persisting bad data. This also unified browser handling between local Windows development and the Dockerized production environment, removing the previous Edge-vs-Chromium branching in driver setup.
* **Jinja2 Templating for the Email Report (2026):** Extracted the report's HTML/CSS out of the Python orchestration script into a standalone `templates/report_email.html` Jinja2 template, replacing a large inline f-string. The notebook now only computes values and renders the template; markup, styling, and the responsive mobile media query live in one dedicated, readable file instead of being interleaved with business logic.
* **Centralized Configuration Layer (2026):** Replaced scattered `os.getenv` calls across the notebook, `app.py`, and `ia_generator.py` with a single `config.py` built on **Pydantic-Settings**. Every environment variable is now declared once with a strict type: secrets use `SecretStr` (masked on print, explicit `.get_secret_value()` to read), recipient lists are parsed and validated address-by-address with `EmailStr`, and filesystem paths resolve to `Path` objects. A missing or malformed variable now fails at import time rather than surfacing as a `None` deep inside the pipeline. Shipped alongside a committed `.env.example` documenting every required key.
* **Country Risk API Migration (2026):** Replaced the Playwright scrape of Ámbito's historical country-risk table with the **ArgentinaDatos REST API**, which exposes the same underlying source as JSON. Eliminates a full Chromium launch to read a single table cell. The new module is fully async (`httpx.AsyncClient`) and returns the value together with its true publication date.
* **Full Async HTTP Ingestion Layer (2026):** Extracted the BCRA and St. Louis FED API calls out of the notebook into dedicated `scrapers/bcra.py` and `scrapers/fed.py` modules using async `httpx`. All six sources, three Playwright browsers and three REST APIs, now execute inside a single `asyncio.gather()` sharing one connection pool. The three API calls, previously sequential and blocking before scraping began, now run inside the browsers' idle wait: **total ingestion time dropped from 22.8s to 18.3s despite adding two sources**. Retry policy distinguishes transient failures (5xx, network) from permanent ones (4xx) and applies exponential backoff.
* **Data Integrity Audit & Historical Backfill (2026):** A systematic comparison of the warehouse against its upstream APIs surfaced two silent capture defects. **Country risk** was shifted one business day: the scraper read Ámbito's last *published* close and stored it against the current date, 160 of 171 divergent rows matched the previous business day exactly. **BCRA effective annual rate** was reading `.iloc[-1]` on a descending-ordered API response, persisting the oldest record of a 1000-point window, a June 2022 rate stored as current, propagating into the AI narrative and the Irving Fisher forward-rate projections. 936 rows were corrected against source; both series now reconcile at 100%. Both modules now sort explicitly and expose the value's true publication date, with staleness warnings surfaced at runtime.
* **Scraper Failure Alerting (2026):** Introduced a standalone `mailer.py` module that converts a `ScraperError` into a plain-text alert email carrying source, failed step, root cause, and traceback. Wired around the ingestion call so a broken selector or a downed API notifies the maintainer before the run aborts, closing the gap where failures died silently in an unattended process. The alert path never raises: an unreachable SMTP server degrades to a console warning rather than masking the original failure.
* **TLS Verification Restored (2026):** The BCRA API integration carried `verify=False`, disabling certificate validation to work around a broken chain on the bank's side. Verified as fixed upstream and removed, restoring standard TLS validation on that request path.
* **Notebook-free Pipeline (2026):** Ported the orchestration notebook into plain Python modules (`data_access`, `transformations`, `charts`, `email_report`, `preview_git`) driven by a `pipeline.py` entry point that both the CLI and the FastAPI service execute. The port was verified against the original notebook run dry on frozen inputs: the four charts, the rendered HTML and both MIME messages come out byte-identical. Three later, intentional fixes (the accumulated-inflation line of the variations chart, one decimal on the inflation axis, and a CSV attachment built from the warehouse instead of a stale local file) are the only differences from the notebook's output, and a golden-file test now pins the HTML byte for byte. Each stage now reports its state and duration, a failed email send turns the run red instead of printing a line, a `--dry-run` mode exercises live scraping without writing or sending anything, and the row date is computed in Argentina time, so a containerized run in UTC can no longer stamp tomorrow's date.
* **Monetary Aggregates & Public Debt in Dollars (2026):** Added two charts to the daily report. The monetary aggregates (monetary base, M2, M3) show how much money circulates and how it grows against inflation. The debt chart tracks, always in US dollars, the Treasury's gross debt, private-sector bank loans, the Central Bank's letters and its transitory advances to the Treasury: BCRA series published in pesos are converted with the official wholesale rate of each day, and the Treasury's monthly workbook is read by its labels, with provisional months flagged. Each chart carries a plain-language explanation plus one sentence computed in Python from the latest figures, so the AI never writes the numbers.
* **Executive PowerPoint, Replaced Daily (2026):** Every run builds an eight-slide executive deck with the indicators, the AI summary and the charts, and publishes it as the single commit of a dedicated branch. GitHub always holds the latest deck while old versions never pile up in the history.
* **Cloud Scheduling on GitHub Actions (2026):** The daily run and a daily control run on GitHub Actions' free plan, switched on and off with a repository variable. A Postgres advisory lock prevents duplicate runs, the national holiday calendar skips non-business days, an unfinished day is detected and flagged, every log line is scrubbed of secrets and recipient addresses before it reaches the public log, and automated commits carry the owner's identity.
* **Deployment Hardening (2026):** Reworked the container and service layer. Added a `.dockerignore`, the image previously built with `COPY . .` and no exclusions, baking the `.env` file into a layer where credentials remain readable via `docker history` regardless of later deletion. Unified the runtime on **Python 3.14-slim** to match the development environment, moved `fastapi`/`uvicorn`/`nbconvert` out of an unpinned inline `pip install` into pinned `requirements.txt` entries, and introduced a `requirements.in` manifest separating direct dependencies from the resolved lock. The container now runs as a non-root user with a shared Playwright browser path and reports liveness through a `HEALTHCHECK`. `app.py` was hardened in turn: authentication now fails **closed** (the previous `if API_KEY and ...` guard left `/run` publicly callable whenever the variable was unset), concurrent invocations are rejected with HTTP 409 via a non-blocking lock instead of running the pipeline twice in parallel, subprocess output no longer leaks into HTTP responses, and the hardcoded `/app` working directory is derived from the module path so the service is runnable locally.

---

## 📁 Repository Layout

```
├── pipeline.py         Daily run and its CLI: stages, per-stage results, alerts
├── data_access.py      Supabase reads, idempotent insert, run lock
├── transformations.py  Today's row, validation, spreads, Fisher forwards, inflation
├── charts.py           The six report charts
├── indicadores.py      Plain-language explanations of the aggregates and debt charts
├── email_report.py     HTML rendering, MIME assembly and sending
├── presentacion.py     The daily executive PowerPoint deck
├── preview_git.py      Commit of Previews/ and publication of the deck branch
├── fechas.py           Argentina-time dates and Spanish month names
├── scrapers/           Ingestion layer: Playwright scrapers + async REST clients
├── templates/          Jinja2 email template
├── notebooks/          The original orchestration notebook, kept as a reference
├── scripts/            Operational tooling (backfills, manual resends, daily control, prototypes)
├── sql/                SQL applied by hand in Supabase: schema, migrations, cleaning
├── tests/              Offline test suite; tests/datos/ pins the mail HTML
├── docs/               Roadmap evaluations and runbooks (Spanish)
├── dashboard/          Streamlit prototype, read-only, with its own requirements
├── .github/workflows/  CI, plus the daily run and daily control (switched on by a variable)
├── data/               Local CSV history (gitignored)
├── Previews/           Daily charts, auto-committed by the pipeline
├── Assets/             Architecture diagrams and their generator
├── config.py           Typed environment configuration (Pydantic-Settings)
├── models.py           Row-level validation schema (Pydantic)
├── mailer.py           Failure alerting over SMTP
├── ia_generator.py     Gemini narrative layer
├── app.py              FastAPI entrypoint
├── pyproject.toml      pytest and ruff configuration
└── requirements*.in    Direct dependencies, locked into the matching .txt
```

---

## 🛟 Operational Tooling

**Daily run.** `pipeline.py` is the whole report end to end, the same code the `/run` endpoint executes:

```bash
python pipeline.py --dry-run                          # live scraping, nothing written or sent
python pipeline.py --dry-run --enviar-a me@mail.com   # same, but the report reaches only me
python pipeline.py                                    # the real run
```

A dry run leaves the six charts, the executive deck, a browser preview and an `.eml` of the report in a temp folder. The exit code is 1 when any stage fails, so schedulers can alert on it.

**Running it in the cloud (GitHub Actions, free plan).** The full guide, in Spanish, is `docs/programacion-y-monitoreo.md`. In short:

1. Merge into `main` and push. GitHub only schedules workflows that live on the default branch.
2. Load the `.env` values as repository secrets: Settings > Secrets and variables > Actions.
3. Run *Corrida diaria* by hand in `dry-run` mode, to check that the Argentine sites answer from GitHub's servers.
4. Run it once in `real` mode.
5. Create the repository variable `CORRIDA_AUTOMATICA` with the value `si`. From then on it runs Monday to Friday at 17:13 Argentina time, and the daily control at 19:43. Set it to `no` to pause.

**Executive deck.** The latest deck is always at [`Reporte Ejecutivo.pptx`](https://github.com/mauroemartinez/RPA-exchange-rate-scrapping-automatic-mailing/raw/reporte-ejecutivo/Reporte%20Ejecutivo.pptx), on the `reporte-ejecutivo` branch. That branch is rebuilt as a single commit every day, so it never accumulates versions. `python scripts/presentacion_ejecutiva.py` builds the same deck by hand from the warehouse.

**Supabase migrations.** `sql/` holds the SQL applied by hand in the Supabase SQL Editor. Two are new, and each opens with a plain-Spanish header: what it does, how to apply it, and how to verify and undo it.

* `06_series_macro.sql` creates `Fact_Series_Macro`, a long-format table for the monetary aggregates, inflation and debt series, each in its source unit. After applying it, `python scripts/agregados_monetarios.py --guardar` loads their full history, and the daily run keeps them up to date.
* `07_ai_secciones.sql` adds the `ai_secciones` column next to `ai_paragraph`. It stores, as JSON, the AI comments shown under the FX and country risk chart and under the Bitcoin chart; with it in place the daily run switches from the single paragraph to that commentary.

Neither touches existing data, and both are safe while the legacy notebook is still in use.

**Daily control.** `python scripts/control_diario.py` fails and sends an alert when a business day ends without its row in the warehouse, which catches the run that never started. `--sin-alerta` only reports.

**Tests.** `pytest` runs an offline suite that never touches the network, the warehouse or SMTP: fake credentials override any real `.env`, and a test that tries to send mail, make an HTTP request, download market data or launch a browser fails on the spot. A golden-file test pins the report's HTML byte for byte. `ruff check .` lints the codebase.

Scripts under `scripts/` run independently of the daily pipeline, for the situations the scheduler does not cover.

**Manual resend.** Sends the most recent report to arbitrary recipients, for subscribers who join mid-month or who never received the mail:

```bash
python scripts/reenvio_manual.py someone@mail.com
python scripts/reenvio_manual.py one@mail.com another@mail.com
python scripts/reenvio_manual.py someone@mail.com --csv       # attaches the tracking CSV
python scripts/reenvio_manual.py someone@mail.com --dry-run   # builds it, sends nothing
```

It replays the daily run rather than repeating it: no scraping, no row validation, no warehouse writes, no Gemini call, no git push. The report is rebuilt from the newest `Fact_Mercado_Macro` row, the AI texts already stored on it, and the chart assets in `Previews/`, through the same rendering module as the daily run, so its HTML matches the daily mail apart from the performance timing line. The sentences under the aggregates and debt charts are recomputed from the latest published data. A single recipient goes in To; several go in Bcc. The script aborts if the latest row carries no AI paragraph, which means the pipeline did not finish or Gemini returned nothing that day. With the daily run on GitHub Actions, run `git pull` before a resend: it reads the charts from the local `Previews/` and leaves out any older than the report.

**Historical backfill.** Repairs the `riesgo_pais` and `bcra_tea` series against their source APIs after a capture bug. Dry-run by default; writes only with `--apply`:

```bash
python scripts/backfill.py                    # dry-run, both series
python scripts/backfill.py --serie bcra_tea   # dry-run, one series
python scripts/backfill.py --apply            # applies the updates
```

---

## 🚀 Roadmap & Upcoming Features (In Development)

The following modules are mapped in the architecture blueprint and are undergoing staging checks prior to production deployment:

* **Project Modularization:** *Done.* The pipeline runs as plain Python modules through `pipeline.py`; the notebook remains only as a reference during the transition.
* **Idempotent Warehouse Writes:** *Done.* Today's row goes in with a single atomic `INSERT ... ON CONFLICT ("Fecha")`, which keeps existing history untouched on a normal run and overwrites it only on an explicit `--forzar` rerun.
* **Native Logging:** *Done for the pipeline.* Every module logs through `logging`, with an optional file handler (`--log-archivo`) so unattended runs leave an auditable trace. The legacy notebook still prints.
* **Per-chart AI Commentary:** *Built, pending activation.* One structured Gemini call returns a summary plus comments for the FX, country risk and Bitcoin charts, validated with Pydantic before it reaches the mail and stored as JSON with the model that wrote it. It switches on once `sql/07_ai_secciones.sql` adds the column; until then the single paragraph keeps working as before.
* **Monetary Aggregates & Public Debt:** *Done.* Two charts in the daily mail with plain-language explanations; debt always in US dollars.
* **API Data Persistence in Supabase:** *Built, pending activation.* The aggregates, inflation and debt series get their own long-format table, `Fact_Series_Macro`, with source dates, frequencies and units, kept up to date by the daily run once `sql/06_series_macro.sql` is applied. The mail charts do not depend on it: each run downloads what they need.
* **Automated Executive PowerPoint Reporting:** *Done.* Every run builds an eight-slide executive deck and publishes it on the `reporte-ejecutivo` branch, replaced daily without accumulating versions.
* **Workflow Orchestration & Automation:** *Ready to switch on.* The daily run and a daily control are scheduled on GitHub Actions' free plan and switch on with the `CORRIDA_AUTOMATICA` repository variable. Holidays and weekends are skipped, and a database lock prevents duplicate runs. CI already runs lint and the offline tests on every push.
* **Streamlit Dashboard:** *Prototype, to be reviewed later.* `dashboard/app.py` explores the full history read-only, with its own dependencies. Publishing it first needs a read-only database role (the SQL is in `docs/evaluacion-powerpoint-y-streamlit.md`).

---

## 🔐 Security & Production Standards

* **Credential Management:** All API keys, connection strings, and sensitive tokens are fully decoupled via environment variables using `.env` files (explicitly excluded via `.gitignore`). Secrets are typed as `SecretStr` in `config.py`, so they render masked in logs and tracebacks and require an explicit `.get_secret_value()` call to read.
* **Resilience:** Built with basic exception-handling blocks to prevent operational failure during scraping anomalies without exposing server secrets in standard logs. Ingestion failures raise a structured `ScraperError` carrying source and step, which triggers an alert email before the run aborts.
* **Public Logs:** GitHub Actions logs are public in a public repository, so every log line, tracebacks included, is scrubbed of each secret and recipient address before it is written.
* **Unattended Runs:** A database lock prevents duplicate runs, an unfinished day is reported instead of skipped, and a daily control alerts when a business day ends without its data. A failed run sends one summary alert.
* **AI Failover:** The Gemini integration implements multi-key rotation on quota exhaustion, ensuring uninterrupted report generation even under API rate limits. Also, if the model rejects the bot because of the high traffic, it moves on to the next model.

---

## 📬 Contact & Feedback

For email subscription, unsubscription and other inquiries:

* **Email:** martinezmauroezequiel@gmail.com
* **LinkedIn:** [linkedin.com/in/mauroemartinez](https://www.linkedin.com/in/mauroemartinez)