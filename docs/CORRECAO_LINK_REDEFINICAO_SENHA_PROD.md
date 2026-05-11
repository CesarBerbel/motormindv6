# Correção: link de definição/redefinição de senha em produção

## Problema

O link enviado por e-mail para definição de senha podia sair fixo como `http://localhost:5173/...` quando `FRONTEND_BASE_URL` não estava configurada corretamente no ambiente de produção.

Isso fazia o token ser válido, mas inutilizável para o usuário final, porque o navegador era direcionado para `localhost` em vez do domínio público do frontend.

## Correção implementada

- `accounts.passwords.build_password_setup_url()` agora aceita o `request` e usa um resolvedor centralizado em `accounts.url_utils.get_frontend_base_url()`.
- O resolvedor usa `FRONTEND_BASE_URL` quando ela contém uma URL pública não-local.
- Se `FRONTEND_BASE_URL` estiver ausente ou ainda apontando para localhost em produção, o sistema tenta usar o `Origin`/`Referer` da chamada feita pelo frontend administrativo, desde que esteja em `CORS_ALLOWED_ORIGINS` ou `CSRF_TRUSTED_ORIGINS`.
- O fallback local continua existindo apenas para desenvolvimento.
- Foram adicionados testes de regressão para garantir que links de senha não apontem para localhost em produção quando a requisição veio do domínio público permitido.

## Configuração obrigatória em produção

Defina no `.env` usado pelo backend:

```env
DEBUG=False
FRONTEND_BASE_URL=https://app.seudominio.com
CORS_ALLOWED_ORIGINS=https://app.seudominio.com
CSRF_TRUSTED_ORIGINS=https://app.seudominio.com
ALLOWED_HOSTS=api.seudominio.com,app.seudominio.com
JWT_AUTH_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
```

Se frontend e API usam subdomínios diferentes e o cookie JWT precisa ser compartilhado entre eles, configure também:

```env
JWT_AUTH_COOKIE_DOMAIN=.seudominio.com
JWT_AUTH_COOKIE_SAMESITE=Lax
```

## Validação manual

1. Suba o backend com o `.env` de produção/staging.
2. Acesse a área administrativa pelo domínio real do frontend.
3. Abra **Usuários**.
4. Acione o envio do link de definição de senha para um usuário com e-mail.
5. Confira no e-mail/log SMTP que o link começa com `https://app.seudominio.com/definir-senha/...`.
6. Abra o link em janela anônima e defina a senha.

## Teste automatizado relacionado

```bash
cd backend
python manage.py test accounts.tests.test_password_setup_links --settings=config.test_settings
```
