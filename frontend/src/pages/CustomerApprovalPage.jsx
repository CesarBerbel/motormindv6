import React, { useEffect, useMemo, useState } from "react";
import { Alert, Badge, Button, Card, Col, Container, Form, Row, Spinner, Table } from "react-bootstrap";
import { useParams } from "react-router-dom";
import api, { apiError, apiUrl } from "../api/client";
import SystemToast from "../components/SystemToast";
import { money } from "../workshopOptions";
import { applyBrowserBranding } from "../utils/branding";

function dateTime(value) {
  return value ? new Date(value).toLocaleString("pt-BR") : "-";
}

function statusVariant(status) {
  if (["approved", "partially_approved"].includes(status)) return "success";
  if (status === "rejected") return "danger";
  if (status === "expired") return "secondary";
  return "warning";
}

function normalizeIds(values = []) {
  return values.map((value) => Number(value)).filter((value) => Number.isFinite(value));
}

export default function CustomerApprovalPage() {
  const { token } = useParams();
  const isEstimateApproval = window.location.pathname.includes("/aprovar-orcamento/");
  const endpointBase = isEstimateApproval ? "/attendance/estimate-approvals" : "/workshop/customer-approvals";
  const [approval, setApproval] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [partialWarning, setPartialWarning] = useState(false);
  const [selectedServices, setSelectedServices] = useState([]);
  const [selectedParts, setSelectedParts] = useState([]);
  const [form, setForm] = useState({ name: "", document: "", notes: "" });

  const pdfUrl = useMemo(() => apiUrl(`${endpointBase}/${token}/pdf/`), [endpointBase, token]);

  async function load() {
    try {
      setLoading(true);
      const { data } = await api.get(`${endpointBase}/${token}/`);
      setApproval(data);
      applyBrowserBranding(data.workshop || {});
      setForm((current) => ({ ...current, name: current.name || data.customer_name_snapshot || "" }));
      if (isEstimateApproval && data.can_decide) {
        setSelectedServices((data.services || []).map((item) => Number(item.id)));
        setSelectedParts((data.parts || []).map((item) => Number(item.id)));
      } else if (isEstimateApproval) {
        setSelectedServices(normalizeIds(data.decision_selected_services || []));
        setSelectedParts(normalizeIds(data.decision_selected_parts || []));
      }
    } catch (err) {
      setError(apiError(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [token, endpointBase]);

  const document = approval?.estimate || approval?.work_order || {};
  const totals = approval?.totals || {};
  const services = approval?.services || [];
  const parts = approval?.parts || [];
  const allServiceIds = services.map((item) => Number(item.id));
  const allPartIds = parts.map((item) => Number(item.id));

  function isPartialSelection() {
    if (!isEstimateApproval) return false;
    if (!services.length) return false;
    return selectedServices.length !== allServiceIds.length || selectedParts.length !== allPartIds.length;
  }

  function validateCredentials() {
    const digits = String(form.document || "").replace(/\D/g, "");
    if (![11, 14].includes(digits.length)) {
      setError("Informe um CPF com 11 dígitos ou CNPJ com 14 dígitos.");
      return false;
    }
    if (!String(form.notes || "").trim()) {
      setError("Informe uma observação antes de aprovar ou recusar.");
      return false;
    }
    return true;
  }

  function toggleService(serviceId, checked) {
    const normalizedServiceId = Number(serviceId);
    const relatedPartIds = parts.filter((part) => Number(part.service_item) === normalizedServiceId).map((part) => Number(part.id));
    setSelectedServices((current) => checked ? Array.from(new Set([...current, normalizedServiceId])) : current.filter((id) => id !== normalizedServiceId));
    setSelectedParts((current) => checked ? Array.from(new Set([...current, ...relatedPartIds])) : current.filter((id) => !relatedPartIds.includes(id)));
    setPartialWarning(false);
  }

  function togglePart(partId, checked) {
    const normalizedPartId = Number(partId);
    setSelectedParts((current) => checked ? Array.from(new Set([...current, normalizedPartId])) : current.filter((id) => id !== normalizedPartId));
    setPartialWarning(false);
  }

  async function sendDecision(decision, { forcePartialConfirm = false } = {}) {
    if (!validateCredentials()) return;
    if (isEstimateApproval && decision === "approved") {
      if (!selectedServices.length) {
        setError("Selecione pelo menos um serviço para aprovação.");
        return;
      }
      if (isPartialSelection() && !forcePartialConfirm) {
        setError("");
        setPartialWarning(true);
        return;
      }
    }
    try {
      setSubmitting(true);
      setError("");
      setPartialWarning(false);
      const payload = isEstimateApproval
        ? { ...form, decision, selected_service_ids: selectedServices, selected_part_ids: selectedParts, confirm_partial: forcePartialConfirm || !isPartialSelection() }
        : { ...form, decision };
      const { data } = await api.post(`${endpointBase}/${token}/`, payload);
      setApproval(data);
      applyBrowserBranding(data.workshop || {});
      setNotice(decision === "approved" ? "Documento aprovado com sucesso." : "Documento recusado com sucesso.");
    } catch (err) {
      setError(apiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <Container className="py-5 text-center"><Spinner animation="border" /><div className="mt-3 text-muted">Carregando documento...</div></Container>;
  }

  if (!approval) {
    return <Container className="py-5"><Alert variant="danger">{error || "Não foi possível carregar este link."}</Alert></Container>;
  }

  return (
    <div className="public-approval-page">
      <Container className="py-4 py-lg-5">
        <SystemToast message={notice} variant="success" delay={3000} onClose={() => setNotice("")} />
        <Card className="border-0 shadow-sm mb-4">
          <Card.Body className="p-4">
            <div className="d-flex flex-wrap justify-content-between align-items-start gap-3">
              <div>
                <div className="text-muted small">{approval.workshop?.legal_name}</div>
                <h1 className="h3 mb-1">{approval.workshop?.display_name}</h1>
                <div className="text-muted small">{approval.workshop?.document_number || "Documento não informado"}</div>
                <div className="text-muted small">{approval.workshop?.phone || ""} {approval.workshop?.email ? `· ${approval.workshop.email}` : ""}</div>
              </div>
              <div className="text-lg-end">
                <Badge bg={statusVariant(approval.effective_status)} className="mb-2">{approval.status_label}</Badge>
                <h2 className="h5 mb-1">{approval.document_type_label}</h2>
                <div className="text-muted small">{isEstimateApproval ? "Orçamento" : "OS"} {document.number}</div>
              </div>
            </div>
          </Card.Body>
        </Card>

        {error ? <Alert variant="danger" onClose={() => setError("")} dismissible>{error}</Alert> : null}
        {partialWarning ? (
          <Alert variant="warning">
            <div className="fw-semibold">Você está aprovando parcialmente este orçamento.</div>
            <div className="small mb-3">Alguns serviços ou peças foram desmarcados. Confirme somente se essa for realmente a decisão do cliente, pois a OS será gerada apenas com os itens selecionados.</div>
            <Button variant="warning" disabled={submitting} onClick={() => sendDecision("approved", { forcePartialConfirm: true })}>Confirmar aprovação parcial</Button>
          </Alert>
        ) : null}

        <Row className="g-4">
          <Col lg={8}>
            <Card className="border-0 shadow-sm mb-4">
              <Card.Header className="bg-white"><strong>{isEstimateApproval ? "Dados do orçamento" : "Dados da ordem"}</strong></Card.Header>
              <Card.Body>
                <Row className="g-3">
                  <Col md={6}><div className="text-muted small">Cliente</div><strong>{document.customer_name}</strong></Col>
                  <Col md={6}><div className="text-muted small">Veículo</div><strong>{document.vehicle_display || "Não informado"}</strong></Col>
                  <Col md={6}><div className="text-muted small">Status</div><strong>{document.status_label}</strong></Col>
                  <Col md={6}><div className="text-muted small">{isEstimateApproval ? "Validade" : "Previsão"}</div><strong>{isEstimateApproval ? (document.valid_until || "-") : dateTime(document.promised_at)}</strong></Col>
                  {isEstimateApproval ? <Col md={6}><div className="text-muted small">Tanque de combustível</div><strong>{document.tank_level_label || `${document.tank_level_percent ?? 0}%`}</strong></Col> : null}
                </Row>
                <hr />
                <h6>Relato</h6>
                <p className="white-space-preline">{document.complaint || "-"}</p>
                <h6>Diagnóstico</h6>
                <p className="white-space-preline">{document.diagnosis || "-"}</p>
                <h6>Observações ao cliente</h6>
                <p className="white-space-preline mb-0">{document.customer_notes || "-"}</p>
              </Card.Body>
            </Card>

            <Card className="border-0 shadow-sm mb-4">
              <Card.Header className="bg-white"><strong>Serviços</strong></Card.Header>
              <Card.Body className="p-0">
                <Table responsive hover className="mb-0">
                  <thead><tr>{isEstimateApproval ? <th>Aprovar</th> : null}<th>Descrição</th><th>Qtd.</th><th>Unitário</th><th>Desc.</th><th>Total</th></tr></thead>
                  <tbody>{services.length ? services.map((item) => {
                    const checked = selectedServices.includes(Number(item.id));
                    return <tr key={item.id}>{isEstimateApproval ? <td><Form.Check type="checkbox" checked={checked} disabled={!approval.can_decide} onChange={(e) => toggleService(item.id, e.target.checked)} /></td> : null}<td>{item.description}</td><td>{item.quantity}</td><td>{money(item.unit_price)}</td><td>{money(item.discount_amount)}</td><td>{money(item.total_amount)}</td></tr>;
                  }) : <tr><td colSpan={isEstimateApproval ? 6 : 5} className="text-muted p-3">Nenhum serviço lançado.</td></tr>}</tbody>
                </Table>
              </Card.Body>
            </Card>

            <Card className="border-0 shadow-sm mb-4">
              <Card.Header className="bg-white"><strong>Peças</strong></Card.Header>
              <Card.Body className="p-0">
                <Table responsive hover className="mb-0">
                  <thead><tr>{isEstimateApproval ? <th>Aprovar</th> : null}<th>Serviço vinculado</th><th>Código</th><th>Descrição</th><th>Qtd.</th><th>Unitário</th><th>Desc.</th><th>Total</th></tr></thead>
                  <tbody>{parts.length ? parts.map((item) => {
                    const serviceIsChecked = !item.service_item || selectedServices.includes(Number(item.service_item));
                    const checked = selectedParts.includes(Number(item.id));
                    return <tr key={item.id}>{isEstimateApproval ? <td><Form.Check type="checkbox" checked={checked && serviceIsChecked} disabled={!approval.can_decide || !serviceIsChecked} onChange={(e) => togglePart(item.id, e.target.checked)} /></td> : null}<td>{item.service_item_description || "Sem vínculo"}</td><td>{item.sku || "-"}</td><td>{item.description}</td><td>{item.quantity}</td><td>{money(item.unit_price)}</td><td>{money(item.discount_amount)}</td><td>{money(item.total_amount)}</td></tr>;
                  }) : <tr><td colSpan={isEstimateApproval ? 8 : 7} className="text-muted p-3">Nenhuma peça lançada.</td></tr>}</tbody>
                </Table>
              </Card.Body>
            </Card>
          </Col>

          <Col lg={4}>
            <Card className="border-0 shadow-sm mb-4 sticky-lg-top public-approval-summary">
              <Card.Header className="bg-white"><strong>Resumo financeiro</strong></Card.Header>
              <Card.Body>
                <div className="d-flex justify-content-between"><span>Serviços</span><strong>{money(totals.subtotal_services)}</strong></div>
                <div className="d-flex justify-content-between"><span>Peças</span><strong>{money(totals.subtotal_parts)}</strong></div>
                <div className="d-flex justify-content-between"><span>Descontos</span><strong>{money(totals.discount_total)}</strong></div>
                <hr />
                <div className="d-flex justify-content-between fs-5"><span>Total</span><strong>{money(totals.grand_total ?? totals.total_amount)}</strong></div>
                {isEstimateApproval ? null : <><div className="d-flex justify-content-between"><span>Pago</span><strong>{money(totals.paid_total)}</strong></div><div className="d-flex justify-content-between"><span>Saldo</span><strong>{money(totals.balance_due)}</strong></div></>}
                <Button as="a" href={pdfUrl} target="_blank" rel="noreferrer" variant="outline-primary" className="w-100 mt-3">Abrir PDF</Button>
              </Card.Body>
            </Card>

            <Card className="border-0 shadow-sm">
              <Card.Header className="bg-white"><strong>Decisão do cliente</strong></Card.Header>
              <Card.Body>
                {approval.can_decide ? (
                  <>
                    <Alert variant="info" className="small">Ao aprovar, você confirma ciência dos itens, valores e condições deste documento. Em orçamento, a OS será gerada somente com serviços e peças aprovados.</Alert>
                    <Form.Label>Nome de quem está decidindo</Form.Label>
                    <Form.Control className="mb-3" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                    <Form.Label>CPF/CNPJ <span className="text-danger">*</span></Form.Label>
                    <Form.Control required className="mb-3" placeholder="Informe CPF ou CNPJ válido" value={form.document} onChange={(e) => setForm({ ...form, document: e.target.value })} />
                    <Form.Label>Observações <span className="text-danger">*</span></Form.Label>
                    <Form.Control required as="textarea" rows={4} className="mb-3" placeholder="Informe sua observação para registrar a decisão" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
                    <div className="d-grid gap-2">
                      <Button variant="success" disabled={submitting} onClick={() => sendDecision("approved")}>{isEstimateApproval ? "Aprovar itens selecionados" : "Aprovar documento"}</Button>
                      <Button variant="outline-danger" disabled={submitting} onClick={() => sendDecision("rejected")}>Recusar documento</Button>
                    </div>
                  </>
                ) : (
                  <Alert variant={["approved", "partially_approved"].includes(approval.effective_status) ? "success" : "secondary"} className="mb-0">
                    <div className="fw-semibold">{approval.status_label}</div>
                    <div className="small">Decisão registrada em {dateTime(approval.decided_at)}.</div>
                    {approval.decision_name ? <div className="small">Responsável: {approval.decision_name}</div> : null}
                    {approval.decision_notes ? <div className="small white-space-preline mt-2">{approval.decision_notes}</div> : null}
                  </Alert>
                )}
              </Card.Body>
            </Card>
          </Col>
        </Row>
      </Container>
    </div>
  );
}
