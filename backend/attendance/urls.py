from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AttendanceDashboardView, CounterSaleViewSet, EstimateApprovalPublicPdfView, EstimateApprovalPublicView, EstimateViewSet

router = DefaultRouter()
router.register("counter-sales", CounterSaleViewSet, basename="attendance-counter-sale")
router.register("estimates", EstimateViewSet, basename="attendance-estimate")

urlpatterns = [
    path("dashboard/", AttendanceDashboardView.as_view(), name="attendance-dashboard"),
    path("estimate-approvals/<uuid:token>/", EstimateApprovalPublicView.as_view(), name="attendance-estimate-approval-public"),
    path("estimate-approvals/<uuid:token>/pdf/", EstimateApprovalPublicPdfView.as_view(), name="attendance-estimate-approval-public-pdf"),
]
urlpatterns += router.urls
