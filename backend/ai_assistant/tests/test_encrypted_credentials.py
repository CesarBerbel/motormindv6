from django.db import connection
from django.test import TestCase

from accounts.encryption import decrypt_credential, encrypt_credential, is_encrypted_credential
from ai_assistant.models import AIProviderConfiguration
from messaging.models import ChannelConfiguration


class EncryptedCredentialTests(TestCase):
    def test_ai_provider_api_key_is_encrypted_at_rest_and_decrypted_on_read(self):
        config = AIProviderConfiguration.objects.create(
            provider=AIProviderConfiguration.Provider.OPENAI,
            api_key="sk-projeto-teste",
            is_enabled=True,
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT api_key FROM ai_assistant_aiproviderconfiguration WHERE id = %s",
                [config.id],
            )
            raw_api_key = cursor.fetchone()[0]

        self.assertNotEqual(raw_api_key, "sk-projeto-teste")
        self.assertTrue(is_encrypted_credential(raw_api_key))
        self.assertEqual(AIProviderConfiguration.objects.get(pk=config.pk).api_key, "sk-projeto-teste")

    def test_whatsapp_access_token_is_encrypted_at_rest_and_decrypted_on_read(self):
        config = ChannelConfiguration.load()
        config.whatsapp_access_token = "EAA-whatsapp-token-teste"
        config.whatsapp_phone_number_id = "123456789"
        config.save()

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT whatsapp_access_token FROM messaging_channelconfiguration WHERE id = %s",
                [config.id],
            )
            raw_token = cursor.fetchone()[0]

        self.assertNotEqual(raw_token, "EAA-whatsapp-token-teste")
        self.assertTrue(is_encrypted_credential(raw_token))
        self.assertEqual(ChannelConfiguration.objects.get(pk=config.pk).whatsapp_access_token, "EAA-whatsapp-token-teste")

    def test_plaintext_legacy_values_remain_readable_until_next_save(self):
        self.assertEqual(decrypt_credential("valor-antigo-em-texto-puro"), "valor-antigo-em-texto-puro")

    def test_encrypt_credential_is_idempotent_for_already_encrypted_values(self):
        encrypted = encrypt_credential("segredo")
        self.assertEqual(encrypt_credential(encrypted), encrypted)
        self.assertEqual(decrypt_credential(encrypted), "segredo")
