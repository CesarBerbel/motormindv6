
from decimal import Decimal
import base64
import binascii
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from rest_framework import serializers

from messaging.models import Contact, MessageTemplate
from messaging.serializers import ContactSerializer, MessageLogSerializer, format_cep, format_cpf_cnpj, normalize_br_phone_e164, only_digits

from ..state_machine import available_status_transitions
from ..models import (
    GeneralCategory,
    ZERO,
    WorkshopProfile,
    BottomNavigationItem,
    PartBrand,
    PART_UNIT_CHOICES,
    normalize_lookup_name,
    normalize_part_unit,
    Part,
    PartStockMovement,
    ServicePackage,
    ServicePackageItem,
    ServiceDefaultPart,
    Vehicle,
    WorkOrder,
    WorkOrderPhoto,
    WorkOrderEvent,
    WorkOrderCustomerApproval,
    WorkOrderDeliverySignature,
    WorkOrderMessage,
    WorkOrderNotificationRule,
    WorkOrderPart,
    WorkOrderPayment,
    WorkOrderService,
    WorkOrderServiceChecklistItem,
    WorkshopService,
    WorkshopServiceChecklistTemplate,
)

User = get_user_model()
