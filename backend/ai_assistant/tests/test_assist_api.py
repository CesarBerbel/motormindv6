from django.contrib.auth.models import User
from rest_framework.test import APITestCase


class AssistApiTests(APITestCase):
    def test_general_task_is_available_for_budget_field_assistance(self):
        user = User.objects.create_user(username="ai-user", password="senha-segura")
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/ai/assist/", {"task": "general"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("prompts", response.data)
        self.assertIn("has_provider", response.data)
