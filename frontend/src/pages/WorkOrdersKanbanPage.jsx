import React, { useEffect, useMemo, useState } from "react";
import { Alert, Badge, Button, Card, Col, Form, Row, Spinner } from "../ui/TailwindPrimitives.jsx";
import { Link, useLocation } from "react-router-dom";
import api, { apiError, apiUrl, results } from "../api/client";
import ErrorAlert from "../components/ErrorAlert";
import SystemToast from "../components/SystemToast";
import PageHeader from "../components/PageHeader";
import AreaTabs from "../components/AreaTabs";
import StatusBadge from "../components/StatusBadge";
import { money, priorities } from "../workshopOptions";
import SearchAutocompleteInput from "../components/SearchAutocompleteInput";
import { buildReturnToState } from "../utils/returnTo";

const OS_STATUS_LABELS = {
  open: "Aberta",
  in_progress: "Em execução",
  waiting_parts: "Aguardando peças",
  awaiting_approval: "Aguardando aprovação",
  paused: "Pausada",
  completed: "Concluída",
  delivered: "Entregue",
  cancelled: "Cancelada",
};

const ESTIMATE_FINAL_STATUSES = new Set(["approved", "rejected", "expired", "converted", "cancelled"]);

const OPERATIONAL_COLUMNS = [
  { key: "open", label: "Aberta", description: "OS abertas e orçamentos abertos aguardando triagem." },
  { key: "in_progress", label: "Em execução", description: "OS em execução." },
  { key: "awaiting_approval", label: "Aguardando aprovação", description: "OS ou orçamentos enviados para aprovação do cliente." },
  { key: "waiting_parts", label: "Aguardando peças", description: "Somente OS entram nesta etapa. Orçamentos não aguardam peça." },
  { key: "paused", label: "Pausada", description: "OS pausadas com motivo registrado." },
  { key: "completed", label: "Concluída", description: "OS concluídas e orçamentos em estado final." },
  { key: "delivered", label: "Entregue", description: "OS entregues ao cliente." },
  { key: "cancelled", label: "Cancelada", description: "OS canceladas." },
];

const STATUS_FILTER_OPTIONS = [
  { value: "open", label: "Aberta" },
  { value: "in_progress", label: "Em execução" },
  { value: "awaiting_approval", label: "Aguardando aprovação" },
  { value: "waiting_parts", label: "Aguardando peças" },
  { value: "paused", label: "Pausada" },
  { value: "completed", label: "Concluída" },
  { value: "delivered", label: "Entregue" },
  { value: "cancelled", label: "Cancelada" },
];

async function fetchAll(endpoint, params = {}) {
  const all = [];
  let page = 1;
  let hasNext = true;

  while (hasNext) {
    const response = await api.get(endpoint, { params: { ...params, page } });
    all.push(...results(response.data));
    hasNext = Boolean(response.data?.next);
    page += 1;
  }

  return all;
}

function kindOf(item) {
  return item?.kind === "estimate" ? "estimate" : "os";
}

function itemKey(item) {
  return `${kindOf(item)}-${item.id}`;
}

function itemRoute(item) {
  return kindOf(item) === "estimate" ? `/work-orders/estimates/${item.id}/edit` : `/work-orders/${item.id}`;
}

function itemPdfPath(item) {
  return kindOf(item) === "estimate" ? `/attendance/estimates/${item.id}/document/` : `/workshop/work-orders/${item.id}/document/`;
}

function visualStatus(item) {
  if (kindOf(item) !== "estimate") return item.status;
  if (item.status === "sent") return "awaiting_approval";
  if (ESTIMATE_FINAL_STATUSES.has(item.status)) return "completed";
  return "open";
}

function formatDate(value) {
  if (!value) return "-";
  const source = String(value);
  const date = source.includes("T") ? new Date(source) : new Date(`${source}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleDateString("pt-BR");
}

function formatDateTime(value) {
  if (!value) return "Sem previsão";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Sem previsão";
  return date.toLocaleString("pt-BR");
}

function normalizeWorkOrder(order) {
  return { ...order, kind: "os", visual_status: visualStatus({ ...order, kind: "os" }) };
}

function normalizeEstimate(estimate) {
  return {
    ...estimate,
    kind: "estimate",
    visual_status: visualStatus({ ...estimate, kind: "estimate" }),
    priority: "normal",
    priority_label: "Normal",
    promised_at: null,
    grand_total: estimate.total_amount,
    balance_due: estimate.total_amount,
    available_status_transitions: [],
  };
}

function itemSearchSuggestion(item) {
  const isEstimate = kindOf(item) === "estimate";
  const typeLabel = isEstimate ? "Orçamento" : "OS";
  const title = [item.number, item.customer_name].filter(Boolean).join(" - ") || typeLabel;
  const status = item.status_label || item.status || "Sem status";
  const priority = item.priority_label || item.priority || "Sem prioridade";
  const vehicle = item.vehicle_display || "Sem veículo";
  const itemTitle = item.title || "Sem título";
  const total = `Total: ${money(item.grand_total || item.total_amount)}`;
  const balance = isEstimate ? "Fluxo: aprovação → OS" : `Saldo: ${money(item.balance_due)}`;
  const dateLabel = isEstimate ? `Validade: ${formatDate(item.valid_until)}` : `Previsão: ${formatDateTime(item.promised_at)}`;

  return {
    key: itemKey(item),
    label: `${typeLabel} ${title}`,
    value: title,
    description: [vehicle, itemTitle, status, priority].filter(Boolean).join(" • "),
    meta: [dateLabel, total, balance, item.complaint].filter(Boolean).join(" • "),
    payload: item,
    searchText: [
      typeLabel,
      item.number,
      item.customer_name,
      item.vehicle_display,
      item.title,
      item.complaint,
      item.status,
      item.status_label,
      item.priority,
      item.priority_label,
      item.grand_total,
      item.total_amount,
      item.balance_due,
      item.promised_at,
      item.valid_until,
    ].filter(Boolean).join(" "),
  };
}

function canDragItem(item) {
  if (kindOf(item) === "estimate") return item.status === "draft";
  return Boolean(item.available_status_transitions?.length);
}

function nextStepHint(item) {
  if (kindOf(item) === "estimate") {
    if (item.status === "draft") return "Rascunho: envie para aprovação do cliente.";
    if (item.status === "sent") return "Aguardando aprovação do cliente. Ao aprovar, uma OS será aberta.";
    if (item.status === "approved") return "Aprovado: pode ser convertido em OS.";
    return "Fluxo finalizado no orçamento.";
  }
  return item.available_status_transitions?.length
    ? `Próxima etapa: ${item.available_status_transitions.map((entry) => entry.status_label).join(" ou ")}`
    : "Sem transição disponível";
}

function canEstimateMoveTo(item, columnKey) {
  if (columnKey === "awaiting_approval") return item.status === "draft";
  return false;
}

export default function WorkOrdersKanbanPage() {
  const location = useLocation();
  const returnState = buildReturnToState(location);
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [kind, setKind] = useState("");
  const [draggingKey, setDraggingKey] = useState(null);
  const [dropTarget, setDropTarget] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const visibleColumns = useMemo(() => {
    if (!status) return OPERATIONAL_COLUMNS;
    return OPERATIONAL_COLUMNS.filter((column) => column.key === status);
  }, [status]);

  const filteredItems = useMemo(() => {
    return items
      .filter((item) => !status || visualStatus(item) === status)
      .filter((item) => !priority || item.priority === priority)
      .filter((item) => !kind || kindOf(item) === kind);
  }, [items, kind, priority, status]);

  const groupedItems = useMemo(() => {
    return visibleColumns.reduce((acc, column) => {
      acc[column.key] = filteredItems.filter((item) => visualStatus(item) === column.key);
      return acc;
    }, {});
  }, [filteredItems, visibleColumns]);

  async function load(nextSearch = search, nextStatus = status, nextPriority = priority, nextKind = kind) {
    const normalizedSearch = String(nextSearch || "").trim();
    setLoading(true);
    setError("");

    try {
      const baseParams = {};
      if (normalizedSearch) baseParams.search = normalizedSearch;

      const [workOrders, estimates] = await Promise.all([
        nextKind === "estimate" ? Promise.resolve([]) : fetchAll("/workshop/work-orders/", baseParams),
        nextKind === "os" ? Promise.resolve([]) : fetchAll("/attendance/estimates/", baseParams),
      ]);

      let combined = [
        ...workOrders.map(normalizeWorkOrder),
        ...estimates.map(normalizeEstimate),
      ];

      if (nextStatus) combined = combined.filter((item) => visualStatus(item) === nextStatus);
      if (nextPriority) combined = combined.filter((item) => item.priority === nextPriority);
      if (nextKind) combined = combined.filter((item) => kindOf(item) === nextKind);

      setItems(combined);
    } catch (err) {
      setError(apiError(err));
    } finally {
      setLoading(false);
    }
  }

  function clearSearch() {
    setSearch("");
    setStatus("");
    setPriority("");
    setKind("");
    load("", "", "", "");
  }

  function selectSuggestion(suggestion, nextValue) {
    const selected = suggestion?.payload;
    setSearch(nextValue || "");

    if (selected?.id) {
      setItems([selected]);
      setStatus(visualStatus(selected));
      setPriority(selected.priority || "");
      setKind(kindOf(selected));
      return;
    }

    load(nextValue, status, priority, kind);
  }

  function handleStatusChange(value) {
    setStatus(value);
    load(search, value, priority, kind);
  }

  function handlePriorityChange(value) {
    setPriority(value);
    load(search, status, value, kind);
  }

  function handleKindChange(value) {
    setKind(value);
    load(search, status, priority, value);
  }

  useEffect(() => {
    load("", "", "", "");
  }, []);

  function onDragStart(event, item) {
    const key = itemKey(item);
    setDraggingKey(key);
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", key);
  }

  function onDragEnd() {
    setDraggingKey(null);
    setDropTarget("");
  }

  async function moveWorkOrder(item, columnKey, previousItems) {
    if (item.status === columnKey) return;

    const allowed = item.available_status_transitions || [];
    if (!allowed.some((entry) => entry.status === columnKey)) {
      const allowedLabels = allowed.map((entry) => entry.status_label).join(", ") || "nenhuma etapa";
      throw new Error(`${item.number} não pode ir de ${item.status_label || item.status} para esta coluna. Próximas etapas permitidas: ${allowedLabels}.`);
    }

    setItems((current) => current.map((entry) => itemKey(entry) === itemKey(item) ? { ...entry, status: columnKey, visual_status: columnKey } : entry));
    const response = await api.post(`/workshop/work-orders/${item.id}/change_status/`, {
      status: columnKey,
      note: "Status alterado pelo Kanban operacional.",
      send_notifications: true,
    });
    setItems((current) => current.map((entry) => itemKey(entry) === itemKey(item) ? normalizeWorkOrder({ ...entry, ...response.data.work_order }) : entry));
    setNotice(`${item.number} movida para ${OS_STATUS_LABELS[columnKey] || columnKey}.`);
  }

  async function moveEstimate(item, columnKey) {
    if (visualStatus(item) === columnKey) return;
    if (columnKey === "waiting_parts") {
      throw new Error(`${item.number} é um orçamento. Orçamento não entra em Aguardando peças.`);
    }
    if (columnKey === "completed") {
      throw new Error(`${item.number} só é finalizado por aprovação/rejeição/cancelamento no fluxo do orçamento.`);
    }
    if (!canEstimateMoveTo(item, columnKey)) {
      throw new Error(`${item.number} não pode ir de ${item.status_label || item.status} para esta coluna.`);
    }

    if (columnKey === "awaiting_approval") {
      const response = await api.post(`/attendance/estimates/${item.id}/create-customer-approval/`, {});
      setNotice(`${item.number} movido para aguardando aprovação.${response.data?.public_url ? " Link público gerado." : ""}`);
    } else {
      throw new Error(`${item.number} só pode sair de rascunho pelo envio para aprovação.`);
    }
    await load(search, status, priority, kind);
  }

  async function moveItem(key, columnKey) {
    const item = items.find((entry) => itemKey(entry) === key);
    if (!item) return;

    const previousItems = items;
    setSaving(true);
    setError("");
    setNotice("");

    try {
      if (kindOf(item) === "estimate") {
        await moveEstimate(item, columnKey);
      } else {
        await moveWorkOrder(item, columnKey, previousItems);
      }
    } catch (err) {
      setItems(previousItems);
      setError(err?.message || apiError(err));
    } finally {
      setSaving(false);
      setDraggingKey(null);
      setDropTarget("");
    }
  }

  function onDrop(event, columnKey) {
    event.preventDefault();
    const key = event.dataTransfer.getData("text/plain") || draggingKey;
    if (key) moveItem(key, columnKey);
  }

  return <div className="kanban-page">
    <PageHeader title="Kanban operacional" subtitle="Arraste OS e envie orçamentos rascunho para aprovação. Orçamento aprovado gera OS pelo fluxo de conversão.">
      <div className="d-flex gap-2 flex-wrap justify-content-end">
        <Button as={Link} to="/work-orders/new" state={returnState}>Nova OS</Button>
        <Button as={Link} to="/work-orders/estimates/new" state={returnState} variant="success">Novo orçamento</Button>
        <Button as={Link} to="/work-orders" variant="outline-secondary">Lista</Button>
        <Button as={Link} to="/work-orders/agenda" variant="outline-primary">Agenda</Button>
      </div>
    </PageHeader>

    <AreaTabs area="attendance" />
    <ErrorAlert error={error} onClose={() => setError("")}/>
    <SystemToast message={notice} variant="success" delay={3000} onClose={() => setNotice("")} />

    <Card className="border-0 shadow-sm mb-3">
      <Card.Body>
        <Row className="g-2 align-items-end">
          <Col xl={4} lg={6}>
            <Form.Label>Busca</Form.Label>
            <SearchAutocompleteInput
              placeholder="Buscar por número, cliente, placa, título, relato ou status"
              value={search}
              onChange={setSearch}
              onSearch={(value) => load(value, status, priority, kind)}
              onSelect={selectSuggestion}
              suggestions={items.map(itemSearchSuggestion)}
              disabled={loading || saving}
            />
          </Col>
          <Col xl={2} lg={3} sm={6}>
            <Form.Label>Tipo</Form.Label>
            <Form.Select value={kind} onChange={(event) => handleKindChange(event.target.value)} disabled={loading || saving}>
              <option value="">OS e orçamentos</option>
              <option value="os">Somente OS</option>
              <option value="estimate">Somente orçamentos</option>
            </Form.Select>
          </Col>
          <Col xl={2} lg={3} sm={6}>
            <Form.Label>Etapa</Form.Label>
            <Form.Select value={status} onChange={(event) => handleStatusChange(event.target.value)} disabled={loading || saving}>
              <option value="">Todas</option>
              {STATUS_FILTER_OPTIONS.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}
            </Form.Select>
          </Col>
          <Col xl={2} lg={3} sm={6}>
            <Form.Label>Prioridade</Form.Label>
            <Form.Select value={priority} onChange={(event) => handlePriorityChange(event.target.value)} disabled={loading || saving}>
              <option value="">Todas</option>
              {priorities.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </Form.Select>
          </Col>
          <Col xl={2} className="d-flex gap-2">
            <Button className="w-100" variant="outline-primary" onClick={() => load(search, status, priority, kind)} disabled={loading || saving}>
              {loading ? "Carregando..." : "Atualizar"}
            </Button>
            <Button className="w-100" variant="outline-secondary" onClick={clearSearch} disabled={loading || saving || (!search && !status && !priority && !kind)}>
              Limpar pesquisa
            </Button>
          </Col>
        </Row>
      </Card.Body>
    </Card>

    {saving && <Alert variant="info" className="py-2">Salvando movimentação...</Alert>}

    <div className="kanban-board operational-kanban-board">
      {visibleColumns.map((column) => {
        const columnItems = groupedItems[column.key] || [];
        return <section
          key={column.key}
          className={`kanban-column ${dropTarget === column.key ? "kanban-column-target" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setDropTarget(column.key);
          }}
          onDragLeave={() => setDropTarget("")}
          onDrop={(event) => onDrop(event, column.key)}
        >
          <div className="kanban-column-header">
            <span>{column.label}</span>
            <Badge bg="secondary">{columnItems.length}</Badge>
          </div>
          <div className="small text-muted mb-3">{column.description}</div>

          {loading ? <div className="text-center text-muted py-4"><Spinner size="sm"/> Carregando</div> : columnItems.length === 0 ? <div className="kanban-empty">Sem OS ou orçamento nesta etapa</div> : columnItems.map((item) => {
            const isEstimate = kindOf(item) === "estimate";
            const canDrag = canDragItem(item);
            const total = money(item.grand_total || item.total_amount);
            return <Card
              key={itemKey(item)}
              className={`kanban-card operational-card ${isEstimate ? "technical-card-estimate" : "technical-card-os"} ${String(draggingKey) === itemKey(item) ? "kanban-card-dragging" : ""} ${canDrag ? "" : "opacity-75"}`}
              draggable={canDrag && !saving}
              onDragStart={(event) => canDrag ? onDragStart(event, item) : event.preventDefault()}
              onDragEnd={onDragEnd}
            >
              <Card.Body>
                <div className="d-flex justify-content-between gap-2 mb-2 align-items-start">
                  <div className="min-width-0">
                    <div className="d-flex align-items-center gap-2 flex-wrap">
                      <Badge bg={isEstimate ? "info" : "primary"}>{isEstimate ? "Orçamento" : "OS"}</Badge>
                      <Link to={itemRoute(item)} state={returnState} className="fw-semibold text-decoration-none">{item.number}</Link>
                    </div>
                  </div>
                  <StatusBadge value={item.status} label={item.status_label}/>
                </div>
                <div className="fw-semibold small mb-1">{item.title || "Sem título"}</div>
                <div className="small text-muted">{item.customer_name || "Cliente não informado"}</div>
                <div className="small text-muted">{item.vehicle_display || "Sem veículo"}</div>
                <div className="d-flex justify-content-between mt-2 small">
                  <span>{isEstimate ? "Validade" : "Previsão"}</span>
                  <strong>{isEstimate ? formatDate(item.valid_until) : formatDate(item.promised_at)}</strong>
                </div>
                <div className="d-flex justify-content-between small">
                  <span>Total</span>
                  <strong>{total}</strong>
                </div>
                {!isEstimate ? <div className="d-flex justify-content-between small"><span>Saldo</span><strong>{money(item.balance_due)}</strong></div> : null}
                <div className="small text-muted mt-2">{nextStepHint(item)}</div>
                <div className="d-flex flex-wrap gap-2 justify-content-end mt-3">
                  <Button as={Link} to={itemRoute(item)} state={returnState} size="sm" variant="outline-secondary">Abrir</Button>
                  <Button as="a" href={apiUrl(itemPdfPath(item))} target="_blank" rel="noreferrer" size="sm" variant="outline-dark">PDF</Button>
                </div>
              </Card.Body>
            </Card>;
          })}
        </section>;
      })}
    </div>
  </div>;
}
