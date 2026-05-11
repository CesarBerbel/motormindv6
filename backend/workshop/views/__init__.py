"""Views do app workshop organizadas por domínio.

A fachada preserva `from workshop.views import ...`, usado por `urls.py` e
por qualquer integração existente.
"""

from .catalog import (
    FipeLookupView,
    GeneralCategoryViewSet,
    PartBrandViewSet,
    PartStockMovementViewSet,
    PartViewSet,
    ServicePackageViewSet,
    ServiceDefaultPartViewSet,
    WorkshopServiceChecklistTemplateViewSet,
    WorkshopServiceViewSet,
)
from .dashboards import RoleDashboardView, TechnicalDashboardView, WorkshopDashboardView
from .profile import WorkshopProfileView
from .public import CustomerApprovalPdfView, CustomerApprovalPublicView, PublicLandingView
from .vehicles import VehicleViewSet
from .work_orders import (
    WorkOrderEventViewSet,
    WorkOrderMessageViewSet,
    WorkOrderNotificationRuleViewSet,
    WorkOrderPartViewSet,
    WorkOrderPaymentViewSet,
    WorkOrderPhotoViewSet,
    WorkOrderServiceChecklistItemViewSet,
    WorkOrderServiceViewSet,
    WorkOrderViewSet,
)

__all__ = [
    "CustomerApprovalPdfView",
    "CustomerApprovalPublicView",
    "FipeLookupView",
    "GeneralCategoryViewSet",
    "PartBrandViewSet",
    "PartStockMovementViewSet",
    "PartViewSet",
    "PublicLandingView",
    "RoleDashboardView",
    "ServicePackageViewSet",
    "ServiceDefaultPartViewSet",
    "TechnicalDashboardView",
    "VehicleViewSet",
    "WorkshopDashboardView",
    "WorkshopProfileView",
    "WorkshopServiceChecklistTemplateViewSet",
    "WorkshopServiceViewSet",
    "WorkOrderEventViewSet",
    "WorkOrderMessageViewSet",
    "WorkOrderNotificationRuleViewSet",
    "WorkOrderPartViewSet",
    "WorkOrderPaymentViewSet",
    "WorkOrderPhotoViewSet",
    "WorkOrderServiceChecklistItemViewSet",
    "WorkOrderServiceViewSet",
    "WorkOrderViewSet",
]
