# UX de itens: serviços, combos e peças padrão

## Objetivo

Esta entrega removeu o fluxo baseado em tabelas para composição de orçamento e OS e introduziu um fluxo mais visual, guiado e reutilizável. A intenção é reduzir erro operacional no balcão/oficina e manter o mesmo padrão visual em todo o sistema administrativo React.

## Ajustes globais de formulário

- Inputs numéricos não exibem mais as setas nativas de incremento/decremento do navegador.
- Campos monetários baseados em `MoneyInput` passam a usar o placeholder padrão `R$ 100,00`.
- Os novos blocos usam a classe `line-builder-*`, aplicável a orçamento, OS e futuras telas de composição.

Arquivos principais:

- `frontend/src/styles.css`
- `frontend/src/components/MoneyInput.jsx`

## Nova experiência de composição

As telas de orçamento e OS agora usam cards editáveis para serviços, combos e peças. Cada card evidencia:

- descrição;
- serviço/peça vinculada;
- quantidade;
- preço;
- desconto;
- total calculado;
- ações principais.

Isso substitui a edição densa em tabela por uma leitura em blocos, mais adequada para operação em notebook, tablet ou balcão.

Arquivos principais:

- `frontend/src/pages/EstimateFormPage.jsx`
- `frontend/src/pages/WorkOrderFormPage.jsx`
- `frontend/src/pages/WorkOrderDetailPage.jsx`

## Peças padrão por serviço

Foi criado o cadastro de peças padrão vinculadas a serviços. No cadastro de serviços, a aba **Peças padrão** permite definir quais peças devem ser adicionadas automaticamente quando o serviço for usado.

Campos disponíveis:

- peça;
- quantidade;
- preço sugerido;
- desconto;
- posição;
- consumo de estoque;
- observações;
- ativo/inativo.

Quando um serviço é adicionado em um orçamento ou em uma OS, as peças padrão ativas vinculadas a ele são adicionadas automaticamente como itens de peça, mantendo o vínculo com o item de serviço.

Arquivos principais:

- `backend/workshop/models/catalog.py`
- `backend/workshop/serializers/catalog.py`
- `backend/workshop/views/catalog.py`
- `backend/workshop/models/work_orders.py`
- `backend/attendance/models.py`
- `frontend/src/pages/WorkshopServicesPage.jsx`

## API

Endpoint administrativo:

```http
GET/POST /api/workshop/service-default-parts/
GET/PATCH/DELETE /api/workshop/service-default-parts/{id}/
```

Filtros úteis:

```http
/api/workshop/service-default-parts/?service={service_id}
/api/workshop/service-default-parts/?active=true
```

## Validações adicionadas

Foram adicionados testes para garantir que:

- uma OS criada com um serviço que possui peças padrão receba automaticamente essas peças;
- um orçamento criado com um serviço que possui peças padrão receba automaticamente essas peças.

Testes principais:

- `workshop.tests.test_work_order_api_flow.WorkOrderApiFlowTests.test_work_order_service_adds_default_parts_from_catalog`
- `attendance.tests.test_estimate_approval_flow.EstimateCustomerApprovalFlowTests.test_estimate_service_adds_default_parts_from_catalog`
