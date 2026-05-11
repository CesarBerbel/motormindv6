# Implementação: JWT em cookies HttpOnly

## Objetivo

Migrar a autenticação JWT do frontend de `localStorage` para cookies `HttpOnly`, reduzindo o impacto de ataques XSS. Com esta alteração, o JavaScript do navegador não consegue ler diretamente o access token nem o refresh token.

## O que foi alterado

### Backend

Arquivos criados:

- `backend/config/authentication.py`

Arquivos alterados:

- `backend/config/auth_views.py`
- `backend/config/settings.py`
- `backend/config/urls.py`
- `backend/.env.example`
- `backend/.env.docker.example`
- `backend/accounts/tests/test_regression_smoke_api.py`

### Frontend

Arquivos alterados:

- `frontend/src/api/client.js`
- `frontend/src/auth/AuthContext.jsx`

## Funcionamento

1. O login continua usando `POST /api/token/`.
2. O backend valida usuário e senha.
3. O backend grava `access` e `refresh` em cookies `HttpOnly`.
4. O corpo da resposta não devolve mais os tokens ao frontend.
5. O Axios passa a enviar cookies com `withCredentials: true`.
6. O frontend carrega o usuário por `GET /api/me/`.
7. Se o access token expirar, o interceptor chama `POST /api/token/refresh/`.
8. O refresh token também é lido do cookie pelo backend.
9. O logout chama `POST /api/token/logout/` e o backend remove os cookies.

## Variáveis adicionadas

```env
CORS_ALLOW_CREDENTIALS=True
CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://localhost:8080
JWT_AUTH_COOKIE_ACCESS=oficina_access_token
JWT_AUTH_COOKIE_REFRESH=oficina_refresh_token
JWT_AUTH_COOKIE_PATH=/
JWT_AUTH_REFRESH_COOKIE_PATH=/api/token/refresh/
JWT_AUTH_COOKIE_DOMAIN=
JWT_AUTH_COOKIE_SAMESITE=Lax
JWT_AUTH_COOKIE_SECURE=False
```

## Produção

Em produção, use obrigatoriamente HTTPS e configure:

```env
JWT_AUTH_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
JWT_AUTH_COOKIE_SAMESITE=Lax
```

Se frontend e backend estiverem em subdomínios diferentes do mesmo domínio, avalie configurar:

```env
JWT_AUTH_COOKIE_DOMAIN=.seudominio.com.br
```

Se frontend e backend estiverem em domínios completamente diferentes, será necessário revisar `SameSite`, CORS, domínio do cookie e proteção CSRF antes de publicar.

## Comandos Windows para rodar

Assumindo que você está na raiz do projeto:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py check
python manage.py test --settings=config.test_settings --verbosity 2
python manage.py runserver
```

Em outro terminal:

```powershell
cd frontend
Remove-Item -Recurse -Force node_modules -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
npm ci
npm run build
npm run dev
```

## Como testar manualmente

1. Abra `http://localhost:5173/login`.
2. Faça login com um usuário válido.
3. Abra o DevTools do navegador.
4. Vá em `Application` ou `Aplicativo` > `Cookies`.
5. Verifique se existem os cookies:
   - `oficina_access_token`
   - `oficina_refresh_token`
6. Confirme que aparecem como `HttpOnly`.
7. Verifique que `localStorage` não contém mais:
   - `access_token`
   - `refresh_token`
8. Clique em `Sair`.
9. Confirme que os cookies foram removidos.

## Comandos Docker

Na raiz do projeto:

```powershell
Copy-Item backend\.env.docker.example backend\.env -Force
docker compose down
docker compose build --no-cache
docker compose up
```

Para acompanhar logs:

```powershell
docker compose logs -f backend
docker compose logs -f frontend
```

## Observação de segurança

Esta implementação reduz exposição de tokens contra XSS, mas não elimina a necessidade de:

- manter CSP forte;
- sanitizar HTML de templates e mensagens;
- manter CORS restrito;
- usar HTTPS em produção;
- revisar proteção CSRF se a arquitetura passar a usar domínios cruzados mais permissivos.
