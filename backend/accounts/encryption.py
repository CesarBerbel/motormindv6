"""Utilitarios para criptografia reversivel de credenciais sensiveis.

Este modulo protege segredos que precisam ser recuperados em texto puro para
integracoes externas, como tokens de WhatsApp e chaves de provedores de IA.
Senhas de usuario continuam usando o hash nativo do Django e nao passam por
esta camada.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

ENCRYPTION_PREFIX = "enc:v1:"


def is_encrypted_credential(value: object) -> bool:
    return isinstance(value, str) and value.startswith(ENCRYPTION_PREFIX)


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    configured_key = (getattr(settings, "CREDENTIAL_ENCRYPTION_KEY", "") or "").strip()
    if configured_key:
        try:
            return Fernet(configured_key.encode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - mensagem customizada para configuracao invalida
            raise ImproperlyConfigured(
                "CREDENTIAL_ENCRYPTION_KEY invalida. Gere uma chave com: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            ) from exc

    if not getattr(settings, "DEBUG", False):
        raise ImproperlyConfigured(
            "Defina CREDENTIAL_ENCRYPTION_KEY antes de iniciar o sistema fora do modo DEBUG."
        )

    logger.warning(
        "CREDENTIAL_ENCRYPTION_KEY nao configurada. Usando chave derivada de SECRET_KEY apenas para desenvolvimento."
    )
    secret_key = getattr(settings, "SECRET_KEY", "") or "dev-only-secret-key"
    digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_credential(value: object) -> object:
    """Criptografa uma credencial textual, preservando valores vazios e ja criptografados."""
    if value is None or value == "":
        return value
    if not isinstance(value, str):
        value = str(value)
    if is_encrypted_credential(value):
        return value
    encrypted = _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTION_PREFIX}{encrypted}"


def decrypt_credential(value: object) -> object:
    """Descriptografa uma credencial, mantendo compatibilidade com valores antigos em texto puro."""
    if value is None or value == "":
        return value
    if not isinstance(value, str):
        return value
    if not is_encrypted_credential(value):
        return value
    token = value[len(ENCRYPTION_PREFIX):]
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ImproperlyConfigured(
            "Nao foi possivel descriptografar uma credencial sensivel. "
            "Verifique se CREDENTIAL_ENCRYPTION_KEY e a mesma usada quando o valor foi salvo."
        ) from exc
