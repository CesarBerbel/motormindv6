# Implementação - Criptografia de credenciais sensíveis

## Objetivo

Proteger credenciais que precisam ser recuperadas em texto puro para integrações externas, mas que não devem ficar legíveis diretamente no banco de dados.

Nesta etapa foram protegidos:

- `ai_assistant.AIProviderConfiguration.api_key`
- `messaging.ChannelConfiguration.whatsapp_access_token`

Senhas de usuários não entram neste fluxo porque continuam usando o mecanismo nativo de hash do Django.

---

## Arquivos criados

```text
backend/accounts/encryption.py
backend/accounts/fields.py
backend/ai_assistant/tests/test_encrypted_credentials.py
docs/IMPLEMENTACAO_CRIPTOGRAFIA_CREDENCIAIS.md
```

---

## Arquivos alterados

```text
backend/requirements.txt
backend/config/settings.py
backend/config/test_settings.py
backend/.env.example
backend/.env.docker.example
backend/ai_assistant/models.py
backend/ai_assistant/admin.py
backend/ai_assistant/migrations/0004_alter_aiproviderconfiguration_api_key.py
backend/messaging/models.py
backend/messaging/admin.py
backend/messaging/migrations/0004_alter_channelconfiguration_whatsapp_access_token.py
```

---

## Como funciona

Foi criada uma camada reutilizável baseada em `cryptography.fernet`.

Valores salvos no banco recebem o prefixo:

```text
enc:v1:
```

Quando o Django lê o model, o campo descriptografa automaticamente o valor para que os serviços existentes continuem usando:

```python
config.api_key
config.whatsapp_access_token
```

sem precisar conhecer a criptografia.

A implementação mantém compatibilidade com valores antigos em texto puro. Valores antigos continuam legíveis e são criptografados quando a migração roda ou quando o registro é salvo novamente.

---

## Variável obrigatória

Adicionada variável:

```env
CREDENTIAL_ENCRYPTION_KEY=5kcy-1LzYgqPVpdZTJdB5pD62tvjs3dM8JTbRzYH7YU=
```

A chave acima é apenas exemplo de desenvolvimento. Em produção, gere uma chave própria.

### Gerar chave nova no Windows

Na raiz do projeto:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copie o valor gerado para:

```text
backend/.env
```

Exemplo:

```env
CREDENTIAL_ENCRYPTION_KEY=SUA_CHAVE_GERADA_AQUI
```

---

## Atenção crítica para produção

Não troque `CREDENTIAL_ENCRYPTION_KEY` depois que houver credenciais salvas, a menos que seja feito um processo controlado de rotação de chave.

Se a chave for perdida ou alterada indevidamente, o sistema não conseguirá descriptografar os tokens já gravados.

---

## Comandos Windows para aplicar

Assumindo que você está na raiz do projeto:

```powershell
git checkout -b security/criptografar-credenciais
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py check
python manage.py test --settings=config.test_settings --verbosity 2
python -m compileall -q .
```

Se ainda não existir ambiente virtual:

```powershell
cd backend
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

---

## Como validar manualmente

1. Acesse o admin do Django.
2. Configure uma chave de IA em `Configurações de IA`.
3. Configure um token WhatsApp em `Channel configuration`.
4. Salve.
5. Abra o banco diretamente e confirme que os campos não aparecem em texto puro.

Exemplo PostgreSQL local:

```powershell
cd backend
python manage.py dbshell
```

Dentro do banco PostgreSQL:

```sql
SELECT provider, api_key FROM ai_assistant_aiproviderconfiguration;
SELECT whatsapp_access_token FROM messaging_channelconfiguration;
```

Os valores devem começar com:

```text
enc:v1:
```

---

## Testes adicionados

Foram adicionados testes para garantir que:

- a chave de IA é criptografada no banco;
- o token WhatsApp é criptografado no banco;
- os models continuam retornando o valor descriptografado para o código Python;
- valores antigos em texto puro continuam legíveis;
- criptografar duas vezes um valor já criptografado não duplica a criptografia.

---

## Fluxo Git recomendado

```powershell
git status
git add .
git commit -m "security: criptografar credenciais sensiveis persistidas"
```

Sugestão de Pull Request:

```text
Título:
security: criptografar credenciais sensíveis persistidas

Descrição:
- adiciona camada reutilizável de criptografia Fernet
- adiciona campos criptografados para credenciais sensíveis
- criptografa API keys de IA em repouso
- criptografa token WhatsApp Meta em repouso
- adiciona variável CREDENTIAL_ENCRYPTION_KEY
- protege exibição de credenciais no admin Django
- adiciona testes automatizados de criptografia em repouso
```
