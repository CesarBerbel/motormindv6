import React from "react";
import { Card, Col, Form, Row } from "../ui/TailwindPrimitives.jsx";

export function AdminFormShell({ title, description, children, actions, className = "", ...props }) {
  return (
    <Form className={`admin-form-shell ${className}`.trim()} {...props}>
      {title || description ? (
        <div className="admin-form-heading mb-3">
          {title ? <h2>{title}</h2> : null}
          {description ? <p>{description}</p> : null}
        </div>
      ) : null}
      <div className="admin-form-sections">{children}</div>
      {actions ? <div className="admin-form-actions">{actions}</div> : null}
    </Form>
  );
}

export function AdminFormSection({ title, description, children, aside, className = "" }) {
  return (
    <Card className={`admin-form-section ${className}`.trim()}>
      <Card.Body>
        <div className="admin-form-section-grid">
          <div className="admin-form-section-intro">
            {title ? <h3>{title}</h3> : null}
            {description ? <p>{description}</p> : null}
            {aside ? <div className="admin-form-section-aside">{aside}</div> : null}
          </div>
          <div className="admin-form-section-content">{children}</div>
        </div>
      </Card.Body>
    </Card>
  );
}

export function AdminFormGrid({ children, columns = 2, className = "" }) {
  return <Row className={`admin-form-grid admin-form-grid-${columns} ${className}`.trim()}>{children}</Row>;
}

export function AdminField({ label, help, required = false, children, md = 6, className = "" }) {
  return (
    <Col md={md} className={`admin-field ${className}`.trim()}>
      {label ? <Form.Label>{label}{required ? <span className="required-mark" aria-label="obrigatório">*</span> : null}</Form.Label> : null}
      {children}
      {help ? <Form.Text className="text-muted">{help}</Form.Text> : null}
    </Col>
  );
}

export function DesignPreviewCard() {
  return (
    <Card className="admin-design-preview">
      <Card.Body>
        <div className="preview-browser-bar" aria-hidden="true"><span /><span /><span /></div>
        <div className="preview-layout">
          <aside><strong>MotorMindV6</strong><span>Oficina</span><span>Financeiro</span><span>Mensageria</span></aside>
          <main>
            <div className="preview-kpi-row"><div><small>OS abertas</small><strong>12</strong></div><div><small>Receber hoje</small><strong>R$ 4.280</strong></div></div>
            <section><h4>Novo atendimento</h4><div className="preview-input">Cliente obrigatório</div><div className="preview-input short">Veículo</div><button type="button">Salvar padrão</button></section>
          </main>
        </div>
        <p className="small text-muted mb-0 mt-3">Prévia do padrão aplicado globalmente a formulários, tabelas, cards e navegação.</p>
      </Card.Body>
    </Card>
  );
}
