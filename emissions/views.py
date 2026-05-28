import csv
import hashlib
import json
import uuid
from io import TextIOWrapper

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import AuditLog, DataSource, EmissionRecord, RawRecord, Tenant
from .serializers import (
    ApprovalSerializer,
    CSVUploadSerializer,
    DataSourceSerializer,
    EmissionRecordSerializer,
    RawRecordSerializer,
    RejectionSerializer,
    TenantSerializer,
)
from .services import get_normalizer


class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = (AllowAny,)


class DataSourceViewSet(viewsets.ModelViewSet):
    serializer_class = DataSourceSerializer
    permission_classes = (AllowAny,)

    def get_queryset(self):
        queryset = DataSource.objects.select_related("tenant")
        tenant_id = self.request.query_params.get("tenant")
        status_value = self.request.query_params.get("status")
        source_type = self.request.query_params.get("source_type")

        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if source_type:
            queryset = queryset.filter(source_type=source_type)
        return queryset


class RawRecordViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = RawRecordSerializer
    permission_classes = (AllowAny,)

    def get_queryset(self):
        queryset = RawRecord.objects.select_related("tenant", "data_source")
        tenant_id = self.request.query_params.get("tenant")
        data_source_id = self.request.query_params.get("data_source")
        processing_status = self.request.query_params.get("processing_status")

        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if data_source_id:
            queryset = queryset.filter(data_source_id=data_source_id)
        if processing_status:
            queryset = queryset.filter(processing_status=processing_status)
        return queryset


class EmissionRecordViewSet(viewsets.ModelViewSet):
    serializer_class = EmissionRecordSerializer
    permission_classes = (AllowAny,)
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_queryset(self):
        queryset = EmissionRecord.objects.select_related(
            "tenant",
            "data_source",
            "raw_record",
            "approved_by",
        )
        params = self.request.query_params

        tenant_id = params.get("tenant")
        data_source_id = params.get("data_source")
        scope = params.get("scope")
        approval_status = params.get("approval_status")
        flagged = params.get("flagged")
        period_start = params.get("period_start")
        period_end = params.get("period_end")

        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if data_source_id:
            queryset = queryset.filter(data_source_id=data_source_id)
        if scope:
            queryset = queryset.filter(scope=scope)
        if approval_status:
            queryset = queryset.filter(approval_status=approval_status)
        if flagged is not None:
            queryset = queryset.filter(is_suspicious=_as_bool(flagged))
        if period_start:
            queryset = queryset.filter(period_start__gte=period_start)
        if period_end:
            queryset = queryset.filter(period_end__lte=period_end)
        return queryset

    def perform_create(self, serializer):
        instance = serializer.save()
        self._audit(AuditLog.Action.CREATE, instance)

    def perform_update(self, serializer):
        try:
            instance = serializer.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        self._audit(AuditLog.Action.UPDATE, instance)

    def perform_destroy(self, instance):
        tenant = instance.tenant
        entity_id = instance.id
        instance.delete()
        self._audit(
            AuditLog.Action.DELETE,
            entity_type="EmissionRecord",
            entity_id=entity_id,
            tenant=tenant,
        )

    @action(detail=False, methods=("post",), url_path="upload-csv")
    def upload_csv(self, request):
        serializer = CSVUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant = serializer.validated_data["tenant"]
        data_source = serializer.validated_data["data_source"]
        upload = serializer.validated_data["file"]
        normalizer_name = serializer.validated_data["normalizer"]
        batch_id = uuid.uuid4()
        rows = _read_csv(upload)
        created_records = []
        errors = []

        with transaction.atomic():
            for line_number, row in rows:
                payload_hash = _hash_payload(row)
                raw_record, raw_created = RawRecord.objects.get_or_create(
                    tenant=tenant,
                    data_source=data_source,
                    payload_hash=payload_hash,
                    defaults={
                        "source_record_id": row.get("source_record_id", ""),
                        "ingestion_batch_id": batch_id,
                        "payload": row,
                        "processing_status": RawRecord.ProcessingStatus.RECEIVED,
                    },
                )

                if not raw_created:
                    raw_record.processing_status = RawRecord.ProcessingStatus.DUPLICATE
                    raw_record.save(update_fields=("processing_status", "updated_at"))
                    continue

                normalizer = get_normalizer(
                    normalizer_name,
                    tenant=tenant,
                    data_source=data_source,
                    raw_record=raw_record,
                )
                record_data = normalizer.normalize(row)
                record_serializer = EmissionRecordSerializer(data=record_data)
                if not record_serializer.is_valid():
                    errors.append(
                        {
                            "line": line_number,
                            "errors": record_serializer.errors,
                        }
                    )
                    raw_record.processing_status = RawRecord.ProcessingStatus.REJECTED
                    raw_record.error_message = json.dumps(record_serializer.errors)
                    raw_record.processed_at = timezone.now()
                    raw_record.save(
                        update_fields=(
                            "processing_status",
                            "error_message",
                            "processed_at",
                            "updated_at",
                        )
                    )
                    continue

                emission_record = record_serializer.save()
                raw_record.processing_status = RawRecord.ProcessingStatus.NORMALIZED
                raw_record.processed_at = timezone.now()
                raw_record.save(
                    update_fields=("processing_status", "processed_at", "updated_at")
                )
                created_records.append(emission_record)

            if errors:
                raise ValidationError({"csv": errors})

            data_source.last_ingested_at = timezone.now()
            data_source.save(update_fields=("last_ingested_at", "updated_at"))

            self._audit(
                AuditLog.Action.INGEST,
                entity_type="CSVUpload",
                entity_id=batch_id,
                tenant=tenant,
                metadata={
                    "normalizer": normalizer_name,
                    "data_source_id": str(data_source.id),
                    "created_records": len(created_records),
                },
            )

        return Response(
            {
                "batch_id": batch_id,
                "created_records": len(created_records),
                "records": EmissionRecordSerializer(created_records, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=("post",))
    def approve(self, request, pk=None):
        emission_record = self.get_object()
        serializer = ApprovalSerializer(
            data=request.data,
            context={"request": request, "emission_record": emission_record},
        )
        serializer.is_valid(raise_exception=True)
        try:
            emission_record = serializer.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        self._audit(AuditLog.Action.APPROVE, emission_record)
        return Response(EmissionRecordSerializer(emission_record).data)

    @action(detail=True, methods=("post",))
    def reject(self, request, pk=None):
        emission_record = self.get_object()
        if emission_record.is_locked:
            raise ValidationError("Locked approved emission records cannot be rejected.")

        serializer = RejectionSerializer(
            data=request.data,
            context={"request": request, "emission_record": emission_record},
        )
        serializer.is_valid(raise_exception=True)
        try:
            emission_record = serializer.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        self._audit(AuditLog.Action.REJECT, emission_record)
        return Response(EmissionRecordSerializer(emission_record).data)

    def _audit(self, action, instance=None, **kwargs):
        tenant = kwargs.get("tenant") or instance.tenant
        entity_type = kwargs.get("entity_type") or instance.__class__.__name__
        entity_id = kwargs.get("entity_id") or instance.id
        metadata = kwargs.get("metadata") or {}
        request = self.request

        AuditLog.objects.create(
            tenant=tenant,
            actor=request.user if request.user.is_authenticated else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )


def _as_bool(value):
    return str(value).lower() in {"1", "true", "yes", "y"}


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _read_csv(upload):
    try:
        wrapper = TextIOWrapper(upload.file, encoding="utf-8-sig")
        reader = csv.DictReader(wrapper)
        if not reader.fieldnames:
            raise ValidationError({"file": "CSV file must include a header row."})
        return [(index, _clean_row(row)) for index, row in enumerate(reader, start=2)]
    except UnicodeDecodeError as exc:
        raise ValidationError({"file": "CSV file must be UTF-8 encoded."}) from exc


def _clean_row(row):
    return {
        (key or "").strip(): (value.strip() if isinstance(value, str) else value)
        for key, value in row.items()
        if key
    }


def _hash_payload(row):
    encoded = json.dumps(row, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
