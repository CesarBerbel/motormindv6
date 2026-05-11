# Correção: PostgreSQL `FOR UPDATE` ao enviar OS/orçamento para aprovação

## Problema

Ao enviar uma OS/orçamento para aprovação, o backend podia retornar:

```text
django.db.utils.NotSupportedError: FOR UPDATE cannot be applied to the nullable side of an outer join
```

Isso ocorre no PostgreSQL quando uma consulta usa `select_for_update()` junto com `select_related()` em relacionamentos opcionais, como veículo, técnico, cliente opcional, fornecedor ou outros vínculos que podem ser nulos. O Django gera um `LEFT OUTER JOIN` e o PostgreSQL não permite aplicar `FOR UPDATE` no lado nullable desse join.

## Correção aplicada

As consultas transacionais que usam `select_for_update()` foram ajustadas para:

```python
select_for_update(of=("self",))
```

Com isso, o banco bloqueia somente a linha da tabela principal da operação, evitando tentar bloquear linhas opcionais vindas de `LEFT OUTER JOIN`.

## Áreas protegidas

A correção foi aplicada de forma ampla nos serviços transacionais dos módulos:

- `accounts/numbering.py`
- `attendance/services.py`
- `finance/services.py`
- `purchasing/services.py`
- `workshop/services/status.py`
- `workshop/services/inventory.py`
- `workshop/services/technical_services.py`

## Fluxo afetado diretamente

- Enviar OS para aprovação.
- Gerar link de aprovação.
- Movimentar orçamento para aguardando aprovação.
- Converter orçamento aprovado em OS.
- Criar/atualizar financeiro ligado a OS, vendas e compras.
- Estornos e pagamentos.
- Movimentações de estoque e compras automáticas.

## Validação

Foi executada validação de sintaxe Python:

```bash
python -m compileall -q backend
```

No ambiente local/Docker, valide também com:

```bash
docker compose exec backend python manage.py test
```

