# Regras de Orçamento e Ordem de Serviço

Este documento registra a implementação das regras operacionais aplicadas ao fluxo de orçamento e OS.

## Orçamento

Estados oficiais:

- `draft` — RASCUNHO
- `sent` — ENVIADO
- `approved` — APROVADO
- `rejected` — RECUSADO
- `expired` — EXPIRADO
- `cancelled` — CANCELADO
- `converted` — CONVERTIDO_EM_OS

Transições validadas no backend:

- RASCUNHO → ENVIADO
- RASCUNHO → CANCELADO
- ENVIADO → APROVADO
- ENVIADO → RECUSADO
- ENVIADO → EXPIRADO
- ENVIADO → CANCELADO
- APROVADO → CANCELADO
- APROVADO → CONVERTIDO_EM_OS somente pelo serviço transacional de conversão em OS

Estados `rejected`, `expired`, `cancelled` e `converted` são terminais para alterações operacionais.

A conversão em OS acontece em transação única e exige orçamento aprovado, cliente e veículo. O orçamento convertido recebe vínculo com a OS gerada e não pode gerar nova OS.

## Ordem de Serviço

Estados operacionais oficiais:

- `open` — ABERTA
- `in_progress` — EM_EXECUCAO
- `waiting_parts` — AGUARDANDO_PECAS
- `awaiting_approval` — AGUARDANDO_APROVACAO
- `paused` — PAUSADA
- `completed` — CONCLUIDA
- `delivered` — ENTREGUE
- `cancelled` — CANCELADA

Estados financeiros oficiais:

- `pending` — PENDENTE
- `partial` — PARCIAL
- `paid` — PAGO
- `cancelled` — CANCELADO

Transições operacionais são centralizadas em `workshop/state_machine.py`. O backend bloqueia transições inválidas, estados terminais, cancelamento sem motivo, pausa sem motivo, entrega com saldo pendente quando a configuração da oficina não permite, e reabertura de OS concluída sem permissão.

O status financeiro é independente do status operacional e é recalculado a partir de pagamentos e total da OS.
