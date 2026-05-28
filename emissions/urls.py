from rest_framework.routers import DefaultRouter

from .views import DataSourceViewSet, EmissionRecordViewSet, RawRecordViewSet, TenantViewSet


router = DefaultRouter()
router.register("tenants", TenantViewSet, basename="tenant")
router.register("data-sources", DataSourceViewSet, basename="data-source")
router.register("raw-records", RawRecordViewSet, basename="raw-record")
router.register("emission-records", EmissionRecordViewSet, basename="emission-record")

urlpatterns = router.urls
