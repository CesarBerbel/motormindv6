import React, { useEffect, useMemo, useState } from "react";
import { Alert, Badge, Button, Card, Col, Form, Modal, Row, Spinner } from "react-bootstrap";
import { Link } from "react-router-dom";
import api, { apiError, apiUrl } from "../api/client";
import ErrorAlert from "../components/ErrorAlert";
import SystemToast from "../components/SystemToast";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import AIAssistButton from "../components/AIAssistButton";
import { money } from "../workshopOptions";

function dateTime(value) { return value ? new Date(value).toLocaleString("pt-BR") : "-"; }
function dateOnly(value) { return value ? new Date(`${value}T00:00:00`).toLocaleDateString("pt-BR") : "-"; }
function kindOf(item) { return item?.kind === "estimate" ? "estimate" : "os"; }
function itemKey(item) { return `${kindOf(item)}-${item.id}`; }
function itemRoute(item) { return kindOf(item) === "estimate" ? `/attendance/estimates/${item.id}/edit` : `/work-orders/${item.id}`; }
function itemPdfPath(item) { return kindOf(item) === "estimate" ? `/attendance/estimates/${item.id}/document/` : `/workshop/work-orders/${item.id}/document/`; }
function actionLabel(action, status, kind = "os") {
  if (kind === "estimate") {
    if (action === "start_diagnosis") return "Iniciar diagnóstico";
    if (action === "send_approval") return "Aguardar aprovação";
    return "Mover orçamento";
  }
  if (action === "start") return status === "waiting_parts" ? "Retomar execução" : "Iniciar execução";
  if (action === "complete") return "Concluir OS";
  if (action === "wait_parts") return "Aguardar peça";
  return "Mover";
}
function nextActionHint(item) {
  if (kindOf(item) === "estimate") {
    if (item.status === "open") return "Orçamento aberto: iniciar diagnóstico técnico.";
    if (item.status === "diagnosis") return "Diagnóstico pronto: enviar para aguardando aprovação.";
    if (item.status === "awaiting_approval") return "Aguardando aprovação integral ou parcial do cliente. Ao aprovar, uma OS será aberta.";
    return "";
  }
  if (item.status === "open") return "Iniciar leva para Em execução";
  if (item.status === "in_progress") return "Concluir leva para Concluída";
  if (item.status === "waiting_parts") return "Retomar leva para Em execução";
  return "";
}
function canMoveItem(item) {
  if (kindOf(item) === "estimate") return ["open", "diagnosis"].includes(item.status);
  return ["open", "waiting_parts", "in_progress"].includes(item.status);
}

function WorkbenchCard({ item, columnKey, busyId, draggingId, onDragStart, onDragEnd, onAction }) {
  const kind = kindOf(item);
  const busy = busyId === itemKey(item);
  const isEstimate = kind === "estimate";
  const canDrag = canMoveItem(item);
  const canStart = !isEstimate && ["open", "waiting_parts"].includes(item.status);
  const canComplete = !isEstimate && ["in_progress", "waiting_parts"].includes(item.status);
  const canWaitParts = !isEstimate && ["open", "in_progress"].includes(item.status);
  const canStartDiagnosis = isEstimate && item.status === "open";
  const canSendApproval = isEstimate && ["open", "diagnosis"].includes(item.status);
  return (
    <Card className={`kanban-card technical-service-card ${isEstimate ? "technical-card-estimate" : "technical-card-os"} ${String(draggingId) === itemKey(item) ? "kanban-card-dragging" : ""}`} draggable={canDrag && !busy} onDragStart={(event) => canDrag ? onDragStart(event, item) : event.preventDefault()} onDragEnd={onDragEnd}>
      <Card.Body>
        <div className="d-flex justify-content-between align-items-start gap-3 mb-2">
          <div>
            <div className="d-flex align-items-center gap-2 flex-wrap"><Badge bg={isEstimate ? "info" : "primary"}>{isEstimate ? "Orçamento" : "OS"}</Badge><Link to={itemRoute(item)} className="fw-semibold text-decoration-none">{item.number}</Link></div>
            <div className="small text-muted mt-1">{item.customer_name || "Cliente não informado"}</div>
          </div>
          <StatusBadge value={item.status} label={item.status_label} />
        </div>
        <div className="fw-semibold small mb-1">{item.title || "Sem título"}</div>
        <div className="small text-muted mb-3">{item.vehicle_display || "Sem veículo"}</div>
        <Row className="g-2 small">
          <Col md={6}><span className="text-muted">Responsável:</span><br /><strong>{item.assigned_to_name || (isEstimate ? "Diagnóstico" : "Sem responsável")}</strong></Col>
          <Col md={6}><span className="text-muted">{isEstimate ? "Validade:" : "Previsão:"}</span><br /><strong>{isEstimate ? dateOnly(item.valid_until) : dateTime(item.promised_at)}</strong></Col>
          <Col md={6}><span className="text-muted">Total:</span><br /><strong>{money(item.grand_total || item.total_amount)}</strong></Col>
          <Col md={6}><span className="text-muted">{isEstimate ? "Fluxo:" : "Saldo:"}</span><br /><strong>{isEstimate ? "Aprovação → OS" : money(item.balance_due)}</strong></Col>
        </Row>
        {nextActionHint(item) ? <div className="small text-muted mt-3">{nextActionHint(item)}</div> : null}
        <div className="d-flex flex-wrap justify-content-end gap-2 mt-3">
          <Button as={Link} to={itemRoute(item)} size="sm" variant="outline-secondary">{isEstimate ? "Abrir orçamento" : "Abrir OS"}</Button>
          <Button as="a" href={apiUrl(itemPdfPath(item))} target="_blank" rel="noreferrer" size="sm" variant="outline-dark">PDF</Button>
          {canWaitParts && columnKey !== "waiting_parts" ? <Button disabled={busy} size="sm" variant="outline-warning" onClick={() => onAction(item, "wait_parts")}>Aguardar peça</Button> : null}
          {canStart ? <Button disabled={busy} size="sm" onClick={() => onAction(item, "start")}>{actionLabel("start", item.status, kind)}</Button> : null}
          {canComplete ? <Button disabled={busy} size="sm" variant="success" onClick={() => onAction(item, "complete")}>{actionLabel("complete", item.status, kind)}</Button> : null}
          {canStartDiagnosis ? <Button disabled={busy} size="sm" variant="info" onClick={() => onAction(item, "start_diagnosis")}>Iniciar diagnóstico</Button> : null}
          {canSendApproval ? <Button disabled={busy} size="sm" variant="warning" onClick={() => onAction(item, "send_approval")}>Aguardar aprovação</Button> : null}
        </div>
      </Card.Body>
    </Card>
  );
}

function WorkbenchColumn({ column, items, loading, busyId, draggingId, dropTarget, onDragStart, onDragEnd, onDrop, onAction }) {
  return <section className={`kanban-column ${dropTarget === column.key ? "kanban-column-target" : ""}`} onDragOver={(event) => { event.preventDefault(); column.setDropTarget(column.key); }} onDragLeave={() => column.setDropTarget("")} onDrop={(event) => onDrop(event, column.key)}>
    <div className="kanban-column-header"><span>{column.title}</span><Badge bg={column.badge || "secondary"}>{items.length}</Badge></div>
    <div className="small text-muted mb-3">{column.description}</div>
    {loading ? <div className="text-center text-muted py-4"><Spinner size="sm" /> Carregando</div> : items.length === 0 ? <div className="kanban-empty">{column.empty}</div> : items.map((item) => <WorkbenchCard key={itemKey(item)} item={item} columnKey={column.key} busyId={busyId} draggingId={draggingId} onDragStart={onDragStart} onDragEnd={onDragEnd} onAction={onAction} />)}
  </section>;
}

export default function TechnicalWorkbenchPage() {
  const [data, setData] = useState(null);
  const [technician, setTechnician] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [draggingId, setDraggingId] = useState(null);
  const [dropTarget, setDropTarget] = useState("");
  const [loading, setLoading] = useState(false);
  const [diagnosisPrompt, setDiagnosisPrompt] = useState({ show: false, item: null, action: "" });
  const [diagnosisText, setDiagnosisText] = useState("");
  const [diagnosisError, setDiagnosisError] = useState("");

  async function load(nextTechnician = technician) {
    setLoading(true); setError("");
    try {
      const params = {}; if (nextTechnician) params.technician = nextTechnician;
      const response = await api.get("/workshop/technical/dashboard/", { params });
      setData(response.data); setTechnician(response.data.selected_technician || nextTechnician || "");
    } catch (err) { setError(apiError(err)); } finally { setLoading(false); }
  }
  useEffect(() => { load(""); }, []);

  const counts = data?.counts || {};
  const technicians = data?.technicians || [];
  const queue = data?.columns?.queue || data?.queue_orders || [];
  const active = data?.columns?.active || data?.active_orders || [];
  const approval = data?.columns?.approval || [];
  const waitingParts = data?.columns?.waiting_parts || data?.waiting_parts_orders || [];
  const done = data?.columns?.done || data?.done_orders || [];
  const allItems = useMemo(() => [...queue, ...active, ...approval, ...waitingParts, ...done], [queue, active, approval, waitingParts, done]);
  const totalOpen = useMemo(() => (counts.queue || 0) + (counts.active || 0) + (counts.awaiting_approval || 0) + (counts.waiting_parts || 0), [counts]);

  function needsDiagnosisPrompt(item, action) { return kindOf(item) === "os" && action === "complete" && !item.diagnosis; }
  function requestAction(item, action) {
    if (needsDiagnosisPrompt(item, action)) { setDiagnosisPrompt({ show: true, item, action }); setDiagnosisText(item?.diagnosis || ""); setDiagnosisError(""); setDraggingId(null); setDropTarget(""); return; }
    runAction(item, action);
  }
  async function runAction(item, action, extraPayload = {}) {
    if (!item || !action) return;
    setBusyId(itemKey(item)); setError(""); setNotice("");
    try {
      if (kindOf(item) === "estimate") {
        if (action === "start_diagnosis") {
          const response = await api.post(`/attendance/estimates/${item.id}/change-status/`, { status: "diagnosis", note: "Orçamento movido para diagnóstico pela Bancada Técnica." });
          setNotice(`${item.number} atualizado para ${response.data?.status_label || "diagnóstico"}.`);
        } else if (action === "send_approval") {
          const response = await api.post(`/attendance/estimates/${item.id}/create-customer-approval/`, {});
          setNotice(`${item.number} enviado para aguardando aprovação.${response.data?.public_url ? " Link público gerado." : ""}`);
        } else { throw new Error("Ação inválida para orçamento."); }
      } else {
        const response = await api.post(`/workshop/work-orders/${item.id}/technical-action/`, { action, note: `${actionLabel(action, item.status, "os")} pela Bancada Técnica.`, ...extraPayload });
        const updated = response.data?.work_order; setNotice(`${item.number} atualizada para ${updated?.status_label || "a próxima etapa"}.`);
      }
      await load(technician);
    } catch (err) { setError(apiError(err)); } finally { setBusyId(null); setDraggingId(null); setDropTarget(""); }
  }
  function closeDiagnosisPrompt() { if (busyId !== null) return; setDiagnosisPrompt({ show: false, item: null, action: "" }); setDiagnosisText(""); setDiagnosisError(""); }
  async function submitDiagnosisPrompt(event) {
    event.preventDefault(); const text = diagnosisText.trim();
    if (!text) { setDiagnosisError("Informe a descrição do diagnóstico para concluir a OS."); return; }
    const item = diagnosisPrompt.item; const action = diagnosisPrompt.action;
    setDiagnosisError(""); setDiagnosisPrompt({ show: false, item: null, action: "" }); setDiagnosisText(""); await runAction(item, action, { diagnosis_description: text });
  }
  function actionForDrop(item, columnKey) {
    if (!item) return "";
    if (kindOf(item) === "estimate") {
      if (columnKey === "active" && item.status === "open") return "start_diagnosis";
      if (columnKey === "approval" && ["open", "diagnosis"].includes(item.status)) return "send_approval";
      return "";
    }
    if (columnKey === "active") return ["open", "waiting_parts"].includes(item.status) ? "start" : "";
    if (columnKey === "waiting_parts") return ["open", "in_progress"].includes(item.status) ? "wait_parts" : "";
    if (columnKey === "done") return ["in_progress", "waiting_parts"].includes(item.status) ? "complete" : "";
    return "";
  }
  function onDragStart(event, item) { const key = itemKey(item); setDraggingId(key); event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", key); }
  function onDragEnd() { setDraggingId(null); setDropTarget(""); }
  function onDrop(event, columnKey) {
    event.preventDefault(); const key = event.dataTransfer.getData("text/plain") || draggingId; const item = allItems.find((entry) => itemKey(entry) === key); const action = actionForDrop(item, columnKey);
    if (!item) return;
    if (!action) { const targetName = columnKey === "waiting_parts" ? "Aguardando peça" : columnKey === "approval" ? "Aguardando aprovação" : "esta coluna"; setError(`${item.number} não pode ser movido para ${targetName} a partir de ${item.status_label || item.status}.`); setDraggingId(null); setDropTarget(""); return; }
    requestAction(item, action);
  }
  function handleTechnicianChange(value) { setTechnician(value); load(value); }

  const columns = [
    { key: "queue", title: "Fila do técnico", description: "OS abertas e orçamentos abertos aguardando diagnóstico.", empty: "Nenhuma OS ou orçamento aberto na fila.", items: queue, setDropTarget },
    { key: "active", title: "Diagnóstico / execução", description: "Orçamentos em diagnóstico e OS em execução operacional.", empty: "Nenhum diagnóstico ou execução em andamento.", items: active, setDropTarget, badge: "primary" },
    { key: "approval", title: "Aguardando aprovação", description: "Orçamentos aguardando aprovação integral ou parcial do cliente.", empty: "Nenhum orçamento aguardando aprovação.", items: approval, setDropTarget, badge: "warning" },
    { key: "waiting_parts", title: "Aguardando peça", description: "Somente OS podem entrar nesta etapa. Orçamento não aguarda peça.", empty: "Nenhuma OS aguardando peça.", items: waitingParts, setDropTarget, badge: "warning" },
    { key: "done", title: "Concluídas", description: "OS finalizadas pela bancada.", empty: "Nenhuma OS concluída pela bancada.", items: done, setDropTarget, badge: "success" },
  ];

  return <div className="kanban-page">
    <PageHeader title="Bancada técnica" subtitle="Fila operacional de OS e orçamentos. Orçamentos seguem aberto → diagnóstico → aguardando aprovação → aprovação integral/parcial → OS nova." />
    <ErrorAlert error={error} onClose={() => setError("")} />
    <SystemToast message={notice} variant="success" delay={3000} onClose={() => setNotice("")} />
    <Modal keyboard={false} show={diagnosisPrompt.show} onHide={closeDiagnosisPrompt} centered backdrop={busyId !== null ? "static" : true}>
      <Form onSubmit={submitDiagnosisPrompt}>
        <Modal.Header closeButton={busyId === null}><Modal.Title>Descrição do diagnóstico</Modal.Title></Modal.Header>
        <Modal.Body>
          <p className="text-muted mb-3">Para concluir a OS {diagnosisPrompt.item?.number ? <strong>{diagnosisPrompt.item.number}</strong> : null} informe uma observação técnica, se necessário.</p>
          <Form.Group controlId="technical-diagnosis-description">
            <div className="d-flex align-items-center justify-content-between gap-2 mb-1"><Form.Label className="mb-0">Observação técnica</Form.Label><AIAssistButton task="diagnosis" value={diagnosisText} context={`OS ${diagnosisPrompt.item?.number || ""} | Cliente: ${diagnosisPrompt.item?.customer_name || ""} | Veiculo: ${diagnosisPrompt.item?.vehicle_display || ""} | Relato: ${diagnosisPrompt.item?.complaint || ""}`} onApply={setDiagnosisText} /></div>
            <Form.Control as="textarea" rows={5} value={diagnosisText} onChange={(event) => { setDiagnosisText(event.target.value); if (diagnosisError) setDiagnosisError(""); }} placeholder="Ex.: Identificado vazamento no cilindro mestre e pastilhas dianteiras abaixo do limite de segurança." isInvalid={!!diagnosisError} autoFocus />
            <Form.Control.Feedback type="invalid">{diagnosisError}</Form.Control.Feedback>
          </Form.Group>
        </Modal.Body>
        <Modal.Footer><Button variant="outline-secondary" onClick={closeDiagnosisPrompt} disabled={busyId !== null}>Cancelar</Button><Button type="submit" variant="success" disabled={busyId !== null}>Concluir OS</Button></Modal.Footer>
      </Form>
    </Modal>
    <Card className="border-0 shadow-sm mb-3"><Card.Body><Row className="g-3 align-items-end">
      <Col lg={4} md={6}><Form.Label>Técnico</Form.Label><Form.Select value={technician} onChange={(event) => handleTechnicianChange(event.target.value)} disabled={loading || busyId !== null}><option value="">Todos os técnicos</option>{technicians.map((item) => <option key={item.id} value={item.id}>{item.name}{item.specialty_label ? ` - ${item.specialty_label}` : ""}</option>)}</Form.Select><Form.Text>Orçamentos aparecem para todos os técnicos enquanto não houver técnico específico vinculado ao orçamento.</Form.Text></Col>
      <Col lg={2} md={3} xs={6}><Card className="card-kpi mb-0"><Card.Body><div className="text-muted small">Fila total</div><div className="h3 fw-bold mb-0">{totalOpen}</div></Card.Body></Card></Col>
      <Col lg={2} md={3} xs={6}><Card className="card-kpi mb-0"><Card.Body><div className="text-muted small">Orçamentos</div><div className="h3 fw-bold mb-0">{(counts.queue_estimates || 0) + (counts.active_estimates || 0) + (counts.awaiting_approval || 0)}</div></Card.Body></Card></Col>
      <Col lg={2} md={3} xs={6}><Card className="card-kpi mb-0"><Card.Body><div className="text-muted small">Aguard. aprovação</div><div className="h3 fw-bold mb-0">{counts.awaiting_approval || 0}</div></Card.Body></Card></Col>
      <Col lg={2} md={3} xs={6}><Card className="card-kpi mb-0"><Card.Body><div className="text-muted small">Aguard. peça</div><div className="h3 fw-bold mb-0">{counts.waiting_parts || 0}</div></Card.Body></Card></Col>
      <Col md="auto"><Button variant="outline-primary" onClick={() => load(technician)} disabled={loading || busyId !== null}>{loading ? "Carregando..." : "Atualizar"}</Button></Col>
    </Row></Card.Body></Card>
    {busyId ? <Alert variant="info" className="py-2">Salvando movimentação da bancada técnica...</Alert> : null}
    <div className="kanban-board technical-workbench-board">{columns.map((column) => <WorkbenchColumn key={column.key} column={column} items={column.items} loading={loading} busyId={busyId} draggingId={draggingId} dropTarget={dropTarget} onDragStart={onDragStart} onDragEnd={onDragEnd} onDrop={onDrop} onAction={requestAction} />)}</div>
  </div>;
}
