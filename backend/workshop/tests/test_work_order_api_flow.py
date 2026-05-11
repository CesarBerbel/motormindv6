from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from messaging.models import Contact
from workshop.models import Part, ServiceDefaultPart, Vehicle, WorkOrder, WorkOrderPart, WorkOrderService, WorkshopService


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class WorkOrderApiFlowTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="owner-workshop",
            email="owner-workshop@example.com",
            password="senha-forte-123",
        )
        self.client.force_authenticate(self.user)


    def test_work_order_service_adds_default_parts_from_catalog(self):
        customer = Contact.objects.create(
            person_type="individual",
            first_name="Cliente",
            last_name="Peças Padrão",
            email="cliente-default-parts@example.com",
        )
        order = WorkOrder.objects.create(
            customer=customer,
            title="OS com peça padrão",
            complaint="Troca preventiva.",
            created_by=self.user,
        )
        service = WorkshopService.objects.create(
            name="Troca de óleo",
            default_unit_price=Decimal("90.00"),
        )
        oil_filter = Part.objects.create(
            sku="FILT-OLEO-001",
            name="Filtro de óleo",
            unit="un",
            sale_price=Decimal("45.00"),
            cost_price=Decimal("20.00"),
            stock_quantity=Decimal("8.00"),
        )
        ServiceDefaultPart.objects.create(
            service=service,
            part=oil_filter,
            quantity=Decimal("1.00"),
            unit_price=Decimal("45.00"),
        )

        service_line = WorkOrderService.objects.create(
            work_order=order,
            service=service,
            description="Troca de óleo",
            quantity=Decimal("1.00"),
            unit_price=Decimal("90.00"),
        )

        part_line = WorkOrderPart.objects.get(work_order=order, linked_service=service_line, part=oil_filter)
        self.assertEqual(part_line.description, "Filtro de óleo")
        self.assertEqual(part_line.quantity, Decimal("1.00"))
        self.assertEqual(part_line.unit_price, Decimal("45.00"))

    def test_create_customer_vehicle_service_part_and_work_order(self):
        contact_response = self.client.post(
            "/api/contacts/",
            {
                "person_type": "individual",
                "first_name": "Cliente",
                "last_name": "Teste",
                "email": "cliente@example.com",
                "phone_e164": "+5511999999999",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(contact_response.status_code, status.HTTP_201_CREATED, contact_response.data)
        contact_id = contact_response.data["id"]

        vehicle_response = self.client.post(
            "/api/workshop/vehicles/",
            {
                "customer_id": contact_id,
                "plate": "ABC1D23",
                "make": "Fiat",
                "model": "Uno",
                "year": 2015,
                "color": "Branco",
                "odometer_km": 100000,
                "steering_type": "hydraulic",
                "has_air_conditioning": True,
                "door_count": 4,
                "transmission_type": "manual",
                "is_modified": True,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(vehicle_response.status_code, status.HTTP_201_CREATED, vehicle_response.data)
        vehicle_id = vehicle_response.data["id"]

        service_response = self.client.post(
            "/api/workshop/services/",
            {
                "code": "REV-TESTE",
                "name": "Revisão teste",
                "description": "Serviço criado pelo teste automatizado.",
                "default_unit_price": "120.00",
                "estimated_hours": "1.00",
                "is_featured": True,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(service_response.status_code, status.HTTP_201_CREATED, service_response.data)

        part_response = self.client.post(
            "/api/workshop/parts/",
            {
                "sku": "PCA-TESTE-001",
                "name": "Filtro teste API",
                "brand": "Marca Teste",
                "unit": "un",
                "cost_price": "20.00",
                "sale_price": "35.00",
                "stock_quantity": "5.00",
                "minimum_stock": "1.00",
                "is_featured": True,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(part_response.status_code, status.HTTP_201_CREATED, part_response.data)

        work_order_response = self.client.post(
            "/api/workshop/work-orders/",
            {
                "customer_id": contact_id,
                "vehicle_id": vehicle_id,
                "title": "OS de teste automatizado",
                "complaint": "Cliente solicitou revisão geral.",
                "priority": "normal",
                "order_type": "standard",
                "mileage_in": 100000,
            },
            format="json",
        )
        self.assertEqual(work_order_response.status_code, status.HTTP_201_CREATED, work_order_response.data)
        self.assertEqual(Contact.objects.count(), 1)
        self.assertEqual(Vehicle.objects.count(), 1)
        vehicle = Vehicle.objects.get()
        self.assertEqual(vehicle.steering_type, Vehicle.SteeringType.HYDRAULIC)
        self.assertTrue(vehicle.has_air_conditioning)
        self.assertEqual(vehicle.door_count, 4)
        self.assertEqual(vehicle.transmission_type, Vehicle.TransmissionType.MANUAL)
        self.assertTrue(vehicle.is_modified)
        self.assertEqual(WorkshopService.objects.count(), 1)
        self.assertEqual(Part.objects.count(), 1)
        self.assertEqual(WorkOrder.objects.count(), 1)

@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class TechnicalWorkbenchDiagnosisTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="owner-technical",
            email="owner-technical@example.com",
            password="senha-forte-123",
        )
        self.client.force_authenticate(self.user)
        self.customer = Contact.objects.create(
            person_type="individual",
            first_name="Cliente",
            last_name="Diagnóstico",
            email="cliente-diagnostico@example.com",
            phone_e164="+5511988887777",
        )

    def test_technical_start_and_complete_order(self):
        order = WorkOrder.objects.create(
            customer=self.customer,
            title="Falha intermitente na partida",
            complaint="Motor demora a pegar pela manhã.",
            status=WorkOrder.Status.OPEN,
            assigned_to=self.user,
        )

        start_response = self.client.post(
            f"/api/workshop/work-orders/{order.id}/technical-action/",
            {"action": "start"},
            format="json",
        )
        self.assertEqual(start_response.status_code, status.HTTP_200_OK, start_response.data)
        order.refresh_from_db()
        self.assertEqual(order.status, WorkOrder.Status.IN_PROGRESS)

        complete_response = self.client.post(
            f"/api/workshop/work-orders/{order.id}/technical-action/",
            {"action": "complete", "note": "Serviço finalizado pela bancada técnica."},
            format="json",
        )
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK, complete_response.data)
        order.refresh_from_db()
        self.assertEqual(order.status, WorkOrder.Status.COMPLETED)
