# Correção do placeholder de data no cadastro de clientes

## Problema

No cadastro de clientes, o campo **Data de nascimento** exibia dois placeholders ao mesmo tempo:

- o placeholder nativo do navegador para `input[type=date]`, como `dd/mm/aaaa`;
- o placeholder customizado com a data atual.

Isso deixava a UX confusa, principalmente no Firefox.

## Solução

O componente global `DateInput` foi ajustado para usar:

- `type="text"` enquanto o campo estiver vazio e sem foco, exibindo apenas o placeholder customizado com a data atual;
- `type="date"` quando o usuário focar o campo ou quando já existir valor preenchido.

Com isso, o campo continua sem preencher automaticamente datas opcionais, mas não mostra placeholder duplicado.

## Arquivos alterados

- `frontend/src/components/DateInput.jsx`
- `frontend/src/styles.css`
