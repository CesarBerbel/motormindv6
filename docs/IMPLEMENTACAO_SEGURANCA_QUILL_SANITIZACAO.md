# Implementação - Segurança do Quill e sanitização de HTML

## Objetivo

Tratar o risco de XSS associado ao editor rico sem executar `npm audit fix --force`, evitando uma alteração automática e potencialmente quebrável.

## O que foi alterado

### Frontend

- Removida a dependência direta `quill` do `frontend/package.json`.
- Mantido `react-quill-new` como integração do editor.
- Adicionado `overrides.quill = "2.0.2"` para manter a versão transitiva usada pelo `react-quill-new` em uma versão que não aparece mais na auditoria de dependências de produção.
- Alterado o import do CSS do editor para `react-quill-new/dist/quill.snow.css`.
- Criado `frontend/src/utils/sanitizeHtml.js` para centralizar sanitização de HTML rico.
- Atualizadas as telas `TemplateFormPage` e `HistoryPage` para usar a função centralizada `sanitizeRichHtml`.
- Adicionados testes frontend de segurança com Vitest e jsdom.
- Atualizado o script `quality` para rodar build, teste de sanitização e auditoria de dependências de produção.

### Backend

- Adicionada dependência `bleach` para sanitização server-side.
- Criado `backend/messaging/sanitizers.py` com whitelist de tags, atributos, protocolos, classes Quill e propriedades CSS permitidas.
- Atualizado `MessageTemplate.clean()` e `MessageTemplate.save()` para sanitizar HTML antes de persistir.
- Atualizado `MessageTemplateSerializer.validate()` para sanitizar payloads recebidos pela API.
- Atualizado `render_message()` para sanitizar HTML renderizado antes de gravar logs ou enviar email.
- Criado comando `sanitize_message_templates` para higienizar templates já existentes no banco.
- Adicionados testes backend contra payloads com script, iframe, handlers de evento e links `javascript:`.

## Comandos de validação

### Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py makemigrations --check --dry-run
python manage.py check
python -m compileall -q .
python manage.py test --settings=config.test_settings --verbosity 2
```

### Frontend

```powershell
cd frontend
npm ci
npm run test:security
npm run build
npm run quality
```

## Sanitizar templates existentes

Esta implementação não cria migration de banco. Para higienizar dados já existentes, rode manualmente após aplicar a versão atualizada:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py sanitize_message_templates --dry-run
python manage.py sanitize_message_templates
```

## Observação sobre auditoria npm

O comando de auditoria de produção passou com zero vulnerabilidades:

```powershell
npm audit --omit=dev --audit-level=low
```

A auditoria completa, incluindo dependências de desenvolvimento, pode apontar avisos relacionados ao Vite/esbuild do servidor de desenvolvimento. Esses avisos não entram no bundle de produção, mas devem ser tratados em uma próxima etapa de atualização controlada do toolchain frontend.
