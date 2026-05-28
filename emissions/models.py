import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Tenant(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=("status", "created_at")),
        ]

    def __str__(self):
        return self.name


class DataSource(TimeStampedModel):
    class SourceType(models.TextChoices):
        API = "api", "API"
        CSV = "csv", "CSV Upload"
        SFTP = "sftp", "SFTP"
        MANUAL = "manual", "Manual Entry"
        INTEGRATION = "integration", "Integration"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        FAILED = "failed", "Failed"
        RETIRED = "retired", "Retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="data_sources")
    name = models.CharField(max_length=255)
    source_type = models.CharField(max_length=30, choices=SourceType.choices, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    external_reference = models.CharField(max_length=255, blank=True)
    configuration = models.JSONField(default=dict, blank=True)
    last_ingested_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("tenant", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "name"),
                name="unique_data_source_name_per_tenant",
            ),
        ]
        indexes = [
            models.Index(fields=("tenant", "source_type")),
            models.Index(fields=("tenant", "status")),
        ]

    def __str__(self):
        return f"{self.tenant}: {self.name}"


class RawRecord(TimeStampedModel):
    class ProcessingStatus(models.TextChoices):
        RECEIVED = "received", "Received"
        NORMALIZED = "normalized", "Normalized"
        REJECTED = "rejected", "Rejected"
        DUPLICATE = "duplicate", "Duplicate"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="raw_records")
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="raw_records",
    )
    source_record_id = models.CharField(max_length=255, blank=True)
    ingestion_batch_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    payload = models.JSONField()
    payload_hash = models.CharField(max_length=128, db_index=True)
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.RECEIVED,
        db_index=True,
    )
    received_at = models.DateTimeField(default=timezone.now, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ("-received_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "data_source", "payload_hash"),
                name="unique_raw_payload_per_source",
            ),
        ]
        indexes = [
            models.Index(fields=("tenant", "processing_status")),
            models.Index(fields=("tenant", "data_source", "received_at")),
            models.Index(fields=("tenant", "source_record_id")),
        ]

    def clean(self):
        super().clean()
        if self.data_source_id and self.tenant_id != self.data_source.tenant_id:
            raise ValidationError("Raw record tenant must match its data source tenant.")

    def __str__(self):
        return f"{self.data_source} raw record {self.id}"


class EmissionRecord(TimeStampedModel):
    class Scope(models.TextChoices):
        SCOPE_1 = "scope_1", "Scope 1"
        SCOPE_2 = "scope_2", "Scope 2"
        SCOPE_3 = "scope_3", "Scope 3"

    class Unit(models.TextChoices):
        KG_CO2E = "kg_co2e", "kg CO2e"
        T_CO2E = "t_co2e", "t CO2e"
        KWH = "kwh", "kWh"
        MWH = "mwh", "MWh"
        GJ = "gj", "GJ"
        LITER = "liter", "Liter"
        CUBIC_METER = "cubic_meter", "Cubic meter"
        KM = "km", "Kilometer"
        MILE = "mile", "Mile"
        PASSENGER_KM = "passenger_km", "Passenger kilometer"

    class ApprovalStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_REVIEW = "pending_review", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="emission_records")
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="emission_records",
    )
    raw_record = models.ForeignKey(
        RawRecord,
        on_delete=models.PROTECT,
        related_name="emission_records",
        null=True,
        blank=True,
    )
    source_record_id = models.CharField(max_length=255, blank=True)
    scope = models.CharField(max_length=20, choices=Scope.choices, db_index=True)
    category = models.CharField(max_length=120, blank=True, db_index=True)
    activity_type = models.CharField(max_length=120, blank=True)
    activity_value = models.DecimalField(max_digits=20, decimal_places=6)
    activity_unit = models.CharField(max_length=30, choices=Unit.choices)
    normalized_value = models.DecimalField(max_digits=20, decimal_places=6)
    normalized_unit = models.CharField(
        max_length=30,
        choices=Unit.choices,
        default=Unit.KG_CO2E,
    )
    co2e_kg = models.DecimalField(max_digits=20, decimal_places=6)
    emission_factor = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
    )
    emission_factor_source = models.CharField(max_length=255, blank=True)
    period_start = models.DateField(db_index=True)
    period_end = models.DateField(db_index=True)
    approval_status = models.CharField(
        max_length=30,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.DRAFT,
        db_index=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approved_emission_records",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    suspicious_flags = models.JSONField(default=list, blank=True)
    is_suspicious = models.BooleanField(default=False, db_index=True)
    is_locked = models.BooleanField(default=False, db_index=True)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-period_start", "-created_at")
        constraints = [
            models.CheckConstraint(
                check=models.Q(period_end__gte=models.F("period_start")),
                name="emission_period_end_on_or_after_start",
            ),
            models.CheckConstraint(
                check=models.Q(activity_value__gte=Decimal("0")),
                name="emission_activity_value_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(normalized_value__gte=Decimal("0")),
                name="emission_normalized_value_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(co2e_kg__gte=Decimal("0")),
                name="emission_co2e_kg_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=("tenant", "scope", "period_start")),
            models.Index(fields=("tenant", "approval_status")),
            models.Index(fields=("tenant", "is_suspicious")),
            models.Index(fields=("tenant", "data_source", "source_record_id")),
        ]

    def clean(self):
        super().clean()
        if self.data_source_id and self.tenant_id != self.data_source.tenant_id:
            raise ValidationError("Emission record tenant must match its data source tenant.")
        if self.raw_record_id and self.tenant_id != self.raw_record.tenant_id:
            raise ValidationError("Emission record tenant must match its raw record tenant.")
        if self.approval_status == self.ApprovalStatus.APPROVED:
            if not self.approved_by_id or not self.approved_at:
                raise ValidationError(
                    "Approved emission records require approver and approval timestamp."
                )

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = type(self).objects.only("is_locked").get(pk=self.pk)
            if previous.is_locked:
                raise ValidationError("Approved emission records are locked and cannot be modified.")

        if self.approval_status == self.ApprovalStatus.APPROVED:
            self.is_locked = True
            self.approved_at = self.approved_at or timezone.now()
        self.is_suspicious = bool(self.suspicious_flags)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tenant} {self.scope} {self.co2e_kg} kg CO2e"


class AuditLog(TimeStampedModel):
    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        INGEST = "ingest", "Ingest"
        LOCK = "lock", "Lock"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="audit_logs")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="emissions_audit_logs",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=30, choices=Action.choices, db_index=True)
    entity_type = models.CharField(max_length=120, db_index=True)
    entity_id = models.UUIDField(db_index=True)
    changes = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-occurred_at",)
        indexes = [
            models.Index(fields=("tenant", "entity_type", "entity_id")),
            models.Index(fields=("tenant", "action", "occurred_at")),
        ]

    def __str__(self):
        return f"{self.tenant} {self.action} {self.entity_type}:{self.entity_id}"
