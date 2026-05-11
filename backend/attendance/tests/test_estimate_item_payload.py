from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from attendance.models import EstimatePartItem, EstimateServiceItem
from messaging.models import Contact
from workshop.models import Part, ServiceDefaultPart, Vehicle, WorkshopService


class EstimateItemPayloadTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="owner-estimate-payload",
            email="owner-estimate-payload@example.com",
            password="senha-forte-123",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.customer = Contact.objects.create(
            person_type="individual",
            first_name="Cliente",
            last_name="Payload",
            email="cliente-payload@example.com",
        )
        self.vehicle = Vehicle.objects.create(customer=self.customer, plate="PAY1L23", make="VW", model="Gol", year=2020)
        self.service = WorkshopService.objects.create(name="Troca de óleo", default_unit_price=Decimal("120.00"))
        self.part = Part.objects.create(
            sku="OLEO-001",
            name="Óleo 5W30",
            unit="un",
            sale_price=Decimal("55.00"),
            cost_price=Decimal("30.00"),
            stock_quantity=Decimal("20.00"),
        )
        ServiceDefaultPart.objects.create(
            service=self.service,
            part=self.part,
            quantity=Decimal("1.00"),
            unit_price=Decimal("55.00"),
        )

    def test_estimate_accepts_frontend_local_service_part_payload(self):
        payload = {
            "customer_id": self.customer.id,
            "vehicle_id": self.vehicle.id,
            "title": "Orçamento com item guiado",
            "complaint": "Cliente solicitou revisão.",
            "diagnosis": "Necessária troca de óleo.",
            "valid_until": "2030-01-30",
            "tank_level_percent": 50,
            "discount_amount": "0.00",
            "services": [
                {
                    "local_id": "service-local-1",
                    "service_id": self.service.id,
                    "source_package_id": None,
                    "description": "Troca de óleo",
                    "quantity": "1.00",
                    "unit_price": "120.00",
                    "discount_amount": "0.00",
                    "notes": "",
                }
            ],
            "parts": [
                {
                    "local_id": "part-local-1",
                    "service_local_id": "service-local-1",
                    "part_id": self.part.id,
                    "description": "Óleo 5W30",
                    "quantity": "1.00",
                    "unit_price": "55.00",
                    "cost_price": "30.00",
                    "discount_amount": "0.00",
                    "notes": "Adicionada automaticamente pelo serviço.",
                }
            ],
        }

        response = self.client.post("/api/attendance/estimates/", payload, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        service_line = EstimateServiceItem.objects.get()
        part_line = EstimatePartItem.objects.get()
        self.assertEqual(part_line.service_item_id, service_line.id)
        self.assertEqual(response.data["total_amount"], "175.00")
