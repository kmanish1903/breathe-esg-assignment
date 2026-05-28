# Sources and source-shape notes

This document explains what I looked at for each source family and how that influenced the sample data and normalizers.

## SAP fuel and procurement

References:

- SAP Help Portal, IDoc structure: https://help.sap.com/saphelp_gbt10/helpdata/en/4b/38625bad7f74fee10000000a421937/content.htm
- SAP Help Portal, Purchase Order OData V4 service: https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/91af7f8d3acd47da90d33aaacfcd0d59/c89eec80ec2043d980cb7b8c89e0a00a.html

What I learned:

- SAP data can be exposed as structured integration objects such as IDocs or modern OData APIs.
- IDoc data is segment-based and often needs mapping knowledge before it is useful outside SAP.
- Purchase-order APIs expose clean business objects, but access depends on the customer's SAP version, authorization, and integration setup.

Prototype interpretation:

I chose a flat export path for the prototype. It represents a realistic onboarding phase where the customer's SAP or finance team gives Breathe ESG a CSV extract rather than direct SAP credentials.

Sample SAP-style row shape:

```csv
document_id,posting_date,plant_code,material_code,activity_value,activity_unit,emission_factor
4900001234,20260201,DE01,DIESEL_BULK,1200,L,2.68
```

Why it looks this way:

- document IDs and posting dates are common ERP anchors,
- plant and material codes are useful but not self-explanatory,
- units may be local or inconsistent,
- emissions may require a factor because SAP usually stores business activity, not carbon.

What would break in real deployment:

- custom SAP fields,
- German or client-specific column headers,
- plant/material lookup tables,
- units tied to material master records,
- multiple line items per document,
- procurement spend-based Scope 3 factors.

## Utility electricity

References:

- Green Button Alliance, Connect My Data overview: https://www.greenbuttonalliance.org/green-button-connect-my-data-cmd
- UtilityAPI Green Button documentation: https://utilityapi.com/docs/greenbutton
- UtilityAPI Green Button XML format: https://utilityapi.com/docs/greenbutton/xml

What I learned:

- Green Button is a common standard for electricity, gas, or water usage and can represent interval or billing data.
- Utility exports may include meter readings, bills, intervals, and units.
- Intervals and billing periods do not always line up cleanly with calendar months.

Prototype interpretation:

I chose portal CSV upload for electricity because it is the shortest realistic path for facilities teams. The data model still keeps billing periods and units so Green Button XML could be added later.

Sample utility row shape:

```csv
source_record_id,meter_id,period_start,period_end,activity_value,activity_unit,emission_factor
UTIL-2026-01,MTR-8842,2026-01-05,2026-02-04,12500,kWh,0.408
```

Why it looks this way:

- meter or account identifiers are common,
- billing periods may cross calendar months,
- kWh is the expected electricity activity unit,
- factor choice may be supplier-specific, grid-average, or market-based.

What would break in real deployment:

- PDF-only bills,
- demand charges and tariff lines,
- interval blocks that need aggregation,
- missing meter/account mapping,
- renewable energy certificates and market-based adjustments.

## Corporate travel

References:

- SAP Help Portal, Concur itinerary details report: https://help.sap.com/docs/SAP_CONCUR/92814b27ae9c4b298c6e80d2a3241445/1c431f2e700b1014a46a108435d32877.html
- SAP Help Portal, Concur Travel and Request integration overview: https://help.sap.com/docs/CONCUR_REQUEST/a98100c3e5e044c4918c6bcbde8bc424/324356316f341014bf0ea6bd23953bae.html
- SAP Help Portal, Concur trip planning: https://help.sap.com/docs/CONCUR_TRAVEL/8b8fdc56b55b47b09e9d2b820045e641/3465b43b3edc45429cf6f14b55bbae3f.html

What I learned:

- Corporate travel systems think in trips and segments.
- Itinerary data can include flights, hotels, cars, vendors, dates, record locators, and ticket details.
- Some downstream reporting has rich itinerary detail, but the exact extract depends on customer setup.

Prototype interpretation:

I chose a travel export row with category and distance when available. For the first pass, the normalizer expects distance in kilometers, miles, or passenger-kilometers. If distance is missing, a real version would calculate flight distance from airport codes or ask the analyst to resolve it.

Sample travel row shape:

```csv
source_record_id,traveler_region,category,activity_type,period_start,period_end,activity_value,activity_unit,emission_factor
TRIP-7781,APAC,business_travel,flight,2026-02-01,2026-02-02,5800,km,0.16
```

Why it looks this way:

- travel systems commonly group data by trip or segment,
- category matters because flights, hotels, rail, and cars use different factors,
- distance may exist, but may also need derivation,
- date ranges matter for hotel nights and trip timing.

What would break in real deployment:

- airport-code distance derivation,
- multi-leg trips,
- hotel country-specific factors,
- car class and fuel type,
- employee privacy requirements,
- expenses that exist without an itinerary.
