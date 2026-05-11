
# Implementação - Divisão dos arquivos grandes do backend workshop

## Objetivo

Reduzir o acoplamento e melhorar a manutenção do app `workshop`, que concentrava modelos e serializers em arquivos monolíticos com mais de mil linhas cada.

## Arquivos monolíticos substituídos

- `backend/workshop/models.py`
- `backend/workshop/serializers.py`

Esses módulos foram transformados em pacotes Python, mantendo compatibilidade com os imports existentes.

## Nova organização de models

```text
backend/workshop/models/
├── __init__.py
├── common.py
├── profile.py
├── catalog.py
├── vehicles.py
└── work_orders.py
```

### Responsabilidades

- `common.py`: constantes, funções utilitárias, upload paths, normalizações e imports comuns.
- `profile.py`: cadastro da oficina.
- `catalog.py`: categorias, marcas, serviços, pacotes e peças.
- `vehicles.py`: veículos.
- `work_orders.py`: ordem de serviço, fotos, serviços da OS, peças da OS, pagamentos, estoque, aprovações, assinatura e mensagens.

## Nova organização de serializers

```text
backend/workshop/serializers/
├── __init__.py
├── common.py
├── profile.py
├── catalog.py
├── vehicles.py
└── work_orders.py
```

### Responsabilidades

- `common.py`: imports compartilhados e dependências externas.
- `profile.py`: serializers do cadastro público/institucional da oficina.
- `catalog.py`: serializers de categorias, marcas, serviços, pacotes, peças e movimentação de estoque.
- `vehicles.py`: serializer de veículos.
- `work_orders.py`: serializers de OS, itens, pagamentos, fotos, eventos, aprovações e mensagens.

## Compatibilidade preservada

Imports antigos continuam válidos:

```python
from workshop.models import WorkOrder, Part
from workshop.serializers import WorkOrderSerializer, PartSerializer
```

Isso evita alteração massiva em views, services, admin, testes e outros apps.

## Cuidados aplicados

- As funções usadas por migrations antigas, como `workshop.models.workshop_logo_upload_path`, continuam exportadas pela fachada `workshop.models`.
- O comando `makemigrations --check --dry-run` deve continuar sem detectar alterações de schema.
- Nenhuma tabela ou campo de banco foi alterado.

## Comandos de validação

```powershell
cd backend
python manage.py makemigrations --check --dry-run
python manage.py check
python -m compileall -q .
python manage.py test --settings=config.test_settings --verbosity 2
```
