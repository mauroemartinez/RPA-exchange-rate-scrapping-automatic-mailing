# 🤖 Argentinian Macroeconomic Automatic Mailing System
> **An Analytics Engineering, Data Pipeline, and AI Automation infrastructure designed to systematically untangle, model, and monitor Argentina's volatile macroeconomic chaos with an automated mailing report.**

---

### 🏗️ System Architecture & Data Pipeline Blueprint
Below is the end-to-end blueprint of the production data life cycle.

<p align="center">
  <img src="https://raw.githubusercontent.com/mauroemartinez/RPA-exchange-rate-scrapping-automatic-mailing/main/Assets/Architecture.jpeg" width="900" alt="Project Architecture">
</p>

---

## 📋 Project Overview

This repository features a robust, portfolio-grade Robotic Process Automation (RPA) and Data Engineering pipeline tailored to track, store, and analyze the complex Argentine economic and exchange rate landscape. 

The system automates the ingestion of highly volatile financial variables, ensures data integrity within a centralized data warehouse, runs mathematical macro-projections, and distributes dynamic, highly-styled financial reports to a private subscriber list.

### 🛠️ Core Tech Stack & Frameworks
* **Data Ingestion (ETL):** httpx (REST APIs), Selenium (Web Scraping).
* **Processing & Relational Mapping:** Pandas (Data Manipulation), SQLAlchemy (ORM).
* **Data Validation:** Pydantic for strict schema validation before data is persisted.
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

---

## 🚀 Roadmap & Upcoming Features (In Development)

The following modules are mapped in the architecture blueprint and are undergoing staging checks prior to production deployment:

* **Selenium to Playwright Migration:** Migrate the web scraping layer from Selenium to Playwright to improve stability, performance, and long-term maintainability.
* **Project Modularization:** Reorganize the architecture to move beyond the notebook and convert the codebase into reusable, scalable modules that are deployment-ready.
* **API Data Persistence in Supabase:** Store API data in Supabase instead of re-consuming the full dataset on every execution.
* **Automated Executive PowerPoint Reporting:** Developing a fully automated `.pptx` executive summary generation layer containing macroeconomic charts, spreads, and key indicators. The generated presentations will be versioned and automatically pushed to GitHub alongside analytical preview assets through integrated Git automation workflows.
* **Workflow Orchestration & Automation:** Migrating from local execution to serverless execution via **GitHub Actions**.
* **Streamlit Dashboard:** Build a Streamlit dashboard so users can consume the full Supabase dataset interactively.

---

## 🔐 Security & Production Standards

* **Credential Management:** All API keys, connection strings, and sensitive tokens are fully decoupled via environment variables using `.env` files (explicitly excluded via `.gitignore`).
* **Resilience:** Built with basic exception-handling blocks to prevent operational failure during scraping anomalies without exposing server secrets in standard logs.
* **AI Failover:** The Gemini integration implements multi-key rotation on quota exhaustion, ensuring uninterrupted report generation even under API rate limits. Also, if the model rejects the bot because of the high traffic, it moves on to the next model.

---

## 📬 Contact & Feedback

This is an educational portfolio project designed under modern analytics engineering best practices. For email subscription, collaboration, architectural inquiries, or technical feedback:

* **Email:** martinezmauroezequiel@gmail.com
* **LinkedIn:** [linkedin.com/in/mauroemartinez](https://www.linkedin.com/in/mauroemartinez)