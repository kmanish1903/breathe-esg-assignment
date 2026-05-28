# Data model

The model is designed around one principle: never lose the source trail. A normalized emissions row is useful only if an analyst can trace it back to the original file, source system, ingestion batch, and review decision.

## Main entities

### Tenant

`Tenant` represents a client company. Every operational table points back to a tenant so the platform can keep client data separated.

Important fields:

- `id`: UUID primary key.
- `slug`: stable client identifier.
- `status`: active, suspended, or archived.
- `metadata`: flexible JSON for client-specific settings.

### DataSource

`DataSource` describes where a row came from. In this prototype a source can be SAP, utility CSV, travel export, manual upload, API, or another integration shape.

Important fields:

- `tenant`: owner of the source.
- `source_type`: API, CSV, SFTP, manual, or integration.
- `configuration`: JSON for source-specific mapping rules.
- `last_ingested_at`: operational visibility for analysts.

There is a uniqueness constraint on `(tenant, name)` so one tenant can have a "Utility CSV" without colliding with another tenant's source.

### RawRecord

`RawRecord` stores the incoming row before normalization. This is the source-of-truth layer for ingestion.

Important fields:

- `payload`: the original CSV row as JSON.
- `payload_hash`: used to detect duplicates for the same tenant and source.
- `ingestion_batch_id`: groups rows from the same upload.
- `processing_status`: received, normalized, rejected, or duplicate.
- `error_message`: stores normalization or validation failure details.

The platform can reject a row without deleting the evidence of what arrived.

### EmissionRecord

`EmissionRecord` is the normalized review object. This is what the analyst sees.

Important fields:

- `tenant`, `data_source`, `raw_record`: source trail.
- `scope`: Scope 1, 2, or 3.
- `activity_value` and `activity_unit`: what came from the source, represented in a model-supported unit.
- `normalized_value` and `normalized_unit`: the normalized activity quantity.
- `co2e_kg`: the common emissions quantity used for review.
- `emission_factor` and `emission_factor_source`: how emissions were calculated when the source did not provide `co2e_kg`.
- `period_start`, `period_end`: billing, posting, or trip period.
- `approval_status`: draft, pending review, approved, rejected.
- `suspicious_flags`, `is_suspicious`: flags generated during normalization.
- `is_locked`: once approved, the row cannot be changed through model save.
- `metadata`: stores normalizer name and source row details.

Why `co2e_kg` instead of only normalized units: analysts need one comparable number across electricity, fuel, and travel. The source activity still matters, so both are stored.

### AuditLog

`AuditLog` records review and ingestion actions.

Important fields:

- `tenant`
- `actor`
- `action`: create, update, delete, approve, reject, ingest, lock.
- `entity_type`, `entity_id`
- `changes` and `metadata`
- `ip_address`, `user_agent`
- `occurred_at`

This is intentionally separate from `EmissionRecord` so audit events can cover uploads, sources, and future entities too.

## Multi-tenancy

The prototype uses explicit tenant foreign keys instead of implicit tenant scoping. That is noisier, but it makes every query and constraint easier to reason about. The serializers and model `clean()` methods check that related rows belong to the same tenant.

For production I would add middleware-level tenant resolution from domain, JWT claim, or organization membership, then make tenant filtering impossible to forget at the query layer.

## Immutability after approval

`EmissionRecord.save()` checks whether the existing row is locked. If it is locked, the save raises a validation error. Approval sets `is_locked = True`.

This is not a substitute for database-level immutability. In production I would add one of:

- database triggers for approved rows,
- append-only revisions,
- or a separate immutable ledger table for audit snapshots.

For the prototype, model-level locking makes the workflow visible and keeps the implementation small.

## PostgreSQL fit

The app currently runs locally on SQLite, but the schema is friendly to PostgreSQL:

- UUID primary keys.
- JSON fields for source payloads and metadata.
- composite indexes for tenant, status, source, scope, and time-window filters.
- check constraints for non-negative quantities and valid periods.

PostgreSQL would be the deployment database.
