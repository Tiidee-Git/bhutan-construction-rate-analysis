# Bhutan Construction Rate Analysis Tool

A GitHub-ready full-stack starter for Bhutan construction rate analysis. Backend: FastAPI + SQLite. Frontend: HTML/CSS/JavaScript. Currency: `Nu.` with two decimal places.

## Official dataset status (checked 12 October 2026)
The MoIT BSR listing currently shows **BSR 2026 Civil** and **LMC 2026 Civil**. The same listing shows **BSR 2025 Electrical** and **LMC 2025 Electrical**; it does not establish an official 2026 Electrical BSR/LMC. Accordingly, do not label electrical 2025 records as 2026 unless MoIT publishes a newer edition.

Official source page: https://moit.gov.bt/bsr/

**This repository does not bundle the official PDFs or claim to have imported their full contents.** The source files are large and must be downloaded from MoIT, then parsed/imported and checked. The included seeded records are illustrative demos only.

## Features
- Search BSR item code or description.
- Civil/electrical classification and source edition fields (extend the schema as needed for separate discipline filters).
- Material, labour and equipment coefficients with unit rates.
- Quantity, overhead and profit calculations; all displayed money values use Nu. and two decimals.
- Source provenance fields: source, edition, town, verification date.
- CSV export and browser Print / Save as PDF.
- AI-assisted draft rate analysis for missing items, if an AI API key is configured. AI outputs are **provisional engineering drafts**, never silently inserted into official BSR/LMC data.
- SQLite persistence and JSON API.

## Run locally
Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```
Open http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs.

AI is optional. Put your provider key in `.env` as `AI_API_KEY`. Never commit `.env`. If not configured, calculator and database still work.

## Docker
```bash
cp .env.example .env
docker compose up --build
```
Use a persistent volume for the database and back it up.

## Importing official data
1. Download the correct BSR and LMC PDFs from the official MoIT page.
2. Convert/verify tables into CSV/XLSX using a suitable PDF table extraction or OCR workflow. Large/image PDFs may need OCR and manual review.
3. Use the template `data/import_template.csv` as a starting point. Keep original PDFs in your own source-controlled storage only if their licensing permits it; do not commit them by default.
4. Record the exact edition, discipline, source file/page, town or cost-index basis, and verification date.
5. Validate codes, units, coefficients, and rates against the official source before production use.

The current API `POST /api/items` supports one item with a `components` array. Example:
```json
{
  "item_code":"CIV-EXAMPLE-001",
  "description":"Example item; replace with verified description",
  "unit":"m3",
  "discipline":"civil",
  "bsr_edition":"BSR 2026 Civil",
  "lmc_edition":"LMC 2026 Civil",
  "source_name":"MoIT BSR/LMC",
  "town":"Reference town / cost-index basis",
  "verification_date":"2026-10-12",
  "overhead_pct":10,
  "profit_pct":0,
  "components":[
    {"component_type":"Material","component_name":"Cement","unit":"bag","coefficient":1.2,"unit_rate":420},
    {"component_type":"Labor","component_name":"Mason","unit":"day","coefficient":0.3,"unit_rate":900}
  ]
}
```
The request schema may need extension for the `discipline` field before using that example as-is. Verify all imported values.

## AI missing-item workflow
The AI endpoint is designed to suggest a draft from the item description, unit, discipline, location and known rates you provide. It should:
- return a transparent component breakdown and assumptions;
- state which inputs are missing and what needs local verification;
- identify its result as AI-generated and provisional;
- not fabricate a BSR/LMC code or claim an official source;
- require a qualified engineer's review before use in estimates/tenders/payment.

Do not treat an AI result as an official rate. The model may make calculation or quantity-assumption errors. Validate prices with current supplier quotations and applicable MOIT specifications.

## Database
- `bsr_items`: item code, description, unit, edition, town, source, verification date, overhead and profit.
- `item_components`: component type/name, unit, coefficient and unit rate.
- SQLite database is created on startup.

## API
- `GET /api/health`
- `GET /api/items?q=concrete`
- `GET /api/items/{item_code}`
- `POST /api/items` create/update item and component breakdown
- `DELETE /api/items/{item_code}`
- `POST /api/ai/draft-rate` generate a provisional AI analysis for a missing item

## Before public deployment
Add authentication and role-based permissions, CSRF/CORS policy as appropriate, rate limits, audit logs, backups, migrations, upload validation, monitoring and a secure secrets manager. Do not expose an AI key to frontend JavaScript. Run behind HTTPS. Official rates should be immutable/versioned, with corrections logged.

## Suggested GitHub setup
Create an empty repository on GitHub, then:
```bash
git init
git add .
git commit -m "Initial Bhutan construction rate analysis app"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/bhutan-construction-rate-analysis.git
git push -u origin main
```

## Current data readiness

This repository is wired for verified data import but does not yet contain a complete extracted BSR/LMC 2026 Civil dataset or an official 2026 Electrical dataset. The AI endpoint intentionally returns drafts only and never promotes AI values to official rates. Check the MoIT page before each dataset refresh.
