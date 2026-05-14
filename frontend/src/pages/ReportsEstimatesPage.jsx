import React, { useEffect, useState } from "react";
import { Badge, Button, Card, Col, Form, Row, Table } from "../ui/TailwindPrimitives.jsx";
import DateInput from "../components/DateInput";
import { Link } from "react-router-dom";
import api, { apiError } from "../api/client";
import AreaTabs from "../components/AreaTabs";
import EmptyState from "../components/EmptyState";
import ErrorAlert from "../components/ErrorAlert";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { dateInputValue, estimateStatuses, formatDate, money } from "../workshopOptions";

function firstDay() { return dateInputValue(new Date(new Date().getFullYear(), new Date().getMonth(), 1)); }
function Kpi({ label, value }) { return <Col md={3}><Card className="card-kpi h-100"><Card.Body><div className="text-muted small">{label}</div><div className="display-6 fw-bold">{value}</div></Card.Body></Card></Col>; }

async function downloadCsv(endpoint, params, filename) {
  const response = await api.get(endpoint, { params, responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([response.data], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

const statusVariant = { draft: "secondary", sent: "warning", approved: "success", rejected: "danger", expired: "warning", converted: "primary", cancelled: "dark" };

export default function ReportsEstimatesPage() {
  const [filters, setFilters] = useState({ start_date: firstDay(), end_date: dateInputValue(), status: "", search: "" });
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try { setData((await api.get("/reports/estimates/", { params: filters })).data); }
    catch (err) { setError(apiError(err)); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function exportCsv() {
    try { await downloadCsv("/reports/estimates/export.csv", filters, "relatorio-orcamentos.csv"); }
    catch (err) { setError(apiError(err)); }
  }

  const s = data?.summary || {};
  return <>
    <PageHeader
      title="Relatório de orçamentos"
      subtitle="Acompanhe valor em orçamentos, aprovações, conversões em OS e pendências de aprovação."
      actions={<div className="d-flex gap-2 flex-wrap"><Link className="btn btn-outline-secondary" to="/reports/executive">Dashboard executivo</Link><Link className="btn btn-outline-primary" to="/reports/work-orders">Relatório de OS</Link></div>}
    />
    <AreaTabs area="reports" />
    <ErrorAlert error={error} onClose={() => setError("")} />
    <Card className="border-0 shadow-sm mb-4"><Card.Body><Row className="g-3 align-items-end">
      <Col md={2}><Form.Label>Data inicial</Form.Label><DateInput value={filters.start_date} onChange={(e)=>setFilters({...filters,start_date:e.target.value})}/></Col>
      <Col md={2}><Form.Label>Data final</Form.Label><DateInput value={filters.end_date} onChange={(e)=>setFilters({...filters,end_date:e.target.value})}/></Col>
      <Col md={3}><Form.Label>Status</Form.Label><Form.Select value={filters.status} onChange={(e)=>setFilters({...filters,status:e.target.value})}><option value="">Todos</option>{estimateStatuses.map(([v,l])=><option key={v} value={v}>{l}</option>)}</Form.Select></Col>
      <Col md={3}><Form.Label>Busca</Form.Label><Form.Control value={filters.search} placeholder="Número, cliente, placa..." onChange={(e)=>setFilters({...filters,search:e.target.value})}/></Col>
      <Col md="auto"><Button onClick={load} disabled={loading}>{loading?"Filtrando...":"Filtrar"}</Button></Col>
      <Col md="auto"><Button variant="outline-success" onClick={exportCsv}>Exportar CSV</Button></Col>
    </Row></Card.Body></Card>

    <Row className="g-3 mb-4">
      <Kpi label="Orçamentos no período" value={s.count || 0}/>
      <Kpi label="Total em orçamentos" value={money(s.total_amount)}/>
      <Kpi label="Ticket médio" value={money(s.ticket_average)}/>
      <Kpi label="Taxa de aprovação" value={`${s.approval_rate || 0}%`}/>
      <Kpi label="Aguardando aprovação" value={s.pending_approval_count || 0}/>
      <Kpi label="Aprovados" value={s.approved_count || 0}/>
      <Kpi label="Convertidos em OS" value={s.converted_count || 0}/>
      <Kpi label="Rejeitados" value={s.rejected_count || 0}/>
    </Row>

    <Row className="g-3 mb-4">
      <Col lg={6}><Card className="border-0 shadow-sm h-100"><Card.Header className="bg-white fw-semibold">Status dos orçamentos</Card.Header><Card.Body>{(data?.status_breakdown||[]).length===0?<EmptyState text="Sem dados no período."/>:(data?.status_breakdown||[]).map((row)=><div key={row.key} className="d-flex justify-content-between border-bottom py-2"><span>{row.label}</span><Badge bg={statusVariant[row.key]||"secondary"}>{row.count}</Badge></div>)}</Card.Body></Card></Col>
    </Row>

    <Card className="border-0 shadow-sm"><Card.Header className="bg-white fw-semibold">Orçamentos</Card.Header><Card.Body className="p-0">{(data?.rows||[]).length===0?<EmptyState text="Nenhum orçamento encontrado."/>:<Table responsive hover className="mb-0"><thead><tr><th>Número</th><th>Criação</th><th>Validade</th><th>Cliente</th><th>Veículo</th><th>Título</th><th>Status</th><th>Total</th><th>OS convertida</th><th></th></tr></thead><tbody>{data.rows.map((row)=><tr key={row.id} className="operation-row-estimate"><td className="fw-semibold">{row.number}</td><td>{formatDate(row.created_at)}</td><td>{formatDate(row.valid_until)}</td><td>{row.customer_name}</td><td>{row.vehicle_display||"-"}</td><td>{row.title||"-"}</td><td><StatusBadge value={row.status} label={row.status_label}/></td><td>{money(row.total_amount)}</td><td>{row.converted_work_order_number||"-"}</td><td><Link to={`/work-orders/estimates/${row.id}/edit`}>Abrir</Link></td></tr>)}</tbody></Table>}</Card.Body></Card>
  </>;
}
