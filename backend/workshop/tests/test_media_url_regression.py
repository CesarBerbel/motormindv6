from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase


TEST_MEDIA_ROOT = Path(settings.BASE_DIR) / "test_media" / "media_url_regression"


def tiny_jpeg(name="foto.jpg"):
    return SimpleUploadedFile(name, b"fake image bytes", content_type="image/jpeg")


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"], MEDIA_ROOT=TEST_MEDIA_ROOT)
class MediaUrlRegressionTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(username="owner-media", email="owner-media@example.com", password="testpass123")
        self.client.force_authenticate(self.user)

    def assert_relative_media_url(self, value):
        self.assertTrue(value.startswith("/media/"), value)
        self.assertFalse(value.startswith("http://"), value)
        self.assertFalse(value.startswith("https://"), value)

    def test_part_photo_url_is_relative_after_save_and_reload(self):
        response = self.client.post(
            "/api/workshop/parts/",
            {
                "sku": "IMG-001",
                "name": "Peça com foto",
                "brand": "Marca Teste",
                "unit": "un",
                "cost_price": "10.00",
                "sale_price": "20.00",
                "stock_quantity": "1.00",
                "minimum_stock": "0.00",
                "is_active": "true",
                "photo": tiny_jpeg("peca.jpg"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assert_relative_media_url(response.data["photo_url"])

        detail = self.client.get(f"/api/workshop/parts/{response.data['id']}/")
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assert_relative_media_url(detail.data["photo_url"])

    def test_user_photo_url_is_relative_after_save_and_reload(self):
        response = self.client.post(
            "/api/users/",
            {
                "username": "funcionario-media",
                "email": "funcionario-media@example.com",
                "first_name": "Funcionário",
                "last_name": "Imagem",
                "person_type": "individual",
                "role": "attendant",
                "is_active": "true",
                "photo_3x4": tiny_jpeg("funcionario.jpg"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assert_relative_media_url(response.data["photo_3x4_url"])

        detail = self.client.get(f"/api/users/{response.data['id']}/")
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assert_relative_media_url(detail.data["photo_3x4_url"])
