"""Campos Django para armazenamento criptografado de credenciais."""

from __future__ import annotations

from django.db import models

from .encryption import decrypt_credential, encrypt_credential


class EncryptedTextField(models.TextField):
    description = "Texto criptografado para credenciais sensiveis"

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return encrypt_credential(value)

    def from_db_value(self, value, expression, connection):  # noqa: ARG002
        return decrypt_credential(value)

    def to_python(self, value):
        value = super().to_python(value)
        return decrypt_credential(value)


class EncryptedCharField(models.CharField):
    description = "Texto curto criptografado para credenciais sensiveis"

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return encrypt_credential(value)

    def from_db_value(self, value, expression, connection):  # noqa: ARG002
        return decrypt_credential(value)

    def to_python(self, value):
        value = super().to_python(value)
        return decrypt_credential(value)
