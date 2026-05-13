import React, { useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, Col, Form, Row, Spinner, Table } from "react-bootstrap";
import { Link, useLocation } from "react-router-dom";
import api, { apiError, results } from "../api/client";
import AreaTabs from "../components/AreaTabs";
import EmptyState from "../components/EmptyState";
import ErrorAlert from "../components/ErrorAlert";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { money, priorities } from "../workshopOptions";
import SearchAutocompleteInput from "../components/SearchAutocompleteInput";
import { buildReturnToState } from "../utils/returnTo";

const ESTIMATE_FINAL_STATUSES = new Set(["approved", "partially_approved", "rejected", "expired", "converted", "cancelled"]);
const STATUS_FILTER_OPTIONS = [
  { value: "open", label: "Aberta" },
  { value: "in_progress", label: "Diagnóstico / execução" },
  { value: "awaiting_approval", label: "Aguardando aprovação" },
  { value: "waiting_parts", label: "Aguardando peças" },
  { value: "completed", label: "Concluída / finalizada" },
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

function visualStatus(item) {
  if (kindOf(item) !== "estimate") return item.status;
  if (item.status === "diagnosis") return "in_progress";
  if (item.status === "awaiting_approval") return "awaiting_approval";
  if (ESTIMATE_FINAL_STATUSES.has(item.status)) return "completed";
  return "open";
}

function visualStatusLabel(item) {
  return STATUS_FILTER_OPTIONS.find((entry) => entry.value === visualStatus(item))?.label || item.status_label || item.status || "Sem etapa";
}

function normalizeWorkOrder(order) {
  return {
    ...order,
    kind: "os",
    operational_date: order.promised_at,
    display_total: order.grand_total,
    display_balance: order.balance_due,
    priority: order.priority || "normal",
    priority_label: order.priority_label || "Normal",
    visual_status: visualStatus({ ...order, kind: "os" }),
  };
}

function normalizeEstimate(estimate) {
  return {
    ...estimate,
    kind: "estimate",
    operational_date: estimate.valid_until,
    display_total: estimate.total_amount,
    display_balance: estimate.total_amount,
    priority: "normal",
    priority_label: "Normal",
    grand_total: estimate.total_amount,
    balance_due: estimate.total_amount,
    visual_status: visualStatus({ ...estimate, kind: "estimate" }),
  };
}

function parseDate(value) {
  if (!value) return null;
  const source = String(value);
  const date = source.includes("T") ? new Date(source) : new Date(`${source}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDateTime(value) {
  const date = parseDate(value);
  if (!date) return "-";
  return String(value || "").includes("T")
    ? new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(date)
    : new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" }).format(date);
}

function itemSearchSuggestion(item) {
  const isEstimate = kindOf(item) === "estimate";
  const typeLabel = isEstimate ? "Orçamento" : "OS";
  const title = [item.number, item.customer_name].filter(Boolean).join(" - ") || typeLabel;
  const status = item.status_label || item.status || "Sem status";
  const priority = item.priority_label || item.priority || "Sem prioridade";
  const vehicle = item.vehicle_display || "Sem veículo";
  const itemTitle = item.title || "Sem título";
  const total = `Total: ${money(item.display_total || item.grand_total || item.total_amount)}`;
  const balance = isEstimate ? "Fluxo: orçamento → OS" : `Saldo: ${money(item.display_balance || item.balance_due)}`;
  const dateLabel = isEstimate ? `Validade: ${formatDateTime(item.valid_until)}` : `Previsão: ${formatDateTime(item.promised_at)}`;

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
      item.display_total,
      item.display_balance,
      item.promised_at,
      item.valid_until,
    ].filter(Boolean).join(" "),
  };
}

function sortItems(a, b) {
  const aDate = parseDate(a.operational_date);
  const bDate = parseDate(b.operational_date);
  if (aDate && bDate) return bDate.getTime() - aDate.getTime();
  if (aDate) return -1;
  if (bDate) return 1;
  return String(a.number || "").localeCompare(String(b.number || ""));
}

export default function WorkOrdersPage() {
  const location = useLocation();
  const returnState = buildReturnToState(location);
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [kind, setKind] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const searchSuggestions = useMemo(() => items.map(itemSearchSuggestion), [items]);

  async function load(nextSearch = search, nextStatus = status, nextPriority = priority, nextKind = kind) {
    const normalizedSearch = String(nextSearch || "").trim();
    setLoading(true);
    setError("");

    try {
      const params = {};
      if (normalizedSearch) params.search = normalizedSearch;

      const [workOrders, estimates] = await Promise.all([
        nextKind === "estimate" ? Promise.resolve([]) : fetchAll("/workshop/work-orders/", params),
        nextKind === "os" ? Promise.resolve([]) : fetchAll("/attendance/estimates/", params),
      ]);

      let combined = [
        ...workOrders.map(normalizeWorkOrder),
        ...estimates.map(normalizeEstimate),
      ];

      if (nextStatus) combined = combined.filter((item) => visualStatus(item) === nextStatus);
      if (nextPriority) combined = combined.filter((item) => item.priority === nextPriority);
      if (nextKind) combined = combined.filter((item) => kindOf(item) === nextKind);

      setItems(combined.sort(sortItems));
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

  useEffect(() => { load("", "", "", ""); }, []);

  return <>
    <PageHeader title="Orçamentos / OS" subtitle="Lista única de orçamentos e ordens de serviço, com navegação rápida para lista, Kanban e agenda.">
      <div className="d-flex gap-2 flex-wrap justify-content-end">
        <Button as={Link} to="/work-orders/new" state={returnState}>Nova OS</Button>
        <Button as={Link} to="/work-orders/estimates/new" state={returnState} variant="success">Novo orçamento</Button>
        <Button as={Link} to="/work-orders/kanban" variant="outline-primary">Kanban</Button>
        <Button as={Link} to="/work-orders/agenda" variant="outline-primary">Agenda</Button>
      </div>
    </PageHeader>
    <AreaTabs area="attendance" />
    <ErrorAlert error={error} onClose={() => setError("")} />

    <Card className="border-0 shadow-sm mb-3">
      <Card.Body>
        <Row className="g-2 align-items-end">
          <Col xl={4} lg={6}>
            <Form.Label>Busca</Form.Label>
            <SearchAutocompleteInput
              placeholder="Buscar por número, cliente, placa, título, relato, status ou prioridade"
              value={search}
              onChange={setSearch}
              onSearch={(value) => load(value, status, priority, kind)}
              onSelect={selectSuggestion}
              suggestions={searchSuggestions}
              disabled={loading}
            />
          </Col>
          <Col xl={2} lg={3} sm={6}>
            <Form.Label>Tipo</Form.Label>
            <Form.Select value={kind} onChange={(event) => handleKindChange(event.target.value)} disabled={loading}>
              <option value="">OS e orçamentos</option>
              <option value="os">Somente OS</option>
              <option value="estimate">Somente orçamentos</option>
            </Form.Select>
          </Col>
          <Col xl={2} lg={3} sm={6}>
            <Form.Label>Etapa</Form.Label>
            <Form.Select value={status} onChange={(event) => handleStatusChange(event.target.value)} disabled={loading}>
              <option value="">Todas</option>
              {STATUS_FILTER_OPTIONS.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}
            </Form.Select>
          </Col>
          <Col xl={2} lg={3} sm={6}>
            <Form.Label>Prioridade</Form.Label>
            <Form.Select value={priority} onChange={(event) => handlePriorityChange(event.target.value)} disabled={loading}>
              <option value="">Todas</option>
              {priorities.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </Form.Select>
          </Col>
          <Col xl={2} className="d-flex gap-2">
            <Button className="w-100" variant="outline-primary" onClick={() => load(search, status, priority, kind)} disabled={loading}>
              {loading ? "Carregando..." : "Atualizar"}
            </Button>
            <Button className="w-100" variant="outline-secondary" onClick={clearSearch} disabled={loading || (!search && !status && !priority && !kind)}>Limpar</Button>
          </Col>
        </Row>
      </Card.Body>
    </Card>

    <Card className="border-0 shadow-sm">
      <Card.Body className="p-0">
        {loading ? <div className="text-center text-muted py-5"><Spinner size="sm" /> Carregando orçamentos e OS...</div> : items.length === 0 ? <EmptyState text="Nenhuma OS ou orçamento encontrado." /> : <Table responsive hover className="mb-0">
          <thead>
            <tr><th>Tipo</th><th>Número</th><th>Cliente</th><th>Veículo</th><th>Título</th><th>Etapa</th><th>Prioridade</th><th>Previsão/Validade</th><th>Total</th><th>Saldo</th><th></th></tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const isEstimate = kindOf(item) === "estimate";
              return <tr key={itemKey(item)} className={isEstimate ? "operation-row-estimate" : "operation-row-os"}>
                <td><Badge bg={isEstimate ? "success" : "primary"}>{isEstimate ? "Orçamento" : "OS"}</Badge></td>
                <td className="fw-semibold">{item.number}</td>
                <td>{item.customer_name || "-"}</td>
                <td>{item.vehicle_display || "-"}</td>
                <td>{item.title || "-"}</td>
                <td><StatusBadge value={visualStatus(item)} label={visualStatusLabel(item)} /></td>
                <td><StatusBadge value={item.priority} label={item.priority_label} /></td>
                <td>{formatDateTime(item.operational_date)}</td>
                <td>{money(item.display_total)}</td>
                <td>{isEstimate ? "-" : money(item.display_balance)}</td>
                <td><Button size="sm" as={Link} to={itemRoute(item)} state={returnState} variant={isEstimate ? "outline-success" : "outline-primary"}>Abrir</Button></td>
              </tr>;
            })}
          </tbody>
        </Table>}
      </Card.Body>
    </Card>
  </>;
}
