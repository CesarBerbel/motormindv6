# Design system administrativo MotorMindV6

Este projeto inclui uma camada visual reutilizável e configurável pela própria área administrativa React, sem depender do Django Admin.

## Onde configurar

Acesse:

```text
Configurações administrativas > Visual e formulários
```

As preferências são salvas no cadastro singleton da oficina (`WorkshopProfile`) e retornadas por:

```text
GET/PUT /api/workshop/company-profile/
```

## Tokens configuráveis

- `ui_theme_mode`: claro, escuro ou automático.
- `ui_primary_color`: cor primária de botões, foco de campos e destaques.
- `ui_accent_color`: cor de realce e marca de obrigatoriedade.
- `ui_sidebar_color`: cor do menu lateral.
- `ui_form_density`: compacto, confortável ou espaçoso.
- `ui_table_density`: compacto ou confortável.
- `ui_card_radius`: suave, arredondado ou muito arredondado.
- `ui_button_style`: preenchido, suave ou contorno.
- `ui_form_layout`: agrupado, plano ou abas/etapas.
- `ui_show_required_hint`: controla a marca visual de obrigatório.
- `ui_enable_motion`: liga/desliga microinterações.

## Componentes reutilizáveis

A base do design system está em `frontend/src/components`:

- `AdminForm.jsx`: `AdminFormShell`, `AdminFormSection`, `AdminFormGrid`, `AdminField`, `DesignPreviewCard`.
- `PageHeader.jsx`: cabeçalho padronizado de páginas.
- `DataTable.jsx`: tabela com empty state e densidade global.
- `FormSection.jsx`, `FormGrid.jsx`, `FormTabs.jsx`: blocos de formulário existentes.
- `ConfirmDialog.jsx`: confirmação global.
- `EmptyState.jsx`, `ErrorAlert.jsx`, `SystemToast.jsx`: feedback e estados vazios.
- `StatusBadge.jsx`: status padronizados.
- `MoneyInput.jsx`, `SearchableSelect.jsx`, `AutocompleteInput.jsx`, `RichTextEditor.jsx`: campos compostos.

## Como aplicar em novas telas

Exemplo recomendado:

```jsx
import { Button, Form } from "../ui/TailwindPrimitives.jsx";
import { AdminField, AdminFormGrid, AdminFormSection } from "../components/AdminForm";

export default function MinhaTela() {
  return (
    <AdminFormSection title="Dados principais" description="Campos essenciais do cadastro.">
      <AdminFormGrid>
        <AdminField label="Nome" required>
          <Form.Control required />
        </AdminField>
        <AdminField label="Status">
          <Form.Select>
            <option>Ativo</option>
            <option>Inativo</option>
          </Form.Select>
        </AdminField>
      </AdminFormGrid>
      <Button className="mt-3" type="submit">Salvar</Button>
    </AdminFormSection>
  );
}
```

## Como o tema é aplicado

`frontend/src/theme.js` normaliza os dados vindos do backend e escreve variáveis CSS no `document.documentElement`. O CSS global usa essas variáveis para Tailwind, cards, botões, campos, tabelas, modais, menu lateral e componentes customizados.

O carregamento acontece no `AuthContext` após `GET /api/workshop/company-profile/`. Na página de configurações, a prévia é aplicada enquanto o usuário altera os campos, antes de salvar.

## Critério de padrão

Novas páginas administrativas devem usar os componentes acima em vez de criar estilos locais de formulário/tabela. Quando houver necessidade de estilo específico, prefira adicionar um token ou classe global reutilizável em `styles.css`.
