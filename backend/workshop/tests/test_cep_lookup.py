from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from accounts.roles import ROLE_ATTENDANT, ROLE_FINANCE
from accounts.services import apply_role_to_user


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class CepLookupTests(APITestCase):
    def test_attendant_can_lookup_cep_through_backend_proxy(self):
        user = get_user_model().objects.create_user(username="cep-attendant", password="senha-forte-123")
        apply_role_to_user(user, ROLE_ATTENDANT)
        self.client.force_authenticate(user)

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "cep": "01001-000",
            "logradouro": "Praça da Sé",
            "bairro": "Sé",
            "localidade": "São Paulo",
            "uf": "SP",
        }

        with patch("workshop.views.catalog.requests.get", return_value=mock_response) as mocked_get:
            response = self.client.get("/api/workshop/cep/?cep=01001000")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["zip_code"], "01001-000")
        self.assertEqual(response.data["address_line"], "Praça da Sé")
        self.assertEqual(response.data["district"], "Sé")
        self.assertEqual(response.data["city"], "São Paulo")
        self.assertEqual(response.data["state"], "SP")
        mocked_get.assert_called_once()

    def test_unrelated_role_cannot_lookup_cep_for_restricted_forms(self):
        user = get_user_model().objects.create_user(username="cep-finance", password="senha-forte-123")
        apply_role_to_user(user, ROLE_FINANCE)
        self.client.force_authenticate(user)

        response = self.client.get("/api/workshop/cep/?cep=01001000")

        self.assertEqual(response.status_code, 403, response.data)
