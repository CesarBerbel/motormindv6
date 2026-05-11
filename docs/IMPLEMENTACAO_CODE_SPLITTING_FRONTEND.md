# Implementação - Code splitting no frontend React

## Objetivo

Reduzir o bundle inicial do frontend e melhorar o carregamento percebido da aplicação.

## O que foi alterado

- `frontend/src/App.jsx` passou a usar `React.lazy()` para carregar páginas sob demanda.
- As rotas foram envolvidas com `Suspense` e fallback visual de carregamento.
- `frontend/components/Layout.jsx` também passou a ser carregado sob demanda.
- `frontend/vite.config.js` passou a separar o editor rico em um chunk próprio chamado `vendor-editor` e as demais dependências em `vendor`.

## Resultado observado no build

Antes da implementação, o principal arquivo JavaScript gerado tinha aproximadamente `974.94 kB` minificado.

Depois da implementação, o arquivo inicial principal passou para aproximadamente `24.76 kB` minificado, com dependências e páginas carregadas em chunks separados.

O maior chunk JavaScript passou a ser `vendor`, com aproximadamente `366.82 kB`, abaixo do limite de alerta padrão de `500 kB` do Vite.

## Comandos de validação

```powershell
cd frontend
npm ci
npm run build
npm run quality
```

## Observação

A auditoria de produção ainda aponta vulnerabilidade baixa conhecida no pacote `quill`. Não foi aplicado `npm audit fix --force`, porque ele propõe alteração potencialmente quebrável.
