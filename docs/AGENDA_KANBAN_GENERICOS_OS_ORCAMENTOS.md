# Agenda e Kanban genéricos para OS e Orçamentos

## Objetivo

A Agenda e o Kanban deixam de ser telas exclusivas de Ordem de Serviço e passam a ser quadros operacionais para dois tipos de card:

- **OS**: card azul.
- **Orçamento**: card verde, seguindo o mesmo padrão visual da Bancada Técnica.

## Kanban operacional

Rota mantida:

```text
/work-orders/kanban
```

A tela agora carrega dados de:

```text
/api/workshop/work-orders/
/api/attendance/estimates/
```

Colunas operacionais:

1. **Aberta**
   - OS `open`.
   - Orçamento `open`.

2. **Diagnóstico / execução**
   - OS `in_progress`.
   - Orçamento `diagnosis`.

3. **Aguardando aprovação**
   - Orçamento `awaiting_approval`.

4. **Aguardando peças**
   - Somente OS `waiting_parts`.
   - Orçamento não pode ser movido para esta coluna.

5. **Concluída / finalizada**
   - OS `completed`.
   - Orçamentos finalizados: `approved`, `partially_approved`, `rejected`, `expired`, `converted`, `cancelled`.

## Movimento de cards

### OS

Usa o endpoint existente:

```text
POST /api/workshop/work-orders/{id}/change_status/
```

Respeita as transições disponíveis retornadas pelo backend em `available_status_transitions`.

### Orçamento

Fluxo esperado:

```text
aberto -> diagnóstico -> aguardando aprovação -> aprovação integral/parcial -> OS nova
```

Alternativas:

```text
rejeitado ou cancelado
```

Movimentos implementados no Kanban:

- `open` -> `diagnosis` via:

```text
POST /api/attendance/estimates/{id}/change-status/
```

- `diagnosis` ou `open` -> `awaiting_approval` via:

```text
POST /api/attendance/estimates/{id}/create-customer-approval/
```

Aprovação integral/parcial, rejeição e cancelamento continuam no fluxo próprio do orçamento/página pública.

## Agenda operacional

Rota mantida:

```text
/work-orders/agenda
```

A tela agora mostra:

- OS pela data `promised_at`.
- Orçamento pela data `valid_until`.

Cards usam as mesmas cores:

- Azul para OS.
- Verde para orçamento.

Filtros adicionados/padronizados:

- Tipo: OS e orçamentos, somente OS ou somente orçamentos.
- Etapa operacional: aberta, diagnóstico/execução, aguardando aprovação, aguardando peças e concluída/finalizada.
- Prioridade: aplica-se às OS; orçamentos entram como prioridade normal para manter compatibilidade visual.

## Navegação

O menu e as abas foram renomeados de `OS - Agenda` e `OS - Kanban` para:

- **Agenda**
- **Kanban**

para refletir que agora as telas são genéricas.
