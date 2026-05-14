from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AuditLog
from finance.models import AccountPayable, FinancialLedgerEntry
from messaging.models import Contact
from workshop.models import Vehicle, WorkOrder, WorkOrderPayment, WorkOrderService


class FinancialAuditTrailApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="owner-audit-finance",
            email="owner-audit-finance@example.com",
            password="senha-forte-123",
        )
        self.client.force_authenticate(self.user)

    def test_payable_payment_reverse_preserves_payment_and_records_audit_and_reversal_ledger(self):
        create = self.client.post(
            "/api/finance/accounts-payable/",
            {
                "supplier_id": None,
                "category": "Ferramentas",
                "description": "Compra de ferramenta",
                "issue_date": "2026-05-10",
                "due_date": "2026-05-10",
                "amount": "120.00",
                "recurrence_type": "cash",
                "installment_total": 1,
                "notes": "",
            },
            format="json",
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        account_id = create.data["created"][0]["id"]

        payment_response = self.client.post(
            f"/api/finance/accounts-payable/{account_id}/register_payment/",
            {"method": "pix", "amount": "120.00", "reference": "PIX-001", "notes": "Pago via PIX."},
            format="json",
        )
        self.assertEqual(payment_response.status_code, status.HTTP_200_OK, payment_response.data)
        payment_id = payment_response.data["payment"]["id"]

        reverse_response = self.client.post(
            f"/api/finance/accounts-payable/{account_id}/payments/{payment_id}/reverse/",
            {"reason": "Pagamento lançado na conta errada."},
            format="json",
        )
        self.assertEqual(reverse_response.status_code, status.HTTP_200_OK, reverse_response.data)
        self.assertTrue(reverse_response.data["payment"]["is_reversed"])

        account = AccountPayable.objects.get(pk=account_id)
        self.assertEqual(account.paid_amount, Decimal("0.00"))
        self.assertEqual(account.balance_amount, Decimal("120.00"))
        self.assertEqual(account.payments.count(), 1)
        self.assertEqual(FinancialLedgerEntry.objects.filter(entry_type=FinancialLedgerEntry.EntryType.REVERSAL).count(), 1)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.FINANCIAL_REVERSAL,
                app_label="finance",
                model_name="accountpayablepayment",
                object_id=str(payment_id),
                metadata__reason="Pagamento lançado na conta errada.",
            ).exists()
        )

    def test_work_order_payment_reverse_preserves_payment_updates_totals_and_records_audit(self):
        customer = Contact.objects.create(first_name="Cliente", last_name="Auditoria", email="cliente-auditoria@example.com")
        vehicle = Vehicle.objects.create(customer=customer, plate="AUD1T23", make="VW", model="Gol", year=2020)
        order = WorkOrder.objects.create(customer=customer, vehicle=vehicle, title="OS auditoria", created_by=self.user, updated_by=self.user)
        WorkOrderService.objects.create(work_order=order, description="Serviço auditado", quantity="1.00", unit_price="200.00")
        order.refresh_from_db()
        order.recalculate_totals()

        payment_response = self.client.post(
            "/api/workshop/work-order-payments/",
            {"work_order": order.id, "method": "pix", "amount": "80.00", "reference": "PIX-OS-001", "notes": "Entrada parcial."},
            format="json",
        )
        self.assertEqual(payment_response.status_code, status.HTTP_201_CREATED, payment_response.data)
        payment_id = payment_response.data["id"]
        order.refresh_from_db()
        self.assertEqual(order.paid_total, Decimal("80.00"))

        delete_response = self.client.delete(f"/api/workshop/work-order-payments/{payment_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_400_BAD_REQUEST, delete_response.data)

        reverse_response = self.client.post(
            f"/api/workshop/work-order-payments/{payment_id}/reverse/",
            {"reason": "Cliente trocou a forma de pagamento."},
            format="json",
        )
        self.assertEqual(reverse_response.status_code, status.HTTP_200_OK, reverse_response.data)
        self.assertTrue(reverse_response.data["payment"]["is_reversed"])
        order.refresh_from_db()
        self.assertEqual(order.paid_total, Decimal("0.00"))
        self.assertEqual(order.balance_due, Decimal("200.00"))
        self.assertEqual(WorkOrderPayment.objects.filter(pk=payment_id).count(), 1)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.FINANCIAL_REVERSAL,
                app_label="workshop",
                model_name="workorderpayment",
                object_id=str(payment_id),
                metadata__reason="Cliente trocou a forma de pagamento.",
            ).exists()
        )

    def test_work_order_discount_change_is_audited(self):
        customer = Contact.objects.create(first_name="Cliente", last_name="Desconto", email="cliente-desconto@example.com")
        vehicle = Vehicle.objects.create(customer=customer, plate="DES1C23", make="VW", model="Gol", year=2020)
        order = WorkOrder.objects.create(customer=customer, vehicle=vehicle, title="OS desconto", created_by=self.user, updated_by=self.user)
        WorkOrderService.objects.create(work_order=order, description="Serviço com desconto", quantity="1.00", unit_price="150.00")
        order.refresh_from_db()
        order.recalculate_totals()

        response = self.client.patch(
            f"/api/workshop/work-orders/{order.id}/",
            {"customer_id": customer.id, "vehicle_id": vehicle.id, "manual_discount_amount": "25.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.FINANCIAL_DISCOUNT,
                app_label="workshop",
                model_name="workorder",
                object_id=str(order.id),
            ).exists()
        )
