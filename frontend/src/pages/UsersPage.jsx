import React, { useEffect, useState } from "react";
import { Badge, Button, Card, Col, Form, Modal, Row, Table } from "../ui/TailwindPrimitives.jsx";
import PhotoCaptureInput from "../components/PhotoCaptureInput";
import DateInput from "../components/DateInput";
import api, { apiError, results } from "../api/client";
import PageHeader from "../components/PageHeader";
import ErrorAlert from "../components/ErrorAlert";
import SystemToast from "../components/SystemToast";
import NoticeBox from "../components/NoticeBox";
import EmptyState from "../components/EmptyState";
import FormTabs, { TabPanel } from "../components/FormTabs";
import TabbedFormFooter, { InlineTabbedFormFooter } from "../components/TabbedFormFooter";
import { maskCep, maskCpfCnpj, onlyDigits } from "../workshopOptions";
import SearchAutocompleteInput from "../components/SearchAutocompleteInput";
import { buildSearchSuggestions } from "../utils/search";
import PhoneInputBR from "../components/PhoneInputBR";
import { maskBrazilPhone, normalizeBrazilPhoneToE164 } from "../utils/phone";
import { confirmDialog } from "../components/ConfirmDialog";
import { lookupCep } from "../utils/cep";

const fallbackRoles = [
  { value: "administrative", label: "Administrativo" },
  { value: "attendant", label: "Atendente" },
  { value: "stock", label: "Estoque" },
  { value: "technician", label: "Técnico" },
  { value: "finance", label: "Financeiro" },
];

const fallbackSpecialties = [
  { value: "mechanic", label: "Mecânico" },
  { value: "bodywork", label: "Funileiro" },
  { value: "electrician", label: "Eletricista" },
];

const tabs = [
  { key: "identification", label: "Identificação", description: "Usuário, PF/PJ, CPF/CNPJ e dados básicos" },
  { key: "access", label: "Acesso", description: "Grupo, sub divisão técnica e status" },
  { key: "photo", label: "Foto 3x4", description: "Imagem do funcionário" },
  { key: "contact", label: "Contato", description: "Email, WhatsApp e telefones" },
  { key: "address", label: "Endereço", description: "Endereço preenchido por CEP" },
  { key: "extra", label: "Observações", description: "Observações internas" },
];

const empty = () => ({
  username: "",
  email: "",
  first_name: "",
  last_name: "",
  person_type: "individual",
  document_number: "",
  trade_name: "",
  state_registration: "",
  municipal_registration: "",
  birth_date: "",
  phone_e164: "",
  secondary_phone_e164: "",
  zip_code: "",
  address_line: "",
  address_number: "",
  address_complement: "",
  district: "",
  city: "",
  state: "",
  country: "Brasil",
  notes: "",
  custom_data: {},
  is_active: true,
  role: "attendant",
  technician_specialty: "",
});

function normalizeUser(user) {
  return {
    username: user.username || "",
    email: user.email || "",
    first_name: user.first_name || "",
    last_name: user.last_name || "",
    person_type: user.person_type || "individual",
    document_number: user.document_number || "",
    trade_name: user.trade_name || "",
    state_registration: user.state_registration || "",
    municipal_registration: user.municipal_registration || "",
    birth_date: user.birth_date || "",
    phone_e164: maskBrazilPhone(user.phone_e164 || ""),
    secondary_phone_e164: maskBrazilPhone(user.secondary_phone_e164 || ""),
    zip_code: user.zip_code || "",
    address_line: user.address_line || "",
    address_number: user.address_number || "",
    address_complement: user.address_complement || "",
    district: user.district || "",
    city: user.city || "",
    state: user.state || "",
    country: user.country || "Brasil",
    notes: user.notes || "",
    custom_data: user.custom_data || {},
    is_active: user.is_active,
    role: user.role_value || "attendant",
    technician_specialty: user.technician_specialty_value || "",
  };
}

export default function UsersPage() {
  const [items, setItems] = useState([]);
  const [roles, setRoles] = useState(fallbackRoles);
  const [specialties, setSpecialties] = useState(fallbackSpecialties);
  const [form, setForm] = useState(empty());
  const [editing, setEditing] = useState(null);
  const [photoFile, setPhotoFile] = useState(null);
  const [removePhoto, setRemovePhoto] = useState(false);
  const [show, setShow] = useState(false);
  const [activeTab, setActiveTab] = useState("identification");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function load(nextSearch = search) {
    try {
      const params = nextSearch ? { search: nextSearch } : {};
      const [{ data: users }, { data: options }] = await Promise.all([api.get("/users/", { params }), api.get("/users/role-options/")]);
      setItems(results(users).filter((user) => !user.is_superuser && !user.is_owner));
      setRoles(options.roles || fallbackRoles);
      setSpecialties(options.technician_specialties || fallbackSpecialties);
    } catch (err) {
      setError(apiError(err));
    }
  }

  useEffect(() => { load(); }, []);

  function clearSearch() {
    setSearch("");
    load("");
  }

  function update(patch) {
    setForm((current) => ({ ...current, ...patch }));
  }

  function open(user = null) {
    setEditing(user);
    setPhotoFile(null);
    setRemovePhoto(false);
    setForm(user ? normalizeUser(user) : empty());
    setActiveTab("identification");
    setShow(true);
    setSuccess("");
  }

  function payload() {
    const data = {
      ...form,
      email: form.email.trim().toLowerCase(),
      phone_e164: normalizeBrazilPhoneToE164(form.phone_e164),
      secondary_phone_e164: normalizeBrazilPhoneToE164(form.secondary_phone_e164),
      document_number: maskCpfCnpj(form.document_number),
      zip_code: maskCep(form.zip_code),
      state: form.state.trim().toUpperCase(),
      custom_data: form.custom_data || {},
    };
    if (data.person_type === "company") data.last_name = "";
    if (data.role !== "technician") data.technician_specialty = "";
    return data;
  }

  async function save(event) {
    event.preventDefault();
    setError("");
    try {
      const data = payload();
      const formData = new FormData();
      Object.entries(data).forEach(([key, value]) => {
        if (typeof value === "object" && value !== null) formData.append(key, JSON.stringify(value));
        else formData.append(key, value ?? "");
      });
      if (photoFile) formData.append("photo_3x4", photoFile);
      if (removePhoto) formData.append("remove_photo_3x4", "true");
      if (editing) await api.put(`/users/${editing.id}/`, formData);
      else await api.post("/users/", formData);
      setShow(false);
      await load();
    } catch (err) {
      setError(err.response ? apiError(err) : err.message);
    }
  }

  async function remove(user) {
    if (!(await confirmDialog(`Excluir usuário ${user.username}?`))) return;
    try {
      await api.delete(`/users/${user.id}/`);
      await load();
    } catch (err) {
      setError(apiError(err));
    }
  }

  async function sendPasswordSetup(user) {
    if (!(await confirmDialog(`Enviar link de definição de senha para ${user.email}?`))) return;
    setError("");
    setSuccess("");
    try {
      const { data } = await api.post(`/users/${user.id}/send-password-setup/`);
      setSuccess(data.detail || "Link enviado com sucesso.");
    } catch (err) {
      setError(apiError(err));
    }
  }

  async function handleCepBlur() {
    if (editingOwner) return;
    const digits = onlyDigits(form.zip_code);
    if (digits.length !== 8) return;
    try {
      const address = await lookupCep(form.zip_code);
      update(address);
      setError("");
    } catch (err) {
      setError(err.message || "Não foi possível buscar o CEP.");
    }
  }

  const editingOwner = editing?.is_owner;
  const isCompany = form.person_type === "company";

  return <>
    <PageHeader title="Usuários e funcionários" subtitle="Cadastro completo de funcionários com perfil de acesso, dados pessoais, endereço e definição de senha por token de email.">
      <Button onClick={() => open()}>Novo funcionário</Button>
    </PageHeader>
    <ErrorAlert error={error} onClose={() => setError("")} />
    <SystemToast message={success} variant="success" delay={3000} onClose={() => setSuccess("")} />
    <NoticeBox variant="info" className="mb-3" title="Cadastro administrativo de usuários">
      O papel <strong>Dono</strong> não aparece nesta tela. Ele é superuser/staff e deve ser criado somente pelo comando <code>python manage.py create_owner_user</code>. Funcionários comuns não recebem senha manual: use o botão <strong>Enviar token</strong> para que a pessoa defina a senha pelo email cadastrado.
    </NoticeBox>

    <Card className="border-0 shadow-sm mb-3"><Card.Body><Row className="g-2"><Col md={8}><SearchAutocompleteInput placeholder="Buscar por usuário, nome, CPF/CNPJ, email, telefone, cidade ou UF" value={search} onChange={setSearch} onSearch={load} suggestions={buildSearchSuggestions(items, ["username", "full_name", "document_number", "email", "phone_e164", "secondary_phone_e164", "city", "state", "role_label"])} /></Col><Col md={2}><Button variant="outline-primary" className="w-100" onClick={() => load()}>Buscar</Button></Col><Col md={2}><Button variant="outline-secondary" className="w-100" onClick={clearSearch} disabled={!search}>Limpar pesquisa</Button></Col></Row></Card.Body></Card>

    <Card className="border-0 shadow-sm"><Card.Body className="p-0">{items.length === 0 ? <EmptyState /> : <Table responsive hover className="mb-0"><thead><tr><th>Foto</th><th>Funcionário</th><th>CPF/CNPJ</th><th>Email</th><th>Telefone</th><th>Grupo</th><th>Sub divisão técnica</th><th>Senha</th><th>Ativo</th><th></th></tr></thead><tbody>{items.map((user) => <tr key={user.id}><td>{user.photo_3x4_url ? <img src={user.photo_3x4_url} alt={`Foto ${user.full_name}`} className="employee-thumb" /> : <div className="employee-thumb-fallback">{String(user.full_name || user.username || "F").slice(0, 1).toUpperCase()}</div>}</td><td><div className="fw-semibold">{user.full_name}</div><div className="small text-muted">@{user.username}{user.city || user.state ? ` · ${[user.city, user.state].filter(Boolean).join(" / ")}` : ""}</div></td><td>{user.document_number || "-"}</td><td>{user.email || "-"}</td><td>{user.phone_e164 ? maskBrazilPhone(user.phone_e164) : "-"}</td><td><Badge bg={user.is_owner ? "dark" : "secondary"}>{user.role_label || "-"}</Badge></td><td>{user.technician_specialty_label || "-"}</td><td>{user.has_usable_password ? "Definida" : "Pendente"}</td><td>{user.is_active ? "Sim" : "Não"}</td><td className="text-end text-nowrap"><Button size="sm" variant="outline-secondary" className="me-2" disabled={user.is_owner || !user.email} onClick={() => sendPasswordSetup(user)}>Enviar token</Button><Button size="sm" variant="outline-primary" className="me-2" disabled={user.is_owner} onClick={() => open(user)}>Editar</Button><Button size="sm" variant="outline-danger" disabled={user.is_owner} onClick={() => remove(user)}>Excluir</Button></td></tr>)}</tbody></Table>}</Card.Body></Card>

    <Modal size="xl" show={show} onHide={() => setShow(false)} className="floating-form-modal"><Form onSubmit={save}><Modal.Header closeButton><Modal.Title>{editing ? "Editar funcionário" : "Novo funcionário"}</Modal.Title></Modal.Header><Modal.Body>{editingOwner ? <NoticeBox variant="warning" className="mb-3" title="Usuário protegido">Usuário Dono não pode ser editado por esta tela.</NoticeBox> : null}<FormTabs tabs={tabs} activeKey={activeTab} onSelect={setActiveTab} className="mb-3" />
      <TabPanel activeKey={activeTab} eventKey="identification"><Row className="g-3"><Col md={3}><Form.Label>Usuário de login</Form.Label><Form.Control value={form.username} onChange={(event) => update({ username: event.target.value })} required disabled={editingOwner} /></Col><Col md={3}><Form.Label>Tipo de pessoa</Form.Label><Form.Select value={form.person_type} onChange={(event) => update({ person_type: event.target.value })} disabled={editingOwner}><option value="individual">Pessoa física</option><option value="company">Pessoa jurídica</option></Form.Select></Col><Col md={isCompany ? 4 : 3}><Form.Label>{isCompany ? "Razão social" : "Nome"}</Form.Label><Form.Control value={form.first_name} onChange={(event) => update({ first_name: event.target.value })} required disabled={editingOwner} /></Col>{!isCompany && <Col md={3}><Form.Label>Sobrenome</Form.Label><Form.Control value={form.last_name} onChange={(event) => update({ last_name: event.target.value })} disabled={editingOwner} /></Col>}<Col md={isCompany ? 2 : 3}><Form.Label>{isCompany ? "CNPJ" : "CPF"}</Form.Label><Form.Control value={form.document_number} onChange={(event) => update({ document_number: maskCpfCnpj(event.target.value) })} placeholder={isCompany ? "00.000.000/0000-00" : "000.000.000-00"} disabled={editingOwner} /></Col>{isCompany && <><Col md={4}><Form.Label>Nome fantasia</Form.Label><Form.Control value={form.trade_name} onChange={(event) => update({ trade_name: event.target.value })} disabled={editingOwner} /></Col><Col md={4}><Form.Label>Inscrição estadual</Form.Label><Form.Control value={form.state_registration} onChange={(event) => update({ state_registration: event.target.value })} disabled={editingOwner} /></Col><Col md={4}><Form.Label>Inscrição municipal</Form.Label><Form.Control value={form.municipal_registration} onChange={(event) => update({ municipal_registration: event.target.value })} disabled={editingOwner} /></Col></>}<Col md={4}><Form.Label>{isCompany ? "Data de fundação" : "Data de nascimento"}</Form.Label><DateInput value={form.birth_date || ""} onChange={(event) => update({ birth_date: event.target.value })} disabled={editingOwner} /></Col></Row></TabPanel>
      <TabPanel activeKey={activeTab} eventKey="access"><Row className="g-3"><Col md={6}><Form.Label>Grupo de usuário</Form.Label><Form.Select value={form.role} onChange={(event) => update({ role: event.target.value, technician_specialty: event.target.value === "technician" ? form.technician_specialty : "" })} disabled={editingOwner} required>{roles.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}</Form.Select></Col><Col md={6}><Form.Label>Sub divisão técnica</Form.Label><Form.Select value={form.technician_specialty} onChange={(event) => update({ technician_specialty: event.target.value })} disabled={editingOwner || form.role !== "technician"} required={form.role === "technician"}><option value="">Selecione...</option>{specialties.map((specialty) => <option key={specialty.value} value={specialty.value}>{specialty.label}</option>)}</Form.Select></Col><Col md={12}><Form.Check label="Funcionário ativo" checked={!!form.is_active} onChange={(event) => update({ is_active: event.target.checked })} disabled={editingOwner} /></Col><Col md={12}><NoticeBox variant="info" className="mb-0" title="Definição de senha">Não existe campo de senha neste cadastro. Depois de salvar, use o botão <strong>Enviar token</strong> na lista para o funcionário definir a senha definitiva por email.</NoticeBox></Col></Row></TabPanel>
      <TabPanel activeKey={activeTab} eventKey="photo">
        <Row className="g-3 align-items-center">
          <Col md={4}>
            <div className="image-preview-card employee-photo-preview">
              {photoFile ? (
                <img src={URL.createObjectURL(photoFile)} alt="Prévia da foto 3x4" />
              ) : !removePhoto && editing?.photo_3x4_url ? (
                <img src={editing.photo_3x4_url} alt={`Foto ${editing.full_name}`} />
              ) : (
                <span className="text-muted">Sem foto 3x4</span>
              )}
            </div>
          </Col>
          <Col md={8}>
            <Form.Label>Foto 3x4 do funcionário</Form.Label>
            <PhotoCaptureInput
              id="employee-photo-3x4"
              disabled={editingOwner}
              cameraLabel="Tirar foto 3x4"
              onFileChange={(file) => { setPhotoFile(file); setRemovePhoto(false); }}
              summary={photoFile ? photoFile.name : "Nenhuma foto selecionada"}
              helpText="No celular, toque em Tirar foto 3x4 para abrir a câmera. Use uma foto frontal para identificação interna. Tamanho máximo validado no backend: 3 MB."
            />
            <div className="d-flex gap-2 mt-3">
              <Button type="button" variant="outline-secondary" disabled={editingOwner} onClick={() => { setPhotoFile(null); setRemovePhoto(false); }}>Limpar seleção</Button>
              {editing?.photo_3x4_url || photoFile ? <Button type="button" variant="outline-danger" disabled={editingOwner} onClick={() => { setPhotoFile(null); setRemovePhoto(true); }}>Remover foto</Button> : null}
            </div>
          </Col>
        </Row>
      </TabPanel>
      <TabPanel activeKey={activeTab} eventKey="contact"><Row className="g-3"><Col md={4}><Form.Label>Email</Form.Label><Form.Control type="email" value={form.email} onChange={(event) => update({ email: event.target.value })} required disabled={editingOwner} placeholder="funcionario@email.com.br" /></Col><Col md={4}><PhoneInputBR label="WhatsApp principal" value={form.phone_e164} onChange={(value) => update({ phone_e164: value })} disabled={editingOwner} /></Col><Col md={4}><PhoneInputBR label="Telefone secundário" value={form.secondary_phone_e164} onChange={(value) => update({ secondary_phone_e164: value })} disabled={editingOwner} helpText="Opcional. Também será salvo em formato +55 para WhatsApp." /></Col></Row></TabPanel>
      <TabPanel activeKey={activeTab} eventKey="address"><Row className="g-3"><Col md={3}><Form.Label>CEP</Form.Label><Form.Control value={form.zip_code} onChange={(event) => update({ zip_code: maskCep(event.target.value) })} onBlur={handleCepBlur} placeholder="00000-000" disabled={editingOwner} /></Col><Col md={5}><Form.Label>Endereço</Form.Label><Form.Control value={form.address_line} onChange={(event) => update({ address_line: event.target.value })} placeholder="Rua, avenida, estrada..." disabled={editingOwner} /></Col><Col md={2}><Form.Label>Número</Form.Label><Form.Control value={form.address_number} onChange={(event) => update({ address_number: event.target.value })} disabled={editingOwner} /></Col><Col md={2}><Form.Label>Complemento</Form.Label><Form.Control value={form.address_complement} onChange={(event) => update({ address_complement: event.target.value })} disabled={editingOwner} /></Col><Col md={4}><Form.Label>Bairro</Form.Label><Form.Control value={form.district} onChange={(event) => update({ district: event.target.value })} disabled={editingOwner} /></Col><Col md={5}><Form.Label>Cidade</Form.Label><Form.Control value={form.city} onChange={(event) => update({ city: event.target.value })} disabled={editingOwner} /></Col><Col md={1}><Form.Label>UF</Form.Label><Form.Control maxLength={2} value={form.state} onChange={(event) => update({ state: event.target.value.toUpperCase() })} disabled={editingOwner} /></Col><Col md={2}><Form.Label>País</Form.Label><Form.Control value={form.country} onChange={(event) => update({ country: event.target.value })} disabled={editingOwner} /></Col></Row></TabPanel>
      <TabPanel activeKey={activeTab} eventKey="extra"><Row className="g-3"><Col md={12}><Form.Label>Observações internas</Form.Label><Form.Control as="textarea" rows={5} value={form.notes} onChange={(event) => update({ notes: event.target.value })} disabled={editingOwner} /></Col></Row></TabPanel>
    </Modal.Body><TabbedFormFooter tabs={tabs} activeKey={activeTab} onSelect={setActiveTab} onCancel={() => setShow(false)} saveLabel="Salvar funcionário" saveDisabled={editingOwner} /></Form></Modal>
  </>;
}
