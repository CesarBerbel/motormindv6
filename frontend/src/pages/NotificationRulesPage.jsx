import React, { useEffect, useState } from "react";
import { Button, Card, Col, Form, Modal, Row, Table } from "react-bootstrap";
import api, { apiError, results } from "../api/client";
import EmptyState from "../components/EmptyState";
import ErrorAlert from "../components/ErrorAlert";
import FormTabs, { TabPanel } from "../components/FormTabs";
import TabbedFormFooter, { InlineTabbedFormFooter } from "../components/TabbedFormFooter";
import NoticeBox from "../components/NoticeBox";
import PageHeader from "../components/PageHeader";
import SearchAutocompleteInput from "../components/SearchAutocompleteInput";
import StatusBadge from "../components/StatusBadge";
import SystemToast from "../components/SystemToast";
import { buildSearchSuggestions } from "../utils/search";
import { estimateStatuses, workOrderStatuses } from "../workshopOptions";
import { confirmDialog } from "../components/ConfirmDialog";

const empty = () => ({ name: "", entity_type: "work_order", trigger_status: "open", channel: "whatsapp", template_id: "", recipient_target: "customer", is_active: true, send_once_per_status: true });

const modalTabs = [
  { key: "rule", label: "Regra", description: "Nome e status gatilho" },
  { key: "message", label: "Mensagem", description: "Canal, destinatário e template" },
  { key: "behavior", label: "Comportamento", description: "Ativação e repetição" },
];

export default function NotificationRulesPage() {
  const [items, setItems] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [form, setForm] = useState(empty());
  const [editing, setEditing] = useState(null);
  const [show, setShow] = useState(false);
  const [activeTab, setActiveTab] = useState("rule");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [entityType, setEntityType] = useState("");
  const [channel, setChannel] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function load(overrides = {}) {
    if (typeof overrides === "string") overrides = { search: overrides };
    try {
      const currentSearch = Object.prototype.hasOwnProperty.call(overrides, "search") ? overrides.search : search;
      const currentEntityType = Object.prototype.hasOwnProperty.call(overrides, "entityType") ? overrides.entityType : entityType;
      const currentStatus = Object.prototype.hasOwnProperty.call(overrides, "status") ? overrides.status : status;
      const currentChannel = Object.prototype.hasOwnProperty.call(overrides, "channel") ? overrides.channel : channel;
      const params = {};
      if (currentSearch) params.search = currentSearch;
      if (currentEntityType) params.entity_type = currentEntityType;
      if (currentStatus) params.trigger_status = currentStatus;
      if (currentChannel) params.channel = currentChannel;
      const [rulesRes, templatesRes] = await Promise.all([
        api.get("/workshop/notification-rules/", { params }),
        api.get("/templates/", { params: { active: "true" } }),
      ]);
      setItems(results(rulesRes.data));
      setTemplates(results(templatesRes.data));
    } catch (err) {
      setError(apiError(err));
    }
  }

  useEffect(() => { load(); }, [entityType, status, channel]);

  function clearSearch() {
    setSearch("");
    setEntityType("");
    setStatus("");
    setChannel("");
    load({ search: "", entityType: "", status: "", channel: "" });
  }

  function open(rule = null) {
    setEditing(rule);
    setForm(rule ? { ...rule, template_id: rule.template || "" } : empty());
    setActiveTab("rule");
    setShow(true);
  }

  function update(patch) {
    setForm((current) => ({ ...current, ...patch }));
  }

  async function save(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    try {
      const payload = { ...form, template_id: Number(form.template_id) };
      if (editing) await api.put(`/workshop/notification-rules/${editing.id}/`, payload);
      else await api.post("/workshop/notification-rules/", payload);
      setShow(false);
      setSuccess(editing ? "Regra de notificação atualizada com sucesso." : "Regra de notificação criada com sucesso.");
      await load();
    } catch (err) {
      setError(apiError(err));
    }
  }

  async function remove(rule) {
    if (!(await confirmDialog(`Excluir regra ${rule.name}?`))) return;
    setError("");
    setSuccess("");
    try {
      await api.delete(`/workshop/notification-rules/${rule.id}/`);
      setSuccess("Regra de notificação excluída com sucesso.");
      await load();
    } catch (err) {
      setError(apiError(err));
    }
  }

  const statusOptions = (form.entity_type || "work_order") === "estimate" ? estimateStatuses : workOrderStatuses;
  const filterStatusOptions = entityType === "estimate" ? estimateStatuses : workOrderStatuses;
  const templatesForChannel = templates.filter((template) => template.channel === form.channel);

  return <>
    <PageHeader title="Notificações automáticas de OS e orçamento" subtitle="Dispare templates de email ou WhatsApp quando a ordem de serviço ou o orçamento mudar de status.">
      <Button onClick={() => open()}>Nova regra</Button>
    </PageHeader>
    <ErrorAlert error={error} onClose={() => setError("")} />
    <SystemToast message={success} variant="success" delay={3000} onClose={() => setSuccess("")} />

    <Card className="border-0 shadow-sm mb-3">
      <Card.Body>
        <Row className="g-2">
          <Col lg={4}>
            <SearchAutocompleteInput placeholder="Buscar regra ou template" value={search} onChange={setSearch} onSearch={load} suggestions={buildSearchSuggestions(items, ["name", "template_name", "trigger_status", "channel"])} />
          </Col>
          <Col lg={2}>
            <Form.Select value={entityType} onChange={(event) => { setEntityType(event.target.value); setStatus(""); }}>
              <option value="">OS e orçamento</option>
              <option value="work_order">Somente OS</option>
              <option value="estimate">Somente orçamento</option>
            </Form.Select>
          </Col>
          <Col lg={2}>
            <Form.Select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">Todos os status</option>
              {filterStatusOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </Form.Select>
          </Col>
          <Col lg={2}>
            <Form.Select value={channel} onChange={(event) => setChannel(event.target.value)}>
              <option value="">Canal</option>
              <option value="email">Email</option>
              <option value="whatsapp">WhatsApp</option>
            </Form.Select>
          </Col>
          <Col lg={1}><Button className="w-100" variant="outline-primary" onClick={() => load()}>Buscar</Button></Col>
          <Col lg={2}><Button className="w-100" variant="outline-secondary" onClick={clearSearch} disabled={!search && !entityType && !status && !channel}>Limpar pesquisa</Button></Col>
        </Row>
      </Card.Body>
    </Card>

    <Card className="border-0 shadow-sm">
      <Card.Body className="p-0">
        {items.length === 0 ? <EmptyState /> : (
          <Table responsive hover className="mb-0">
            <thead><tr><th>Regra</th><th>Documento</th><th>Status gatilho</th><th>Canal</th><th>Destinatário</th><th>Template</th><th>Envio único</th><th>Ativa</th><th></th></tr></thead>
            <tbody>{items.map((rule) => (
              <tr key={rule.id}>
                <td className="fw-semibold">{rule.name}</td>
                <td>{rule.entity_type === "estimate" ? "Orçamento" : "OS"}</td>
                <td><StatusBadge value={rule.trigger_status} label={rule.trigger_status_label} /></td>
                <td><StatusBadge value={rule.channel} /></td>
                <td>{rule.recipient_target === "workshop" ? "Oficina" : rule.recipient_target === "both" ? "Cliente e oficina" : "Cliente"}</td>
                <td>{rule.template_name}</td>
                <td>{rule.send_once_per_status ? "Sim" : "Não"}</td>
                <td>{rule.is_active ? "Sim" : "Não"}</td>
                <td className="text-end">
                  <Button size="sm" variant="outline-primary" onClick={() => open(rule)} className="me-2">Editar</Button>
                  <Button size="sm" variant="outline-danger" onClick={() => remove(rule)}>Excluir</Button>
                </td>
              </tr>
            ))}</tbody>
          </Table>
        )}
      </Card.Body>
    </Card>

    <Modal keyboard={false} backdrop="static" size="lg" show={show} onHide={() => setShow(false)} dialogClassName="modal-wide-tabs" className="floating-form-modal">
      <Form onSubmit={save}>
        <Modal.Header closeButton><Modal.Title>{editing ? "Editar" : "Nova"} regra</Modal.Title></Modal.Header>
        <Modal.Body>
          <FormTabs tabs={modalTabs} activeKey={activeTab} onSelect={setActiveTab} className="mb-3" />

          <TabPanel activeKey={activeTab} eventKey="rule">
            <Row className="g-3">
              <Col md={4}>
                <Form.Group>
                  <Form.Label>Nome da regra</Form.Label>
                  <Form.Control required value={form.name} onChange={(event) => update({ name: event.target.value })} />
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group>
                  <Form.Label>Documento</Form.Label>
                  <Form.Select value={form.entity_type || "work_order"} onChange={(event) => update({ entity_type: event.target.value, trigger_status: event.target.value === "estimate" ? "open" : "open" })}>
                    <option value="work_order">Ordem de serviço</option>
                    <option value="estimate">Orçamento</option>
                  </Form.Select>
                  <Form.Text>Escolha se a regra será disparada pelo status da OS ou pelo status do orçamento.</Form.Text>
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group>
                  <Form.Label>Status gatilho</Form.Label>
                  <Form.Select value={form.trigger_status} onChange={(event) => update({ trigger_status: event.target.value })}>
                    {statusOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </Form.Select>
                </Form.Group>
              </Col>
            </Row>
          </TabPanel>

          <TabPanel activeKey={activeTab} eventKey="message">
            <Row className="g-3">
              <Col md={4}>
                <Form.Group>
                  <Form.Label>Canal</Form.Label>
                  <Form.Select value={form.channel} onChange={(event) => update({ channel: event.target.value, template_id: "" })}>
                    <option value="whatsapp">WhatsApp</option>
                    <option value="email">Email</option>
                  </Form.Select>
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group>
                  <Form.Label>Enviar para</Form.Label>
                  <Form.Select value={form.recipient_target || "customer"} onChange={(event) => update({ recipient_target: event.target.value })}>
                    <option value="customer">Cliente</option>
                    <option value="workshop">Oficina</option>
                    <option value="both">Cliente e oficina</option>
                  </Form.Select>
                  <Form.Text>Email e WhatsApp da oficina são os cadastrados no admin.</Form.Text>
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group>
                  <Form.Label>Template</Form.Label>
                  <Form.Select required value={form.template_id || ""} onChange={(event) => update({ template_id: event.target.value })}>
                    <option value="">Selecione</option>
                    {templatesForChannel.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
                  </Form.Select>
                  <Form.Text>O canal da regra precisa ser igual ao canal do template.</Form.Text>
                </Form.Group>
              </Col>
            </Row>
          </TabPanel>

          <TabPanel activeKey={activeTab} eventKey="behavior">
            <Row className="g-3">
              <Col md={6}>
                <Form.Check label="Ativa" checked={!!form.is_active} onChange={(event) => update({ is_active: event.target.checked })} />
              </Col>
              <Col md={6}>
                <Form.Check label="Enviar só uma vez para este status em cada documento" checked={!!form.send_once_per_status} onChange={(event) => update({ send_once_per_status: event.target.checked })} />
              </Col>
            </Row>
            <NoticeBox variant="info" className="mt-3" title="Controle contra envio repetido">
              Quando o envio único está ativo, a mesma OS ou o mesmo orçamento não recebe novamente esta regra ao permanecer no mesmo status.
            </NoticeBox>
          </TabPanel>
        </Modal.Body>
        <TabbedFormFooter tabs={modalTabs} activeKey={activeTab} onSelect={setActiveTab} onCancel={() => setShow(false)} saveLabel="Salvar" />
      </Form>
    </Modal>
  </>;
}
