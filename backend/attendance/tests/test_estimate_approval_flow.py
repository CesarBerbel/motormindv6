from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from attendance.models import Estimate, EstimatePartItem, EstimateServiceItem
from attendance.serializers import EstimateCustomerApprovalPublicSerializer
from attendance.services import change_estimate_status, create_revision_estimate_from_work_order, decide_estimate_approval, ensure_pending_estimate_approval, manually_approve_estimate
from messaging.models import ChannelConfiguration, Contact, MessageLog, MessageTemplate
from purchasing.models import PurchaseOrder
from workshop.models import Part, PartStockMovement, ServicePackage, ServicePackageItem, Vehicle, WorkOrder, WorkOrderMessage, WorkOrderNotificationRule, WorkOrderEvent, WorkOrderPart, ServiceDefaultPart, WorkshopProfile, WorkshopService


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EstimateCustomerApprovalFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="owner-estimate-flow",
            email="owner-estimate-flow@example.com",
            password="senha-forte-123",
        )
        WorkshopProfile.get_solo()
        self.customer = Contact.objects.create(
            person_type="individual",
            first_name="Cliente",
            last_name="Orcamento",
            email="cliente-orcamento@example.com",
            phone_e164="+5511999999999",
        )
        self.vehicle = Vehicle.objects.create(customer=self.customer, plate="ABC1D23", make="VW", model="Gol", year=2020)
        self.service_one = WorkshopService.objects.create(name="Troca de pastilhas", default_unit_price=Decimal("180.00"))
        self.service_two = WorkshopService.objects.create(name="Limpeza de bicos", default_unit_price=Decimal("250.00"))
        self.part_one = Part.objects.create(sku="PAST-001", name="Pastilha dianteira", unit="un", sale_price=Decimal("120.00"), cost_price=Decimal("70.00"), stock_quantity=Decimal("10.00"))
        self.part_two = Part.objects.create(sku="KIT-002", name="Kit limpeza", unit="un", sale_price=Decimal("80.00"), cost_price=Decimal("40.00"), stock_quantity=Decimal("10.00"))
        self.estimate = Estimate.objects.create(
            customer=self.customer,
            vehicle=self.vehicle,
            title="Orçamento de teste",
            complaint="Freio fazendo ruído.",
            diagnosis="Pastilhas gastas e bicos sujos.",
            tank_level_percent=Estimate.TankLevel.HALF,
            created_by=self.user,
            updated_by=self.user,
        )
        self.estimate_service_one = EstimateServiceItem.objects.create(estimate=self.estimate, service=self.service_one, description="Troca de pastilhas", quantity=Decimal("1.00"), unit_price=Decimal("180.00"))
        self.estimate_service_two = EstimateServiceItem.objects.create(estimate=self.estimate, service=self.service_two, description="Limpeza de bicos", quantity=Decimal("1.00"), unit_price=Decimal("250.00"))
        self.estimate_part_one = EstimatePartItem.objects.create(estimate=self.estimate, service_item=self.estimate_service_one, part=self.part_one, description="Pastilha dianteira", quantity=Decimal("1.00"), unit_price=Decimal("120.00"), cost_price=Decimal("70.00"))
        self.estimate_part_two = EstimatePartItem.objects.create(estimate=self.estimate, service_item=self.estimate_service_two, part=self.part_two, description="Kit limpeza", quantity=Decimal("1.00"), unit_price=Decimal("80.00"), cost_price=Decimal("40.00"))



    def test_estimate_service_adds_default_parts_from_catalog(self):
        default_part = Part.objects.create(
            sku="OLEO-5W30",
            name="Óleo 5W30",
            unit="l",
            sale_price=Decimal("55.00"),
            cost_price=Decimal("32.00"),
            stock_quantity=Decimal("20.00"),
        )
        service = WorkshopService.objects.create(name="Troca de óleo completa", default_unit_price=Decimal("100.00"))
        ServiceDefaultPart.objects.create(
            service=service,
            part=default_part,
            quantity=Decimal("4.00"),
            unit_price=Decimal("55.00"),
        )
        estimate = Estimate.objects.create(
            customer=self.customer,
            vehicle=self.vehicle,
            title="Orçamento com peça padrão",
            created_by=self.user,
            updated_by=self.user,
        )

        service_line = EstimateServiceItem.objects.create(
            estimate=estimate,
            service=service,
            description="Troca de óleo completa",
            quantity=Decimal("1.00"),
            unit_price=Decimal("100.00"),
        )

        part_line = EstimatePartItem.objects.get(estimate=estimate, service_item=service_line, part=default_part)
        self.assertEqual(part_line.description, "Óleo 5W30")
        self.assertEqual(part_line.quantity, Decimal("4.00"))
        self.assertEqual(part_line.unit_price, Decimal("55.00"))

    def test_estimate_part_total_does_not_include_linked_service_total(self):
        self.estimate_service_one.quantity = Decimal("1.00")
        self.estimate_service_one.unit_price = Decimal("2000.00")
        self.estimate_service_one.discount_amount = Decimal("0.00")
        self.estimate_service_one.save()
        self.estimate_part_one.quantity = Decimal("4.00")
        self.estimate_part_one.unit_price = Decimal("200.00")
        self.estimate_part_one.discount_amount = Decimal("0.00")
        self.estimate_part_one.save()

        self.estimate.recalculate_totals(save=True)
        self.estimate.refresh_from_db()
        self.estimate_part_one.refresh_from_db()

        self.assertEqual(self.estimate_part_one.subtotal_amount, Decimal("800.0000"))
        self.assertEqual(self.estimate_part_one.total_amount, Decimal("800.0000"))
        self.assertEqual(self.estimate.subtotal_parts, Decimal("880.00"))
        self.assertNotEqual(self.estimate_part_one.total_amount, Decimal("2800.00"))

    def test_estimate_items_can_only_change_when_open_or_rejected(self):
        self.estimate.status = Estimate.Status.AWAITING_APPROVAL
        self.estimate.save(update_fields=["status", "updated_at"])

        self.estimate_service_one.unit_price = Decimal("199.00")
        with self.assertRaises(ValidationError):
            self.estimate_service_one.save()

        self.estimate.status = Estimate.Status.REJECTED
        self.estimate.save(update_fields=["status", "updated_at"])
        self.estimate_service_one.unit_price = Decimal("199.00")
        self.estimate_service_one.save()
        self.estimate_service_one.refresh_from_db()
        self.assertEqual(self.estimate_service_one.unit_price, Decimal("199.00"))

    def test_approved_work_order_generates_revision_estimate_and_reopens_existing_order(self):
        approval = ensure_pending_estimate_approval(self.estimate, actor=self.user)
        _updated_approval, work_order = decide_estimate_approval(
            approval,
            "approved",
            selected_service_ids=[self.estimate_service_one.id],
            selected_part_ids=[self.estimate_part_one.id],
            name="Cliente Orcamento",
            document="12345678909",
            notes="Aprovo o orçamento inicial.",
            confirm_partial=True,
            actor=self.user,
        )
        self.assertEqual(WorkOrder.objects.count(), 1)
        work_order.status = WorkOrder.Status.IN_PROGRESS
        work_order.approved_at = timezone.now()
        work_order.save(update_fields=["status", "approved_at", "updated_at"])

        revision = create_revision_estimate_from_work_order(
            work_order,
            payload={"title": "Revisão aprovada pelo cliente"},
            actor=self.user,
        )
        self.assertEqual(revision.revision_work_order, work_order)
        self.assertEqual(revision.status, Estimate.Status.OPEN)
        self.assertEqual(revision.services.count(), 1)

        _manual_approval, reopened_order = manually_approve_estimate(
            revision,
            actor=self.user,
            approval_type="total",
            signature_name="Cliente Orcamento",
            signature_document="12345678909",
            notes="Aprovação manual da revisão.",
        )

        self.assertEqual(reopened_order.id, work_order.id)
        self.assertEqual(WorkOrder.objects.count(), 1)
        work_order.refresh_from_db()
        revision.refresh_from_db()
        self.assertEqual(work_order.status, WorkOrder.Status.OPEN)
        self.assertEqual(work_order.source_estimate_id, revision.id)
        self.assertEqual(revision.status, Estimate.Status.CONVERTED)
        self.assertEqual(revision.revision_work_order, work_order)

    def test_partial_estimate_approval_generates_open_work_order_only_with_selected_items(self):
        approval = ensure_pending_estimate_approval(self.estimate, actor=self.user)

        updated_approval, work_order = decide_estimate_approval(
            approval,
            "approved",
            selected_service_ids=[self.estimate_service_one.id],
            selected_part_ids=[self.estimate_part_one.id],
            name="Cliente Orcamento",
            document="12345678909",
            notes="Aprovo apenas o serviço de freio neste momento.",
            confirm_partial=True,
            actor=self.user,
        )

        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.status, Estimate.Status.CONVERTED)
        self.assertEqual(updated_approval.status, updated_approval.Status.PARTIALLY_APPROVED)
        self.assertIsNotNone(updated_approval.generated_work_order)
        self.assertEqual(work_order.status, WorkOrder.Status.OPEN)
        self.assertEqual(work_order.source_estimate_id, self.estimate.id)
        self.assertEqual(work_order.services.count(), 1)
        self.assertEqual(work_order.parts.count(), 1)
        self.assertEqual(work_order.services.first().description, "Troca de pastilhas")
        part_line = work_order.parts.first()
        self.assertEqual(part_line.description, "Pastilha dianteira")
        self.assertEqual(part_line.stock_reservation_status, WorkOrderPart.ReservationStatus.RESERVED)
        self.assertEqual(part_line.stock_reserved_quantity, Decimal("1.00"))
        self.assertEqual(part_line.stock_shortage_quantity, Decimal("0.00"))
        self.part_one.refresh_from_db()
        self.assertEqual(self.part_one.stock_quantity, Decimal("10.00"))
        self.assertEqual(self.part_one.reserved_quantity, Decimal("1.00"))
        self.assertTrue(PartStockMovement.objects.filter(work_order=work_order, movement_type=PartStockMovement.MovementType.RESERVATION).exists())
        self.assertEqual(self.estimate.tank_level_percent, Estimate.TankLevel.HALF)

    def test_estimate_approval_sets_work_order_waiting_parts_when_stock_is_missing(self):
        self.part_one.stock_quantity = Decimal("0.00")
        self.part_one.save()
        approval = ensure_pending_estimate_approval(self.estimate, actor=self.user)

        _updated_approval, work_order = decide_estimate_approval(
            approval,
            "approved",
            selected_service_ids=[self.estimate_service_one.id],
            selected_part_ids=[self.estimate_part_one.id],
            name="Cliente Orcamento",
            document="12345678909",
            notes="Aprovo o serviço de freio.",
            confirm_partial=True,
            actor=self.user,
        )

        work_order.refresh_from_db()
        line = work_order.parts.get()
        self.part_one.refresh_from_db()
        self.assertEqual(work_order.status, WorkOrder.Status.WAITING_PARTS)
        self.assertEqual(line.stock_reservation_status, WorkOrderPart.ReservationStatus.UNAVAILABLE)
        self.assertEqual(line.stock_reserved_quantity, Decimal("0.00"))
        self.assertEqual(line.stock_shortage_quantity, Decimal("1.00"))
        self.assertEqual(self.part_one.reserved_quantity, Decimal("0.00"))
        purchase_order = PurchaseOrder.objects.get(work_order=work_order, origin=PurchaseOrder.Origin.AUTOMATIC)
        self.assertEqual(purchase_order.status, PurchaseOrder.Status.DRAFT)
        purchase_item = purchase_order.items.get(work_order_part=line)
        self.assertEqual(purchase_item.quantity, Decimal("1.00"))
        self.assertEqual(purchase_item.part, self.part_one)
        self.assertTrue(WorkOrderEvent.objects.filter(work_order=work_order, event_type=WorkOrderEvent.EventType.PURCHASE_NEEDED).exists())

    def test_estimate_approval_sets_partial_reservation_when_stock_is_partial(self):
        self.estimate_part_one.quantity = Decimal("3.00")
        self.estimate_part_one.save()
        self.part_one.stock_quantity = Decimal("2.00")
        self.part_one.save()
        approval = ensure_pending_estimate_approval(self.estimate, actor=self.user)

        _updated_approval, work_order = decide_estimate_approval(
            approval,
            "approved",
            selected_service_ids=[self.estimate_service_one.id],
            selected_part_ids=[self.estimate_part_one.id],
            name="Cliente Orcamento",
            document="12345678909",
            notes="Aprovo o serviço de freio.",
            confirm_partial=True,
            actor=self.user,
        )

        work_order.refresh_from_db()
        line = work_order.parts.get()
        self.part_one.refresh_from_db()
        self.assertEqual(work_order.status, WorkOrder.Status.WAITING_PARTS)
        self.assertEqual(line.stock_reservation_status, WorkOrderPart.ReservationStatus.PARTIAL)
        self.assertEqual(line.stock_reserved_quantity, Decimal("2.00"))
        self.assertEqual(line.stock_shortage_quantity, Decimal("1.00"))
        self.assertEqual(self.part_one.reserved_quantity, Decimal("2.00"))
        purchase_order = PurchaseOrder.objects.get(work_order=work_order, origin=PurchaseOrder.Origin.AUTOMATIC)
        self.assertEqual(purchase_order.items.get(work_order_part=line).quantity, Decimal("1.00"))

    def test_estimate_approval_creates_purchase_need_when_existing_reservation_uses_stock(self):
        self.part_one.stock_quantity = Decimal("1.00")
        self.part_one.reserved_quantity = Decimal("1.00")
        self.part_one.save()
        approval = ensure_pending_estimate_approval(self.estimate, actor=self.user)

        _updated_approval, work_order = decide_estimate_approval(
            approval,
            "approved",
            selected_service_ids=[self.estimate_service_one.id],
            selected_part_ids=[self.estimate_part_one.id],
            name="Cliente Orcamento",
            document="12345678909",
            notes="Aprovo o serviço de freio.",
            confirm_partial=True,
            actor=self.user,
        )

        work_order.refresh_from_db()
        line = work_order.parts.get()
        self.assertEqual(work_order.status, WorkOrder.Status.WAITING_PARTS)
        self.assertEqual(line.stock_reservation_status, WorkOrderPart.ReservationStatus.UNAVAILABLE)
        self.assertEqual(line.stock_shortage_quantity, Decimal("1.00"))
        purchase_order = PurchaseOrder.objects.get(work_order=work_order, origin=PurchaseOrder.Origin.AUTOMATIC)
        self.assertEqual(purchase_order.items.get(work_order_part=line).quantity, Decimal("1.00"))

    def test_estimate_service_keeps_source_package_when_generating_work_order(self):
        package = ServicePackage.objects.create(code="PCT-FREIO", name="Combo freio", discount_amount=Decimal("10.00"))
        ServicePackageItem.objects.create(service_package=package, service=self.service_one, description="Troca de pastilhas no combo", quantity=Decimal("1.00"), unit_price=Decimal("180.00"), position=1)
        self.estimate_service_one.source_package = package
        self.estimate_service_one.save()
        approval = ensure_pending_estimate_approval(self.estimate, actor=self.user)

        _updated_approval, work_order = decide_estimate_approval(
            approval,
            "approved",
            selected_service_ids=[self.estimate_service_one.id, self.estimate_service_two.id],
            selected_part_ids=[self.estimate_part_one.id, self.estimate_part_two.id],
            name="Cliente Orcamento",
            document="12345678909",
            notes="Aprovo o orçamento completo.",
            confirm_partial=False,
            actor=self.user,
        )

        self.assertEqual(work_order.services.filter(source_package=package).count(), 1)
        self.assertEqual(work_order.services.get(source_package=package).description, "Troca de pastilhas")

    def test_public_estimate_approval_serializer_uses_workshop_phone_e164(self):
        profile = WorkshopProfile.get_solo()
        profile.phone_e164 = "+551132323232"
        profile.email = "oficina@example.com"
        profile.address_line = "Rua Teste"
        profile.address_number = "123"
        profile.city = "Sao Paulo"
        profile.state = "SP"
        profile.save()
        approval = ensure_pending_estimate_approval(self.estimate, actor=self.user)

        data = EstimateCustomerApprovalPublicSerializer(instance=approval).data

        self.assertEqual(data["workshop"]["phone"], "+551132323232")
        self.assertEqual(data["workshop"]["email"], "oficina@example.com")
        self.assertIn("Rua Teste", data["workshop"]["address"])


    def test_can_generate_estimate_pdf_with_vehicle_and_tank_data(self):
        self.vehicle.steering_type = Vehicle.SteeringType.HYDRAULIC
        self.vehicle.transmission_type = Vehicle.TransmissionType.MANUAL
        self.vehicle.has_air_conditioning = True
        self.vehicle.door_count = 4
        self.vehicle.is_modified = True
        self.vehicle.fipe_brand_code = "59"
        self.vehicle.fipe_model_code = "5940"
        self.vehicle.fipe_year_code = "2020-1"
        self.vehicle.save()
        from rest_framework.test import APIClient

        api_client = APIClient()
        api_client.force_authenticate(self.user)
        response = api_client.get(f"/api/attendance/estimates/{self.estimate.id}/document/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_public_estimate_approval_pdf_is_available_without_authentication(self):
        approval = ensure_pending_estimate_approval(self.estimate, actor=self.user)

        response = self.client.get(f"/api/attendance/estimate-approvals/{approval.token}/pdf/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_estimate_status_change_sends_automatic_budget_notification(self):
        config = ChannelConfiguration.load()
        config.email_enabled = True
        config.default_from_email = "oficina@example.com"
        config.save()
        template = MessageTemplate.objects.create(
            name="Orçamento em diagnóstico",
            channel=MessageTemplate.Channel.EMAIL,
            email_subject="Orçamento {{ numero_orcamento }} em diagnóstico",
            email_html_body="Olá {{ nome_cliente }}, orçamento {{ numero_orcamento }} está {{ status_orcamento }}.",
            email_text_body="Olá {{ nome_cliente }}, orçamento {{ numero_orcamento }} está {{ status_orcamento }}.",
        )
        rule = WorkOrderNotificationRule.objects.create(
            name="Avisar cliente quando orçamento entrar em diagnóstico",
            entity_type=WorkOrderNotificationRule.EntityType.ESTIMATE,
            trigger_status=Estimate.Status.DIAGNOSIS,
            channel=MessageTemplate.Channel.EMAIL,
            template=template,
            recipient_target=WorkOrderNotificationRule.RecipientTarget.CUSTOMER,
            is_active=True,
            send_once_per_status=True,
        )

        with self.captureOnCommitCallbacks(execute=True):
            change_estimate_status(
                self.estimate,
                Estimate.Status.DIAGNOSIS,
                actor=self.user,
                note="Iniciar diagnóstico do orçamento.",
                send_notifications=True,
            )

        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.status, Estimate.Status.DIAGNOSIS)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("cliente-orcamento@example.com", mail.outbox[0].to)
        self.assertIn(self.estimate.number, mail.outbox[0].subject)
        self.assertEqual(MessageLog.objects.filter(status=MessageLog.Status.SENT).count(), 1)
        relation = WorkOrderMessage.objects.get(estimate=self.estimate, notification_rule=rule)
        self.assertIsNone(relation.work_order)
        self.assertEqual(relation.trigger_status, Estimate.Status.DIAGNOSIS)
