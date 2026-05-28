# Decisions

This document lists the main ambiguities I resolved while building the prototype. I tried to choose a small slice that is realistic enough to defend without pretending to solve every ingestion problem.

## Source ingestion choices

### SAP

Choice: handle SAP as exported flat CSV-like data rather than a live SAP integration.

Why: a real SAP integration can mean IDoc, OData, BAPI, custom ABAP extract, or middleware. For a four-day prototype, a CSV/flat-file upload is the most useful slice because ESG analysts often receive extracts prepared by IT rather than direct production SAP access.

Subset handled:

- fuel/procurement-style rows,
- inconsistent date formats,
- inconsistent unit labels,
- document IDs,
- posting/invoice dates,
- liter and cubic-meter style quantities.

Ignored:

- IDoc segment parsing,
- SAP plant-code lookup tables,
- material master enrichment,
- currency and procurement spend-based factors,
- real SAP authentication.

What I would ask the PM:

- Are we onboarding through the customer's SAP team or through files from sustainability/finance?
- Which modules are in scope first: MM purchase orders, FI invoices, PM fuel logs, or SD billing?
- Do plant codes and material codes already have ESG mapping tables?

### Utility electricity

Choice: handle utility portal CSV exports first.

Why: Green Button XML and APIs exist, but facilities teams often start with portal downloads or spreadsheet exports. CSV upload is a practical first path while keeping room for Green Button XML later.

Subset handled:

- electricity quantity in kWh, MWh, or GJ,
- billing period start and end,
- emission factor or explicit `co2e_kg`,
- suspicious values such as very high consumption or high emissions intensity.

Ignored:

- PDF bill extraction,
- interval meter XML,
- demand charges and tariff line items,
- calendar-month allocation for billing periods that cross months.

What I would ask the PM:

- Do auditors need monthly allocation or bill-period reporting?
- Are emission factors location-based, market-based, supplier-specific, or all three?
- Are renewable certificates tracked in a separate system?

### Corporate travel

Choice: handle travel platform export rows, not a live Concur/Navan API pull.

Why: travel platforms expose itinerary and expense details in several ways, and API access depends on customer licensing and admin setup. A CSV export lets the prototype model the hard ESG questions: category, distance, missing distance, and factor choice.

Subset handled:

- business travel as Scope 3,
- kilometers, miles, and passenger-kilometers,
- flight/hotel/ground transport category fields,
- high-distance and high-emissions suspicious flags.

Ignored:

- airport-code distance calculation,
- hotel country-night factors,
- rental car fuel type inference,
- traveler identity and HR hierarchy.

What I would ask the PM:

- Is travel data coming from booked itineraries, expenses, card feeds, or a monthly report?
- Do we need employee-level visibility, or should rows be anonymized?
- Which emission factor library is accepted by auditors?

## Normalization design

I used one shared `BaseNormalizer` and three source-specific subclasses:

- `SAPNormalizer`
- `UtilityNormalizer`
- `TravelNormalizer`

The shared layer handles common work: cleaning header names, parsing decimals, parsing dates, calculating `co2e_kg`, and generating suspicious flags. The subclasses define default scope/category/activity type, canonical activity unit, unit conversions, and thresholds.

This avoids three completely separate ingestion paths while still letting each source behave differently.

## Review workflow

I made approval a first-class state on `EmissionRecord` rather than a boolean. The states are:

- draft
- pending review
- approved
- rejected

Approval locks the row. Rejection requires a reason. Audit logs are written for ingestion, updates, approval, and rejection.

## Frontend choice

The frontend is intentionally an analyst dashboard, not a marketing page. It puts upload, filters, flagged records, and review actions in the first screen because that is the actual daily workflow.

## Authentication

For local demo usability, the API ViewSets currently use `AllowAny`. That is not a production decision. Before deployment, I would restore authenticated access and tenant-scoped permissions.
