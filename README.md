# 🤖 Argentinian Macroeconomic Automatic Mailing System
> **An Analytics Engineering, Data Pipeline, and AI Automation infrastructure designed to systematically untangle, model, and monitor Argentina's volatile macroeconomic chaos with an automated mailing report.**

---

### 🏗️ System Architecture & Data Pipeline Blueprint
Below is the end-to-end blueprint of the production data life cycle.

<p align="center">
  <img src="https://raw.githubusercontent.com/mauroemartinez/RPA-exchange-rate-scrapping-automatic-mailing/main/Assets/Architecture.png" width="900" alt="Project Architecture">
</p>

---

## 📋 Project Overview

This repository features a robust, portfolio-grade Robotic Process Automation (RPA) and Data Engineering pipeline tailored to track, store, and analyze the complex Argentine economic and exchange rate landscape.

The system automates the ingestion of highly volatile financial variables, ensures data integrity within a centralized data warehouse, runs mathematical macro-projections, and distributes dynamic, highly-styled financial reports to a private subscriber list.

### 🛠️ Core Tech Stack & Frameworks
* **Data Ingestion (ETL):** httpx (REST APIs), Playwright (async Web Scraping).
* **Processing & Relational Mapping:** Pandas (Data Manipulation), SQLAlchemy (ORM).
* **Data Validation:** Pydantic for strict schema validation before data is persisted.
* **Configuration Management:** Pydantic-Settings for typed, fail-fast environment configuration.
* **Data Warehouse:** **Supabase PostgreSQL** for cloud-hosted analytics and persistency. Before Supabase, I used Microsoft SQL Server 2022, Microsoft SQL Server 2019.
* **Generative AI:** Google Gemini 2.5 Flash API (Contextual Macro Narrative Generation).
* **Data Visualization & Delivery:** Matplotlib, Seaborn, Jinja2 HTML/CSS templates, Tabula PDF Parsing, SMTP Service.

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
* **Deployment Hardening (2026):** Reworked the container and service layer. Added a `.dockerignore`, the image previously built with `COPY . .` and no exclusions, baking the `.env` file into a layer where credentials remain readable via `docker history` regardless of later deletion. Unified the runtime on **Python 3.14-slim** to match the development environment, moved `fastapi`/`uvicorn`/`nbconvert` out of an unpinned inline `pip install` into pinned `requirements.txt` entries, and introduced a `requirements.in` manifest separating direct dependencies from the resolved lock. The container now runs as a non-root user with a shared Playwright browser path and reports liveness through a `HEALTHCHECK`. `app.py` was hardened in turn: authentication now fails **closed** (the previous `if API_KEY and ...` guard left `/run` publicly callable whenever the variable was unset), concurrent invocations are rejected with HTTP 409 via a non-blocking lock instead of running the pipeline twice in parallel, subprocess output no longer leaks into HTTP responses, and the hardcoded `/app` working directory is derived from the module path so the service is runnable locally.

---

## 📁 Repository Layout

```
├── notebooks/          Orchestration notebook (relocates to project root on startup)
├── scrapers/           Ingestion layer: Playwright scrapers + async REST clients
├── templates/          Jinja2 email template
├── scripts/            One-off maintenance (historical backfills)
├── sql/                Schema, bulk load and exploratory queries
├── data/               Local CSV history (gitignored)
├── Previews/           Generated chart assets, auto-committed by the pipeline
├── Assets/             Architecture diagram
├── config.py           Typed environment configuration (Pydantic-Settings)
├── models.py           Row-level validation schema (Pydantic)
├── mailer.py           Failure alerting over SMTP
├── ia_generator.py     Gemini narrative layer
└── app.py              FastAPI entrypoint
```

---

## 🚀 Roadmap & Upcoming Features (In Development)

The following modules are mapped in the architecture blueprint and are undergoing staging checks prior to production deployment:

* **Project Modularization:** Reorganize the architecture to move beyond the notebook and convert the codebase into reusable, scalable modules that are deployment-ready. *In progress:* the ingestion layer (`scrapers/`), configuration (`config.py`), validation (`models.py`), alerting (`mailer.py`), and the AI layer (`ia_generator.py`) are already extracted; `database.py`, `charts.py`, and a `main.py` orchestrator remain.
* **Idempotent Warehouse Writes:** Replace the current read-all-dates-then-filter insert with a native Postgres `INSERT ... ON CONFLICT ("Fecha") DO UPDATE` guarded by `COALESCE`, so a run that brings a value overwrites, while a run whose source was down preserves existing history. Atomic, single round-trip, and correctable without external backfill scripts.
* **Native Logging:** Replace remaining `print()` calls with the `logging` module and a file handler, so unattended runs leave an auditable trace.
* **API Data Persistence in Supabase:** Store API data in Supabase instead of re-consuming the full dataset on every execution.
* **Automated Executive PowerPoint Reporting:** Developing a fully automated `.pptx` executive summary generation layer containing macroeconomic charts, spreads, and key indicators. The generated presentations will be versioned and automatically pushed to GitHub alongside analytical preview assets through integrated Git automation workflows.
* **Workflow Orchestration & Automation:** Migrating from local execution to serverless execution via **GitHub Actions**.
* **Streamlit Dashboard:** Build a Streamlit dashboard so users can consume the full Supabase dataset interactively.

---

## 🔐 Security & Production Standards

* **Credential Management:** All API keys, connection strings, and sensitive tokens are fully decoupled via environment variables using `.env` files (explicitly excluded via `.gitignore`). Secrets are typed as `SecretStr` in `config.py`, so they render masked in logs and tracebacks and require an explicit `.get_secret_value()` call to read.
* **Resilience:** Built with basic exception-handling blocks to prevent operational failure during scraping anomalies without exposing server secrets in standard logs. Ingestion failures raise a structured `ScraperError` carrying source and step, which triggers an alert email before the run aborts.
* **AI Failover:** The Gemini integration implements multi-key rotation on quota exhaustion, ensuring uninterrupted report generation even under API rate limits. Also, if the model rejects the bot because of the high traffic, it moves on to the next model.

---

## 📬 Contact & Feedback

For email subscription, unsubscription and other inquiries:

* **Email:** martinezmauroezequiel@gmail.com
* **LinkedIn:** [linkedin.com/in/mauroemartinez](https://www.linkedin.com/in/mauroemartinez)