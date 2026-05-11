# Padronização de campos e buscas

## Objetivo

Padronizar a experiência de formulários e listas administrativas para reduzir ambiguidade visual e evitar campos com valores aparentando preenchimento automático quando deveriam estar vazios.

## Campos de data

Foi criado o componente reutilizável `DateInput` em `frontend/src/components/DateInput.jsx`.

Padrão adotado:

- todo campo de data passa pelo mesmo componente;
- quando vazio, exibe apenas a data atual como placeholder visual no padrão brasileiro;
- o valor real continua vazio até o usuário escolher uma data;
- foi removida a duplicidade visual que ocorria no cadastro de clientes;
- campos opcionais de nascimento/fundação de clientes, fornecedores e usuários não são mais preenchidos automaticamente com a data atual.

## Campos numéricos não monetários

Foi criado o componente reutilizável `IntegerInput` em `frontend/src/components/IntegerInput.jsx`.

Padrão adotado:

- campos numéricos não monetários são exibidos como inteiros;
- valores vindos como `1.00` passam a aparecer como `1`;
- quando o campo está vazio, o placeholder padrão é `0`;
- as setas nativas de incremento/decremento continuam ocultas via CSS global;
- quantidades que já possuem valor padrão continuam aparecendo preenchidas, mas sem casas decimais.

## Campos monetários

O componente `MoneyInput` foi ajustado para usar o placeholder global:

```text
R$ 0,00
```

Campos monetários vazios continuam vazios no valor real, exibindo somente o placeholder.

## Buscas em listas

O componente `SearchAutocompleteInput` deixou de renderizar botão interno de limpeza por padrão. As páginas de lista passam a ter um único botão geral:

```text
Limpar pesquisa
```

Esse botão limpa busca textual e filtros associados da tela quando aplicável.

## Validação

Validação executada:

```bash
cd frontend
npm ci --prefer-offline --no-audit --progress=false
npm run build
```

Resultado: build concluído com sucesso.

Também foi executado:

```bash
python -m compileall -q backend
```

Resultado: sem erros de sintaxe no backend.
