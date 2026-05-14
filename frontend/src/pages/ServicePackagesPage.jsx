import React, { useEffect, useMemo, useState } from "react";
import { Button, Card, Col, Form, Modal, Row, Table } from "../ui/TailwindPrimitives.jsx";
import IntegerInput from "../components/IntegerInput";
import api, { apiError, results } from "../api/client";
import EmptyState from "../components/EmptyState";
import ErrorAlert from "../components/ErrorAlert";
import FormTabs, { TabPanel } from "../components/FormTabs";
import TabbedFormFooter, { InlineTabbedFormFooter } from "../components/TabbedFormFooter";
import MoneyInput from "../components/MoneyInput";
import PageHeader from "../components/PageHeader";
import AreaTabs from "../components/AreaTabs";
import SearchableSelect from "../components/SearchableSelect";
import { money } from "../workshopOptions";
import SearchAutocompleteInput from "../components/SearchAutocompleteInput";
import { confirmDialog } from "../components/ConfirmDialog";

let localIdCounter = 0;
function makeLocalId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  localIdCounter += 1;
  return `local-${Date.now()}-${localIdCounter}`;
}

const emptyPackage = () => ({
  code: "",
  name: "",
  description: "",
  discount_percent: "",
  is_active: true,
  items: [],
});

const emptyItem = () => ({
  local_id: makeLocalId(),
  service_id: "",
  description: "",
  quantity: "1",
  unit_price: "",
  position: "",
});

const tabs = [
  { key: "package", label: "Pacote", description: "Código, nome, descrição e status" },
  { key: "items", label: "Serviços", description: "Itens pesquisáveis e valores" },
];

function packageSearchSuggestion(servicePackage) {
  const title = [servicePackage.code, servicePackage.name].filter(Boolean).join(" - ") || "Pacote sem nome";
  const packageItems = servicePackage.items || [];
  const itemSummary = packageItems.map((line) => {
    const serviceLabel = [line.service_code, line.service_name || line.description].filter(Boolean).join(" - ");
    const quantity = line.quantity ? `Qtd. ${line.quantity}` : "";
    return [serviceLabel, quantity].filter(Boolean).join(" ");
  }).filter(Boolean).join(" • ");
  const status = servicePackage.is_active ? "Ativo" : "Inativo";
  const totals = [
    `${packageItems.length || 0} serviço(s)`,
    `Subtotal: ${money(servicePackage.subtotal_amount)}`,
    `Desconto: ${servicePackage.discount_percent || "0.00"}% (${money(servicePackage.discount_amount)})`,
    `Total: ${money(servicePackage.total_amount)}`,
  ].join(" • ");

  return {
    key: servicePackage.id,
    label: title,
    value: title,
    description: totals,
    meta: [itemSummary, servicePackage.description, status].filter(Boolean).join(" • "),
    payload: servicePackage,
    searchText: [
      title,
      servicePackage.code,
      servicePackage.name,
      servicePackage.description,
      status,
      servicePackage.subtotal_amount,
      servicePackage.discount_amount,
      servicePackage.discount_percent,
      servicePackage.total_amount,
      ...packageItems.flatMap((line) => [
        line.service_code,
        line.service_name,
        line.service_category_name,
        line.description,
        line.quantity,
        line.unit_price,
      ]),
    ].filter(Boolean).join(" "),
  };
}

function buildPackageSearchSuggestions(packages) {
  return (packages || []).map(packageSearchSuggestion);
}

function decimal(value) {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function itemSubtotal(item) {
  return decimal(item.quantity) * decimal(item.unit_price);
}

export default function ServicePackagesPage() {
  const [items, setItems] = useState([]);
  const [services, setServices] = useState([]);
  const [form, setForm] = useState(emptyPackage());
  const [editing, setEditing] = useState(null);
  const [show, setShow] = useState(false);
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("package");
  const [error, setError] = useState("");
  const [newPackageItem, setNewPackageItem] = useState(emptyItem());
  const [showServiceItemModal, setShowServiceItemModal] = useState(false);

  const serviceOptions = [
    { value: "", label: "Manual" },
    ...services.map((service) => ({
      value: service.id,
      label: [service.code, service.name, service.category_name].filter(Boolean).join(" - "),
    })),
  ];
  const formSubtotal = useMemo(() => form.items.reduce((total, item) => total + itemSubtotal(item), 0), [form.items]);
  const formDiscountAmount = useMemo(() => (formSubtotal * decimal(form.discount_percent)) / 100, [formSubtotal, form.discount_percent]);
  const formTotal = useMemo(() => Math.max(formSubtotal - formDiscountAmount, 0), [formSubtotal, formDiscountAmount]);

  async function load(nextSearch = search) {
    const normalizedSearch = String(nextSearch || "").trim();

    try {
      const [packageRes, serviceRes] = await Promise.all([
        api.get("/workshop/service-packages/", { params: normalizedSearch ? { search: normalizedSearch } : {} }),
        api.get("/workshop/services/", { params: { active: "true" } }),
      ]);
      setItems(results(packageRes.data));
      setServices(results(serviceRes.data));
    } catch (err) {
      setError(apiError(err));
    }
  }

  function clearSearch() {
    setSearch("");
    load("");
  }

  function selectPackageSuggestion(suggestion, nextValue) {
    const selectedPackage = suggestion?.payload;
    setSearch(nextValue || "");

    if (selectedPackage?.id) {
      setItems([selectedPackage]);
      return;
    }

    load(nextValue);
  }

  async function nextPackageCode() {
    try {
      const { data } = await api.get("/workshop/service-packages/next-code/");
      return data?.code || "";
    } catch (err) {
      setError(apiError(err));
      return "";
    }
  }

  useEffect(() => {
    load();
  }, []);

  function update(patch) {
    setForm((current) => ({ ...current, ...patch }));
  }

  async function open(item = null) {
    setEditing(item);
    setActiveTab("package");
    if (item) {
      setForm({
        code: item.code || "",
        name: item.name || "",
        description: item.description || "",
        discount_percent: item.discount_percent || "0.00",
        is_active: item.is_active,
        items: (item.items || []).map((line, index) => ({
          local_id: makeLocalId(),
          service_id: line.service || line.service_id || "",
          service_name: line.service_name || "",
          service_code: line.service_code || "",
          description: line.description || "",
          quantity: line.quantity || "1.00",
          unit_price: line.unit_price || "0.00",
          position: line.position || index + 1,
        })),
      });
    } else {
      const nextCode = await nextPackageCode();
      setForm({ ...emptyPackage(), code: nextCode });
    }
    setShow(true);
  }

  function openServiceItemModal() {
    setNewPackageItem({ ...emptyItem(), position: form.items.length + 1 });
    setShowServiceItemModal(true);
    setActiveTab("items");
  }

  function closeServiceItemModal() {
    setShowServiceItemModal(false);
    setNewPackageItem({ ...emptyItem(), position: form.items.length + 1 });
  }

  function selectPackageService(serviceId) {
    const selected = services.find((service) => String(service.id) === String(serviceId));
    setNewPackageItem((current) => ({
      ...current,
      service_id: serviceId,
      service_name: selected?.name || "",
      service_code: selected?.code || "",
      description: selected?.name || current.description || "",
      unit_price: selected?.default_unit_price || current.unit_price || "0.00",
    }));
  }

  function addItem() {
    const description = String(newPackageItem.description || "").trim();
    if (!description) {
      setError("Informe a descrição do serviço antes de inserir no pacote.");
      return;
    }

    setForm((current) => ({
      ...current,
      items: [
        ...current.items,
        {
          ...newPackageItem,
          local_id: makeLocalId(),
          description,
          quantity: newPackageItem.quantity || "1.00",
          unit_price: newPackageItem.unit_price || "0.00",
          position: newPackageItem.position || current.items.length + 1,
        },
      ].map((line, index) => ({ ...line, position: line.position || index + 1 })),
    }));
    closeServiceItemModal();
  }

  function removeItem(localId) {
    setForm((current) => ({
      ...current,
      items: current.items.filter((line) => line.local_id !== localId).map((line, index) => ({ ...line, position: index + 1 })),
    }));
  }

  function serviceLabel(line) {
    const selected = services.find((service) => String(service.id) === String(line.service_id));
    return [line.service_code || selected?.code, line.service_name || selected?.name || line.description].filter(Boolean).join(" - ") || "Serviço manual";
  }

  async function save(event) {
    event.preventDefault();
    setError("");

    const payload = {
      ...form,
      discount_percent: form.discount_percent || "0.00",
      items: form.items.map((line, index) => ({
        service_id: line.service_id ? Number(line.service_id) : null,
        description: line.description,
        quantity: line.quantity || "1.00",
        unit_price: line.unit_price || "0.00",
        position: index + 1,
      })),
    };

    try {
      if (editing) {
        await api.put(`/workshop/service-packages/${editing.id}/`, payload);
      } else {
        await api.post("/workshop/service-packages/", payload);
      }
      setShow(false);
      await load();
    } catch (err) {
      setError(apiError(err));
    }
  }

  async function remove(item) {
    if (!(await confirmDialog(`Excluir o pacote ${item.name}?`))) return;
    try {
      await api.delete(`/workshop/service-packages/${item.id}/`);
      await load();
    } catch (err) {
      setError(apiError(err));
    }
  }

  return <>
    <PageHeader title="Pacotes de serviços" subtitle="Monte combos agrupando vários serviços do catálogo em um formulário padronizado.">
      <Button onClick={() => open()}>Novo pacote</Button>
    </PageHeader>

    <AreaTabs area="technical" />
    <ErrorAlert error={error} onClose={() => setError("")}/>

    <Card className="border-0 shadow-sm mb-3">
      <Card.Body>
        <Row className="g-2 align-items-end">
          <Col md={10}>
            <Form.Label>Busca</Form.Label>
            <SearchAutocompleteInput
              placeholder="Buscar por código, nome, descrição, serviço, categoria, valor ou status"
              value={search}
              onChange={setSearch}
              onSearch={load}
              onSelect={selectPackageSuggestion}
              suggestions={buildPackageSearchSuggestions(items)}
            />
          </Col>
          <Col md={2}>
            <Button className="w-100" variant="outline-secondary" onClick={clearSearch} disabled={!search}>Limpar pesquisa</Button>
          </Col>
        </Row>
      </Card.Body>
    </Card>

    <Card className="border-0 shadow-sm">
      <Card.Body className="p-0">
        {items.length === 0 ? <EmptyState title="Nenhum pacote cadastrado"/> : <Table responsive hover className="mb-0">
          <thead>
            <tr>
              <th>Código</th>
              <th>Pacote</th>
              <th>Itens</th>
              <th>Subtotal</th>
              <th>Desconto</th>
              <th>Total</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => <tr key={item.id}>
              <td>{item.code || "-"}</td>
              <td className="fw-semibold">{item.name}</td>
              <td>{item.items?.length || 0}</td>
              <td>{money(item.subtotal_amount)}</td>
              <td>{item.discount_percent || "0.00"}% ({money(item.discount_amount)})</td>
              <td>{money(item.total_amount)}</td>
              <td>{item.is_active ? "Ativo" : "Inativo"}</td>
              <td className="text-end">
                <Button size="sm" variant="outline-primary" onClick={() => open(item)} className="me-2">Editar</Button>
                <Button size="sm" variant="outline-danger" onClick={() => remove(item)}>Excluir</Button>
              </td>
            </tr>)}
          </tbody>
        </Table>}
      </Card.Body>
    </Card>

    <Modal keyboard={false} backdrop="static" size="xl" show={show} onHide={() => setShow(false)} className="floating-form-modal">
      <Form onSubmit={save}>
        <Modal.Header closeButton>
          <Modal.Title>{editing ? "Editar" : "Novo"} pacote</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <FormTabs tabs={tabs} activeKey={activeTab} onSelect={setActiveTab} />

          <TabPanel activeKey={activeTab} eventKey="package">
            <Card className="form-section-card">
              <Card.Body>
                <div className="form-section-title">Dados do pacote</div>
                <Row className="g-3">
                  <Col md={3}>
                    <Form.Label>Código</Form.Label>
                    <Form.Control value={form.code || ""} onChange={(event) => update({ code: event.target.value.toUpperCase() })}/>
                  </Col>
                  <Col md={7}>
                    <Form.Label>Nome</Form.Label>
                    <Form.Control required value={form.name} onChange={(event) => update({ name: event.target.value })}/>
                  </Col>
                  <Col md={2} className="d-flex align-items-end">
                    <Form.Check label="Ativo" checked={!!form.is_active} onChange={(event) => update({ is_active: event.target.checked })}/>
                  </Col>
                  <Col md={3}>
                    <Form.Label>Desconto do pacote (%)</Form.Label>
                    <Form.Control type="number" min="0" max="100" step="0.01" inputMode="decimal" value={form.discount_percent || ""} onChange={(event) => update({ discount_percent: event.target.value })}/>
                    <Form.Text>Percentual aplicado uma vez sobre o total dos serviços do pacote.</Form.Text>
                  </Col>
                </Row>

                <Form.Group className="mt-3">
                  <Form.Label>Descrição</Form.Label>
                  <Form.Control as="textarea" rows={3} value={form.description || ""} onChange={(event) => update({ description: event.target.value })}/>
                </Form.Group>
              </Card.Body>
            </Card>
          </TabPanel>

          <TabPanel activeKey={activeTab} eventKey="items">
            <Card className="form-section-card">
              <Card.Body>
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <div>
                    <div className="form-section-title mb-1">Serviços do pacote</div>
                    <div className="text-muted small">Use o campo pesquisável para localizar serviços do catálogo rapidamente.</div>
                  </div>
                  <Button size="sm" variant="outline-primary" type="button" onClick={openServiceItemModal}>Inserir serviço</Button>
                </div>

                {form.items.length === 0 ? <EmptyState title="Nenhum serviço no pacote" description="Clique em Inserir serviço para adicionar o primeiro item."/> : <Table responsive bordered className="align-middle">
                  <thead>
                    <tr>
                      <th style={{ width: 90 }}>Ordem</th>
                      <th style={{ minWidth: 260 }}>Serviço</th>
                      <th>Descrição</th>
                      <th style={{ width: 120 }}>Qtd.</th>
                      <th style={{ width: 140 }}>Unitário</th>
                      <th style={{ width: 130 }}>Subtotal</th>
                      <th style={{ width: 90 }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {form.items.map((line) => <tr key={line.local_id}>
                      <td>{line.position || "-"}</td>
                      <td className="fw-semibold">{serviceLabel(line)}</td>
                      <td>{line.description || "-"}</td>
                      <td>{line.quantity || "1.00"}</td>
                      <td>{money(line.unit_price || 0)}</td>
                      <td>{money(itemSubtotal(line))}</td>
                      <td className="text-end"><Button size="sm" variant="outline-danger" type="button" onClick={() => removeItem(line.local_id)}>Remover</Button></td>
                    </tr>)}
                  </tbody>
                </Table>}

                <div className="text-end fs-5 form-muted-box mt-3">
                  <div>Subtotal dos serviços: <strong>{money(formSubtotal)}</strong></div>
                  <div>Desconto do pacote: <strong>{decimal(form.discount_percent).toFixed(2)}% ({money(formDiscountAmount)})</strong></div>
                  <div>Total do pacote: <strong>{money(formTotal)}</strong></div>
                </div>
              </Card.Body>
            </Card>
          </TabPanel>
        </Modal.Body>
        <TabbedFormFooter tabs={tabs} activeKey={activeTab} onSelect={setActiveTab} onCancel={() => setShow(false)} saveLabel="Salvar" />
      </Form>
    </Modal>

    <Modal show={showServiceItemModal} onHide={closeServiceItemModal} centered size="lg" backdrop="static">
      <Modal.Header closeButton>
        <Modal.Title>Inserir serviço no pacote</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Row className="g-3 align-items-end">
          <Col md={7}>
            <SearchableSelect
              label="Serviço"
              value={newPackageItem.service_id || ""}
              options={serviceOptions}
              onChange={selectPackageService}
              placeholder="Pesquisar serviço"
              emptyMessage="Nenhum serviço encontrado."
            />
          </Col>
          <Col md={2}>
            <Form.Label>Qtd.</Form.Label>
            <IntegerInput min="0.01" step="0.01" value={newPackageItem.quantity} onChange={(event) => setNewPackageItem({ ...newPackageItem, quantity: event.target.value })}/>
          </Col>
          <Col md={3}>
            <Form.Label>Ordem</Form.Label>
            <IntegerInput value={newPackageItem.position} onChange={(event) => setNewPackageItem({ ...newPackageItem, position: event.target.value })}/>
          </Col>
          <Col md={8}>
            <Form.Label>Descrição</Form.Label>
            <Form.Control required value={newPackageItem.description || ""} onChange={(event) => setNewPackageItem({ ...newPackageItem, description: event.target.value })} placeholder="Descrição que aparecerá no pacote" autoFocus />
          </Col>
          <Col md={4}>
            <Form.Label>Unitário</Form.Label>
            <MoneyInput value={newPackageItem.unit_price} onChange={(value) => setNewPackageItem({ ...newPackageItem, unit_price: value })}/>
          </Col>
          <Col md={12} className="text-end form-muted-box">
            Subtotal do serviço: <strong>{money(itemSubtotal(newPackageItem))}</strong>
          </Col>
        </Row>
      </Modal.Body>
      <Modal.Footer>
        <Button type="button" variant="outline-secondary" onClick={closeServiceItemModal}>Cancelar</Button>
        <Button type="button" variant="success" onClick={addItem}>Inserir serviço</Button>
      </Modal.Footer>
    </Modal>
  </>;
}
