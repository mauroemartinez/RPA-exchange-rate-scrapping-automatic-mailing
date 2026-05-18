# 🤖 Argentinian Macroeconomic Automatic Mailing System
> **A high-performance Analytics Engineering, Data Pipeline, and RPA infrastructure designed to systematically untangle, model, and monitor Argentina's volatile financial chaos.**

---

### 🏗️ System Architecture & Data Pipeline Blueprint
Below is the end-to-end blueprint of the production data life cycle, including current infrastructure and upcoming integration layers.

![System Architecture](assets/Architecture.jpeg)

---

## 📋 Project Overview

This repository features a robust, portfolio-grade Robotic Process Automation (RPA) and Data Engineering pipeline tailored to track, store, and analyze the complex Argentine economic and exchange rate landscape. 

The system automates the ingestion of highly volatile financial variables, ensures data integrity within a centralized data warehouse, runs mathematical macro-projections, and distributes dynamic, highly-styled financial reports to a private subscriber list.

### 🛠️ Core Tech Stack & Frameworks
* **Data Ingestion (ETL/ELT):** Requests (REST APIs), Selenium / Playwright (Web Scraping).
* **Processing & Relational Mapping:** Pandas (Data Manipulation), SQLAlchemy (ORM).
* **Data Warehouse:** Microsoft SQL Server 2022 (Staging & Analytical Layers).
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
* **Automated Repository Preview Synchronization (2026):** Implemented automated Git versioning workflows directly from the Python orchestration layer. The system now detects modified visualization assets inside the `/Previews` directory and automatically executes staged Git commits and pushes to GitHub, ensuring the repository always reflects the latest generated analytical outputs without manual intervention.
---

## 🚀 Roadmap & Upcoming Features (In Development)

The following modules are mapped in the architecture blueprint and are undergoing staging checks prior to production deployment:

* **Generative AI Insights Integration:** Connecting the **Gemini 1.5 Flash API** to dynamically evaluate active analytical tables and produce contextualized macro narrative paragraphs prior to delivery.
* **Automated Executive PowerPoint Reporting:** Developing a fully automated `.pptx` executive summary generation layer containing macroeconomic charts, spreads, and key indicators. The generated presentations will be versioned and automatically pushed to GitHub alongside analytical preview assets through integrated Git automation workflows.
* **Data Validation Layer (Pydantic):** Implementing strict schema validation models via **Pydantic** to enforce data types at the raw ingestion gate before loading to Staging.
* **Crypto Asset Monitoring Expansion:** Scaling the ingestion engine to track historical and live **Bitcoin (BTC)** pricing trends and liquidity pools.
* **Cloud Infrastructure Migration (Supabase):** Transitioning the local SQL Server instance to **Supabase** to leverage cloud-hosted PostgreSQL scalability and shared analytical access.
* **Workflow Orchestration & Automation:** Migrating from local execution to serverless execution via **GitHub Actions**.

---

## 🔐 Security & Production Standards

* **Credential Management:** All API keys, connection strings, and sensitive tokens are fully decoupled via environment variables using `.env` files (explicitly excluded via `.gitignore`).
* **Resilience:** Built with basic exception-handling blocks to prevent operational failure during scraping anomalies without exposing server secrets in standard logs.

---

## 📬 Contact & Feedback

This is an educational portfolio project designed under modern analytics engineering best practices. For email susbscription, collaboration, architectural inquiries, or technical feedback:

* **Email:** martinezmauroezequiel@gmail.com
* **LinkedIn:** [linkedin.com/in/mauroemartinez](https://www.linkedin.com/in/mauroemartinez)