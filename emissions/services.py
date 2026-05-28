from datetime import datetime
from decimal import Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError

from .models import EmissionRecord


class BaseNormalizer:
    source_name = "base"
    default_scope = EmissionRecord.Scope.SCOPE_1
    default_category = ""
    default_activity_type = ""
    default_emission_factor_source = ""
    canonical_activity_unit = EmissionRecord.Unit.KG_CO2E
    unit_conversions = {}
    suspicious_thresholds = {}

    def __init__(self, tenant=None, data_source=None, raw_record=None):
        self.tenant = tenant
        self.data_source = data_source
        self.raw_record = raw_record

    def normalize(self, row):
        row = self.clean_row(row)
        source_unit = self.pick(row, "activity_unit", "unit", "uom")
        activity_value = self.decimal(self.pick(row, "activity_value", "quantity", "amount", "value"))
        normalized_value, normalized_unit = self.normalize_activity(activity_value, source_unit)
        emission_factor = self.decimal_optional(
            self.pick(row, "emission_factor", "co2e_factor", "factor")
        )
        co2e_kg = self.co2e_kg(row, normalized_value, normalized_unit, emission_factor)
        period_start = self.standardize_date(
            self.pick(row, "period_start", "start_date", "date", "posting_date", "invoice_date")
        )
        period_end = self.standardize_date(
            self.pick(row, "period_end", "end_date", "date", "posting_date", "invoice_date")
        )
        suspicious_flags = self.detect_suspicious(row, normalized_value, co2e_kg, period_start, period_end)

        record = {
            "source_record_id": self.pick(row, "source_record_id", "external_id", "document_id", default=""),
            "scope": self.pick(row, "scope", default=self.default_scope),
            "category": self.pick(row, "category", default=self.default_category),
            "activity_type": self.pick(row, "activity_type", default=self.default_activity_type),
            "activity_value": activity_value,
            "activity_unit": self.model_unit(source_unit),
            "normalized_value": normalized_value,
            "normalized_unit": normalized_unit,
            "co2e_kg": co2e_kg,
            "emission_factor": emission_factor,
            "emission_factor_source": self.pick(
                row,
                "emission_factor_source",
                default=self.default_emission_factor_source,
            ),
            "period_start": period_start,
            "period_end": period_end,
            "approval_status": EmissionRecord.ApprovalStatus.DRAFT,
            "suspicious_flags": suspicious_flags,
            "notes": self.pick(row, "notes", default=""),
            "metadata": {
                "normalizer": self.source_name,
                "source_row": row,
            },
        }
        if self.tenant:
            record["tenant"] = self.tenant.id
        if self.data_source:
            record["data_source"] = self.data_source.id
        if self.raw_record:
            record["raw_record"] = self.raw_record.id
        return record

    def normalize_activity(self, value, unit):
        normalized_unit = self.canonical_activity_unit
        source_unit = self.normalize_unit_label(unit)
        conversion = self.unit_conversions.get((source_unit, normalized_unit))
        if source_unit == normalized_unit:
            return value, normalized_unit
        if conversion is None:
            raise ValidationError(
                {"activity_unit": f"Unsupported unit '{unit}' for {self.source_name} normalization."}
            )
        return value * conversion, normalized_unit

    def co2e_kg(self, row, normalized_value, normalized_unit, emission_factor):
        explicit_co2e = self.decimal_optional(self.pick(row, "co2e_kg", "emissions_kg", "kg_co2e"))
        if explicit_co2e is not None:
            return explicit_co2e
        if emission_factor is None:
            raise ValidationError({"emission_factor": "Emission factor or co2e_kg is required."})
        return normalized_value * emission_factor

    def detect_suspicious(self, row, normalized_value, co2e_kg, period_start, period_end):
        flags = []
        if normalized_value < 0:
            flags.append("negative_activity_value")
        if co2e_kg < 0:
            flags.append("negative_co2e")
        if period_end < period_start:
            flags.append("period_end_before_start")
        if normalized_value == 0 and co2e_kg > 0:
            flags.append("emissions_without_activity")

        max_activity = self.suspicious_thresholds.get("max_activity")
        max_co2e = self.suspicious_thresholds.get("max_co2e_kg")
        intensity = co2e_kg / normalized_value if normalized_value else None
        max_intensity = self.suspicious_thresholds.get("max_intensity")

        if max_activity and normalized_value > max_activity:
            flags.append("activity_value_above_expected_range")
        if max_co2e and co2e_kg > max_co2e:
            flags.append("co2e_above_expected_range")
        if max_intensity and intensity and intensity > max_intensity:
            flags.append("emission_intensity_above_expected_range")

        return flags

    @staticmethod
    def clean_row(row):
        return {
            str(key).strip().lower(): value.strip() if isinstance(value, str) else value
            for key, value in row.items()
            if key is not None
        }

    @staticmethod
    def pick(row, *keys, default=None):
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return value
        return default

    @staticmethod
    def decimal(value):
        if value in (None, ""):
            raise ValidationError({"activity_value": "A numeric activity value is required."})
        try:
            return Decimal(str(value).replace(",", ""))
        except (InvalidOperation, ValueError) as exc:
            raise ValidationError({"activity_value": f"Invalid numeric value '{value}'."}) from exc

    @staticmethod
    def decimal_optional(value):
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value).replace(",", ""))
        except (InvalidOperation, ValueError) as exc:
            raise ValidationError({"decimal": f"Invalid numeric value '{value}'."}) from exc

    @staticmethod
    def standardize_date(value):
        if not value:
            raise ValidationError({"date": "A date value is required."})
        if hasattr(value, "isoformat"):
            return value.isoformat()

        raw_value = str(value).strip()
        formats = (
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%d.%m.%Y",
            "%Y%m%d",
        )
        for date_format in formats:
            try:
                return datetime.strptime(raw_value, date_format).date().isoformat()
            except ValueError:
                continue
        raise ValidationError({"date": f"Unsupported date format '{value}'."})

    @classmethod
    def normalize_unit_label(cls, unit):
        value = str(unit or cls.canonical_activity_unit).strip().lower()
        aliases = {
            "kg co2e": EmissionRecord.Unit.KG_CO2E,
            "kg_co2e": EmissionRecord.Unit.KG_CO2E,
            "tco2e": EmissionRecord.Unit.T_CO2E,
            "t co2e": EmissionRecord.Unit.T_CO2E,
            "tonne co2e": EmissionRecord.Unit.T_CO2E,
            "kwh": EmissionRecord.Unit.KWH,
            "mwh": EmissionRecord.Unit.MWH,
            "gj": EmissionRecord.Unit.GJ,
            "l": EmissionRecord.Unit.LITER,
            "liter": EmissionRecord.Unit.LITER,
            "litre": EmissionRecord.Unit.LITER,
            "m3": EmissionRecord.Unit.CUBIC_METER,
            "cubic_meter": EmissionRecord.Unit.CUBIC_METER,
            "km": EmissionRecord.Unit.KM,
            "kilometer": EmissionRecord.Unit.KM,
            "kilometre": EmissionRecord.Unit.KM,
            "mile": EmissionRecord.Unit.MILE,
            "mi": EmissionRecord.Unit.MILE,
            "passenger_km": EmissionRecord.Unit.PASSENGER_KM,
            "passenger km": EmissionRecord.Unit.PASSENGER_KM,
        }
        return aliases.get(value, value)

    @classmethod
    def model_unit(cls, unit):
        normalized = cls.normalize_unit_label(unit)
        valid_units = {choice.value for choice in EmissionRecord.Unit}
        if normalized not in valid_units:
            raise ValidationError({"activity_unit": f"Unsupported model unit '{unit}'."})
        return normalized


class SAPNormalizer(BaseNormalizer):
    source_name = "sap"
    default_scope = EmissionRecord.Scope.SCOPE_1
    default_category = "stationary_combustion"
    default_activity_type = "purchased_fuel"
    default_emission_factor_source = "SAP source emission factor"
    canonical_activity_unit = EmissionRecord.Unit.LITER
    unit_conversions = {
        (EmissionRecord.Unit.LITER, EmissionRecord.Unit.LITER): Decimal("1"),
        (EmissionRecord.Unit.CUBIC_METER, EmissionRecord.Unit.LITER): Decimal("1000"),
    }
    suspicious_thresholds = {
        "max_activity": Decimal("1000000"),
        "max_co2e_kg": Decimal("5000000"),
        "max_intensity": Decimal("20"),
    }


class UtilityNormalizer(BaseNormalizer):
    source_name = "utility"
    default_scope = EmissionRecord.Scope.SCOPE_2
    default_category = "purchased_electricity"
    default_activity_type = "electricity"
    default_emission_factor_source = "Utility bill emission factor"
    canonical_activity_unit = EmissionRecord.Unit.KWH
    unit_conversions = {
        (EmissionRecord.Unit.KWH, EmissionRecord.Unit.KWH): Decimal("1"),
        (EmissionRecord.Unit.MWH, EmissionRecord.Unit.KWH): Decimal("1000"),
        (EmissionRecord.Unit.GJ, EmissionRecord.Unit.KWH): Decimal("277.777778"),
    }
    suspicious_thresholds = {
        "max_activity": Decimal("10000000"),
        "max_co2e_kg": Decimal("8000000"),
        "max_intensity": Decimal("2"),
    }


class TravelNormalizer(BaseNormalizer):
    source_name = "travel"
    default_scope = EmissionRecord.Scope.SCOPE_3
    default_category = "business_travel"
    default_activity_type = "passenger_transport"
    default_emission_factor_source = "Travel emission factor"
    canonical_activity_unit = EmissionRecord.Unit.KM
    unit_conversions = {
        (EmissionRecord.Unit.KM, EmissionRecord.Unit.KM): Decimal("1"),
        (EmissionRecord.Unit.MILE, EmissionRecord.Unit.KM): Decimal("1.609344"),
        (EmissionRecord.Unit.PASSENGER_KM, EmissionRecord.Unit.KM): Decimal("1"),
    }
    suspicious_thresholds = {
        "max_activity": Decimal("50000"),
        "max_co2e_kg": Decimal("100000"),
        "max_intensity": Decimal("5"),
    }


NORMALIZERS = {
    SAPNormalizer.source_name: SAPNormalizer,
    UtilityNormalizer.source_name: UtilityNormalizer,
    TravelNormalizer.source_name: TravelNormalizer,
}


def get_normalizer(name, **kwargs):
    try:
        normalizer_class = NORMALIZERS[name]
    except KeyError as exc:
        raise ValidationError({"normalizer": f"Unsupported normalizer '{name}'."}) from exc
    return normalizer_class(**kwargs)
