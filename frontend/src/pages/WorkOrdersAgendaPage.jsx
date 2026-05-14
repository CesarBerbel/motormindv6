import React, { useEffect, useMemo, useState } from "react";
import { Badge, Button, ButtonGroup, Card, Col, Form, Row, Spinner } from "../ui/TailwindPrimitives.jsx";
import { Link, useLocation } from "react-router-dom";
import api, { apiError, results } from "../api/client";
import AreaTabs from "../components/AreaTabs";
import DateInput from "../components/DateInput";
import EmptyState from "../components/EmptyState";
import ErrorAlert from "../components/ErrorAlert";
import PageHeader from "../components/PageHeader";
import SearchAutocompleteInput from "../components/SearchAutocompleteInput";
import StatusBadge from "../components/StatusBadge";
import { money, priorities } from "../workshopOptions";
import { buildReturnToState } from "../utils/returnTo";

const OS_FINAL_STATUSES = new Set(["delivered", "cancelled"]);
const ESTIMATE_FINAL_STATUSES = new Set(["approved", "rejected", "expired", "converted", "cancelled"]);
const VIEW_MODES = [
  ["day", "Dia"],
  ["week", "Semana"],
  ["month", "Mês"],
];
const WEEKDAY_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
const STATUS_FILTER_OPTIONS = [
  { value: "open", label: "Aberta" },
  { value: "in_progress", label: "Em execução" },
  { value: "awaiting_approval", label: "Aguardando aprovação" },
  { value: "waiting_parts", label: "Aguardando peças" },
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

function visualStatus(item) {
  if (kindOf(item) !== "estimate") return item.status;
  if (item.status === "sent") return "awaiting_approval";
  if (ESTIMATE_FINAL_STATUSES.has(item.status)) return "completed";
  return "open";
}

function statusLabelForVisual(value) {
  return STATUS_FILTER_OPTIONS.find((item) => item.value === value)?.label || value || "Sem etapa";
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
  };
}

function parseDate(value) {
  if (!value) return null;
  const source = String(value);
  const date = source.includes("T") ? new Date(source) : new Date(`${source}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function itemScheduledAt(item) {
  return kindOf(item) === "estimate" ? item.valid_until : item.promised_at;
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function cloneDate(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function dateKey(value) {
  const date = parseDate(value);
  if (!date) return "without-date";
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function dateOnly(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function addDays(date, amount) {
  const next = cloneDate(date);
  next.setDate(next.getDate() + amount);
  return next;
}

function addMonths(date, amount) {
  const next = cloneDate(date);
  next.setMonth(next.getMonth() + amount);
  return next;
}

function startOfWeek(date) {
  const base = cloneDate(date);
  const day = base.getDay();
  const offset = day === 0 ? -6 : 1 - day;
  base.setDate(base.getDate() + offset);
  return base;
}

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function endOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth() + 1, 1);
}

function formatDateInput(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function formatDateHeading(key) {
  if (key === "without-date") return "Sem data operacional";
  const date = new Date(`${key}T00:00:00`);
  const today = dateOnly(new Date());
  const target = dateOnly(date);
  const diffDays = Math.round((target.getTime() - today.getTime()) / 86400000);
  const label = new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" }).format(date);

  if (diffDays === 0) return `Hoje • ${label}`;
  if (diffDays === 1) return `Amanhã • ${label}`;
  if (diffDays === -1) return `Ontem • ${label}`;
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function formatShortDate(date) {
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit" }).format(date);
}

function formatLongDate(date) {
  return new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" }).format(date);
}

function formatMonthYear(date) {
  const label = new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric" }).format(date);
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function formatDateTime(value) {
  const date = parseDate(value);
  if (!date) return "Sem data";
  const hasTime = String(value || "").includes("T");
  return hasTime
    ? new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(date)
    : new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" }).format(date);
}

function formatTime(item) {
  const value = itemScheduledAt(item);
  const date = parseDate(value);
  if (!date) return "--:--";
  if (kindOf(item) === "estimate" || !String(value || "").includes("T")) return "Dia todo";
  return new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" }).format(date);
}

function isSameDate(a, b) {
  return dateOnly(a).getTime() === dateOnly(b).getTime();
}

function isFinalItem(item) {
  return kindOf(item) === "estimate" ? ESTIMATE_FINAL_STATUSES.has(item.status) : OS_FINAL_STATUSES.has(item.status);
}

function isOverdue(item) {
  const scheduled = parseDate(itemScheduledAt(item));
  if (!scheduled || isFinalItem(item)) return false;
  return dateOnly(scheduled).getTime() < dateOnly(new Date()).getTime();
}

function isToday(item) {
  const scheduled = parseDate(itemScheduledAt(item));
  if (!scheduled) return false;
  return isSameDate(scheduled, new Date());
}

function buildAgendaSuggestion(item) {
  const isEstimate = kindOf(item) === "estimate";
  const typeLabel = isEstimate ? "Orçamento" : "OS";
  const title = [item.number, item.customer_name].filter(Boolean).join(" - ") || typeLabel;
  const vehicle = item.vehicle_display || "Sem veículo";
  const status = item.status_label || item.status || "Sem status";
  const priority = item.priority_label || item.priority || "Sem prioridade";
  const scheduled = isEstimate ? `Validade: ${formatDateTime(item.valid_until)}` : `Previsão: ${formatDateTime(item.promised_at)}`;

  return {
    key: itemKey(item),
    label: `${typeLabel} ${title}`,
    value: title,
    description: [vehicle, item.title || "Sem título", status, priority].filter(Boolean).join(" • "),
    meta: [scheduled, `Total: ${money(item.grand_total || item.total_amount)}`, isEstimate ? "Fluxo: aprovação → OS" : `Saldo: ${money(item.balance_due)}`].join(" • "),
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
      item.promised_at,
      item.valid_until,
    ].filter(Boolean).join(" "),
  };
}

function sortItemsByScheduledAt(a, b) {
  const aDate = parseDate(itemScheduledAt(a));
  const bDate = parseDate(itemScheduledAt(b));
  if (!aDate && !bDate) return String(a.number || "").localeCompare(String(b.number || ""));
  if (!aDate) return 1;
  if (!bDate) return -1;
  return aDate.getTime() - bDate.getTime();
}

function buildPeriodDays(viewMode, referenceDate) {
  if (viewMode === "week") {
    const first = startOfWeek(referenceDate);
    return Array.from({ length: 7 }, (_, index) => addDays(first, index));
  }
  return [cloneDate(referenceDate)];
}

function buildMonthCells(referenceDate) {
  const first = startOfMonth(referenceDate);
  const lastExclusive = endOfMonth(referenceDate);
  const leadingBlanks = (first.getDay() + 6) % 7;
  const cells = Array.from({ length: leadingBlanks }, () => null);
  for (let day = cloneDate(first); day < lastExclusive; day = addDays(day, 1)) {
    cells.push(cloneDate(day));
  }
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

function getPeriodLabel(viewMode, referenceDate) {
  if (viewMode === "month") return formatMonthYear(referenceDate);
  if (viewMode === "week") {
    const first = startOfWeek(referenceDate);
    const last = addDays(first, 6);
    return `${formatShortDate(first)} a ${formatShortDate(last)}`;
  }
  const label = formatLongDate(referenceDate);
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function getPeriodStep(viewMode) {
  if (viewMode === "month") return "month";
  if (viewMode === "week") return "week";
  return "day";
}

function itemCard(item, linkState) {
  const overdue = isOverdue(item);
  const isEstimate = kindOf(item) === "estimate";
  return <Card key={itemKey(item)} className={`agenda-order-card operational-card ${isEstimate ? "technical-card-estimate" : "technical-card-os"} border-0 shadow-sm ${overdue ? "agenda-order-overdue" : ""}`}>
    <Card.Body>
      <div className="d-flex flex-wrap justify-content-between gap-3">
        <div className="min-width-0">
          <div className="d-flex flex-wrap align-items-center gap-2 mb-2">
            <Badge bg={isEstimate ? "info" : "primary"}>{isEstimate ? "Orçamento" : "OS"}</Badge>
            <Link to={itemRoute(item)} state={linkState} className="fw-semibold text-decoration-none">{item.number}</Link>
            {overdue ? <Badge bg="danger">Atrasado</Badge> : null}
            <StatusBadge value={item.status} label={item.status_label} />
            {!isEstimate ? <StatusBadge value={item.priority} label={item.priority_label} /> : null}
          </div>
          <div className="fw-semibold text-truncate">{item.title || "Sem título"}</div>
          <div className="text-muted small">{item.customer_name || "Cliente não informado"}</div>
          <div className="text-muted small">{item.vehicle_display || "Sem veículo"}</div>
        </div>
        <div className="agenda-order-meta text-lg-end">
          <div className="small text-muted">{isEstimate ? "Validade" : "Previsão"}</div>
          <div className="fw-semibold">{formatTime(item)}</div>
          <div className="small text-muted mt-2">{isEstimate ? "Total / fluxo" : "Total / saldo"}</div>
          <div className="fw-semibold">{money(item.grand_total || item.total_amount)}{isEstimate ? " / OS" : ` / ${money(item.balance_due)}`}</div>
        </div>
      </div>
      {item.complaint ? <div className="agenda-order-complaint small text-muted mt-3">{item.complaint}</div> : null}
    </Card.Body>
  </Card>;
}

export default function WorkOrdersAgendaPage() {
  const location = useLocation();
  const returnState = buildReturnToState(location);
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [kind, setKind] = useState("");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [includeFinished, setIncludeFinished] = useState(false);
  const [viewMode, setViewMode] = useState("week");
  const [referenceDate, setReferenceDate] = useState(() => dateOnly(new Date()));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load(nextSearch = search, nextStatus = status, nextPriority = priority, nextKind = kind) {
    setLoading(true);
    setError("");
    try {
      const params = {};
      const normalizedSearch = String(nextSearch || "").trim();
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

      setItems(combined);
    } catch (err) {
      setError(apiError(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load("", "", "", "");
  }, []);

  const filteredItems = useMemo(() => {
    return items
      .filter((item) => includeFinished || !isFinalItem(item))
      .filter((item) => !overdueOnly || isOverdue(item))
      .filter((item) => !status || visualStatus(item) === status)
      .filter((item) => !priority || item.priority === priority)
      .filter((item) => !kind || kindOf(item) === kind)
      .sort(sortItemsByScheduledAt);
  }, [items, includeFinished, overdueOnly, priority, status, kind]);

  const itemsWithDate = useMemo(() => filteredItems.filter((item) => Boolean(itemScheduledAt(item))), [filteredItems]);

  const itemsByDate = useMemo(() => {
    const map = new Map();
    itemsWithDate.forEach((item) => {
      const key = dateKey(itemScheduledAt(item));
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(item);
    });
    return map;
  }, [itemsWithDate]);

  const periodDays = useMemo(() => buildPeriodDays(viewMode, referenceDate), [viewMode, referenceDate]);
  const monthCells = useMemo(() => buildMonthCells(referenceDate), [referenceDate]);
  const periodLabel = useMemo(() => getPeriodLabel(viewMode, referenceDate), [viewMode, referenceDate]);

  const periodItemCount = useMemo(() => {
    if (viewMode === "month") {
      const month = referenceDate.getMonth();
      const year = referenceDate.getFullYear();
      return itemsWithDate.filter((item) => {
        const scheduled = parseDate(itemScheduledAt(item));
        return scheduled && scheduled.getMonth() === month && scheduled.getFullYear() === year;
      }).length;
    }

    return periodDays.reduce((total, day) => total + (itemsByDate.get(formatDateInput(day))?.length || 0), 0);
  }, [itemsByDate, itemsWithDate, periodDays, referenceDate, viewMode]);

  const summary = useMemo(() => {
    const activeItems = items.filter((item) => !isFinalItem(item));
    const scheduled = activeItems.filter((item) => Boolean(itemScheduledAt(item)));
    return {
      active: activeItems.length,
      os: activeItems.filter((item) => kindOf(item) === "os").length,
      estimates: activeItems.filter((item) => kindOf(item) === "estimate").length,
      scheduled: scheduled.length,
      overdue: activeItems.filter(isOverdue).length,
      today: scheduled.filter(isToday).length,
      withoutDate: activeItems.filter((item) => !itemScheduledAt(item)).length,
    };
  }, [items]);

  function clearSearch() {
    setSearch("");
    setStatus("");
    setPriority("");
    setKind("");
    setOverdueOnly(false);
    setIncludeFinished(false);
    load("", "", "", "");
  }

  function selectSuggestion(suggestion, nextValue) {
    const selected = suggestion?.payload;
    setSearch(nextValue || "");
    if (selected?.id) {
      setItems([selected]);
      setStatus(visualStatus(selected));
      setKind(kindOf(selected));
      setPriority(selected.priority || "");
      const scheduled = parseDate(itemScheduledAt(selected));
      if (scheduled) setReferenceDate(dateOnly(scheduled));
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

  function movePeriod(direction) {
    const step = getPeriodStep(viewMode);
    if (step === "month") {
      setReferenceDate((current) => addMonths(current, direction));
      return;
    }
    setReferenceDate((current) => addDays(current, step === "week" ? direction * 7 : direction));
  }

  function renderDaySection(day) {
    const key = formatDateInput(day);
    const dayItems = itemsByDate.get(key) || [];
    const overdueCount = dayItems.filter(isOverdue).length;
    const osCount = dayItems.filter((item) => kindOf(item) === "os").length;
    const estimateCount = dayItems.filter((item) => kindOf(item) === "estimate").length;
    return <section key={key} className={`agenda-day ${overdueCount ? "agenda-day-overdue" : ""}`}>
      <div className="agenda-day-header">
        <div>
          <h5 className="mb-1">{formatDateHeading(key)}</h5>
          <div className="text-muted small">{dayItems.length} item(ns){osCount ? ` • ${osCount} OS` : ""}{estimateCount ? ` • ${estimateCount} orçamento(s)` : ""}{overdueCount ? ` • ${overdueCount} atrasado(s)` : ""}</div>
        </div>
        <Badge bg={overdueCount ? "danger" : "secondary"}>{dayItems.length}</Badge>
      </div>

      {dayItems.length ? <div className="agenda-order-list">{dayItems.map((item) => itemCard(item, returnState))}</div> : <Card className="border-0 shadow-sm agenda-empty-day"><Card.Body className="text-muted small">Nenhuma OS ou orçamento para este dia.</Card.Body></Card>}
    </section>;
  }

  function renderMonthView() {
    return <Card className="border-0 shadow-sm">
      <Card.Body>
        <div className="agenda-month-grid agenda-month-weekdays mb-2">
          {WEEKDAY_LABELS.map((label) => <div key={label} className="agenda-month-weekday">{label}</div>)}
        </div>
        <div className="agenda-month-grid">
          {monthCells.map((date, index) => {
            if (!date) return <div key={`blank-${index}`} className="agenda-month-cell agenda-month-cell-empty" />;
            const key = formatDateInput(date);
            const count = itemsByDate.get(key)?.length || 0;
            const overdueCount = itemsByDate.get(key)?.filter(isOverdue).length || 0;
            const today = isSameDate(date, new Date());
            return <button
              key={key}
              type="button"
              className={`agenda-month-cell ${count ? "agenda-month-cell-has-orders" : ""} ${today ? "agenda-month-cell-today" : ""}`}
              onClick={() => {
                if (!count) return;
                setReferenceDate(dateOnly(date));
                setViewMode("day");
              }}
              disabled={!count}
              title={count ? `${count} item(ns) na agenda` : "Sem item na agenda"}
            >
              <span className="agenda-month-day-number">{date.getDate()}</span>
              <span className={`agenda-month-count ${overdueCount ? "agenda-month-count-overdue" : ""}`}>{count} item(ns)</span>
            </button>;
          })}
        </div>
        <div className="text-muted small mt-3">Na visão mensal, cada dia mostra a quantidade de OS e orçamentos. Clique em um dia com itens para abrir a visão diária.</div>
      </Card.Body>
    </Card>;
  }

  const showEmptyPeriod = !loading && periodItemCount === 0;

  return <>
    <PageHeader title="Agenda operacional" subtitle="Visualize OS por previsão de entrega e orçamentos por validade, com cores diferentes para cada tipo.">
      <div className="d-flex gap-2 flex-wrap justify-content-end">
        <Button as={Link} to="/work-orders/new" state={returnState}>Nova OS</Button>
        <Button as={Link} to="/work-orders/estimates/new" state={returnState} variant="success">Novo orçamento</Button>
        <Button as={Link} to="/work-orders" variant="outline-secondary">Lista</Button>
        <Button as={Link} to="/work-orders/kanban" variant="outline-primary">Kanban</Button>
      </div>
    </PageHeader>
    <AreaTabs area="attendance" />
    <ErrorAlert error={error} onClose={() => setError("")} />

    <Row className="g-3 mb-3">
      <Col sm={6} xl={3}>
        <Card className="border-0 shadow-sm h-100"><Card.Body><div className="text-muted small">Itens ativos</div><div className="fs-3 fw-semibold">{summary.active}</div><div className="small text-muted">{summary.os} OS • {summary.estimates} orçamento(s)</div></Card.Body></Card>
      </Col>
      <Col sm={6} xl={3}>
        <Card className="border-0 shadow-sm h-100"><Card.Body><div className="text-muted small">Com data</div><div className="fs-3 fw-semibold">{summary.scheduled}</div></Card.Body></Card>
      </Col>
      <Col sm={6} xl={3}>
        <Card className="border-0 shadow-sm h-100"><Card.Body><div className="text-muted small">Atrasados</div><div className="fs-3 fw-semibold text-danger">{summary.overdue}</div></Card.Body></Card>
      </Col>
      <Col sm={6} xl={3}>
        <Card className="border-0 shadow-sm h-100"><Card.Body><div className="text-muted small">Para hoje</div><div className="fs-3 fw-semibold">{summary.today}</div><div className="small text-muted">Sem data: {summary.withoutDate}</div></Card.Body></Card>
      </Col>
    </Row>

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
              suggestions={filteredItems.map(buildAgendaSuggestion)}
            />
          </Col>
          <Col xl={2} lg={3} sm={6}>
            <Form.Label>Tipo</Form.Label>
            <Form.Select value={kind} onChange={(event) => handleKindChange(event.target.value)}>
              <option value="">OS e orçamentos</option>
              <option value="os">Somente OS</option>
              <option value="estimate">Somente orçamentos</option>
            </Form.Select>
          </Col>
          <Col xl={2} lg={3} sm={6}>
            <Form.Label>Etapa</Form.Label>
            <Form.Select value={status} onChange={(event) => handleStatusChange(event.target.value)}>
              <option value="">Todas</option>
              {STATUS_FILTER_OPTIONS.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}
            </Form.Select>
          </Col>
          <Col xl={2} lg={3} sm={6}>
            <Form.Label>Prioridade</Form.Label>
            <Form.Select value={priority} onChange={(event) => handlePriorityChange(event.target.value)}>
              <option value="">Todas</option>
              {priorities.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </Form.Select>
          </Col>
          <Col xl={2}>
            <div className="d-flex flex-wrap gap-3 align-items-center justify-content-xl-end">
              <Form.Check
                type="switch"
                id="agenda-overdue-only"
                label="Atrasados"
                checked={overdueOnly}
                onChange={(event) => setOverdueOnly(event.target.checked)}
              />
              <Form.Check
                type="switch"
                id="agenda-include-finished"
                label="Finalizados"
                checked={includeFinished}
                onChange={(event) => setIncludeFinished(event.target.checked)}
              />
              <Button variant="outline-secondary" onClick={clearSearch} disabled={!search && !status && !priority && !kind && !overdueOnly && !includeFinished}>Limpar pesquisa</Button>
            </div>
          </Col>
        </Row>
      </Card.Body>
    </Card>

    <Card className="border-0 shadow-sm mb-3">
      <Card.Body>
        <Row className="g-2 align-items-center">
          <Col lg={4}>
            <ButtonGroup className="agenda-view-toggle" aria-label="Tipo de visão da agenda">
              {VIEW_MODES.map(([value, label]) => <Button key={value} variant={viewMode === value ? "primary" : "outline-primary"} onClick={() => setViewMode(value)}>{label}</Button>)}
            </ButtonGroup>
          </Col>
          <Col lg={4} className="text-lg-center">
            <div className="fw-semibold fs-5">{periodLabel}</div>
            <div className="text-muted small">{periodItemCount} item(ns) no período{status ? ` • ${statusLabelForVisual(status)}` : ""}</div>
          </Col>
          <Col lg={4}>
            <div className="d-flex flex-wrap gap-2 justify-content-lg-end">
              <Button variant="outline-secondary" onClick={() => movePeriod(-1)}>Anterior</Button>
              <Button variant="outline-secondary" onClick={() => setReferenceDate(dateOnly(new Date()))}>Hoje</Button>
              <Button variant="outline-secondary" onClick={() => movePeriod(1)}>Próximo</Button>
              <DateInput
                value={formatDateInput(referenceDate)}
                onChange={(event) => {
                  if (!event.target.value) return;
                  setReferenceDate(new Date(`${event.target.value}T00:00:00`));
                }}
                className="agenda-date-picker"
              />
            </div>
          </Col>
        </Row>
      </Card.Body>
    </Card>

    {loading ? <Card className="border-0 shadow-sm"><Card.Body className="text-center text-muted py-5"><Spinner size="sm" className="me-2" />Carregando agenda...</Card.Body></Card> : null}

    {showEmptyPeriod ? <Card className="border-0 shadow-sm mb-3"><Card.Body><EmptyState title="Nenhuma OS ou orçamento encontrado" description="Não há itens para o período e filtros selecionados." /></Card.Body></Card> : null}

    {!loading && viewMode === "month" ? renderMonthView() : null}

    {!loading && viewMode !== "month" ? <div className={`agenda-timeline agenda-timeline-${viewMode}`}>
      {periodDays.map(renderDaySection)}
    </div> : null}
  </>;
}
