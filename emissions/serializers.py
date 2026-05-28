from django.utils import timezone
from rest_framework import serializers

from .models import AuditLog, DataSource, EmissionRecord, RawRecord, Tenant


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = (
            "id",
            "name",
            "slug",
            "status",
            "metadata",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = (
            "id",
            "tenant",
            "name",
            "source_type",
            "status",
            "external_reference",
            "configuration",
            "last_ingested_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = (
            "id",
            "tenant",
            "data_source",
            "source_record_id",
            "ingestion_batch_id",
            "payload",
            "payload_hash",
            "processing_status",
            "received_at",
            "processed_at",
            "error_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class EmissionRecordSerializer(serializers.ModelSerializer):
    data_source_name = serializers.CharField(source="data_source.name", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.get_username", read_only=True)

    class Meta:
        model = EmissionRecord
        fields = (
            "id",
            "tenant",
            "tenant_name",
            "data_source",
            "data_source_name",
            "raw_record",
            "source_record_id",
            "scope",
            "category",
            "activity_type",
            "activity_value",
            "activity_unit",
            "normalized_value",
            "normalized_unit",
            "co2e_kg",
            "emission_factor",
            "emission_factor_source",
            "period_start",
            "period_end",
            "approval_status",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "rejection_reason",
            "suspicious_flags",
            "is_suspicious",
            "is_locked",
            "notes",
            "metadata",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "approved_by",
            "approved_at",
            "is_suspicious",
            "is_locked",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        tenant = attrs.get("tenant") or getattr(self.instance, "tenant", None)
        data_source = attrs.get("data_source") or getattr(self.instance, "data_source", None)
        raw_record = attrs.get("raw_record") or getattr(self.instance, "raw_record", None)

        if data_source and tenant and data_source.tenant_id != tenant.id:
            raise serializers.ValidationError(
                {"data_source": "Data source must belong to the selected tenant."}
            )
        if raw_record and tenant and raw_record.tenant_id != tenant.id:
            raise serializers.ValidationError(
                {"raw_record": "Raw record must belong to the selected tenant."}
            )
        return attrs


class CSVUploadSerializer(serializers.Serializer):
    tenant = serializers.PrimaryKeyRelatedField(queryset=Tenant.objects.all())
    data_source = serializers.PrimaryKeyRelatedField(queryset=DataSource.objects.all())
    file = serializers.FileField()
    normalizer = serializers.ChoiceField(
        choices=("sap", "utility", "travel"),
        required=False,
        default="utility",
    )

    def validate(self, attrs):
        if attrs["data_source"].tenant_id != attrs["tenant"].id:
            raise serializers.ValidationError(
                {"data_source": "Data source must belong to the selected tenant."}
            )
        return attrs


class ApprovalSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)

    def save(self, **kwargs):
        emission_record = self.context["emission_record"]
        user = self.context["request"].user
        emission_record.approval_status = EmissionRecord.ApprovalStatus.APPROVED
        emission_record.approved_by = user if user and user.is_authenticated else None
        emission_record.approved_at = timezone.now()
        if self.validated_data.get("notes"):
            emission_record.notes = self.validated_data["notes"]
        emission_record.save(update_fields=None)
        return emission_record


class RejectionSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField()

    def save(self, **kwargs):
        emission_record = self.context["emission_record"]
        emission_record.approval_status = EmissionRecord.ApprovalStatus.REJECTED
        emission_record.rejection_reason = self.validated_data["rejection_reason"]
        emission_record.approved_by = None
        emission_record.approved_at = None
        emission_record.is_locked = False
        emission_record.save(update_fields=None)
        return emission_record


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = (
            "id",
            "tenant",
            "actor",
            "action",
            "entity_type",
            "entity_id",
            "changes",
            "metadata",
            "ip_address",
            "user_agent",
            "occurred_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
