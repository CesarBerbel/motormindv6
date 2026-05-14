import React, { useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, Col, Form, Modal, Row, Table } from "../ui/TailwindPrimitives.jsx";
import { Link, useLocation, useNavigate } from "react-router-dom";
import api, { apiError, apiUrl, results } from "../api/client";
import AreaTabs from "../components/AreaTabs";
import EmptyState from "../components/EmptyState";
import ErrorAlert from "../components/ErrorAlert";
import PageHeader from "../components/PageHeader";
import SearchAutocompleteInput from "../components/SearchAutocompleteInput";
import { estimateStatuses, formatDate, money } from "../workshopOptions";
import { buildReturnToState } from "../utils/returnTo";

const statusOptions = [["", "Todos"], ...estimateStatuses];
const statusVariant = { draft: "secondary", sent: "warning", approved: "success", rejected: "danger", expired: "warning", converted: "primary", cancelled: "dark" };
const cancellableStatuses = new Set(["draft", "sent", "approved"]);

function buildEstimateSearchSuggestions(items) {
  return (items || []).map((item) => {
    const number = item.number || `Orçamento #${item.id}`;
    const title = item.title || item.complaint || "Sem título";
    const customer = item.customer_name || "Cliente não informado";
    const vehicle = item.vehicle_display || "Veículo não informado";
    const status = item.status_label || "Status não informado";
    const total = money(item.total_amount || 0);
    const validUntil = formatDate(item.valid_until);

    return {
      key: `estimate-${item.id}`,
      value: number,
      label: `${number} - ${title}`,
      description: `${customer} · ${vehicle}`,
      meta: `${status} · Total: ${total}${validUntil ? ` · Validade: ${validUntil}` : ""}`,
      searchText: [number, title, customer, vehicle, status, item.complaint, total, validUntil].filter(Boolean).join(" "),
    };
  });
}

export default function EstimatesPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const returnState = buildReturnToState(location);
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [cancelTarget, setCancelTarget] = useState(null);
  const [cancelForm, setCancelForm] = useState({ reason: "", send_notifications: true });
  const searchSuggestions = useMemo(() => buildEstimateSearchSuggestions(items), [items]);

  async function load(nextSearch = search, nextStatus = status) {
    try {
      const params = {};
      if (nextSearch) params.search = nextSearch;
      if (nextStatus) params.status = nextStatus;
      const estimateRes = await api.get("/attendance/estimates/", { params });
      setItems(results(estimateRes.data));
    } catch (err) {
      setError(apiError(err));
    }
  }

  useEffect(() => { load(); }, [status]);

  async function changeStatus(item, newStatus) {
    try {
      await api.post(`/attendance/estimates/${item.id}/change-status/`, { status: newStatus });
      await load();
    } catch (err) {
      setError(apiError(err));
    }
  }

  async function convert(item) {
    try {
      const { data } = await api.post(`/attendance/estimates/${item.id}/convert-to-work-order/`, {});
      await load();
      window.location.href = `/work-orders/${data.id}`;
    } catch (err) {
      setError(apiError(err));
    }
  }

  async function sendCustomerApproval(item) {
    try {
      const { data } = await api.post(`/attendance/estimates/${item.id}/create-customer-approval/`, {});
      await load();
      if (data.public_url) {
        window.alert(`E-mail de aprovação enviado. Link público: ${data.public_url}`);
      } else {
        window.alert("E-mail de aprovação enviado ao cliente.");
      }
    } catch (err) {
      setError(apiError(err));
    }
  }

  function openCancel(item) {
    setCancelTarget(item);
    setCancelForm({ reason: "", send_notifications: true });
  }

  async function submitCancel(event) {
    event.preventDefault();
    if (!cancelTarget) return;
    try {
      await api.post(`/attendance/estimates/${cancelTarget.id}/cancel/`, cancelForm);
      setCancelTarget(null);
      setCancelForm({ reason: "", send_notifications: true });
      await load();
    } catch (err) {
      setError(apiError(err));
    }
  }

  function onSearch(nextValue) {
    setSearch(nextValue);
    load(nextValue);
  }

  function clearSearch() {
    setSearch("");
    setStatus("");
    load("", "");
  }

  return <>
    <PageHeader title="Orçamentos" subtitle="Fluxo comercial do atendimento: montar orçamento, enviar, aprovar, rejeitar e converter em OS." actions={<Button className="btn btn-primary" onClick={() => navigate("/attendance/estimates/new", { state: returnState })}>Novo orçamento</Button>} />
    <AreaTabs area="attendance" />
    <ErrorAlert error={error} onClose={() => setError("")} />

    <Card className="border-0 shadow-sm mb-3"><Card.Body><Row className="g-2"><Col md={5}><SearchAutocompleteInput placeholder="Buscar orçamento, cliente, placa ou descrição" value={search} onChange={setSearch} onSearch={onSearch} suggestions={searchSuggestions} /></Col><Col md={3}><Form.Select value={status} onChange={(event) => setStatus(event.target.value)}>{statusOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Form.Select></Col><Col md={2}><Button variant="outline-primary" className="w-100" onClick={() => load()}>Buscar</Button></Col><Col md={2}><Button variant="outline-secondary" className="w-100" onClick={clearSearch} disabled={!search && !status}>Limpar pesquisa</Button></Col></Row></Card.Body></Card>

    <Card className="border-0 shadow-sm"><Card.Body className="p-0">
      {items.length === 0 ? <EmptyState /> : <Table responsive hover className="mb-0"><thead><tr><th>Número</th><th>Cliente</th><th>Veículo</th><th>Total</th><th>Validade</th><th>Status</th><th></th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td className="fw-semibold">{item.number}</td><td>{item.customer_name}</td><td>{item.vehicle_display}</td><td>{money(item.total_amount)}</td><td>{formatDate(item.valid_until)}</td><td><Badge bg={statusVariant[item.status] || "secondary"}>{item.status_label}</Badge></td><td className="text-end"><Button size="sm" variant="outline-secondary" className="me-2" onClick={() => navigate(`/attendance/estimates/${item.id}/edit`, { state: returnState })}>{item.can_edit === false ? "Abrir" : "Editar"}</Button><Button as="a" size="sm" variant="outline-dark" className="me-2" href={apiUrl(`/attendance/estimates/${item.id}/document/`)} target="_blank" rel="noreferrer">PDF</Button>{["draft", "sent"].includes(item.status) && <Button size="sm" variant="outline-warning" className="me-2" onClick={() => sendCustomerApproval(item)}>Enviar aprovação</Button>}{item.status === "approved" && <Button size="sm" className="me-2" onClick={() => convert(item)}>Converter em OS</Button>}{cancellableStatuses.has(item.status) && <Button size="sm" variant="outline-danger" className="me-2" onClick={() => openCancel(item)}>Cancelar</Button>}{item.converted_work_order && <Link className="btn btn-sm btn-outline-primary" to={`/work-orders/${item.converted_work_order}`} state={returnState}>Abrir OS</Link>}</td></tr>)}</tbody></Table>}
    </Card.Body></Card>

    <Modal show={!!cancelTarget} onHide={() => setCancelTarget(null)} centered>
      <Form onSubmit={submitCancel}>
        <Modal.Header closeButton><Modal.Title>Cancelar orçamento {cancelTarget?.number ? `- ${cancelTarget.number}` : ""}</Modal.Title></Modal.Header>
        <Modal.Body>
          <p className="text-muted small mb-3">A justificativa será gravada no orçamento e usada para auditoria do cancelamento.</p>
          <Form.Label>Justificativa</Form.Label>
          <Form.Control required minLength={5} as="textarea" rows={4} value={cancelForm.reason} onChange={(event) => setCancelForm({ ...cancelForm, reason: event.target.value })} placeholder="Ex.: Cliente recusou o orçamento." />
          <Form.Check className="mt-3" label="Disparar notificações automáticas de cancelamento" checked={cancelForm.send_notifications} onChange={(event) => setCancelForm({ ...cancelForm, send_notifications: event.target.checked })} />
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setCancelTarget(null)}>Fechar</Button>
          <Button variant="danger" type="submit">Confirmar cancelamento</Button>
        </Modal.Footer>
      </Form>
    </Modal>
  </>;
}
