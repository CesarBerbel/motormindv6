# Bancada técnica com orçamentos

## Alteração aplicada

A Bancada Técnica agora mistura dois tipos de cards:

- **OS**: card azul, fluxo operacional normal da ordem de serviço.
- **Orçamento**: card verde, fluxo próprio de diagnóstico e aprovação.

## Fluxo do orçamento na bancada

O orçamento segue este ciclo:

1. **Aberto** (`open`) aparece na coluna **Fila do técnico**.
2. Ao clicar em **Iniciar diagnóstico** ou arrastar para **Diagnóstico / execução**, muda para **Diagnóstico** (`diagnosis`).
3. Ao clicar em **Aguardar aprovação** ou arrastar para **Aguardando aprovação**, o sistema gera o link público de aprovação e muda para **Aguardando aprovação** (`awaiting_approval`).
4. A aprovação pública pode ser integral ou parcial.
5. Ao aprovar integral ou parcialmente, o backend gera uma **OS nova** com os itens aprovados.
6. O orçamento também pode ser rejeitado ou cancelado nos fluxos já existentes.

## Regra importante

Orçamento **não entra em Aguardando peça**. A coluna **Aguardando peça** continua exclusiva para OS.

## Endpoints usados pelo frontend

- `GET /api/workshop/technical/dashboard/`
  - agora retorna cards com `kind: "os"` e `kind: "estimate"`.
- `POST /api/attendance/estimates/{id}/change-status/`
  - usado para mover orçamento aberto para diagnóstico.
- `POST /api/attendance/estimates/{id}/create-customer-approval/`
  - usado para colocar orçamento em aguardando aprovação e gerar link público.

## UX

A tela diferencia os cards por cor:

- OS: lateral azul.
- Orçamento: lateral verde.

Cada card mostra o tipo do item, status, cliente, veículo, total e ação principal.
