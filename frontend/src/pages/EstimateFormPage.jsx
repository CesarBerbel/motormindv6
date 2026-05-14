import React, { useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, Col, Form, Modal, Row, Spinner, Table } from "../ui/TailwindPrimitives.jsx";
import DateInput from "../components/DateInput";
import IntegerInput from "../components/IntegerInput";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import api, { apiError, results } from "../api/client";
import { makeLocalId } from "../utils/localId";
import AreaTabs from "../components/AreaTabs";
import AIAssistButton from "../components/AIAssistButton";
import ErrorAlert from "../components/ErrorAlert";
import FormTabs, { TabPanel } from "../components/FormTabs";
import TabbedFormFooter from "../components/TabbedFormFooter";
import MoneyInput from "../components/MoneyInput";
import PercentInput from "../components/PercentInput";
import PageHeader from "../components/PageHeader";
import PhoneInputBR from "../components/PhoneInputBR";
import SearchableSelect from "../components/SearchableSelect";
import { dateInputValue, fuelTankLevelOptions, maskCpfCnpj, money, normalizePartUnit, partUnitOptions, vehicleSteeringTypes, vehicleTransmissionTypes } from "../workshopOptions";
import { normalizeBrazilPhoneToE164 } from "../utils/phone";
import { resolveReturnTo } from "../utils/returnTo";

const emptyEstimate = () => ({ customer_id: "", vehicle_id: "", title: "", complaint: "", diagnosis: "", internal_notes: "", customer_notes: "", valid_until: dateInputValue(), tank_level_percent: "0", discount_percent: "0", services: [], parts: [] });
const emptyService = () => ({ local_id: makeLocalId(), service_id: "", description: "", quantity: "1.00", unit_price: "", discount_percent: "0", notes: "" });
const emptyPart = () => ({ local_id: makeLocalId(), service_local_id: "", part_id: "", description: "", quantity: "1.00", unit_price: "", cost_price: "", discount_percent: "0", notes: "" });
const emptyQuickCustomerVehicle = () => ({
  person_type: "individual",
  first_name: "",
  last_name: "",
  trade_name: "",
  document_number: "",
  email: "",
  phone_e164: "",
  plate: "",
  make: "",
  model: "",
  version: "",
  year: "",
  color: "",
  odometer_km: "",
  steering_type: "",
  has_air_conditioning: false,
  door_count: "",
  transmission_type: "",
  is_modified: false,
  fipe_brand_code: "",
  fipe_model_code: "",
  fipe_year_code: "",
  notes: "",
});


const emptyQuickService = () => ({
  code: "",
  name: "",
  category_id: "",
  description: "",
  default_unit_price: "0.00",
  estimated_hours: "0.00",
  is_featured: false,
  is_active: true,
});

const emptyQuickPart = () => ({
  service_local_id: "",
  sku: "",
  name: "",
  category_id: "",
  brand: "",
  location: "",
  unit: "un",
  cost_price: "0.00",
  sale_price: "0.00",
  initial_stock_quantity: "0.00",
  initial_stock_unit_cost: "0.00",
  initial_stock_notes: "Entrada inicial pela peça rápida",
  is_featured: false,
  is_active: true,
  notes: "",
});

const emptyQuickPackage = () => ({
  code: "",
  name: "",
  description: "",
  discount_amount: "0.00",
  is_active: true,
  items: [],
});

const emptyQuickPackageItem = () => ({
  local_id: makeLocalId(),
  service_id: "",
  description: "",
  quantity: "1.00",
  unit_price: "0.00",
});

const quickCustomerVehicleTabs = [
  { key: "customer", label: "Cliente", description: "Nome, documento e contato" },
  { key: "fipe", label: "FIPE", description: "FIPE, placa e dados técnicos" },
  { key: "review", label: "Revisão", description: "Confirmar cadastro" },
];


const quickServiceTabs = [
  { key: "identification", label: "Identificação", description: "Código, nome e categoria" },
  { key: "pricing", label: "Preço", description: "Valor e tempo padrão" },
  { key: "review", label: "Revisão", description: "Confirmar serviço" },
];

const quickPartTabs = [
  { key: "identification", label: "Identificação", description: "SKU, peça e categoria" },
  { key: "stock", label: "Preço e entrada", description: "Unidade, preços e entrada inicial" },
  { key: "review", label: "Revisão", description: "Confirmar peça" },
];

const quickPackageTabs = [
  { key: "package", label: "Combo", description: "Código, nome e desconto" },
  { key: "items", label: "Serviços", description: "Itens do combo" },
  { key: "review", label: "Revisão", description: "Confirmar combo" },
];

function decimal(value) { const parsed = Number(value || 0); return Number.isFinite(parsed) ? parsed : 0; }
function lineSubtotal(line) { return decimal(line.quantity) * decimal(line.unit_price); }
function percentAmount(base, percent) { return Math.max(decimal(base) * decimal(percent) / 100, 0); }
function percentFromAmount(base, amount) { const parsedBase = decimal(base); return parsedBase > 0 ? ((decimal(amount) / parsedBase) * 100).toFixed(2) : "0"; }
function lineDiscountAmount(line) { return percentAmount(lineSubtotal(line), line.discount_percent); }
function lineTotal(line) { return Math.max(lineSubtotal(line) - lineDiscountAmount(line), 0); }
function contactName(contact) { return contact.full_name || `${contact.first_name || ""} ${contact.last_name || ""}`.trim() || "Cliente sem nome"; }
function normalizePlate(value) { return String(value || "").toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 7); }
function normalizeFipeName(value) { return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]/g, ""); }
function catalogInitials(name = "") {
  const pieces = String(name).trim().split(/\s+/).filter(Boolean).slice(0, 2);
  return pieces.map((part) => part[0]?.toUpperCase()).join("") || "+";
}
function sortCatalogByUsage(items = []) {
  return [...items].sort((a, b) => {
    const featuredDiff = Number(Boolean(b.is_featured)) - Number(Boolean(a.is_featured));
    if (featuredDiff !== 0) return featuredDiff;
    const usageDiff = Number(b.usage_count || 0) - Number(a.usage_count || 0);
    if (usageDiff !== 0) return usageDiff;
    return String(a.name || "").localeCompare(String(b.name || ""), "pt-BR");
  });
}
function partLineSubtotal(line) { return decimal(line.quantity) * decimal(line.unit_price); }
function partDiscountAmount(line) { return percentAmount(partLineSubtotal(line), line.discount_percent); }
function partLineTotal(line) { return Math.max(partLineSubtotal(line) - partDiscountAmount(line), 0); }
function defaultPartsForService(service, serviceLocalId = "") {
  const templates = Array.isArray(service?.default_parts) ? service.default_parts : [];
  return templates
    .filter((template) => template?.is_active !== false)
    .map((template) => ({
      ...emptyPart(),
      service_local_id: serviceLocalId || "",
      part_id: template.part ? String(template.part) : template.part_id ? String(template.part_id) : "",
      description: template.part_name || "Peça padrão do serviço",
      quantity: template.quantity || "1.00",
      unit_price: template.effective_unit_price || template.unit_price || template.part_sale_price || "0.00",
      cost_price: template.part_cost_price || "0.00",
      discount_percent: percentFromAmount(decimal(template.quantity || "1.00") * decimal(template.effective_unit_price || template.unit_price || template.part_sale_price || "0.00"), template.discount_amount || "0.00"),
      notes: template.notes || (service?.name ? `Adicionada automaticamente pelo serviço ${service.name}.` : "Adicionada automaticamente pelo serviço."),
    }));
}


function QuickCustomerVehicleModal({ show, onHide, onCreated }) {
  const [form, setForm] = useState(emptyQuickCustomerVehicle());
  const [activeTab, setActiveTab] = useState("customer");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [brands, setBrands] = useState([]);
  const [models, setModels] = useState([]);
  const [years, setYears] = useState([]);
  const [fipeLoading, setFipeLoading] = useState(false);

  const isCompany = form.person_type === "company";
  const customerDisplay = isCompany ? form.first_name || "Razão social não informada" : [form.first_name, form.last_name].filter(Boolean).join(" ") || "Cliente não informado";
  const vehicleDisplay = [form.plate || "Sem placa", form.make, form.model, form.year].filter(Boolean).join(" - ");

  const brandOptions = useMemo(() => [
    { value: "", label: form.make ? `Manter marca atual: ${form.make}` : "Selecione a marca FIPE" },
    ...brands.map((brand) => ({ value: brand.codigo, label: brand.nome })),
  ], [brands, form.make]);

  const modelOptions = useMemo(() => [
    { value: "", label: form.model ? `Manter modelo atual: ${form.model}` : "Selecione o modelo FIPE" },
    ...models.map((model) => ({ value: model.codigo, label: model.nome })),
  ], [models, form.model]);

  const yearOptions = useMemo(() => [
    { value: "", label: form.version ? `Manter ano/versão atual: ${form.version}` : "Selecione o ano/versão FIPE" },
    ...years.map((year) => ({ value: year.codigo, label: year.nome })),
  ], [years, form.version]);

  useEffect(() => {
    if (show) {
      setForm(emptyQuickCustomerVehicle());
      setActiveTab("customer");
      setError("");
      setSaving(false);
      setModels([]);
      setYears([]);
      if (brands.length === 0) loadBrands();
    }
  }, [show]);

  useEffect(() => {
    if (!show) return;
    if (brands.length === 0) return;
    if (form.fipe_brand_code || !form.make) return;
    const currentMake = normalizeFipeName(form.make);
    const matchedBrand = brands.find((brand) => normalizeFipeName(brand.nome) === currentMake);
    if (!matchedBrand) return;
    setForm((current) => ({ ...current, fipe_brand_code: matchedBrand.codigo }));
    loadModels(matchedBrand.codigo);
  }, [show, brands, form.fipe_brand_code, form.make]);

  async function loadBrands() {
    try {
      setFipeLoading(true);
      setBrands(results((await api.get("/workshop/fipe/brands/", { params: { vehicle_type: "carros" } })).data));
    } catch (err) {
      setError(apiError(err));
    } finally {
      setFipeLoading(false);
    }
  }

  async function loadModels(brandCode) {
    if (!brandCode) {
      setModels([]);
      return;
    }
    try {
      setFipeLoading(true);
      const response = await api.get("/workshop/fipe/models/", { params: { vehicle_type: "carros", brand_code: brandCode } });
      setModels(response.data?.modelos || []);
    } catch (err) {
      setError(apiError(err));
    } finally {
      setFipeLoading(false);
    }
  }

  async function loadYears(brandCode, modelCode) {
    if (!brandCode || !modelCode) {
      setYears([]);
      return;
    }
    try {
      setFipeLoading(true);
      setYears(results((await api.get("/workshop/fipe/years/", { params: { vehicle_type: "carros", brand_code: brandCode, model_code: modelCode } })).data));
    } catch (err) {
      setError(apiError(err));
    } finally {
      setFipeLoading(false);
    }
  }

  async function loadFipeDetail(brandCode, modelCode, yearCode, yearLabel) {
    const parsedYear = Number(String(yearLabel || "").match(/\d{4}/)?.[0] || "") || "";
    try {
      setFipeLoading(true);
      const response = await api.get("/workshop/fipe/detail/", { params: { vehicle_type: "carros", brand_code: brandCode, model_code: modelCode, year_code: yearCode } });
      const detail = response.data || {};
      setForm((current) => ({
        ...current,
        fipe_year_code: yearCode,
        year: detail.AnoModelo || parsedYear,
        version: yearLabel || [detail.Combustivel, detail.CodigoFipe].filter(Boolean).join(" - "),
      }));
    } catch (err) {
      setForm((current) => ({ ...current, fipe_year_code: yearCode, year: parsedYear, version: yearLabel || current.version }));
      setError(apiError(err));
    } finally {
      setFipeLoading(false);
    }
  }

  function handleBrandChange(code) {
    if (!code) {
      update({ fipe_brand_code: "", fipe_model_code: "", fipe_year_code: "" });
      setModels([]);
      setYears([]);
      return;
    }
    const brand = brands.find((item) => String(item.codigo) === String(code));
    update({
      fipe_brand_code: code,
      fipe_model_code: "",
      fipe_year_code: "",
      make: brand?.nome || form.make,
      model: "",
      version: "",
      year: "",
    });
    setYears([]);
    loadModels(code);
  }

  function handleModelChange(code) {
    if (!code) {
      update({ fipe_model_code: "", fipe_year_code: "" });
      setYears([]);
      return;
    }
    const model = models.find((item) => String(item.codigo) === String(code));
    update({
      fipe_model_code: code,
      fipe_year_code: "",
      model: model?.nome || form.model,
      version: "",
      year: "",
    });
    loadYears(form.fipe_brand_code, code);
  }

  function handleYearChange(code) {
    const year = years.find((item) => String(item.codigo) === String(code));
    loadFipeDetail(form.fipe_brand_code, form.fipe_model_code, code, year?.nome || "");
  }

  function clearFipeLink() {
    update({ fipe_brand_code: "", fipe_model_code: "", fipe_year_code: "" });
    setModels([]);
    setYears([]);
  }

  function update(patch) {
    setForm((current) => ({ ...current, ...patch }));
  }

  function validate() {
    if (!form.first_name.trim()) {
      setActiveTab("customer");
      setError(isCompany ? "Informe a razão social do cliente." : "Informe o nome do cliente.");
      return false;
    }
    if (!form.plate.trim()) {
      setActiveTab("fipe");
      setError("Informe a placa do veículo.");
      return false;
    }
    if (!form.make.trim()) {
      setActiveTab("fipe");
      setError("Informe a marca do veículo.");
      return false;
    }
    if (!form.model.trim()) {
      setActiveTab("fipe");
      setError("Informe o modelo do veículo.");
      return false;
    }
    return true;
  }

  async function save(event) {
    event.preventDefault();
    setError("");
    if (!validate()) return;
    setSaving(true);

    try {
      const contactPayload = {
        person_type: form.person_type,
        first_name: form.first_name.trim(),
        last_name: isCompany ? "" : form.last_name.trim(),
        trade_name: isCompany ? form.trade_name.trim() : "",
        document_number: maskCpfCnpj(form.document_number),
        email: form.email.trim().toLowerCase(),
        phone_e164: normalizeBrazilPhoneToE164(form.phone_e164),
        secondary_phone_e164: "",
        country: "Brasil",
        notes: "Cadastrado rapidamente pelo formulário de orçamento.",
        group_ids: [],
        custom_data: {},
        is_active: true,
      };

      const contactResponse = await api.post("/contacts/", contactPayload);
      const contact = contactResponse.data;

      const vehiclePayload = {
        customer_id: contact.id,
        plate: normalizePlate(form.plate),
        make: form.make.trim(),
        model: form.model.trim(),
        version: form.version.trim(),
        year: form.year ? Number(form.year) : null,
        color: form.color.trim(),
        vin: "",
        odometer_km: form.odometer_km ? Number(form.odometer_km) : 0,
        steering_type: form.steering_type || "",
        has_air_conditioning: !!form.has_air_conditioning,
        door_count: form.door_count ? Number(form.door_count) : null,
        transmission_type: form.transmission_type || "",
        is_modified: !!form.is_modified,
        fipe_brand_code: form.fipe_brand_code || "",
        fipe_model_code: form.fipe_model_code || "",
        fipe_year_code: form.fipe_year_code || "",
        notes: form.notes.trim() || "Cadastrado rapidamente pelo formulário de orçamento.",
        is_active: true,
      };

      const vehicleResponse = await api.post("/workshop/vehicles/", vehiclePayload);
      onCreated(contact, vehicleResponse.data);
      onHide();
    } catch (err) {
      setError(apiError(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal keyboard={false} backdrop="static" size="xl" show={show} onHide={onHide} className="floating-form-modal" dialogClassName="modal-wide-tabs" centered>
      <Form onSubmit={save} noValidate>
        <Modal.Header closeButton={!saving}>
          <Modal.Title>Novo cliente e veículo</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="info" className="mb-3">
            Cadastre o cliente e o veículo sem sair do orçamento. Ao salvar, os dois cadastros serão selecionados automaticamente no orçamento atual.
          </Alert>
          <ErrorAlert error={error} onClose={() => setError("")} />
          <FormTabs tabs={quickCustomerVehicleTabs} activeKey={activeTab} onSelect={setActiveTab} />

          <TabPanel activeKey={activeTab} eventKey="customer">
            <Card className="form-section-card">
              <Card.Body>
                <div className="form-section-title">Dados essenciais do cliente</div>
                <Row className="g-3">
                  <Col md={3}>
                    <Form.Label>Tipo de pessoa</Form.Label>
                    <Form.Select value={form.person_type} onChange={(event) => update({ person_type: event.target.value, last_name: event.target.value === "company" ? "" : form.last_name })}>
                      <option value="individual">Pessoa física</option>
                      <option value="company">Pessoa jurídica</option>
                    </Form.Select>
                  </Col>
                  <Col md={isCompany ? 6 : 4}>
                    <Form.Label>{isCompany ? "Razão social" : "Nome"}</Form.Label>
                    <Form.Control required value={form.first_name} onChange={(event) => update({ first_name: event.target.value })} />
                  </Col>
                  {!isCompany ? (
                    <Col md={3}>
                      <Form.Label>Sobrenome</Form.Label>
                      <Form.Control value={form.last_name} onChange={(event) => update({ last_name: event.target.value })} />
                    </Col>
                  ) : null}
                  <Col md={isCompany ? 3 : 2}>
                    <Form.Label>{isCompany ? "CNPJ" : "CPF"}</Form.Label>
                    <Form.Control value={form.document_number} onChange={(event) => update({ document_number: maskCpfCnpj(event.target.value) })} placeholder={isCompany ? "00.000.000/0000-00" : "000.000.000-00"} />
                  </Col>
                  {isCompany ? (
                    <Col md={4}>
                      <Form.Label>Nome fantasia</Form.Label>
                      <Form.Control value={form.trade_name} onChange={(event) => update({ trade_name: event.target.value })} />
                    </Col>
                  ) : null}
                  <Col md={4}>
                    <Form.Label>Email</Form.Label>
                    <Form.Control type="email" value={form.email} onChange={(event) => update({ email: event.target.value })} placeholder="cliente@email.com" />
                  </Col>
                  <Col md={4}>
                    <PhoneInputBR label="WhatsApp" value={form.phone_e164} onChange={(value) => update({ phone_e164: value })} />
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          </TabPanel>

          <TabPanel activeKey={activeTab} eventKey="fipe">
            <Card className="form-section-card">
              <Card.Body>
                <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2 mb-3">
                  <div>
                    <div className="form-section-title mb-1">Consulta FIPE</div>
                    <p className="text-muted small mb-0">Pesquise marca, modelo e ano/versão pela FIPE. Ao selecionar, marca, modelo, ano e versão são preenchidos automaticamente no cadastro rápido.</p>
                  </div>
                  <div className="d-flex align-items-center gap-2">
                    {fipeLoading ? <Spinner animation="border" size="sm" /> : null}
                    <Button type="button" size="sm" variant="outline-secondary" onClick={clearFipeLink}>Limpar vínculo FIPE</Button>
                  </div>
                </div>
                <Row className="g-3">
                  <Col md={4}>
                    <SearchableSelect
                      id="quickVehicleFipeBrand"
                      label="Marca FIPE"
                      value={form.fipe_brand_code || ""}
                      options={brandOptions}
                      onChange={handleBrandChange}
                      placeholder="Pesquisar marca"
                      emptyMessage="Nenhuma marca FIPE encontrada."
                      helpText={form.fipe_brand_code ? "Marca vinculada. Se trocar a marca, modelo e ano serão recalculados." : "Selecione a marca para carregar modelos FIPE."}
                    />
                  </Col>
                  <Col md={4}>
                    <SearchableSelect
                      id="quickVehicleFipeModel"
                      label="Modelo FIPE"
                      value={form.fipe_model_code || ""}
                      options={modelOptions}
                      onChange={handleModelChange}
                      placeholder="Pesquisar modelo"
                      emptyMessage="Nenhum modelo FIPE encontrado."
                      disabled={!form.fipe_brand_code}
                      helpText={!form.fipe_brand_code ? "Selecione a marca FIPE primeiro." : "Selecione o modelo para carregar os anos/versões."}
                    />
                  </Col>
                  <Col md={4}>
                    <SearchableSelect
                      id="quickVehicleFipeYear"
                      label="Ano / versão FIPE"
                      value={form.fipe_year_code || ""}
                      options={yearOptions}
                      onChange={handleYearChange}
                      placeholder="Pesquisar ano/versão"
                      emptyMessage="Nenhum ano/versão FIPE encontrado."
                      disabled={!form.fipe_model_code}
                      helpText={!form.fipe_model_code ? "Selecione o modelo FIPE primeiro." : "Ao selecionar, ano e versão são atualizados automaticamente."}
                    />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Placa</Form.Label>
                    <Form.Control required value={form.plate} onChange={(event) => update({ plate: normalizePlate(event.target.value) })} placeholder="ABC1D23" />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Cor</Form.Label>
                    <Form.Control value={form.color} onChange={(event) => update({ color: event.target.value })} />
                  </Col>
                  <Col md={3}>
                    <Form.Label>KM atual</Form.Label>
                    <IntegerInput min="0" value={form.odometer_km} onChange={(event) => update({ odometer_km: event.target.value })} />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Portas</Form.Label>
                    <IntegerInput min="0" max="10" value={form.door_count} onChange={(event) => update({ door_count: event.target.value })} placeholder="Ex.: 4" />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Direção</Form.Label>
                    <Form.Select value={form.steering_type} onChange={(event) => update({ steering_type: event.target.value })}>
                      {vehicleSteeringTypes.map(([value, label]) => <option key={value || "blank"} value={value}>{label}</option>)}
                    </Form.Select>
                  </Col>
                  <Col md={3}>
                    <Form.Label>Câmbio</Form.Label>
                    <Form.Select value={form.transmission_type} onChange={(event) => update({ transmission_type: event.target.value })}>
                      {vehicleTransmissionTypes.map(([value, label]) => <option key={value || "blank"} value={value}>{label}</option>)}
                    </Form.Select>
                  </Col>
                  <Col md={3}>
                    <Form.Label>Conforto</Form.Label>
                    <Form.Check className="mt-2" label="Ar-condicionado" checked={form.has_air_conditioning} onChange={(event) => update({ has_air_conditioning: event.target.checked })} />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Originalidade</Form.Label>
                    <Form.Check className="mt-2" label="Veículo modificado" checked={form.is_modified} onChange={(event) => update({ is_modified: event.target.checked })} />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Marca preenchida</Form.Label>
                    <Form.Control value={form.make} onChange={(event) => update({ make: event.target.value })} placeholder="Ex.: Volkswagen" />
                  </Col>
                  <Col md={5}>
                    <Form.Label>Modelo preenchido</Form.Label>
                    <Form.Control value={form.model} onChange={(event) => update({ model: event.target.value })} placeholder="Ex.: Gol" />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Ano preenchido</Form.Label>
                    <IntegerInput min="1900" max="2100" value={form.year} onChange={(event) => update({ year: event.target.value })} />
                  </Col>
                  <Col md={8}>
                    <Form.Label>Versão / referência FIPE</Form.Label>
                    <Form.Control value={form.version} onChange={(event) => update({ version: event.target.value })} placeholder="Ex.: Gasolina - 005001-0" />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Observações do veículo</Form.Label>
                    <Form.Control as="textarea" rows={2} value={form.notes} onChange={(event) => update({ notes: event.target.value })} placeholder="Opcional" />
                  </Col>
                </Row>
                <Alert variant="secondary" className="mt-3 mb-0 small">
                  A consulta FIPE usa o mesmo endpoint já existente no cadastro normal de veículos. Se a API externa estiver indisponível, você ainda pode preencher marca e modelo manualmente.
                </Alert>
              </Card.Body>
            </Card>
          </TabPanel>

          <TabPanel activeKey={activeTab} eventKey="review">
            <Card className="form-section-card">
              <Card.Body>
                <div className="form-section-title">Conferência antes de salvar</div>
                <Row className="g-3">
                  <Col md={6}>
                    <div className="form-muted-box h-100">
                      <div className="small text-muted">Cliente</div>
                      <div className="fw-semibold">{customerDisplay}</div>
                      <div className="small text-muted mt-2">{form.document_number || "Sem CPF/CNPJ"}</div>
                      <div className="small text-muted">{form.email || "Sem email"}</div>
                      <div className="small text-muted">{form.phone_e164 || "Sem WhatsApp"}</div>
                    </div>
                  </Col>
                  <Col md={6}>
                    <div className="form-muted-box h-100">
                      <div className="small text-muted">Veículo</div>
                      <div className="fw-semibold">{vehicleDisplay || "Veículo não informado"}</div>
                      <div className="small text-muted mt-2">Cor: {form.color || "não informada"}</div>
                      <div className="small text-muted">Versão: {form.version || "não informada"}</div>
                      <div className="small text-muted">FIPE: {[form.fipe_brand_code, form.fipe_model_code, form.fipe_year_code].filter(Boolean).join(" / ") || "sem vínculo"}</div>
                      <div className="small text-muted">KM: {form.odometer_km || "0"}</div>
                      <div className="small text-muted">Direção: {vehicleSteeringTypes.find(([value]) => value === form.steering_type)?.[1] || "não informada"}</div>
                      <div className="small text-muted">Câmbio: {vehicleTransmissionTypes.find(([value]) => value === form.transmission_type)?.[1] || "não informado"}</div>
                      <div className="small text-muted">Portas: {form.door_count || "não informado"}</div>
                      <div className="small text-muted">Ar-condicionado: {form.has_air_conditioning ? "sim" : "não"}</div>
                      <div className="small text-muted">Modificado: {form.is_modified ? "sim" : "não"}</div>
                    </div>
                  </Col>
                </Row>
                <Alert variant="warning" className="mt-3 mb-0">
                  Ao confirmar, o sistema criará primeiro o cliente e depois o veículo vinculado a ele. Se a placa ou CPF/CNPJ já existir, o cadastro será bloqueado pelo backend para evitar duplicidade.
                </Alert>
              </Card.Body>
            </Card>
          </TabPanel>
        </Modal.Body>
        <TabbedFormFooter
          tabs={quickCustomerVehicleTabs}
          activeKey={activeTab}
          onSelect={setActiveTab}
          onCancel={onHide}
          cancelLabel="Fechar"
          saveLabel={saving ? "Salvando..." : "Salvar cliente e veículo"}
          saveDisabled={saving}
        />
      </Form>
    </Modal>
  );
}


function QuickServiceModal({ show, onHide, onCreated, categories }) {
  const [form, setForm] = useState(emptyQuickService());
  const [activeTab, setActiveTab] = useState("identification");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const categoryOptions = useMemo(() => [
    { value: "", label: "Sem categoria", description: "Serviço será cadastrado sem categoria." },
    ...(categories || []).map((category) => ({ value: category.id, label: category.name, description: category.code ? `Código: ${category.code}` : "Categoria de serviço" })),
  ], [categories]);

  useEffect(() => {
    if (!show) return;
    setForm(emptyQuickService());
    setActiveTab("identification");
    setError("");
    setSaving(false);
    api.get("/workshop/services/next-code/")
      .then(({ data }) => setForm((current) => ({ ...current, code: data?.code || "" })))
      .catch(() => setForm((current) => ({ ...current, code: "" })));
  }, [show]);

  function update(patch) {
    setForm((current) => ({ ...current, ...patch }));
  }

  function validate() {
    if (!form.name.trim()) {
      setActiveTab("identification");
      setError("Informe o nome do serviço.");
      return false;
    }
    if (decimal(form.default_unit_price) < 0) {
      setActiveTab("pricing");
      setError("O valor padrão do serviço não pode ser negativo.");
      return false;
    }
    return true;
  }

  async function save(event) {
    event.preventDefault();
    setError("");
    if (!validate()) return;
    setSaving(true);

    try {
      const payload = {
        code: form.code.trim().toUpperCase(),
        name: form.name.trim(),
        category_id: form.category_id ? Number(form.category_id) : "",
        legacy_category_name: "",
        description: form.description.trim(),
        default_unit_price: form.default_unit_price || "0.00",
        estimated_hours: form.estimated_hours || "0.00",
        is_featured: !!form.is_featured,
        is_active: !!form.is_active,
      };
      const { data } = await api.post("/workshop/services/", payload);
      onCreated(data);
      onHide();
    } catch (err) {
      setError(apiError(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal keyboard={false} backdrop="static" size="lg" show={show} onHide={onHide} className="floating-form-modal" centered>
      <Form onSubmit={save} noValidate>
        <Modal.Header closeButton={!saving}>
          <Modal.Title>Novo serviço rápido</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="info" className="mb-3">
            Cadastre um serviço sem sair do orçamento. Ao salvar, ele será incluído no catálogo e adicionado ao orçamento atual.
          </Alert>
          <ErrorAlert error={error} onClose={() => setError("")} />
          <FormTabs tabs={quickServiceTabs} activeKey={activeTab} onSelect={setActiveTab} />

          <TabPanel activeKey={activeTab} eventKey="identification">
            <Card className="form-section-card">
              <Card.Body>
                <div className="form-section-title">Identificação do serviço</div>
                <Row className="g-3">
                  <Col md={4}>
                    <Form.Label>Código</Form.Label>
                    <Form.Control value={form.code} onChange={(event) => update({ code: event.target.value.toUpperCase() })} placeholder="Gerado automaticamente" />
                  </Col>
                  <Col md={8}>
                    <Form.Label>Nome do serviço</Form.Label>
                    <Form.Control required value={form.name} onChange={(event) => update({ name: event.target.value })} placeholder="Ex.: Troca de pastilhas dianteiras" />
                  </Col>
                  <Col md={12}>
                    <SearchableSelect
                      id="quickServiceCategory"
                      label="Categoria"
                      value={form.category_id}
                      options={categoryOptions}
                      onChange={(value) => update({ category_id: value })}
                      placeholder="Pesquisar categoria de serviço"
                      emptyMessage="Nenhuma categoria de serviço encontrada."
                    />
                  </Col>
                  <Col md={12}>
                    <Form.Label>Descrição padrão</Form.Label>
                    <Form.Control as="textarea" rows={4} value={form.description} onChange={(event) => update({ description: event.target.value })} placeholder="Descrição técnica/comercial que poderá ser reaproveitada no orçamento." />
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          </TabPanel>

          <TabPanel activeKey={activeTab} eventKey="pricing">
            <Card className="form-section-card">
              <Card.Body>
                <div className="form-section-title">Preço e tempo padrão</div>
                <Row className="g-3">
                  <Col md={6}>
                    <Form.Label>Valor padrão</Form.Label>
                    <MoneyInput value={form.default_unit_price} onChange={(value) => update({ default_unit_price: value })} />
                  </Col>
                  <Col md={6}>
                    <Form.Label>Horas estimadas</Form.Label>
                    <IntegerInput min="0" step="0.01" value={form.estimated_hours} onChange={(event) => update({ estimated_hours: event.target.value })} />
                  </Col>
                  <Col md={6}>
                    <Form.Check label="Serviço preferido/mais usado" checked={form.is_featured} onChange={(event) => update({ is_featured: event.target.checked })} />
                  </Col>
                  <Col md={6}>
                    <Form.Check label="Ativo no catálogo" checked={form.is_active} onChange={(event) => update({ is_active: event.target.checked })} />
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          </TabPanel>

          <TabPanel activeKey={activeTab} eventKey="review">
            <Card className="form-section-card">
              <Card.Body>
                <div className="form-section-title">Conferência antes de salvar</div>
                <div className="form-muted-box">
                  <div className="fw-semibold">{[form.code, form.name || "Serviço não informado"].filter(Boolean).join(" - ")}</div>
                  <div className="small text-muted mt-2">Categoria: {categoryOptions.find((option) => String(option.value) === String(form.category_id))?.label || "Sem categoria"}</div>
                  <div className="small text-muted">Valor padrão: {money(form.default_unit_price || 0)}</div>
                  <div className="small text-muted">Horas estimadas: {form.estimated_hours || "0.00"}</div>
                  <div className="small text-muted mt-2">{form.description || "Sem descrição padrão."}</div>
                </div>
                <Alert variant="warning" className="mt-3 mb-0">
                  O serviço será criado no catálogo técnico e também será adicionado ao orçamento atual como item de mão de obra.
                </Alert>
              </Card.Body>
            </Card>
          </TabPanel>
        </Modal.Body>
        <TabbedFormFooter
          tabs={quickServiceTabs}
          activeKey={activeTab}
          onSelect={setActiveTab}
          onCancel={onHide}
          cancelLabel="Fechar"
          saveLabel={saving ? "Salvando..." : "Salvar serviço"}
          saveDisabled={saving}
        />
      </Form>
    </Modal>
  );
}

function QuickPartModal({ show, onHide, onCreated, categories, serviceLineOptions }) {
  const [form, setForm] = useState(emptyQuickPart());
  const [activeTab, setActiveTab] = useState("identification");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const categoryOptions = useMemo(() => [
    { value: "", label: "Sem categoria", description: "Peça será cadastrada sem categoria." },
    ...(categories || []).map((category) => ({ value: category.id, label: category.name, description: category.code ? `Código: ${category.code}` : "Categoria de peça" })),
  ], [categories]);

  useEffect(() => {
    if (!show) return;
    let cancelled = false;
    const firstRealService = (serviceLineOptions || []).find((option) => option.value);
    async function prepareForm() {
      let nextSku = "";
      try {
        const { data } = await api.get("/workshop/parts/next-sku/");
        nextSku = data?.sku || "";
      } catch {
        nextSku = "";
      }
      if (!cancelled) setForm({ ...emptyQuickPart(), sku: nextSku, service_local_id: firstRealService?.value || "" });
    }
    prepareForm();
    setActiveTab("identification");
    setError("");
    setSaving(false);
    return () => { cancelled = true; };
  }, [show, serviceLineOptions]);

  function update(patch) {
    setForm((current) => ({ ...current, ...patch }));
  }

  function validate() {
    // O SKU vem preenchido automaticamente. Caso falhe, o backend também gera um código ao salvar.
    if (!form.name.trim()) {
      setActiveTab("identification");
      setError("Informe o nome da peça.");
      return false;
    }
    if (decimal(form.sale_price) < decimal(form.cost_price)) {
      setActiveTab("stock");
      setError("O preço de venda está menor que o custo. Revise antes de cadastrar a peça.");
      return false;
    }
    return true;
  }

  async function save(event) {
    event.preventDefault();
    setError("");
    if (!validate()) return;
    setSaving(true);

    try {
      const payload = {
        sku: form.sku.trim().toUpperCase(),
        name: form.name.trim(),
        category_id: form.category_id ? Number(form.category_id) : "",
        brand: form.brand.trim(),
        location: form.location.trim(),
        unit: normalizePartUnit(form.unit),
        cost_price: form.cost_price || "0.00",
        sale_price: form.sale_price || "0.00",
        is_featured: !!form.is_featured,
        is_active: !!form.is_active,
        notes: form.notes.trim(),
      };
      const { data } = await api.post("/workshop/parts/", payload);
      if (decimal(form.initial_stock_quantity) > 0) {
        await api.post(`/workshop/parts/${data.id}/adjust_stock/`, {
          movement_type: "purchase",
          quantity: Number(decimal(form.initial_stock_quantity)).toFixed(2),
          unit_cost: form.initial_stock_unit_cost || form.cost_price || "0.00",
          notes: form.initial_stock_notes || "Entrada inicial pela peça rápida",
        });
      }
      onCreated(data, form.service_local_id || "");
      onHide();
    } catch (err) {
      setError(apiError(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal keyboard={false} backdrop="static" size="lg" show={show} onHide={onHide} className="floating-form-modal" centered>
      <Form onSubmit={save} noValidate>
        <Modal.Header closeButton={!saving}>
          <Modal.Title>Nova peça rápida</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="info" className="mb-3">
            Cadastre uma peça sem sair do orçamento. A entrada inicial, quando informada, será registrada por movimentação de estoque.
          </Alert>
          <ErrorAlert error={error} onClose={() => setError("")} />
          <FormTabs tabs={quickPartTabs} activeKey={activeTab} onSelect={setActiveTab} />

          <TabPanel activeKey={activeTab} eventKey="identification">
            <Card className="form-section-card">
              <Card.Body>
                <div className="form-section-title">Identificação da peça</div>
                <Row className="g-3">
                  <Col md={4}>
                    <Form.Label>SKU / código interno</Form.Label>
                    <Form.Control required value={form.sku} onChange={(event) => update({ sku: event.target.value.toUpperCase() })} placeholder="Ex.: PAST-FREIO-001" />
                  </Col>
                  <Col md={8}>
                    <Form.Label>Nome da peça</Form.Label>
                    <Form.Control required value={form.name} onChange={(event) => update({ name: event.target.value })} placeholder="Ex.: Pastilha de freio dianteira" />
                  </Col>
                  <Col md={6}>
                    <SearchableSelect
                      id="quickPartCategory"
                      label="Categoria"
                      value={form.category_id}
                      options={categoryOptions}
                      onChange={(value) => update({ category_id: value })}
                      placeholder="Pesquisar categoria de peça"
                      emptyMessage="Nenhuma categoria de peça encontrada."
                    />
                  </Col>
                  <Col md={6}>
                    <SearchableSelect
                      id="quickPartLinkedService"
                      label="Serviço vinculado no orçamento"
                      value={form.service_local_id}
                      options={serviceLineOptions}
                      onChange={(value) => update({ service_local_id: value })}
                      placeholder="Pesquisar serviço do orçamento"
                      emptyMessage="Nenhum serviço no orçamento. A peça será cadastrada sem vínculo."
                      helpText="Opcional. Define em qual serviço esta peça aparecerá para aprovação do cliente."
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Marca</Form.Label>
                    <Form.Control value={form.brand} onChange={(event) => update({ brand: event.target.value })} placeholder="Opcional" />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Localização</Form.Label>
                    <Form.Control value={form.location} onChange={(event) => update({ location: event.target.value })} placeholder="Ex.: Prateleira A1" />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Ativa</Form.Label>
                    <Form.Check className="mt-2" label="Disponível no catálogo" checked={form.is_active} onChange={(event) => update({ is_active: event.target.checked })} />
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          </TabPanel>

          <TabPanel activeKey={activeTab} eventKey="stock">
            <Card className="form-section-card">
              <Card.Body>
                <div className="form-section-title">Preço e entrada inicial</div>
                <Row className="g-3">
                  <Col md={4}>
                    <Form.Label>Unidade</Form.Label>
                    <Form.Select value={form.unit} onChange={(event) => update({ unit: normalizePartUnit(event.target.value) })}>
                      {partUnitOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </Form.Select>
                  </Col>
                  <Col md={4}>
                    <Form.Label>Custo</Form.Label>
                    <MoneyInput value={form.cost_price} onChange={(value) => update({ cost_price: value })} />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Preço de venda</Form.Label>
                    <MoneyInput value={form.sale_price} onChange={(value) => update({ sale_price: value })} />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Entrada inicial</Form.Label>
                    <IntegerInput min="0" step="0.01" value={form.initial_stock_quantity} onChange={(event) => update({ initial_stock_quantity: event.target.value })} />
                    <Form.Text>Opcional. Cria um movimento de entrada no estoque.</Form.Text>
                  </Col>
                  <Col md={4}>
                    <Form.Label>Custo da entrada</Form.Label>
                    <MoneyInput value={form.initial_stock_unit_cost || form.cost_price} onChange={(value) => update({ initial_stock_unit_cost: value })} />
                  </Col>
                  <Col md={4}>
                    <Form.Check className="mt-4" label="Peça preferida/mais usada" checked={form.is_featured} onChange={(event) => update({ is_featured: event.target.checked })} />
                  </Col>
                  <Col md={12}>
                    <Form.Label>Observação da entrada</Form.Label>
                    <Form.Control value={form.initial_stock_notes} onChange={(event) => update({ initial_stock_notes: event.target.value })} />
                  </Col>
                  <Col md={12}>
                    <Form.Label>Observações internas da peça</Form.Label>
                    <Form.Control as="textarea" rows={3} value={form.notes} onChange={(event) => update({ notes: event.target.value })} />
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          </TabPanel>

          <TabPanel activeKey={activeTab} eventKey="review">
            <Card className="form-section-card">
              <Card.Body>
                <div className="form-section-title">Conferência antes de salvar</div>
                <div className="form-muted-box">
                  <div className="fw-semibold">{[form.sku || "Sem SKU", form.name || "Peça não informada"].filter(Boolean).join(" - ")}</div>
                  <div className="small text-muted mt-2">Categoria: {categoryOptions.find((option) => String(option.value) === String(form.category_id))?.label || "Sem categoria"}</div>
                  <div className="small text-muted">Marca: {form.brand || "Sem marca"}</div>
                  <div className="small text-muted">Serviço vinculado: {serviceLineOptions.find((option) => String(option.value) === String(form.service_local_id))?.label || "Sem vínculo"}</div>
                  <div className="small text-muted">Entrada inicial: {form.initial_stock_quantity || "0.00"} {normalizePartUnit(form.unit)}</div>
                  <div className="small text-muted">Custo: {money(form.cost_price || 0)} · Venda: {money(form.sale_price || 0)}</div>
                </div>
                <Alert variant="warning" className="mt-3 mb-0">
                  A peça será criada no catálogo e adicionada ao orçamento atual. A entrada inicial será lançada como movimentação de estoque.
                </Alert>
              </Card.Body>
            </Card>
          </TabPanel>
        </Modal.Body>
        <TabbedFormFooter
          tabs={quickPartTabs}
          activeKey={activeTab}
          onSelect={setActiveTab}
          onCancel={onHide}
          cancelLabel="Fechar"
          saveLabel={saving ? "Salvando..." : "Salvar peça"}
          saveDisabled={saving}
        />
      </Form>
    </Modal>
  );
}



function IncludeServiceModal({ show, onHide, onConfirm, services }) {
  const [selectedIds, setSelectedIds] = useState([]);
  const orderedServices = useMemo(() => sortCatalogByUsage(services || []), [services]);

  useEffect(() => {
    if (show) setSelectedIds([]);
  }, [show]);

  function toggle(serviceId) {
    const normalized = String(serviceId);
    setSelectedIds((current) => current.includes(normalized) ? current.filter((item) => item !== normalized) : [...current, normalized]);
  }

  function submit(event) {
    event.preventDefault();
    const selectedServices = orderedServices.filter((service) => selectedIds.includes(String(service.id)));
    if (!selectedServices.length) return;
    onConfirm(selectedServices);
    onHide();
  }

  return <Modal keyboard={false} backdrop="static" size="xl" show={show} onHide={onHide} dialogClassName="floating-form-modal">
    <Form onSubmit={submit}>
      <Modal.Header closeButton><Modal.Title>Adicionar serviço ao orçamento</Modal.Title></Modal.Header>
      <Modal.Body>
        <Card className="border-0 bg-light mb-3"><Card.Body>
          <div className="d-flex flex-wrap justify-content-between align-items-start gap-2 mb-3">
            <div>
              <h6 className="mb-1">Serviços preferidos e mais utilizados</h6>
              <div className="small text-muted">Clique em um ou mais thumbnails para selecionar os serviços que entrarão no orçamento.</div>
            </div>
            <div className="small fw-semibold text-primary">Selecionados: {selectedIds.length}</div>
          </div>
          <div className="os-catalog-grid">
            {orderedServices.map((service) => {
              const selected = selectedIds.includes(String(service.id));
              return <button type="button" key={service.id} className={`os-catalog-card ${selected ? "selected" : ""}`.trim()} onClick={() => toggle(service.id)}>
                <span className="os-catalog-thumb">{service.photo_url ? <img src={service.photo_url} alt={`Foto ${service.name}`} /> : <span>{catalogInitials(service.name)}</span>}</span>
                <span className="os-catalog-title">{service.name}</span>
                <span className="os-catalog-meta">{service.category_name || "Sem categoria"}</span>
                <span className="os-catalog-meta">{money(service.default_unit_price || 0)} · usado {service.usage_count || 0}x</span>
                {service.is_featured ? <span className="os-catalog-featured">Preferido</span> : null}
                {selected ? <span className="os-catalog-selected">Selecionado</span> : null}
              </button>;
            })}
            {!orderedServices.length ? <div className="text-muted small p-3">Nenhum serviço cadastrado.</div> : null}
          </div>
        </Card.Body></Card>
        <Alert variant="light" className="border small mb-0">O preço sugerido vem do cadastro do serviço e pode ser ajustado na tabela do orçamento depois da inclusão.</Alert>
      </Modal.Body>
      <Modal.Footer><Button variant="secondary" onClick={onHide}>Cancelar</Button><Button type="submit" disabled={!selectedIds.length}>Adicionar {selectedIds.length || ""} serviço(s)</Button></Modal.Footer>
    </Form>
  </Modal>;
}

function IncludePartModal({ show, onHide, onConfirm, parts, serviceLineOptions }) {
  const [selectedIds, setSelectedIds] = useState([]);
  const [serviceLocalId, setServiceLocalId] = useState("");
  const orderedParts = useMemo(() => sortCatalogByUsage(parts || []), [parts]);

  useEffect(() => {
    if (show) {
      setSelectedIds([]);
      const firstService = (serviceLineOptions || []).find((option) => option.value);
      setServiceLocalId(firstService?.value || "");
    }
  }, [show, serviceLineOptions]);

  function toggle(partId) {
    const normalized = String(partId);
    setSelectedIds((current) => current.includes(normalized) ? current.filter((item) => item !== normalized) : [...current, normalized]);
  }

  function submit(event) {
    event.preventDefault();
    const selectedParts = orderedParts.filter((part) => selectedIds.includes(String(part.id)));
    if (!selectedParts.length) return;
    onConfirm(selectedParts, serviceLocalId || "");
    onHide();
  }

  return <Modal keyboard={false} backdrop="static" size="xl" show={show} onHide={onHide} dialogClassName="floating-form-modal">
    <Form onSubmit={submit}>
      <Modal.Header closeButton><Modal.Title>Adicionar peça ao orçamento</Modal.Title></Modal.Header>
      <Modal.Body>
        <Card className="border-0 bg-light mb-3"><Card.Body>
          <div className="d-flex flex-wrap justify-content-between align-items-start gap-2 mb-3">
            <div>
              <h6 className="mb-1">Peças preferidas e mais utilizadas</h6>
              <div className="small text-muted">Clique em um ou mais thumbnails para selecionar as peças. O total de cada peça é calculado somente por quantidade × valor unitário, sem somar o serviço vinculado.</div>
            </div>
            <div className="small fw-semibold text-primary">Selecionadas: {selectedIds.length}</div>
          </div>
          <Row className="g-3 mb-3">
            <Col lg={6}>
              <SearchableSelect
                label="Serviço vinculado para as peças selecionadas"
                value={serviceLocalId}
                options={serviceLineOptions}
                onChange={setServiceLocalId}
                placeholder="Pesquisar serviço vinculado"
                emptyMessage="Nenhum serviço no orçamento."
              />
              <div className="small text-muted mt-1">Esse vínculo é apenas organizacional para aprovação parcial. Ele não entra no cálculo do total da peça.</div>
            </Col>
          </Row>
          <div className="os-catalog-grid">
            {orderedParts.map((part) => {
              const selected = selectedIds.includes(String(part.id));
              return <button type="button" key={part.id} className={`os-catalog-card ${selected ? "selected" : ""}`.trim()} onClick={() => toggle(part.id)}>
                <span className="os-catalog-thumb">{part.photo_url ? <img src={part.photo_url} alt={`Foto ${part.name}`} /> : <span>{catalogInitials(part.name)}</span>}</span>
                <span className="os-catalog-title">{part.name}</span>
                <span className="os-catalog-meta">{part.sku || "Sem SKU"} · estoque {part.stock_quantity ?? 0} {part.unit || "un"}</span>
                <span className="os-catalog-meta">{money(part.sale_price || 0)} · usado {part.usage_count || 0}x</span>
                {part.is_featured ? <span className="os-catalog-featured">Preferida</span> : null}
                {selected ? <span className="os-catalog-selected">Selecionada</span> : null}
              </button>;
            })}
            {!orderedParts.length ? <div className="text-muted small p-3">Nenhuma peça cadastrada.</div> : null}
          </div>
        </Card.Body></Card>
        <Alert variant="light" className="border small mb-0">Depois de incluir, ajuste quantidade, valor unitário, desconto e vínculo individualmente na tabela do orçamento.</Alert>
      </Modal.Body>
      <Modal.Footer><Button variant="secondary" onClick={onHide}>Cancelar</Button><Button type="submit" disabled={!selectedIds.length}>Adicionar {selectedIds.length || ""} peça(s)</Button></Modal.Footer>
    </Form>
  </Modal>;
}



function EstimateServiceLineModal({ show, onHide, onConfirm, services }) {
  const [line, setLine] = useState(emptyService());
  const serviceOptions = useMemo(() => [
    { value: "", label: "Serviço manual", description: "Digite livremente a descrição, quantidade e valor." },
    ...sortCatalogByUsage(services || []).map((service) => ({
      value: service.id,
      label: [service.code, service.name].filter(Boolean).join(" - "),
      description: service.category_name || "Serviço cadastrado",
      meta: `Valor padrão: ${money(service.default_unit_price || 0)}`,
    })),
  ], [services]);

  useEffect(() => {
    if (show) setLine(emptyService());
  }, [show]);

  function update(patch) {
    setLine((current) => ({ ...current, ...patch }));
  }

  function selectService(serviceId) {
    const service = (services || []).find((item) => String(item.id) === String(serviceId));
    update(service ? {
      service_id: String(service.id),
      description: service.name || service.description || "",
      unit_price: service.default_unit_price || "0.00",
    } : { service_id: "" });
  }

  function submit(event) {
    event.preventDefault();
    const description = String(line.description || "").trim();
    if (!description) return;
    onConfirm({ ...line, description, quantity: line.quantity || "1.00", unit_price: line.unit_price || "0.00", discount_percent: line.discount_percent || "0" });
  }

  return <Modal keyboard={false} backdrop="static" size="lg" show={show} onHide={onHide} dialogClassName="floating-form-modal">
    <Form onSubmit={submit}>
      <Modal.Header closeButton><Modal.Title>Incluir serviço no orçamento</Modal.Title></Modal.Header>
      <Modal.Body>
        <Row className="g-3">
          <Col md={12}><SearchableSelect label="Serviço do catálogo" value={line.service_id || ""} options={serviceOptions} onChange={selectService} placeholder="Pesquisar serviço ou manter manual" emptyMessage="Nenhum serviço encontrado." /></Col>
          <Col md={12}><Form.Label>Descrição para o cliente</Form.Label><Form.Control required value={line.description} onChange={(event) => update({ description: event.target.value })} placeholder="Ex.: Revisão preventiva" /></Col>
          <Col md={3}><Form.Label>Qtd.</Form.Label><IntegerInput min="0.01" step="0.01" value={line.quantity} onChange={(event) => update({ quantity: event.target.value })} /></Col>
          <Col md={3}><Form.Label>Unitário</Form.Label><MoneyInput value={line.unit_price} onChange={(value) => update({ unit_price: value })} /></Col>
          <Col md={3}><Form.Label>Desconto (%)</Form.Label><PercentInput value={line.discount_percent} onChange={(event) => update({ discount_percent: event.target.value })} /></Col>
          <Col md={3}><div className="finance-total-box total"><span>Total</span><strong>{money(lineTotal(line))}</strong></div></Col>
          <Col md={12}><Form.Label>Observações internas da linha</Form.Label><Form.Control as="textarea" rows={2} value={line.notes || ""} onChange={(event) => update({ notes: event.target.value })} /></Col>
        </Row>
      </Modal.Body>
      <Modal.Footer><Button variant="secondary" onClick={onHide}>Cancelar</Button><Button type="submit" disabled={!String(line.description || "").trim()}>Incluir serviço</Button></Modal.Footer>
    </Form>
  </Modal>;
}

function EstimatePartLineModal({ show, onHide, onConfirm, parts, serviceLineOptions }) {
  const [line, setLine] = useState(emptyPart());
  const partOptions = useMemo(() => [
    { value: "", label: "Peça manual", description: "Digite livremente a descrição, quantidade e valor." },
    ...sortCatalogByUsage(parts || []).map((part) => ({
      value: part.id,
      label: [part.sku, part.name].filter(Boolean).join(" - "),
      description: part.category_name || "Peça cadastrada",
      meta: `Estoque: ${part.stock_quantity ?? 0} · Venda: ${money(part.sale_price || 0)}`,
    })),
  ], [parts]);

  useEffect(() => {
    if (!show) return;
    const firstService = (serviceLineOptions || []).find((option) => option.value);
    setLine({ ...emptyPart(), service_local_id: firstService?.value || "" });
  }, [show, serviceLineOptions]);

  function update(patch) {
    setLine((current) => ({ ...current, ...patch }));
  }

  function selectPart(partId) {
    const part = (parts || []).find((item) => String(item.id) === String(partId));
    update(part ? {
      part_id: String(part.id),
      description: part.name || "",
      unit_price: part.sale_price || "0.00",
      cost_price: part.cost_price || "0.00",
    } : { part_id: "" });
  }

  function submit(event) {
    event.preventDefault();
    const description = String(line.description || "").trim();
    if (!description) return;
    onConfirm({ ...line, description, quantity: line.quantity || "1.00", unit_price: line.unit_price || "0.00", cost_price: line.cost_price || "0.00", discount_percent: line.discount_percent || "0" });
  }

  return <Modal keyboard={false} backdrop="static" size="lg" show={show} onHide={onHide} dialogClassName="floating-form-modal">
    <Form onSubmit={submit}>
      <Modal.Header closeButton><Modal.Title>Incluir peça no orçamento</Modal.Title></Modal.Header>
      <Modal.Body>
        <Row className="g-3">
          <Col md={12}><SearchableSelect label="Serviço vinculado" value={line.service_local_id || ""} options={serviceLineOptions} onChange={(value) => update({ service_local_id: value })} placeholder="Pesquisar serviço vinculado" emptyMessage="Nenhum serviço no orçamento." /></Col>
          <Col md={12}><SearchableSelect label="Peça do catálogo" value={line.part_id || ""} options={partOptions} onChange={selectPart} placeholder="Pesquisar peça ou manter manual" emptyMessage="Nenhuma peça encontrada." /></Col>
          <Col md={12}><Form.Label>Descrição para o cliente</Form.Label><Form.Control required value={line.description} onChange={(event) => update({ description: event.target.value })} placeholder="Ex.: Filtro de óleo" /></Col>
          <Col md={3}><Form.Label>Qtd.</Form.Label><IntegerInput min="0.01" step="0.01" value={line.quantity} onChange={(event) => update({ quantity: event.target.value })} /></Col>
          <Col md={3}><Form.Label>Unitário</Form.Label><MoneyInput value={line.unit_price} onChange={(value) => update({ unit_price: value })} /></Col>
          <Col md={3}><Form.Label>Desconto (%)</Form.Label><PercentInput value={line.discount_percent} onChange={(event) => update({ discount_percent: event.target.value })} /></Col>
          <Col md={3}><div className="finance-total-box total"><span>Total</span><strong>{money(partLineTotal(line))}</strong></div></Col>
          <Col md={4}><Form.Label>Custo interno</Form.Label><MoneyInput value={line.cost_price} onChange={(value) => update({ cost_price: value })} /></Col>
          <Col md={8}><Form.Label>Observações internas da linha</Form.Label><Form.Control value={line.notes || ""} onChange={(event) => update({ notes: event.target.value })} /></Col>
        </Row>
      </Modal.Body>
      <Modal.Footer><Button variant="secondary" onClick={onHide}>Cancelar</Button><Button type="submit" disabled={!String(line.description || "").trim()}>Incluir peça</Button></Modal.Footer>
    </Form>
  </Modal>;
}


function ReplaceServiceModal({ show, onHide, onConfirm, services, line }) {
  const [selectedId, setSelectedId] = useState("");
  const [quantity, setQuantity] = useState("1.00");
  const orderedServices = useMemo(() => sortCatalogByUsage(services || []), [services]);
  const selectedService = orderedServices.find((service) => String(service.id) === String(selectedId));

  useEffect(() => {
    if (!show || !line) return;
    setSelectedId(line.service_id ? String(line.service_id) : "");
    setQuantity(line.quantity || "1.00");
  }, [show, line]);

  function submit(event) {
    event.preventDefault();
    if (!line?.local_id || !selectedService) return;
    onConfirm(line.local_id, selectedService, quantity || line.quantity || "1.00");
    onHide();
  }

  return <Modal keyboard={false} backdrop="static" size="xl" show={show} onHide={onHide} dialogClassName="floating-form-modal">
    <Form onSubmit={submit}>
      <Modal.Header closeButton><Modal.Title>Trocar serviço da linha</Modal.Title></Modal.Header>
      <Modal.Body>
        <Alert variant="info" className="mb-3">
          Selecione o novo serviço pelo mesmo padrão de thumbnails. A linha mantém o desconto, observações, identificador interno e peças vinculadas ao serviço; a quantidade abaixo pode ser mantida ou alterada antes da troca.
        </Alert>
        <Card className="border-0 bg-light mb-3"><Card.Body>
          <Row className="g-3 align-items-end mb-3">
            <Col lg={8}>
              <div className="small text-muted mb-1">Serviço atual</div>
              <div className="fw-semibold">{line?.description || "Serviço sem descrição"}</div>
              <div className="small text-muted">Desconto preservado: {line?.discount_percent || 0}% · Total atual: {money(lineTotal(line || {}))}</div>
            </Col>
            <Col lg={4}>
              <Form.Label>Quantidade após a troca</Form.Label>
              <IntegerInput min="0.01" step="0.01" value={quantity} onChange={(event) => setQuantity(event.target.value)} />
              <Form.Text>O campo inicia com a quantidade da linha atual.</Form.Text>
            </Col>
          </Row>
          <div className="d-flex flex-wrap justify-content-between align-items-start gap-2 mb-3">
            <div>
              <h6 className="mb-1">Serviços disponíveis</h6>
              <div className="small text-muted">Clique em um thumbnail para escolher o serviço substituto da linha existente.</div>
            </div>
            <div className="small fw-semibold text-primary">Selecionado: {selectedService?.name || "nenhum"}</div>
          </div>
          <div className="os-catalog-grid">
            {orderedServices.map((service) => {
              const selected = String(service.id) === String(selectedId);
              return <button type="button" key={service.id} className={`os-catalog-card ${selected ? "selected" : ""}`.trim()} onClick={() => setSelectedId(String(service.id))}>
                <span className="os-catalog-thumb">{service.photo_url ? <img src={service.photo_url} alt={`Foto ${service.name}`} /> : <span>{catalogInitials(service.name)}</span>}</span>
                <span className="os-catalog-title">{service.name}</span>
                <span className="os-catalog-meta">{service.category_name || "Sem categoria"}</span>
                <span className="os-catalog-meta">{money(service.default_unit_price || 0)} · usado {service.usage_count || 0}x</span>
                {service.is_featured ? <span className="os-catalog-featured">Preferido</span> : null}
                {selected ? <span className="os-catalog-selected">Substituto</span> : null}
              </button>;
            })}
            {!orderedServices.length ? <div className="text-muted small p-3">Nenhum serviço cadastrado.</div> : null}
          </div>
        </Card.Body></Card>
        <Alert variant="light" className="border small mb-0">O valor unitário será atualizado pelo preço padrão do novo serviço. Desconto, observações e vínculos de peças da linha permanecem preservados.</Alert>
      </Modal.Body>
      <Modal.Footer><Button variant="secondary" onClick={onHide}>Cancelar</Button><Button type="submit" disabled={!selectedService}>Trocar serviço</Button></Modal.Footer>
    </Form>
  </Modal>;
}

function ReplacePartModal({ show, onHide, onConfirm, parts, line, serviceLineOptions }) {
  const [selectedId, setSelectedId] = useState("");
  const [quantity, setQuantity] = useState("1.00");
  const [serviceLocalId, setServiceLocalId] = useState("");
  const orderedParts = useMemo(() => sortCatalogByUsage(parts || []), [parts]);
  const selectedPart = orderedParts.find((part) => String(part.id) === String(selectedId));

  useEffect(() => {
    if (!show || !line) return;
    setSelectedId(line.part_id ? String(line.part_id) : "");
    setQuantity(line.quantity || "1.00");
    setServiceLocalId(line.service_local_id || "");
  }, [show, line]);

  function submit(event) {
    event.preventDefault();
    if (!line?.local_id || !selectedPart) return;
    onConfirm(line.local_id, selectedPart, quantity || line.quantity || "1.00", serviceLocalId || "");
    onHide();
  }

  return <Modal keyboard={false} backdrop="static" size="xl" show={show} onHide={onHide} dialogClassName="floating-form-modal">
    <Form onSubmit={submit}>
      <Modal.Header closeButton><Modal.Title>Trocar peça da linha</Modal.Title></Modal.Header>
      <Modal.Body>
        <Alert variant="info" className="mb-3">
          Selecione a nova peça pelo mesmo padrão de thumbnails. A linha mantém desconto, observações e o vínculo de serviço atual; quantidade e vínculo podem ser ajustados antes de confirmar.
        </Alert>
        <Card className="border-0 bg-light mb-3"><Card.Body>
          <Row className="g-3 align-items-end mb-3">
            <Col lg={4}>
              <div className="small text-muted mb-1">Peça atual</div>
              <div className="fw-semibold">{line?.description || "Peça sem descrição"}</div>
              <div className="small text-muted">Desconto preservado: {line?.discount_percent || 0}% · Total atual: {money(partLineTotal(line || {}))}</div>
            </Col>
            <Col lg={3}>
              <Form.Label>Quantidade após a troca</Form.Label>
              <IntegerInput min="0.01" step="0.01" value={quantity} onChange={(event) => setQuantity(event.target.value)} />
              <Form.Text>O campo inicia com a quantidade da linha atual.</Form.Text>
            </Col>
            <Col lg={5}>
              <SearchableSelect
                label="Serviço vinculado após a troca"
                value={serviceLocalId}
                options={serviceLineOptions}
                onChange={setServiceLocalId}
                placeholder="Pesquisar serviço vinculado"
                emptyMessage="Nenhum serviço no orçamento."
              />
              <div className="small text-muted mt-1">Mantém o vínculo atual por padrão para preservar a aprovação item a item.</div>
            </Col>
          </Row>
          <div className="d-flex flex-wrap justify-content-between align-items-start gap-2 mb-3">
            <div>
              <h6 className="mb-1">Peças disponíveis</h6>
              <div className="small text-muted">Clique em um thumbnail para escolher a peça substituta da linha existente.</div>
            </div>
            <div className="small fw-semibold text-primary">Selecionada: {selectedPart?.name || "nenhuma"}</div>
          </div>
          <div className="os-catalog-grid">
            {orderedParts.map((part) => {
              const selected = String(part.id) === String(selectedId);
              return <button type="button" key={part.id} className={`os-catalog-card ${selected ? "selected" : ""}`.trim()} onClick={() => setSelectedId(String(part.id))}>
                <span className="os-catalog-thumb">{part.photo_url ? <img src={part.photo_url} alt={`Foto ${part.name}`} /> : <span>{catalogInitials(part.name)}</span>}</span>
                <span className="os-catalog-title">{part.name}</span>
                <span className="os-catalog-meta">{part.sku || "Sem SKU"} · estoque {part.stock_quantity ?? 0} {part.unit || "un"}</span>
                <span className="os-catalog-meta">{money(part.sale_price || 0)} · usado {part.usage_count || 0}x</span>
                {part.is_featured ? <span className="os-catalog-featured">Preferida</span> : null}
                {selected ? <span className="os-catalog-selected">Substituta</span> : null}
              </button>;
            })}
            {!orderedParts.length ? <div className="text-muted small p-3">Nenhuma peça cadastrada.</div> : null}
          </div>
        </Card.Body></Card>
        <Alert variant="light" className="border small mb-0">O valor unitário e o custo serão atualizados pelo cadastro da nova peça. Desconto, observações e rastreio da linha permanecem preservados.</Alert>
      </Modal.Body>
      <Modal.Footer><Button variant="secondary" onClick={onHide}>Cancelar</Button><Button type="submit" disabled={!selectedPart}>Trocar peça</Button></Modal.Footer>
    </Form>
  </Modal>;
}

function IncludePackageModal({ show, onHide, onConfirm, servicePackages }) {
  const [selectedIds, setSelectedIds] = useState([]);
  const orderedPackages = useMemo(() => [...(servicePackages || [])].sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), "pt-BR")), [servicePackages]);

  useEffect(() => {
    if (show) setSelectedIds([]);
  }, [show]);

  function toggle(packageId) {
    const normalized = String(packageId);
    setSelectedIds((current) => current.includes(normalized) ? current.filter((item) => item !== normalized) : [...current, normalized]);
  }

  function submit(event) {
    event.preventDefault();
    const selectedPackages = orderedPackages.filter((servicePackage) => selectedIds.includes(String(servicePackage.id)));
    if (!selectedPackages.length) return;
    onConfirm(selectedPackages);
    onHide();
  }

  return <Modal keyboard={false} backdrop="static" size="xl" show={show} onHide={onHide} dialogClassName="floating-form-modal">
    <Form onSubmit={submit}>
      <Modal.Header closeButton><Modal.Title>Incluir combo no orçamento</Modal.Title></Modal.Header>
      <Modal.Body>
        <Card className="border-0 bg-light mb-3"><Card.Body>
          <div className="d-flex flex-wrap justify-content-between align-items-start gap-2 mb-3">
            <div>
              <h6 className="mb-1">Combos cadastrados</h6>
              <div className="small text-muted">Clique em um ou mais thumbnails para incluir todos os serviços dos combos no orçamento.</div>
            </div>
            <div className="small fw-semibold text-primary">Selecionados: {selectedIds.length}</div>
          </div>
          <div className="os-catalog-grid">
            {orderedPackages.map((servicePackage) => {
              const selected = selectedIds.includes(String(servicePackage.id));
              return <button type="button" key={servicePackage.id} className={`os-catalog-card ${selected ? "selected" : ""}`.trim()} onClick={() => toggle(servicePackage.id)}>
                <span className="os-catalog-thumb"><span>{catalogInitials(servicePackage.name)}</span></span>
                <span className="os-catalog-title">{servicePackage.name}</span>
                <span className="os-catalog-meta">{servicePackage.code || "Sem código"} · {servicePackage.items?.length || 0} serviço(s)</span>
                <span className="os-catalog-meta">Total: {money(servicePackage.total_amount || 0)}</span>
                {decimal(servicePackage.discount_amount) > 0 ? <span className="os-catalog-featured">Desconto {money(servicePackage.discount_amount)}</span> : null}
                {selected ? <span className="os-catalog-selected">Selecionado</span> : null}
              </button>;
            })}
            {!orderedPackages.length ? <div className="text-muted small p-3">Nenhum combo cadastrado.</div> : null}
          </div>
        </Card.Body></Card>
        <Alert variant="light" className="border small mb-0">O desconto cadastrado no combo será somado ao desconto geral do orçamento, mantendo os serviços listados individualmente para aprovação do cliente.</Alert>
      </Modal.Body>
      <Modal.Footer><Button variant="secondary" onClick={onHide}>Cancelar</Button><Button type="submit" disabled={!selectedIds.length}>Incluir {selectedIds.length || ""} combo(s)</Button></Modal.Footer>
    </Form>
  </Modal>;
}

function QuickPackageModal({ show, onHide, onCreated, services }) {
  const [form, setForm] = useState(emptyQuickPackage());
  const [activeTab, setActiveTab] = useState("package");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const serviceOptions = useMemo(() => [
    { value: "", label: "Serviço manual", description: "Use esta opção para digitar a descrição manualmente." },
    ...(services || []).map((service) => ({
      value: service.id,
      label: [service.code, service.name].filter(Boolean).join(" - "),
      description: service.category_name || "Serviço cadastrado",
      meta: `Valor padrão: ${money(service.default_unit_price || 0)}`,
    })),
  ], [services]);

  const subtotal = useMemo(() => form.items.reduce((total, item) => total + lineSubtotal(item), 0), [form.items]);
  const total = Math.max(subtotal - decimal(form.discount_amount), 0);

  useEffect(() => {
    if (!show) return;
    setForm(emptyQuickPackage());
    setActiveTab("package");
    setError("");
    setSaving(false);
    api.get("/workshop/service-packages/next-code/")
      .then(({ data }) => setForm((current) => ({ ...current, code: data?.code || "" })))
      .catch(() => setForm((current) => ({ ...current, code: "" })));
  }, [show]);

  function update(patch) {
    setForm((current) => ({ ...current, ...patch }));
  }

  function addItem() {
    setForm((current) => ({ ...current, items: [...current.items, emptyQuickPackageItem()] }));
    setActiveTab("items");
  }

  function updateItem(localId, patch) {
    setForm((current) => ({
      ...current,
      items: current.items.map((line) => (line.local_id === localId ? { ...line, ...patch } : line)),
    }));
  }

  function removeItem(localId) {
    setForm((current) => ({ ...current, items: current.items.filter((line) => line.local_id !== localId) }));
  }

  function selectService(localId, serviceId) {
    const service = (services || []).find((item) => String(item.id) === String(serviceId));
    updateItem(localId, service ? {
      service_id: serviceId,
      description: service.name || service.description || "",
      unit_price: service.default_unit_price || "0.00",
    } : { service_id: serviceId });
  }

  function validate() {
    if (!form.name.trim()) {
      setActiveTab("package");
      setError("Informe o nome do combo.");
      return false;
    }
    if (form.items.length === 0) {
      setActiveTab("items");
      setError("Inclua pelo menos um serviço no combo.");
      return false;
    }
    const invalidItem = form.items.find((item) => !String(item.description || "").trim());
    if (invalidItem) {
      setActiveTab("items");
      setError("Todos os serviços do combo precisam ter descrição.");
      return false;
    }
    return true;
  }

  async function save(event) {
    event.preventDefault();
    setError("");
    if (!validate()) return;
    setSaving(true);

    try {
      const payload = {
        code: form.code.trim().toUpperCase(),
        name: form.name.trim(),
        description: form.description.trim(),
        discount_amount: form.discount_amount || "0.00",
        is_active: !!form.is_active,
        items: form.items.map((line, index) => ({
          service_id: line.service_id ? Number(line.service_id) : null,
          description: line.description,
          quantity: line.quantity || "1.00",
          unit_price: line.unit_price || "0.00",
          position: index + 1,
        })),
      };
      const { data } = await api.post("/workshop/service-packages/", payload);
      onCreated(data);
      onHide();
    } catch (err) {
      setError(apiError(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal keyboard={false} backdrop="static" size="lg" show={show} onHide={onHide} className="floating-form-modal" centered>
      <Form onSubmit={save} noValidate>
        <Modal.Header closeButton={!saving}>
          <Modal.Title>Novo combo rápido</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="info" className="mb-3">
            Cadastre um combo/pacote sem sair do orçamento. Ao salvar, o combo será criado no catálogo e seus serviços serão adicionados ao orçamento atual.
          </Alert>
          <ErrorAlert error={error} onClose={() => setError("")} />
          <FormTabs tabs={quickPackageTabs} activeKey={activeTab} onSelect={setActiveTab} />

          <TabPanel activeKey={activeTab} eventKey="package">
            <Card className="form-section-card">
              <Card.Body>
                <div className="form-section-title">Identificação do combo</div>
                <Row className="g-3">
                  <Col md={4}>
                    <Form.Label>Código</Form.Label>
                    <Form.Control value={form.code} onChange={(event) => update({ code: event.target.value.toUpperCase() })} placeholder="Gerado automaticamente" />
                  </Col>
                  <Col md={8}>
                    <Form.Label>Nome do combo</Form.Label>
                    <Form.Control required value={form.name} onChange={(event) => update({ name: event.target.value })} placeholder="Ex.: Revisão preventiva básica" />
                  </Col>
                  <Col md={8}>
                    <Form.Label>Descrição comercial/técnica</Form.Label>
                    <Form.Control as="textarea" rows={4} value={form.description} onChange={(event) => update({ description: event.target.value })} placeholder="Explique o que está incluído no combo." />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Desconto do combo</Form.Label>
                    <MoneyInput value={form.discount_amount} onChange={(value) => update({ discount_amount: value })} />
                    <Form.Check className="mt-3" label="Combo ativo no catálogo" checked={form.is_active} onChange={(event) => update({ is_active: event.target.checked })} />
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          </TabPanel>

          <TabPanel activeKey={activeTab} eventKey="items">
            <Card className="form-section-card">
              <Card.Header className="bg-white d-flex justify-content-between align-items-center">
                <div>
                  <span className="fw-semibold d-block">Serviços do combo</span>
                  <span className="small text-muted">Pesquise serviços cadastrados ou informe serviços manuais.</span>
                </div>
                <Button size="sm" type="button" variant="outline-primary" onClick={addItem}>Adicionar serviço</Button>
              </Card.Header>
              <Card.Body className="p-0">
                <Table responsive bordered className="mb-0 align-middle">
                  <thead><tr><th style={{ minWidth: 280 }}>Serviço</th><th style={{ minWidth: 260 }}>Descrição</th><th style={{ width: 110 }}>Qtd</th><th style={{ width: 140 }}>Unitário</th><th style={{ width: 130 }}>Total</th><th style={{ width: 100 }}></th></tr></thead>
                  <tbody>
                    {form.items.length === 0 ? <tr><td colSpan={6} className="text-center text-muted py-4">Nenhum serviço no combo.</td></tr> : null}
                    {form.items.map((line) => (
                      <tr key={line.local_id}>
                        <td><SearchableSelect value={line.service_id || ""} options={serviceOptions} onChange={(value) => selectService(line.local_id, value)} placeholder="Pesquisar serviço" emptyMessage="Nenhum serviço encontrado." />{line.source_package_name ? <div className="small text-primary mt-1">Combo: {line.source_package_name}</div> : null}</td>
                        <td><Form.Control value={line.description} onChange={(event) => updateItem(line.local_id, { description: event.target.value })} placeholder="Descrição do serviço no combo" /></td>
                        <td><IntegerInput min="0.01" step="0.01" value={line.quantity} onChange={(event) => updateItem(line.local_id, { quantity: event.target.value })} /></td>
                        <td><MoneyInput value={line.unit_price} onChange={(value) => updateItem(line.local_id, { unit_price: value })} /></td>
                        <td>{money(lineSubtotal(line))}</td>
                        <td><Button size="sm" variant="outline-danger" type="button" onClick={() => removeItem(line.local_id)}>Remover</Button></td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Card.Body>
            </Card>
          </TabPanel>

          <TabPanel activeKey={activeTab} eventKey="review">
            <Card className="form-section-card">
              <Card.Body>
                <div className="form-section-title">Conferência antes de salvar</div>
                <div className="form-muted-box">
                  <div className="fw-semibold">{[form.code, form.name || "Combo não informado"].filter(Boolean).join(" - ")}</div>
                  <div className="small text-muted mt-2">Serviços: {form.items.length}</div>
                  <div className="small text-muted">Subtotal: {money(subtotal)} · Desconto: {money(form.discount_amount || 0)} · Total: {money(total)}</div>
                  <div className="small text-muted mt-2">{form.description || "Sem descrição."}</div>
                </div>
                <Alert variant="warning" className="mt-3 mb-0">
                  Os serviços do combo serão adicionados ao orçamento como linhas de serviço vinculadas ao pacote criado.
                </Alert>
              </Card.Body>
            </Card>
          </TabPanel>
        </Modal.Body>
        <TabbedFormFooter
          tabs={quickPackageTabs}
          activeKey={activeTab}
          onSelect={setActiveTab}
          onCancel={onHide}
          cancelLabel="Fechar"
          saveLabel={saving ? "Salvando..." : "Salvar combo"}
          saveDisabled={saving}
        />
      </Form>
    </Modal>
  );
}

export default function EstimateFormPage({ embedded = false, returnTo }) {
  const { id } = useParams();
  const editing = Boolean(id);
  const navigate = useNavigate();
  const location = useLocation();
  const returnPath = returnTo || resolveReturnTo(location, "/attendance/estimates");
  const closeForm = () => navigate(returnPath, { replace: true });
  const [contacts, setContacts] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [services, setServices] = useState([]);
  const [parts, setParts] = useState([]);
  const [servicePackages, setServicePackages] = useState([]);
  const [serviceCategories, setServiceCategories] = useState([]);
  const [partCategories, setPartCategories] = useState([]);
  const [form, setForm] = useState(emptyEstimate());
  const [sourceEstimate, setSourceEstimate] = useState(null);
  const [activeTab, setActiveTab] = useState("customer");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [quickCustomerVehicleModal, setQuickCustomerVehicleModal] = useState(false);
  const [quickServiceModal, setQuickServiceModal] = useState(false);
  const [quickPartModal, setQuickPartModal] = useState(false);
  const [quickPackageModal, setQuickPackageModal] = useState(false);
  const [includeServiceModal, setIncludeServiceModal] = useState(false);
  const [includePartModal, setIncludePartModal] = useState(false);
  const [includePackageModal, setIncludePackageModal] = useState(false);
  const [manualServiceModal, setManualServiceModal] = useState(false);
  const [manualPartModal, setManualPartModal] = useState(false);
  const [replaceServiceLine, setReplaceServiceLine] = useState(null);
  const [replacePartLine, setReplacePartLine] = useState(null);

  const vehiclesForCustomer = useMemo(() => vehicles.filter((vehicle) => String(vehicle.customer?.id) === String(form.customer_id)), [vehicles, form.customer_id]);
  const subtotalServices = useMemo(() => form.services.reduce((total, line) => total + lineSubtotal(line), 0), [form.services]);
  const subtotalParts = useMemo(() => form.parts.reduce((total, line) => total + partLineSubtotal(line), 0), [form.parts]);
  const itemDiscounts = useMemo(() => form.services.reduce((total, line) => total + lineDiscountAmount(line), 0) + form.parts.reduce((total, line) => total + partDiscountAmount(line), 0), [form.services, form.parts]);
  const estimateDiscountBase = Math.max(subtotalServices + subtotalParts - itemDiscounts, 0);
  const generalDiscountAmount = useMemo(() => percentAmount(estimateDiscountBase, form.discount_percent), [estimateDiscountBase, form.discount_percent]);
  const finalTotal = Math.max(estimateDiscountBase - generalDiscountAmount, 0);

  const customerOptions = useMemo(() => contacts.map((contact) => ({ value: contact.id, label: contactName(contact), description: [contact.phone_e164 || "sem telefone", contact.email || "sem email"].join(" · "), meta: contact.document_number ? `CPF/CNPJ: ${contact.document_number}` : "" })), [contacts]);
  const vehicleOptions = useMemo(() => vehiclesForCustomer.map((vehicle) => ({ value: vehicle.id, label: vehicle.display_name || [vehicle.plate, vehicle.model].filter(Boolean).join(" - ") || `Veículo #${vehicle.id}`, description: [vehicle.make || vehicle.brand, vehicle.model, vehicle.year].filter(Boolean).join(" · "), meta: vehicle.plate ? `Placa: ${vehicle.plate}` : "" })), [vehiclesForCustomer]);
  const serviceOptions = useMemo(() => [{ value: "", label: "Serviço manual", description: "Use esta opção para digitar a descrição manualmente." }, ...services.map((service) => ({ value: service.id, label: [service.code, service.name].filter(Boolean).join(" - "), description: service.category_name || "Serviço cadastrado", meta: `Valor padrão: ${money(service.default_unit_price || 0)}` }))], [services]);
  const packageOptions = useMemo(() => [{ value: "", label: "Selecione um combo", description: "Adicione todos os serviços do combo ao orçamento." }, ...servicePackages.map((servicePackage) => ({ value: servicePackage.id, label: [servicePackage.code, servicePackage.name].filter(Boolean).join(" - "), description: `${servicePackage.items?.length || 0} serviço(s) · Total: ${money(servicePackage.total_amount || 0)}`, meta: servicePackage.description || "Combo/pacote de serviços" }))], [servicePackages]);
  const partOptions = useMemo(() => [{ value: "", label: "Peça manual", description: "Use esta opção para digitar a descrição manualmente." }, ...parts.map((part) => ({ value: part.id, label: [part.sku, part.name].filter(Boolean).join(" - "), description: part.category_name || "Peça cadastrada", meta: `Estoque: ${part.stock_quantity ?? 0} · Venda: ${money(part.sale_price || 0)}` }))], [parts]);
  const serviceLineOptions = useMemo(() => [{ value: "", label: "Sem vínculo", description: "A peça ficará solta no orçamento." }, ...form.services.map((serviceLine, index) => ({ value: serviceLine.local_id, label: `Serviço ${index + 1} - ${serviceLine.description || "sem descrição"}`, description: `Total do serviço: ${money(lineTotal(serviceLine))}` }))], [form.services]);
  const selectedCustomer = useMemo(() => contacts.find((contact) => String(contact.id) === String(form.customer_id)), [contacts, form.customer_id]);
  const selectedVehicle = useMemo(() => vehicles.find((vehicle) => String(vehicle.id) === String(form.vehicle_id)), [vehicles, form.vehicle_id]);
  const partsWithoutLinkedService = useMemo(() => form.parts.filter((line) => !line.service_local_id), [form.parts]);

  const tabs = [
    { key: "customer", label: "Cliente", description: "Dados principais" },
    { key: "services", label: "Serviços", description: "Mão de obra", badge: form.services.length || "" },
    { key: "parts", label: "Peças", description: partsWithoutLinkedService.length ? `${partsWithoutLinkedService.length} sem vínculo` : "Materiais e peças", badge: form.parts.length || "" },
    { key: "summary", label: "Resumo", description: "Valores e observações" },
  ];

  async function loadReferences() {
    try {
      const [contactRes, vehicleRes, serviceRes, partRes, packageRes, serviceCategoryRes, partCategoryRes] = await Promise.all([
        api.get("/contacts/"),
        api.get("/workshop/vehicles/", { params: { active: "true" } }),
        api.get("/workshop/services/", { params: { active: "true" } }),
        api.get("/workshop/parts/", { params: { active: "true" } }),
        api.get("/workshop/service-packages/", { params: { active: "true" } }),
        api.get("/workshop/categories/", { params: { type: "service", active: "true" } }),
        api.get("/workshop/categories/", { params: { type: "part", active: "true" } }),
      ]);
      setContacts(results(contactRes.data));
      setVehicles(results(vehicleRes.data));
      setServices(results(serviceRes.data));
      setParts(results(partRes.data));
      setServicePackages(results(packageRes.data));
      setServiceCategories(results(serviceCategoryRes.data));
      setPartCategories(results(partCategoryRes.data));

      if (editing) {
        const { data } = await api.get(`/attendance/estimates/${id}/`);
        setSourceEstimate(data);
        const loadedServices = (data.services || []).map((line) => ({
          ...line,
          local_id: String(line.id || makeLocalId()),
          service_id: line.service || line.service_id || "",
          source_package_id: line.source_package || line.source_package_id || "",
          source_package_name: line.source_package_name || "",
          quantity: line.quantity || "1.00",
          unit_price: line.unit_price || "0.00",
          discount_percent: percentFromAmount(decimal(line.quantity || "1.00") * decimal(line.unit_price || "0.00"), line.discount_amount || "0.00"),
        }));
        const loadedParts = (data.parts || []).map((line) => ({
          ...line,
          local_id: String(line.id || makeLocalId()),
          service_local_id: line.service_item ? String(line.service_item) : "",
          part_id: line.part || line.part_id || "",
          quantity: line.quantity || "1.00",
          unit_price: line.unit_price || "0.00",
          cost_price: line.cost_price || "0.00",
          discount_percent: percentFromAmount(decimal(line.quantity || "1.00") * decimal(line.unit_price || "0.00"), line.discount_amount || "0.00"),
        }));
        const generalDiscountBase = Math.max(
          loadedServices.reduce((total, line) => total + lineSubtotal(line), 0)
          + loadedParts.reduce((total, line) => total + partLineSubtotal(line), 0)
          - loadedServices.reduce((total, line) => total + lineDiscountAmount(line), 0)
          - loadedParts.reduce((total, line) => total + partDiscountAmount(line), 0),
          0,
        );
        setForm({
          customer_id: data.customer?.id || "",
          vehicle_id: data.vehicle?.id || "",
          title: data.title || "",
          complaint: data.complaint || "",
          diagnosis: data.diagnosis || "",
          internal_notes: data.internal_notes || "",
          customer_notes: data.customer_notes || "",
          valid_until: data.valid_until || dateInputValue(),
          tank_level_percent: String(data.tank_level_percent ?? 0),
          discount_percent: percentFromAmount(generalDiscountBase, data.discount_amount || "0.00"),
          services: loadedServices,
          parts: loadedParts,
        });
      } else {
        setSourceEstimate(null);
        setForm(emptyEstimate());
      }
    } catch (err) {
      setError(apiError(err));
    }
  }

  useEffect(() => { loadReferences(); }, [id]);

  function addService(line) {
    setForm((current) => ({ ...current, services: [...current.services, { ...emptyService(), ...line, local_id: line.local_id || makeLocalId() }] }));
    setManualServiceModal(false);
    setActiveTab("services");
  }
  function addPart(line) {
    setForm((current) => ({ ...current, parts: [...current.parts, { ...emptyPart(), ...line, local_id: line.local_id || makeLocalId() }] }));
    setManualPartModal(false);
    setActiveTab("parts");
  }
  function addSelectedServicesToEstimate(selectedServices) {
    const nextLines = selectedServices.map((service) => ({
      ...emptyService(),
      service_id: String(service.id),
      source_package_id: "",
      source_package_name: "",
      description: service.name || service.description || "",
      unit_price: service.default_unit_price || "0.00",
      discount_percent: "0",
    }));
    const nextParts = selectedServices.flatMap((service, index) => defaultPartsForService(service, nextLines[index]?.local_id));
    setForm((current) => ({ ...current, services: [...current.services, ...nextLines], parts: [...current.parts, ...nextParts] }));
    setActiveTab("services");
  }
  function addSelectedPartsToEstimate(selectedParts, serviceLocalId = "") {
    const nextLines = selectedParts.map((part) => ({
      ...emptyPart(),
      service_local_id: serviceLocalId || "",
      part_id: String(part.id),
      description: part.name || "",
      unit_price: part.sale_price || "0.00",
      cost_price: part.cost_price || "0.00",
      discount_percent: "0",
    }));
    setForm((current) => ({ ...current, parts: [...current.parts, ...nextLines] }));
    setActiveTab("parts");
  }
  function removeService(localId) { setForm((current) => ({ ...current, services: current.services.filter((line) => line.local_id !== localId), parts: current.parts.filter((line) => line.service_local_id !== localId) })); }
  function removePart(localId) { setForm((current) => ({ ...current, parts: current.parts.filter((line) => line.local_id !== localId) })); }
  function updateService(localId, patch) { setForm((current) => ({ ...current, services: current.services.map((line) => line.local_id === localId ? { ...line, ...patch } : line) })); }
  function updatePart(localId, patch) { setForm((current) => ({ ...current, parts: current.parts.map((line) => line.local_id === localId ? { ...line, ...patch } : line) })); }

  function replaceServiceInEstimate(localId, service, quantity = "1.00") {
    if (!service?.id) return;
    const autoParts = defaultPartsForService(service, localId);
    setForm((current) => ({
      ...current,
      services: current.services.map((line) => (line.local_id === localId ? {
        ...line,
        service_id: String(service.id),
        source_package_id: "",
        source_package_name: "",
        description: service.name || service.description || line.description || "",
        quantity: quantity || line.quantity || "1.00",
        unit_price: service.default_unit_price || "0.00",
      } : line)),
      parts: [...current.parts, ...autoParts],
    }));
    setActiveTab("services");
  }

  function replacePartInEstimate(localId, part, quantity = "1.00", serviceLocalId = "") {
    if (!part?.id) return;
    setForm((current) => ({
      ...current,
      parts: current.parts.map((line) => (line.local_id === localId ? {
        ...line,
        service_local_id: serviceLocalId || "",
        part_id: String(part.id),
        description: part.name || line.description || "",
        quantity: quantity || line.quantity || "1.00",
        unit_price: part.sale_price || "0.00",
        cost_price: part.cost_price || "0.00",
      } : line)),
    }));
    setActiveTab("parts");
  }

  function selectCustomer(customerId) {
    const customerVehicles = vehicles.filter((vehicle) => String(vehicle.customer?.id) === String(customerId));
    setForm((current) => ({ ...current, customer_id: customerId, vehicle_id: customerId ? String(customerVehicles[0]?.id || "") : "" }));
  }

  function handleQuickCustomerVehicleCreated(contact, vehicle) {
    setContacts((current) => [contact, ...current.filter((item) => String(item.id) !== String(contact.id))]);
    setVehicles((current) => [vehicle, ...current.filter((item) => String(item.id) !== String(vehicle.id))]);
    setForm((current) => ({ ...current, customer_id: String(contact.id), vehicle_id: String(vehicle.id) }));
    setActiveTab("customer");
  }

  function handleQuickServiceCreated(service) {
    const serviceId = String(service.id);
    const nextLine = {
      ...emptyService(),
      service_id: serviceId,
      description: service.name || service.description || "",
      unit_price: service.default_unit_price || "0.00",
    };
    const nextParts = defaultPartsForService(service, nextLine.local_id);
    setServices((current) => [service, ...current.filter((item) => String(item.id) !== serviceId)]);
    setForm((current) => ({ ...current, services: [...current.services, nextLine], parts: [...current.parts, ...nextParts] }));
    setActiveTab("services");
  }

  function addPackageToEstimate(servicePackage) {
    const packageItems = servicePackage?.items || [];
    if (!servicePackage?.id || packageItems.length === 0) {
      setError("O combo selecionado não possui serviços cadastrados.");
      return;
    }
    const nextLines = packageItems.map((item) => ({
      ...emptyService(),
      service_id: item.service || item.service_id || "",
      source_package_id: servicePackage.id,
      source_package_name: servicePackage.name || "",
      description: item.description || item.service_name || servicePackage.name || "Serviço do combo",
      quantity: item.quantity || "1.00",
      unit_price: item.unit_price || "0.00",
      discount_percent: "0",
      notes: servicePackage.name ? `Combo: ${servicePackage.name}` : "",
    }));
    const packageDefaultParts = packageItems.flatMap((item, index) => {
      const service = services.find((candidate) => String(candidate.id) === String(item.service || item.service_id || ""));
      return defaultPartsForService(service, nextLines[index]?.local_id);
    });
    setForm((current) => {
      const nextServices = [...current.services, ...nextLines];
      const nextParts = [...current.parts, ...packageDefaultParts];
      const currentServiceSubtotal = current.services.reduce((total, line) => total + lineSubtotal(line), 0);
      const currentPartSubtotal = current.parts.reduce((total, line) => total + partLineSubtotal(line), 0);
      const currentItemDiscounts = current.services.reduce((total, line) => total + lineDiscountAmount(line), 0) + current.parts.reduce((total, line) => total + partDiscountAmount(line), 0);
      const currentBase = Math.max(currentServiceSubtotal + currentPartSubtotal - currentItemDiscounts, 0);
      const currentGeneralDiscount = percentAmount(currentBase, current.discount_percent);
      const nextServiceSubtotal = nextServices.reduce((total, line) => total + lineSubtotal(line), 0);
      const nextPartSubtotal = nextParts.reduce((total, line) => total + partLineSubtotal(line), 0);
      const nextItemDiscounts = nextServices.reduce((total, line) => total + lineDiscountAmount(line), 0) + nextParts.reduce((total, line) => total + partDiscountAmount(line), 0);
      const nextBase = Math.max(nextServiceSubtotal + nextPartSubtotal - nextItemDiscounts, 0);
      return {
        ...current,
        discount_percent: percentFromAmount(nextBase, currentGeneralDiscount + decimal(servicePackage.discount_amount)),
        services: nextServices,
        parts: nextParts,
      };
    });
    setActiveTab("services");
  }

  function handlePackageSelect(selectedPackages) {
    (selectedPackages || []).forEach((servicePackage) => addPackageToEstimate(servicePackage));
  }

  function handleQuickPackageCreated(servicePackage) {
    setServicePackages((current) => [servicePackage, ...current.filter((item) => String(item.id) !== String(servicePackage.id))]);
    addPackageToEstimate(servicePackage);
  }

  function handleQuickPartCreated(part, serviceLocalId = "") {
    const partId = String(part.id);
    const nextLine = {
      ...emptyPart(),
      service_local_id: serviceLocalId || "",
      part_id: partId,
      description: part.name || "",
      unit_price: part.sale_price || "0.00",
      cost_price: part.cost_price || "0.00",
    };
    setParts((current) => [part, ...current.filter((item) => String(item.id) !== partId)]);
    setForm((current) => ({ ...current, parts: [...current.parts, nextLine] }));
    setActiveTab("parts");
  }

  function selectService(localId, serviceId) {
    const service = services.find((item) => String(item.id) === String(serviceId));
    setForm((current) => ({
      ...current,
      services: current.services.map((line) => line.local_id === localId ? (service ? { ...line, service_id: serviceId, source_package_id: "", source_package_name: "", description: service.name, unit_price: service.default_unit_price || "0.00" } : { ...line, service_id: serviceId, source_package_id: "", source_package_name: "" }) : line),
      parts: service ? [...current.parts, ...defaultPartsForService(service, localId)] : current.parts,
    }));
  }

  function selectPart(localId, partId) {
    const part = parts.find((item) => String(item.id) === String(partId));
    updatePart(localId, part ? { part_id: partId, description: part.name, unit_price: part.sale_price || "0.00", cost_price: part.cost_price || "0.00" } : { part_id: partId });
  }

  function buildAiContext(extra = "") {
    const servicesSummary = form.services.length
      ? form.services.map((line, index) => `Serviço ${index + 1}: ${line.description || "sem descrição"}, qtd ${line.quantity || 1}, unitário ${money(line.unit_price || 0)}, total ${money(lineTotal(line))}`).join("; ")
      : "sem serviços informados";
    const partsSummary = form.parts.length
      ? form.parts.map((line, index) => `Peça ${index + 1}: ${line.description || "sem descrição"}, qtd ${line.quantity || 1}, unitário ${money(line.unit_price || 0)}, total ${money(partLineTotal(line))}`).join("; ")
      : "sem peças informadas";

    return [
      `Orçamento ${editing ? id : "novo"}`,
      `Cliente: ${selectedCustomer ? contactName(selectedCustomer) : "não selecionado"}`,
      `Veículo: ${selectedVehicle?.display_name || selectedVehicle?.plate || "não selecionado"}`,
      `Tanque: ${form.tank_level_percent || 0}%`,
      `Título: ${form.title || "não informado"}`,
      `Queixa: ${form.complaint || "não informada"}`,
      `Diagnóstico: ${form.diagnosis || "não informado"}`,
      `Serviços: ${servicesSummary}`,
      `Peças: ${partsSummary}`,
      `Total previsto: ${money(finalTotal)}`,
      extra,
    ].filter(Boolean).join(" | ");
  }

  function validateBeforeSave() {
    if (!form.customer_id) { setActiveTab("customer"); setError("Selecione um cliente válido no autocomplete antes de salvar o orçamento."); return false; }
    if (!form.title.trim()) { setActiveTab("customer"); setError("Informe o título do orçamento antes de salvar."); return false; }
    if (form.services.length === 0 && form.parts.length === 0) { setActiveTab("services"); setError("Inclua pelo menos um serviço ou uma peça no orçamento."); return false; }
    return true;
  }

  async function save(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    if (!validateBeforeSave()) { setSaving(false); return; }
    if (editing && sourceEstimate?.can_edit === false) {
      setError("Orçamento só pode ser editado quando estiver aberto ou recusado.");
      setSaving(false);
      return;
    }
    try {
      const { discount_percent: _discountPercent, ...formPayload } = form;
      const payload = {
        ...formPayload,
        customer_id: Number(form.customer_id),
        vehicle_id: form.vehicle_id ? Number(form.vehicle_id) : null,
        tank_level_percent: Number(form.tank_level_percent || 0),
        discount_amount: generalDiscountAmount.toFixed(2),
        services: form.services.map(({ local_id, service, service_name, source_package, source_package_name, subtotal_amount, total_amount, discount_percent, ...line }) => ({
          ...line,
          local_id,
          service_id: line.service_id ? Number(line.service_id) : null,
          source_package_id: line.source_package_id ? Number(line.source_package_id) : null,
          quantity: line.quantity || "1.00",
          unit_price: line.unit_price || "0.00",
          discount_amount: percentAmount(decimal(line.quantity || "1.00") * decimal(line.unit_price || "0.00"), discount_percent).toFixed(2),
        })),
        parts: form.parts.map(({ local_id, part, part_name, part_sku, stock_available, subtotal_amount, total_amount, service_item, service_item_description, discount_percent, ...line }) => ({
          ...line,
          service_local_id: line.service_local_id || "",
          part_id: line.part_id ? Number(line.part_id) : null,
          quantity: line.quantity || "1.00",
          unit_price: line.unit_price || "0.00",
          cost_price: line.cost_price || "0.00",
          discount_amount: percentAmount(decimal(line.quantity || "1.00") * decimal(line.unit_price || "0.00"), discount_percent).toFixed(2),
        })),
      };
      if (editing) await api.put(`/attendance/estimates/${id}/`, payload);
      else await api.post("/attendance/estimates/", payload);
      closeForm();
    } catch (err) {
      setError(apiError(err));
    } finally {
      setSaving(false);
    }
  }

  return <>
    {!embedded ? (<><PageHeader title={editing ? "Editar orçamento" : "Novo orçamento"} subtitle="Monte o orçamento por abas: cliente, serviços, peças e resumo financeiro." actions={<Link className="btn btn-outline-secondary" to={returnPath}>Voltar para orçamentos</Link>} /><AreaTabs area="attendance" /></>) : null}
    <ErrorAlert error={error} onClose={() => setError("")} />
    {editing && sourceEstimate?.can_edit === false ? <Alert variant="warning">Este orçamento não pode ser alterado no status atual. Apenas orçamentos abertos ou recusados podem ser editados.</Alert> : null}

    <Form onSubmit={save} noValidate>
      <FormTabs tabs={tabs} activeKey={activeTab} onSelect={setActiveTab} />

      <TabPanel activeKey={activeTab} eventKey="customer">
        <Card className="border-0 shadow-sm mb-3">
          <Card.Header className="bg-white d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2">
            <div>
              <span className="fw-semibold d-block">Dados principais</span>
              <span className="small text-muted">Selecione um cliente existente ou cadastre cliente e veículo sem sair do orçamento.</span>
            </div>
            <Button type="button" variant="outline-primary" onClick={() => setQuickCustomerVehicleModal(true)}>Cadastrar cliente e veículo</Button>
          </Card.Header>
          <Card.Body>
            <Row className="g-3">
              <Col md={6}><SearchableSelect id="estimateCustomer" label="Cliente" required value={form.customer_id} options={customerOptions} onChange={selectCustomer} placeholder="Pesquisar cliente por nome, telefone, e-mail ou documento" emptyMessage="Nenhum cliente encontrado. Use o botão Cadastrar cliente e veículo para criar sem sair do orçamento." helpText="Use o autocomplete para selecionar um cliente válido. O botão Limpar remove o cliente e o veículo selecionados." /></Col>
              <Col md={6}><SearchableSelect id="estimateVehicle" label="Veículo" value={form.vehicle_id} options={vehicleOptions} onChange={(value) => setForm({ ...form, vehicle_id: value })} placeholder={form.customer_id ? "Pesquisar veículo do cliente" : "Selecione um cliente primeiro"} disabled={!form.customer_id} emptyMessage="Nenhum veículo encontrado para este cliente." helpText="O primeiro veículo do cliente é sugerido automaticamente quando existir." /></Col>
              <Col md={3}><Form.Label>Validade</Form.Label><DateInput value={form.valid_until} onChange={(event) => setForm({ ...form, valid_until: event.target.value })} /></Col>
              <Col md={3}>
                <Form.Label>Tanque de combustível</Form.Label>
                <Form.Select value={form.tank_level_percent} onChange={(event) => setForm({ ...form, tank_level_percent: event.target.value })}>
                  {fuelTankLevelOptions.map(([value, label]) => <option key={value} value={String(value)}>{label}</option>)}
                </Form.Select>
                <Form.Text>Percentual informado em intervalos de 25%.</Form.Text>
              </Col>
              <Col md={6}>
                <div className="d-flex align-items-center justify-content-between gap-2 mb-1">
                  <Form.Label className="mb-0">Título do orçamento</Form.Label>
                  <AIAssistButton task="general" value={form.title} context={buildAiContext("Gere um título curto, comercial e fiel ao orçamento. Não inclua valores se eles não forem necessários.")} onApply={(text) => setForm((current) => ({ ...current, title: text }))} />
                </div>
                <Form.Control required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Ex.: Revisão completa com troca de peças" />
              </Col>
              <Col md={6}>
                <div className="d-flex align-items-center justify-content-between gap-2 mb-1">
                  <Form.Label className="mb-0">Queixa / solicitação do cliente</Form.Label>
                  <AIAssistButton task="customer_report" value={form.complaint} context={buildAiContext("Organize apenas a queixa ou solicitação inicial do cliente, sem criar sintomas novos.")} onApply={(text) => setForm((current) => ({ ...current, complaint: text }))} />
                </div>
                <Form.Control as="textarea" rows={4} value={form.complaint} onChange={(event) => setForm({ ...form, complaint: event.target.value })} />
              </Col>
              <Col md={6}>
                <div className="d-flex align-items-center justify-content-between gap-2 mb-1">
                  <Form.Label className="mb-0">Diagnóstico prévio</Form.Label>
                  <AIAssistButton task="diagnosis" value={form.diagnosis} context={buildAiContext("Redija o diagnóstico prévio do orçamento com base somente na queixa, nos serviços e nas peças já informados.")} onApply={(text) => setForm((current) => ({ ...current, diagnosis: text }))} />
                </div>
                <Form.Control as="textarea" rows={4} value={form.diagnosis} onChange={(event) => setForm({ ...form, diagnosis: event.target.value })} />
              </Col>
            </Row>
          </Card.Body>
        </Card>
      </TabPanel>

      <TabPanel activeKey={activeTab} eventKey="services">
        <Card className="border-0 shadow-sm mb-3">
          <Card.Header className="bg-white">
            <div className="d-flex flex-column flex-lg-row justify-content-between align-items-lg-start gap-3">
              <div>
                <span className="fw-semibold d-block">Serviços e combos do orçamento</span>
                <span className="small text-muted">Use cards editáveis: escolha serviço/combo, revise preço e veja peças padrão sugeridas automaticamente.</span>
                <span className="small text-primary d-block mt-1">Cálculo atualizado: serviços {money(form.services.reduce((total, line) => total + lineTotal(line), 0))} · orçamento {money(finalTotal)}</span>
              </div>
              <div className="d-flex flex-column flex-md-row gap-2 align-items-stretch align-items-md-start">
                <Button size="sm" variant="outline-primary" type="button" onClick={() => setIncludePackageModal(true)}>Incluir combo</Button>
                <Button size="sm" variant="outline-primary" type="button" onClick={() => setIncludeServiceModal(true)}>Adicionar serviço</Button>
                <Button size="sm" variant="outline-secondary" type="button" onClick={() => setQuickPackageModal(true)}>Cadastrar combo</Button>
                <Button size="sm" variant="outline-secondary" type="button" onClick={() => setQuickServiceModal(true)}>Cadastrar serviço</Button>
                <Button size="sm" variant="outline-secondary" type="button" onClick={() => setManualServiceModal(true)}>Serviço manual</Button>
              </div>
            </div>
          </Card.Header>
          <Card.Body>
            {form.services.length === 0 ? <Alert variant="light" className="border mb-0">Nenhum serviço adicionado. Comece por um serviço cadastrado, combo ou serviço manual.</Alert> : null}
            <div className="line-builder-stack">
              {form.services.map((line, index) => {
                const linkedParts = form.parts.filter((partLine) => partLine.service_local_id === line.local_id);
                return (
                  <div className="line-builder-card" key={line.local_id}>
                    <div className="line-builder-card-header">
                      <div className="d-flex gap-2 align-items-start">
                        <span className="line-builder-index">{index + 1}</span>
                        <div>
                          <div className="line-builder-title">{line.description || "Serviço sem descrição"}</div>
                          <div className="line-builder-meta">{line.source_package_name ? `Combo: ${line.source_package_name}` : "Serviço avulso"} · {linkedParts.length} peça(s) vinculada(s)</div>
                        </div>
                      </div>
                      <div className="line-builder-total"><span>Total</span><strong>{money(lineTotal(line))}</strong></div>
                    </div>
                    <Row className="g-3 align-items-end">
                      <Col lg={4}><SearchableSelect value={line.service_id || ""} options={serviceOptions} onChange={(value) => selectService(line.local_id, value)} placeholder="Pesquisar serviço" emptyMessage="Nenhum serviço encontrado." /></Col>
                      <Col lg={8}>
                        <div className="d-flex align-items-center justify-content-between gap-2 mb-1">
                          <Form.Label className="mb-0">Descrição para o cliente</Form.Label>
                          <AIAssistButton task="general" value={line.description} context={buildAiContext(`Melhore a descrição do serviço ${index + 1} para orçamento. Serviço atual: ${line.description || "não informado"}. Não prometa execução; descreva como item proposto para aprovação.`)} onApply={(text) => updateService(line.local_id, { description: text })} />
                        </div>
                        <Form.Control value={line.description} onChange={(event) => updateService(line.local_id, { description: event.target.value })} placeholder="Descrição do serviço" />
                      </Col>
                      <Col md={3}><Form.Label>Qtd.</Form.Label><IntegerInput min="0.01" step="0.01" value={line.quantity} onChange={(event) => updateService(line.local_id, { quantity: event.target.value })} /></Col>
                      <Col md={3}><Form.Label>Unitário</Form.Label><MoneyInput value={line.unit_price} onChange={(value) => updateService(line.local_id, { unit_price: value })} /></Col>
                      <Col md={3}><Form.Label>Desconto (%)</Form.Label><PercentInput value={line.discount_percent} onChange={(event) => updateService(line.local_id, { discount_percent: event.target.value })} /></Col>
                      <Col md={3} className="line-builder-actions"><Button size="sm" variant="outline-primary" type="button" disabled={!services.length} onClick={() => setReplaceServiceLine(line)}>Trocar</Button><Button size="sm" variant="outline-danger" type="button" onClick={() => removeService(line.local_id)}>Remover</Button></Col>
                    </Row>
                  </div>
                );
              })}
            </div>
          </Card.Body>
        </Card>
      </TabPanel>

      <TabPanel activeKey={activeTab} eventKey="parts">
        <Card className="border-0 shadow-sm mb-3">
          <Card.Header className="bg-white d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2">
            <div>
              <span className="fw-semibold d-block">Peças do orçamento</span>
              <span className="small text-muted">Peças podem ser manuais ou vinculadas a um serviço. Peças padrão entram automaticamente ao selecionar serviços configurados.</span>
              <span className="small text-primary d-block mt-1">Cálculo atualizado: peças {money(form.parts.reduce((total, line) => total + partLineTotal(line), 0))} · orçamento {money(finalTotal)}</span>
            </div>
            <div className="d-flex gap-2">
              <Button size="sm" variant="outline-primary" type="button" onClick={() => setIncludePartModal(true)}>Adicionar peça</Button>
              <Button size="sm" variant="outline-secondary" type="button" onClick={() => setQuickPartModal(true)}>Cadastrar peça</Button>
              <Button size="sm" variant="outline-secondary" type="button" onClick={() => setManualPartModal(true)}>Peça manual</Button>
            </div>
          </Card.Header>
          {partsWithoutLinkedService.length > 0 ? <Alert variant="warning" className="m-3 mb-0"><strong>Atenção:</strong> {partsWithoutLinkedService.length} peça(s) estão sem serviço vinculado. Elas ainda podem ser salvas, mas o ideal é vincular cada peça ao serviço correspondente.</Alert> : null}
          <Card.Body>
            {form.parts.length === 0 ? <Alert variant="light" className="border mb-0">Nenhuma peça adicionada. Ao adicionar um serviço com peças padrão cadastradas, elas aparecerão aqui automaticamente.</Alert> : null}
            <div className="line-builder-stack">
              {form.parts.map((line, index) => (
                <div key={line.local_id} className={`line-builder-card ${!line.service_local_id ? "is-warning" : ""}`.trim()}>
                  <div className="line-builder-card-header">
                    <div className="d-flex gap-2 align-items-start">
                      <span className="line-builder-index">{index + 1}</span>
                      <div>
                        <div className="line-builder-title">{line.description || "Peça sem descrição"}</div>
                        <div className="line-builder-meta">{line.service_local_id ? "Vinculada a serviço" : "Sem vínculo de serviço"}</div>
                      </div>
                    </div>
                    <div className="line-builder-total"><span>Total</span><strong>{money(partLineTotal(line))}</strong></div>
                  </div>
                  <Row className="g-3 align-items-end">
                    <Col lg={4}><SearchableSelect value={line.service_local_id || ""} options={serviceLineOptions} onChange={(value) => updatePart(line.local_id, { service_local_id: value })} placeholder="Pesquisar serviço vinculado" emptyMessage="Nenhum serviço no orçamento." /></Col>
                    <Col lg={4}><SearchableSelect value={line.part_id || ""} options={partOptions} onChange={(value) => selectPart(line.local_id, value)} placeholder="Pesquisar peça" emptyMessage="Nenhuma peça encontrada." /></Col>
                    <Col lg={4}>
                      <div className="d-flex align-items-center justify-content-between gap-2 mb-1">
                        <Form.Label className="mb-0">Descrição para o cliente</Form.Label>
                        <AIAssistButton task="general" value={line.description} context={buildAiContext(`Melhore a descrição da peça ${index + 1} para orçamento. Peça atual: ${line.description || "não informada"}. Não invente marca, código ou compatibilidade.`)} onApply={(text) => updatePart(line.local_id, { description: text })} />
                      </div>
                      <Form.Control value={line.description} onChange={(event) => updatePart(line.local_id, { description: event.target.value })} placeholder="Descrição da peça" />
                    </Col>
                    <Col md={3}><Form.Label>Qtd.</Form.Label><IntegerInput min="0.01" step="0.01" value={line.quantity} onChange={(event) => updatePart(line.local_id, { quantity: event.target.value })} /></Col>
                    <Col md={3}><Form.Label>Unitário</Form.Label><MoneyInput value={line.unit_price} onChange={(value) => updatePart(line.local_id, { unit_price: value })} /></Col>
                    <Col md={3}><Form.Label>Desconto (%)</Form.Label><PercentInput value={line.discount_percent} onChange={(event) => updatePart(line.local_id, { discount_percent: event.target.value })} /></Col>
                    <Col md={3} className="line-builder-actions"><Button size="sm" variant="outline-primary" type="button" disabled={!parts.length} onClick={() => setReplacePartLine(line)}>Trocar</Button><Button size="sm" variant="outline-danger" type="button" onClick={() => removePart(line.local_id)}>Remover</Button></Col>
                  </Row>
                </div>
              ))}
            </div>
          </Card.Body>
        </Card>
      </TabPanel>

      <TabPanel activeKey={activeTab} eventKey="summary">
        <Card className="border-0 shadow-sm mb-3"><Card.Header className="bg-white fw-semibold">Resumo financeiro e observações</Card.Header><Card.Body><Row className="g-3 mb-3">
          <Col md={3}><div className="finance-total-box"><span>Subtotal serviços</span><strong>{money(subtotalServices)}</strong></div></Col>
          <Col md={3}><div className="finance-total-box"><span>Subtotal peças</span><strong>{money(subtotalParts)}</strong></div></Col>
          <Col md={3}><Form.Label>Desconto geral (%)</Form.Label><PercentInput value={form.discount_percent} onChange={(event) => setForm({ ...form, discount_percent: event.target.value })} /><div className="small text-muted mt-1">Equivale a {money(generalDiscountAmount)}</div></Col>
          <Col md={3}><div className="finance-total-box total"><span>Total previsto</span><strong>{money(finalTotal)}</strong></div></Col>
          <Col md={6}>
            <div className="d-flex align-items-center justify-content-between gap-2 mb-1">
              <Form.Label className="mb-0">Observações internas</Form.Label>
              <AIAssistButton task="general" value={form.internal_notes} context={buildAiContext("Gere observações internas objetivas para a equipe. Não escreva texto comercial para cliente neste campo.")} onApply={(text) => setForm((current) => ({ ...current, internal_notes: text }))} />
            </div>
            <Form.Control as="textarea" rows={3} value={form.internal_notes} onChange={(event) => setForm({ ...form, internal_notes: event.target.value })} />
          </Col>
          <Col md={6}>
            <div className="d-flex align-items-center justify-content-between gap-2 mb-1">
              <Form.Label className="mb-0">Observações para o cliente</Form.Label>
              <AIAssistButton task="email" value={form.customer_notes} context={buildAiContext("Escreva observações claras para o cliente aprovar o orçamento. Seja cordial, objetivo e não inclua informações não cadastradas.")} onApply={(text) => setForm((current) => ({ ...current, customer_notes: text }))} />
            </div>
            <Form.Control as="textarea" rows={3} value={form.customer_notes} onChange={(event) => setForm({ ...form, customer_notes: event.target.value })} />
          </Col>
        </Row></Card.Body></Card>
      </TabPanel>
      <TabbedFormFooter tabs={tabs} activeKey={activeTab} onSelect={setActiveTab} onCancel={closeForm} saveLabel={saving ? "Salvando..." : editing ? "Salvar alterações" : "Salvar orçamento"} saveDisabled={saving || (editing && sourceEstimate?.can_edit === false)} />
    </Form>
    <QuickCustomerVehicleModal show={quickCustomerVehicleModal} onHide={() => setQuickCustomerVehicleModal(false)} onCreated={handleQuickCustomerVehicleCreated} />
    <QuickServiceModal show={quickServiceModal} onHide={() => setQuickServiceModal(false)} onCreated={handleQuickServiceCreated} categories={serviceCategories} />
    <IncludeServiceModal show={includeServiceModal} onHide={() => setIncludeServiceModal(false)} onConfirm={addSelectedServicesToEstimate} services={services} />
    <IncludePackageModal show={includePackageModal} onHide={() => setIncludePackageModal(false)} onConfirm={handlePackageSelect} servicePackages={servicePackages} />
    <QuickPackageModal show={quickPackageModal} onHide={() => setQuickPackageModal(false)} onCreated={handleQuickPackageCreated} services={services} />
    <QuickPartModal show={quickPartModal} onHide={() => setQuickPartModal(false)} onCreated={handleQuickPartCreated} categories={partCategories} serviceLineOptions={serviceLineOptions} />
    <IncludePartModal show={includePartModal} onHide={() => setIncludePartModal(false)} onConfirm={addSelectedPartsToEstimate} parts={parts} serviceLineOptions={serviceLineOptions} />
    <EstimateServiceLineModal show={manualServiceModal} onHide={() => setManualServiceModal(false)} onConfirm={addService} services={services} />
    <EstimatePartLineModal show={manualPartModal} onHide={() => setManualPartModal(false)} onConfirm={addPart} parts={parts} serviceLineOptions={serviceLineOptions} />
    <ReplaceServiceModal show={Boolean(replaceServiceLine)} onHide={() => setReplaceServiceLine(null)} onConfirm={replaceServiceInEstimate} services={services} line={replaceServiceLine} />
    <ReplacePartModal show={Boolean(replacePartLine)} onHide={() => setReplacePartLine(null)} onConfirm={replacePartInEstimate} parts={parts} line={replacePartLine} serviceLineOptions={serviceLineOptions} />
  </>;
}
