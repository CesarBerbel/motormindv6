# Layout administrativo em largura total

A interface administrativa foi ajustada para usar toda a largura disponivel do lado direito do menu lateral, mantendo o mesmo comportamento visual do Kanban de OS.

## Alteracoes

- O `Layout.jsx` agora aplica `content-full-width` em todas as paginas protegidas.
- O CSS global de `.main-content .container-fluid.py-4` deixou de limitar o conteudo a `1440px` centralizado.
- A regra especial do Kanban permanece apenas para o modo de altura/scroll interno da tela de Kanban.
- Bancada tecnica, cadastros, listas, dashboards e formularios passam a ocupar todo o painel disponivel.

## Arquivos alterados

- `frontend/src/components/Layout.jsx`
- `frontend/src/styles.css`
