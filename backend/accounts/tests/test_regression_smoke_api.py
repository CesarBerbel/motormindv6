from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class MainApiRegressionSmokeTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="owner-smoke",
            email="owner-smoke@example.com",
            password="senha-forte-123",
        )
        self.client.force_authenticate(self.user)

    def test_authenticated_core_list_endpoints_do_not_crash(self):
        endpoints = [
            "/api/me/",
            "/api/users/",
            "/api/contact-groups/",
            "/api/contacts/",
            "/api/templates/",
            "/api/workshop/categories/",
            "/api/workshop/vehicles/",
            "/api/workshop/services/",
            "/api/workshop/parts/",
            "/api/workshop/work-orders/",
            "/api/purchasing/suppliers/",
            "/api/purchasing/purchase-orders/",
            "/api/finance/accounts-payable/",
            "/api/finance/accounts-receivable/",
            "/api/accounts/audit-logs/",
        ]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertLess(response.status_code, 500, getattr(response, "data", response.content))
                self.assertNotIn(response.status_code, {401, 403}, getattr(response, "data", response.content))

    def test_token_endpoint_sets_httponly_cookies_for_valid_credentials(self):
        self.client.force_authenticate(None)
        response = self.client.post(
            "/api/token/",
            {"username": "owner-smoke", "password": "senha-forte-123"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn(settings.JWT_AUTH_COOKIE_ACCESS, response.cookies)
        self.assertIn(settings.JWT_AUTH_COOKIE_REFRESH, response.cookies)
        self.assertTrue(response.cookies[settings.JWT_AUTH_COOKIE_ACCESS]["httponly"])
        self.assertTrue(response.cookies[settings.JWT_AUTH_COOKIE_REFRESH]["httponly"])

    def test_cookie_authenticated_user_can_access_me_endpoint(self):
        self.client.force_authenticate(None)
        login = self.client.post(
            "/api/token/",
            {"username": "owner-smoke", "password": "senha-forte-123"},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)

        response = self.client.get("/api/me/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["username"], "owner-smoke")

    def test_users_area_does_not_list_superusers(self):
        employee = get_user_model().objects.create_user(
            username="employee-smoke",
            email="employee-smoke@example.com",
            password="senha-forte-123",
        )

        response = self.client.get("/api/users/")

        self.assertEqual(response.status_code, 200, response.data)
        records = response.data.get("results", response.data)
        usernames = {record["username"] for record in records}
        self.assertIn(employee.username, usernames)
        self.assertNotIn(self.user.username, usernames)

    def test_refresh_endpoint_uses_refresh_cookie_and_rotates_access_cookie(self):
        self.client.force_authenticate(None)
        login = self.client.post(
            "/api/token/",
            {"username": "owner-smoke", "password": "senha-forte-123"},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)

        response = self.client.post("/api/token/refresh/", {}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn(settings.JWT_AUTH_COOKIE_ACCESS, response.cookies)
        self.assertNotIn("access", response.data)

    def test_logout_endpoint_clears_auth_cookies(self):
        self.client.force_authenticate(None)
        login = self.client.post(
            "/api/token/",
            {"username": "owner-smoke", "password": "senha-forte-123"},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)

        response = self.client.post("/api/token/logout/", {}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.cookies[settings.JWT_AUTH_COOKIE_ACCESS].value, "")
        self.assertEqual(response.cookies[settings.JWT_AUTH_COOKIE_REFRESH].value, "")

    def test_login_endpoint_rejects_invalid_credentials_without_server_error(self):
        self.client.force_authenticate(None)
        response = self.client.post(
            "/api/token/",
            {"username": "owner-smoke", "password": "senha-errada"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.data.get("detail") or response.data.get("message"), response.data)
