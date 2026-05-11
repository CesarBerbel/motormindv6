
"""Modelos do app workshop organizados por dominio.

Este modulo funciona como fachada de compatibilidade para manter imports antigos,
por exemplo: ``from workshop.models import WorkOrder``.
"""

from .common import *
from .profile import WorkshopProfile
from .catalog import (
    GeneralCategory,
    PartBrand,
    WorkshopService,
    WorkshopServiceChecklistTemplate,
    ServicePackage,
    ServicePackageItem,
    Part,
    ServiceDefaultPart,
)
from .vehicles import Vehicle
from .work_orders import (
    WorkOrder,
    WorkOrderPhoto,
    WorkOrderService,
    WorkOrderServiceChecklistItem,
    WorkOrderPart,
    WorkOrderPayment,
    PartStockMovement,
    WorkOrderEvent,
    WorkOrderCustomerApproval,
    WorkOrderDeliverySignature,
    WorkOrderNotificationRule,
    WorkOrderMessage,
)

__all__ = [
    "ZERO",
    "PART_UNIT_CHOICES",
    "IMAGE_EXTENSIONS",
    "IMAGE_EXTENSIONS_WITH_SVG",
    "MAX_IMAGE_SIZE",
    "MAX_LOGO_SIZE",
    "normalize_lookup_name",
    "normalize_part_unit",
    "safe_upload_path",
    "workshop_logo_upload_path",
    "service_photo_upload_path",
    "part_photo_upload_path",
    "work_order_photo_upload_path",
    "work_order_checklist_photo_upload_path",
    "work_order_signature_upload_path",
    "validate_file_size",
    "generate_prefixed_sequence_code",
    "WorkshopProfile",
    "GeneralCategory",
    "PartBrand",
    "WorkshopService",
    "WorkshopServiceChecklistTemplate",
    "ServicePackage",
    "ServicePackageItem",
    "Part",
    "ServiceDefaultPart",
    "Vehicle",
    "WorkOrder",
    "WorkOrderPhoto",
    "WorkOrderService",
    "WorkOrderServiceChecklistItem",
    "WorkOrderPart",
    "WorkOrderPayment",
    "PartStockMovement",
    "WorkOrderEvent",
    "WorkOrderCustomerApproval",
    "WorkOrderDeliverySignature",
    "WorkOrderNotificationRule",
    "WorkOrderMessage",
]
