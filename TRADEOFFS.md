# Tradeoffs

## 1. I did not build a real SAP connector

SAP reality is large: IDocs, OData services, BAPIs, custom extracts, middleware, authorization, plant/material enrichment, and customer-specific configuration. Building a fake "SAP connector" would look impressive but would not prove much.

Instead, I handled the shape an analyst is likely to see early in onboarding: a flat export with awkward units, dates, and IDs. The model still keeps enough source metadata to swap the CSV upload for a real connector later.

## 2. I did not parse PDFs or Green Button XML

Utility data often arrives as PDFs, portal CSVs, or Green Button XML. PDF extraction is a separate reliability problem, and Green Button deserves a proper XML parser with interval handling.

I chose portal CSV first because it is easy for a facilities team to provide and enough to test the review workflow. A production version should add Green Button XML next, especially for interval usage.

## 3. I did not implement full authentication and deployment hardening

The API was loosened to `AllowAny` so the local React demo can run without a login build-out. That is acceptable for local demonstration only.

Before a deployed submission, I would:

- restore authenticated API permissions,
- add tenant membership checks,
- use PostgreSQL,
- move secrets into environment variables,
- configure CORS for the deployed frontend,
- add deployment health checks.

## Other things intentionally kept small

- No background job queue. CSV rows are processed synchronously.
- No factor library management. Rows can provide an emission factor or explicit `co2e_kg`.
- No row-level edit history beyond `AuditLog`.
- No full test suite yet. The highest-risk next tests are normalizer unit tests and approval-locking tests.
