# 🤖 Argentinian Macroeconomic Automatic Mailing

This project is a portfolio-grade RPA system for Argentine exchange rate tracking, report generation, and automated email delivery.

## 📋 What it does

- Scrapes exchange rate data from sources like DolarHoy, Banco Nación, Ámbito Financiero, and more.
- Consumes historical economic data from BCRA and Fed APIs.
- Builds a cumulative dataset of exchange rates, interest rates, and inflation.
- Generates charts, tables, and automatically sends summary reports by email.
- Uses Selenium for scraping, pandas for data processing, and email automation to deliver results.

## 🚀 Roadmap & Future Vision

- **Cloud Deployment**: Move the workflow to the cloud so it can run reliably without the local machine being on.
- **Daily Automation via GitHub Copilot / GitHub Actions**: Execute the process every day automatically, instead of running it manually.
- **AI-Generated Summaries**: Add an AI-powered narrative paragraph to explain the latest market moves. This is already being developed in a separate repo.
- **Online Database**: Transition from a local CSV to a cloud database for better scalability and shared access.
- **More robust scheduling and alerting**: Add error monitoring and notifications when something fails.

## 🧭 Milestones

1. Completed the Contatech course, which only taught how to get one DolarHoy value into Excel using Selenium and openpyxl. That gave me the chance to fulfill an idea I had years ago: build a system that emails a summary of Argentina’s chaotic exchange rate situation.
2. Collected the first DolarHoy data and added Banco Nación rates, which are extremely useful for international trade. This also solved a workplace problem where someone had to enter data manually every day.
3. Since I already knew pandas, I combined everything into a single dataframe.
4. Built the automatic mailing system—data was not visible yet, but the core was one step away.
5. Completed the mailing pipeline and data started arriving in email reports. Wooohooo!
6. Added visualizations using matplotlib and seaborn; I fought a lot with ticks and date formatting for a long time.
7. Added calculations for spreads, variations, and performance metrics.
8. Several friends, coworkers, and contacts subscribed to the mailing list :D
9. With help from Camila Siquila, I added HTML formatting to the email.
10. Used `tabulate` so older daily data appears in the email in clean HTML tables.
11. Started tracking country risk and interest rates.
12. Made the dataset more serious by adding historical data from BNA and MEP.
13. Started tracking Fed interest rates and calculating forward exchange rate projections based on Irving Fisher (look up the economist name if needed!).
14. Added more charts for country risk, interest rates, and inflation.
15. Added inflation tables for recent months and interaction metrics for bimonthly, quarterly, and year-over-year comparisons to support salary update decisions.
16. Added CSS (95% AI scripted) to give it a much more professional look.
17. Implemented SQLAlchemy lines to save everything in an SQL Server database.
18. Migrated to SQL 2025 + SSMS 22.

## 🔐 Security Notes

- API keys and credentials should live in `.env`, never in source code.
- `.gitignore` should exclude `.env` and any sensitive data files.
- Handle exceptions securely so tokens and secrets are never exposed in logs.
- Validate external data before processing it.

## 📬 Contributions & Feedback

This is an educational portfolio project. If you have suggestions or want to contribute:

- Email: `martinezmauroezequiel@gmail.com`
- LinkedIn: [www.linkedin.com/in/mauroemartinez](https://www.linkedin.com/in/mauroemartinez)

Last update: April 2026  
Version: 1.0 (Pre-release for integration)
