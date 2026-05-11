# Implementação - Auditoria financeira e rastreabilidade

## Objetivo

Fortalecer a rastreabilidade de ações críticas de OS e financeiro, principalmente:

- pagamentos e recebimentos;
- estornos;
- descontos;
- mudanças de status financeiro;
- alterações críticas de ordens de serviço;
- lançamentos no ledger financeiro.

## Principais mudanças

### 1. Pagamentos passam a ser estornados, não apagados

Foram adicionados campos de estorno aos pagamentos de OS, contas a receber e contas a pagar:

- `reversed_at`;
- `reversed_by`;
- `reversal_reason`;
- propriedade `is_reversed`.

A exclusão direta de pagamento de OS pela API foi bloqueada. A ação correta agora é chamar o endpoint `reverse` com justificativa.

### 2. Totais ignoram pagamentos estornados

Os cálculos de `paid_total`, `paid_amount`, `balance_due` e `balance_amount` passam a considerar apenas pagamentos ativos:

```python
reversed_at__isnull=True
```

### 3. Ledger registra lançamento de estorno

Ao estornar um pagamento, é criado um lançamento `FinancialLedgerEntry.EntryType.REVERSAL`, vinculado ao lançamento financeiro original quando ele existir.

### 4. AuditLog recebeu ações financeiras explícitas

Foram adicionadas ações como:

- `financial_create`;
- `financial_update`;
- `financial_payment`;
- `financial_reversal`;
- `financial_discount`;
- `financial_status`;
- `critical_update`.

### 5. Snapshots before/after

Foi criada uma camada reutilizável em `accounts/audit.py` para gerar snapshots JSON seguros e diffs estruturados.

### 6. Novos endpoints de estorno

Conta a pagar:

```http
POST /api/finance/accounts-payable/{account_id}/payments/{payment_id}/reverse/
```

Conta a receber manual:

```http
POST /api/finance/accounts-receivable/{account_id}/payments/{payment_id}/reverse/
```

Pagamento direto de OS:

```http
POST /api/workshop/work-order-payments/{payment_id}/reverse/
```

Payload:

```json
{
  "reason": "Justificativa obrigatória com pelo menos 5 caracteres."
}
```

## Migrations criadas

```text
backend/accounts/migrations/0006_alter_auditlog_action.py
backend/finance/migrations/0007_accountpayablepayment_reversal_reason_and_more.py
backend/workshop/migrations/0022_workorderpayment_reversal_reason_and_more.py
```

## Comandos Windows

Assumindo que você está na raiz do projeto:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py check
python manage.py test --settings=config.test_settings --verbosity 2
python -m compileall -q .
python manage.py runserver
```

Frontend:

```powershell
cd frontend
Remove-Item -Recurse -Force node_modules -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
npm ci
npm run quality
npm run dev
```

Docker:

```powershell
Copy-Item backend\.env.docker.example backend\.env -Force
docker compose down
docker compose build --no-cache
docker compose up
```

## Testes adicionados

Arquivo:

```text
backend/finance/tests/test_financial_audit_trail.py
```

Cobertura adicionada:

- estorno de conta a pagar preserva pagamento original;
- estorno cria lançamento reverso no ledger;
- estorno cria `AuditLog` com justificativa;
- pagamento de OS não pode mais ser excluído diretamente;
- estorno de pagamento de OS atualiza totais;
- alteração de desconto manual de OS gera auditoria financeira.

## Observação sobre banco de dados

Não apague o banco de dados. Esta implementação exige apenas aplicar migrations no PostgreSQL:

```powershell
cd backend
python manage.py migrate
```

Os pagamentos antigos continuarão ativos porque os novos campos de estorno são nulos por padrão.
