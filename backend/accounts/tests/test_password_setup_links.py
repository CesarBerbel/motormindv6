from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from accounts.passwords import build_password_setup_url


class PasswordSetupLinkTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="password-link-user",
            email="password-link-user@example.com",
            password="senha-forte-123",
        )
        self.factory = RequestFactory()

    @override_settings(
        DEBUG=False,
        FRONTEND_BASE_URL="http://localhost:5173",
        CORS_ALLOWED_ORIGINS=["https://app.oficina.example"],
        CSRF_TRUSTED_ORIGINS=["https://app.oficina.example"],
        ALLOWED_HOSTS=["api.oficina.example", "testserver"],
    )
    def test_password_setup_link_uses_allowed_request_origin_when_config_is_localhost_in_prod(self):
        request = self.factory.post(
            "/api/users/1/send-password-setup/",
            HTTP_ORIGIN="https://app.oficina.example",
            HTTP_HOST="api.oficina.example",
            secure=True,
        )

        url = build_password_setup_url(self.user, request=request)

        self.assertTrue(url.startswith("https://app.oficina.example/definir-senha/"), url)
        self.assertNotIn("localhost", url)

    @override_settings(
        DEBUG=False,
        FRONTEND_BASE_URL="https://admin.oficina.example",
        CORS_ALLOWED_ORIGINS=["https://app.oficina.example"],
        CSRF_TRUSTED_ORIGINS=["https://app.oficina.example"],
    )
    def test_password_setup_link_prefers_configured_public_frontend_url(self):
        request = self.factory.post(
            "/api/users/1/send-password-setup/",
            HTTP_ORIGIN="https://app.oficina.example",
        )

        url = build_password_setup_url(self.user, request=request)

        self.assertTrue(url.startswith("https://admin.oficina.example/definir-senha/"), url)

    @override_settings(DEBUG=True, FRONTEND_BASE_URL="http://localhost:5173")
    def test_password_setup_link_keeps_local_url_in_development(self):
        url = build_password_setup_url(self.user)

        self.assertTrue(url.startswith("http://localhost:5173/definir-senha/"), url)
