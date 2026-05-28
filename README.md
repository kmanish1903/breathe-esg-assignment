# Breathe ESG emissions ingestion prototype

This is a prototype for the Breathe ESG intern assignment. The app ingests activity and emissions rows from three realistic enterprise source families, normalizes them into a common model, and gives an analyst a review dashboard for suspicious rows and approval.

The main idea is simple: keep the original source row, create a normalized emissions row beside it, and make the approval step explicit. Once a row is approved it becomes locked, because audit workflows should not silently mutate signed-off data.

## What is built

- Django REST API for tenants, data sources, raw records, normalized emission records, and audit logs.
- Normalizers for SAP-style fuel/procurement rows, utility electricity rows, and corporate travel rows.
- React + Tailwind dashboard for CSV upload, filtering, suspicious record review, and approve/reject workflow.
- Local SQLite setup for development. The models use fields and indexes that are PostgreSQL-friendly for deployment.

## How to run locally

Backend:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev -- --port 5173 --host 127.0.0.1
```

Open:

```text
http://127.0.0.1:5173
```

API base URL defaults to:

```text
http://localhost:8000
```

You can override it with `VITE_API_BASE_URL`.

## Demo data

The local database may include a demo tenant and two demo emission records:

```text
Tenant: Demo Tenant
Tenant ID: 3a8ed475-2d9b-4cd3-abf4-9a821b14c074
```

One demo row is intentionally suspicious so the flagged-record workflow is visible.

## CSV upload shape

The upload endpoint is:

```text
POST /emission-records/upload-csv/
```

Required form fields:

- `tenant`
- `data_source`
- `normalizer`: `sap`, `utility`, or `travel`
- `file`

The normalizers accept flexible CSV headers such as:

- `source_record_id`
- `activity_value`, `quantity`, `amount`, or `value`
- `activity_unit`, `unit`, or `uom`
- `emission_factor`, `co2e_factor`, or `factor`
- `co2e_kg`, `emissions_kg`, or `kg_co2e`
- `period_start`, `start_date`, `date`, `posting_date`, or `invoice_date`
- `period_end`, `end_date`, `date`, `posting_date`, or `invoice_date`

## Important docs

- [MODEL.md](MODEL.md)
- [DECISIONS.md](DECISIONS.md)
- [TRADEOFFS.md](TRADEOFFS.md)
- [SOURCES.md](SOURCES.md)

## Deployment note

The assignment requires a deployed app. This repository is ready to deploy, but the live URL should be added here after deploying to Render, Railway, Fly, or a similar host.

Suggested production changes before sharing a public URL:

- Use PostgreSQL instead of SQLite.
- Restore authenticated API permissions.
- Move secrets and allowed hosts to environment variables.
- Add a deployed frontend environment variable for `VITE_API_BASE_URL`.
- Store uploaded files in object storage if uploads need to be retained.
