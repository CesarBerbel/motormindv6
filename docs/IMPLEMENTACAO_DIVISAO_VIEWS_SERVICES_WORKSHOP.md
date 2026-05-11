# Implementação - Divisão de `workshop.views` e `workshop.services`

## Objetivo

Reduzir o tamanho e a responsabilidade dos arquivos `backend/workshop/views.py` e `backend/workshop/services.py`, preservando compatibilidade com imports existentes.

## O que foi feito

- `backend/workshop/services.py` foi transformado no pacote `backend/workshop/services/`.
- `backend/workshop/views.py` foi transformado no pacote `backend/workshop/views/`.
- `__init__.py` foi criado nos dois pacotes para manter imports antigos funcionando.
- Nenhum model foi alterado.
- Nenhuma migration foi criada.
- Nenhuma URL pública foi alterada.

## Nova organização de services

```text
backend/workshop/services/
├── __init__.py
├── approvals.py
├── context.py
├── events.py
├── inventory.py
├── notifications.py
├── state_targets.py
├── status.py
└── technical_services.py
```

## Nova organização de views

```text
backend/workshop/views/
├── __init__.py
├── catalog.py
├── common.py
├── dashboards.py
├── profile.py
├── public.py
├── vehicles.py
└── work_orders.py
```

## Comandos de validação

```powershell
cd backend
python manage.py makemigrations --check --dry-run
python manage.py check
python -m compileall -q .
python manage.py test --settings=config.test_settings --verbosity 2
```
