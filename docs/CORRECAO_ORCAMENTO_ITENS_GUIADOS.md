# Correção - inclusão guiada de serviços, combos e peças no orçamento

## Problema corrigido

Na tela de orçamento, o modal de inclusão abria normalmente, mas ao clicar em **Adicionar serviço(s)** ou **Incluir combo(s)** nada era inserido. A causa era uma chamada no frontend para `defaultPartsForService(...)` sem a função existir no arquivo da tela.

Ao salvar o orçamento, o backend também retornava validação aninhada em `parts`/`services` e o frontend exibia `parts: [object Object]`, dificultando o diagnóstico.

## Ajustes realizados

- Criada a função `defaultPartsForService(service, serviceLocalId)` em `EstimateFormPage.jsx`.
- Serviços e combos agora adicionam as peças padrão vinculadas ao serviço imediatamente no orçamento.
- Payload das peças do orçamento foi limpo para não enviar campos visuais desnecessários.
- `EstimateServiceItemSerializer` e `EstimatePartItemSerializer` tratam `estimate` como campo somente leitura quando usados de forma aninhada.
- `EstimatePartItemSerializer` aceita e descarta `local_id`, preservando compatibilidade com o construtor visual do frontend.
- O formatador de erros da API agora expande listas/objetos aninhados e não exibe mais `[object Object]`.
- Adicionado teste automatizado cobrindo criação de orçamento com `local_id` de serviço e peça vinculada.

## Validação executada

Backend:

```bash
cd backend
DATABASE_URL=sqlite:////tmp/motormindv6_full_bugfix.sqlite DJANGO_SETTINGS_MODULE=config.test_settings python manage.py test
```

Resultado: `Ran 62 tests ... OK`.

Frontend:

```bash
cd frontend
npm ci --prefer-offline --no-audit --progress=false
npm run build
```

Resultado: build Vite concluído com sucesso.
