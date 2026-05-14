# Correção: edição de serviço

## Problema

Ao clicar em **Editar** na tela `Catálogo de serviços`, o frontend quebrava dentro de `WorkshopServicesPage.jsx` e o modal de edição não ficava utilizável.

## Causa

A aba **Peças padrão** renderizava o componente `<Alert />`, porém `Alert` não estava importado de `../ui/TailwindPrimitives.jsx` em `frontend/src/pages/WorkshopServicesPage.jsx`.

Mesmo que a aba inicial fosse outra, o componente da página podia ser avaliado durante a renderização do modal, disparando erro de runtime.

## Correção aplicada

O import foi ajustado para incluir `Alert`:

```jsx
import { Alert, Button, Card, Col, Form, Modal, Row, Table } from "../ui/TailwindPrimitives.jsx";
```

## Validação

Frontend validado com:

```bash
cd frontend
npm ci --prefer-offline --no-audit --progress=false
npm run build
```

Resultado: build concluído com sucesso.
