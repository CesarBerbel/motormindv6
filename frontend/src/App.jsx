import React, { Suspense, lazy } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { defaultDashboardPath, hasPermission } from "./auth/permissions";
import { Modal } from "react-bootstrap";
import { resolveReturnTo } from "./utils/returnTo";

const Layout = lazy(() => import("./components/Layout"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const SetPasswordPage = lazy(() => import("./pages/SetPasswordPage"));
const LandingPage = lazy(() => import("./pages/LandingPage"));
const CustomerApprovalPage = lazy(() => import("./pages/CustomerApprovalPage"));

const AreaDashboardPage = lazy(() => import("./pages/AreaDashboardPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const AttendanceDashboardPage = lazy(() => import("./pages/AttendanceDashboardPage"));
const CounterSalesPage = lazy(() => import("./pages/CounterSalesPage"));
const CounterSaleFormPage = lazy(() => import("./pages/CounterSaleFormPage"));
const EstimatesPage = lazy(() => import("./pages/EstimatesPage"));
const EstimateFormPage = lazy(() => import("./pages/EstimateFormPage"));

const WorkOrdersPage = lazy(() => import("./pages/WorkOrdersPage"));
const WorkOrderFormPage = lazy(() => import("./pages/WorkOrderFormPage"));
const WorkOrderDetailPage = lazy(() => import("./pages/WorkOrderDetailPage"));
const WorkOrdersKanbanPage = lazy(() => import("./pages/WorkOrdersKanbanPage"));
const WorkOrdersAgendaPage = lazy(() => import("./pages/WorkOrdersAgendaPage"));
const VehiclesPage = lazy(() => import("./pages/VehiclesPage"));
const CategoriesPage = lazy(() => import("./pages/CategoriesPage"));
const WorkshopServicesPage = lazy(() => import("./pages/WorkshopServicesPage"));
const ServicePackagesPage = lazy(() => import("./pages/ServicePackagesPage"));
const PartsPage = lazy(() => import("./pages/PartsPage"));
const StockMovementsPage = lazy(() => import("./pages/StockMovementsPage"));
const TechnicalWorkbenchPage = lazy(() => import("./pages/TechnicalWorkbenchPage"));

const FinanceDashboardPage = lazy(() => import("./pages/FinanceDashboardPage"));
const FinancePayablesPage = lazy(() => import("./pages/FinancePayablesPage"));
const FinanceReceivablesPage = lazy(() => import("./pages/FinanceReceivablesPage"));
const FinanceReceivableFormPage = lazy(() => import("./pages/FinanceReceivableFormPage"));
const FinanceCashFlowPage = lazy(() => import("./pages/FinanceCashFlowPage"));

const PurchaseOrdersPage = lazy(() => import("./pages/PurchaseOrdersPage"));
const SuppliersPage = lazy(() => import("./pages/SuppliersPage"));

const ContactsPage = lazy(() => import("./pages/ContactsPage"));
const ContactGroupsPage = lazy(() => import("./pages/ContactGroupsPage"));
const TemplatesPage = lazy(() => import("./pages/TemplatesPage"));
const TemplateFormPage = lazy(() => import("./pages/TemplateFormPage"));
const SendManualPage = lazy(() => import("./pages/SendManualPage"));
const AutomationsPage = lazy(() => import("./pages/AutomationsPage"));
const AutomationFormPage = lazy(() => import("./pages/AutomationFormPage"));
const HistoryPage = lazy(() => import("./pages/HistoryPage"));
const NotificationRulesPage = lazy(() => import("./pages/NotificationRulesPage"));

const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const UsersPage = lazy(() => import("./pages/UsersPage"));
const SystemHealthPage = lazy(() => import("./pages/SystemHealthPage"));
const AuditLogsPage = lazy(() => import("./pages/AuditLogsPage"));

const ReportsExecutivePage = lazy(() => import("./pages/ReportsExecutivePage"));
const ReportsWorkOrdersPage = lazy(() => import("./pages/ReportsWorkOrdersPage"));
const ReportsEstimatesPage = lazy(() => import("./pages/ReportsEstimatesPage"));
const ReportsFinancePage = lazy(() => import("./pages/ReportsFinancePage"));
const ReportsInventoryPage = lazy(() => import("./pages/ReportsInventoryPage"));

function RouteLoading() {
  return (
    <div className="p-5 text-muted" role="status" aria-live="polite">
      Carregando módulo...
    </div>
  );
}

function FloatingRouteForm({ backTo, title, children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const returnTo = resolveReturnTo(location, backTo);
  const closeForm = () => navigate(returnTo, { replace: true });
  const formContent = React.isValidElement(children) ? React.cloneElement(children, { returnTo }) : children;

  return (
    <Modal keyboard={false} show size="xl" onHide={closeForm} className="floating-form-modal" dialogClassName="modal-floating-form" backdrop="static">
      <Modal.Header closeButton>
        <Modal.Title>{title}</Modal.Title>
      </Modal.Header>
      <Modal.Body>{formContent}</Modal.Body>
    </Modal>
  );
}

function AccessDenied() {
  return (
    <div className="p-5">
      <h3>Acesso negado</h3>
      <p className="text-muted mb-0">Seu grupo de usuário não possui permissão para acessar esta área.</p>
    </div>
  );
}

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <RouteLoading />;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.is_active) return <AccessDenied />;
  return children;
}

function Guard({ permission, children }) {
  const { user } = useAuth();
  if (!hasPermission(user, permission)) return <AccessDenied />;
  return children;
}

function DashboardRedirect() {
  const { user } = useAuth();
  return <Navigate to={defaultDashboardPath(user)} replace />;
}

function HomeRoute() {
  const { user, loading } = useAuth();
  if (loading) return <RouteLoading />;
  if (user) return <Navigate to={defaultDashboardPath(user)} replace />;
  return <LandingPage />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteLoading />}>
        <Routes>
          <Route path="/" element={<HomeRoute />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/definir-senha/:uidb64/:token" element={<SetPasswordPage />} />
          <Route path="/aprovar-os/:token" element={<CustomerApprovalPage />} />
          <Route path="/aprovar-orcamento/:token" element={<CustomerApprovalPage />} />
          <Route element={<Protected><Layout /></Protected>}>
            <Route path="dashboard/:area" element={<AreaDashboardPage />} />
            <Route path="attendance/dashboard" element={<Guard permission="dashboard.attendance"><AttendanceDashboardPage /></Guard>} />
            <Route path="attendance/counter-sales" element={<Guard permission="counter_sales.view"><CounterSalesPage /></Guard>} />
            <Route path="attendance/counter-sales/new" element={<Guard permission="counter_sales.manage"><FloatingRouteForm backTo="/attendance/counter-sales" title="Nova venda avulsa"><CounterSaleFormPage embedded /></FloatingRouteForm></Guard>} />
            <Route path="attendance/estimates" element={<Guard permission="estimates.view"><EstimatesPage /></Guard>} />
            <Route path="attendance/estimates/new" element={<Guard permission="estimates.manage"><FloatingRouteForm backTo="/attendance/estimates" title="Novo orçamento"><EstimateFormPage embedded /></FloatingRouteForm></Guard>} />
            <Route path="attendance/estimates/:id/edit" element={<Guard permission="estimates.manage"><FloatingRouteForm backTo="/attendance/estimates" title="Editar orçamento"><EstimateFormPage embedded /></FloatingRouteForm></Guard>} />
            <Route path="message-dashboard" element={<Guard permission="messaging.manage"><DashboardPage /></Guard>} />
            <Route path="work-orders" element={<Guard permission="work_orders.view"><WorkOrdersPage /></Guard>} />
            <Route path="work-orders/new" element={<Guard permission="work_orders.create"><FloatingRouteForm backTo="/work-orders" title="Nova ordem de serviço"><WorkOrderFormPage embedded /></FloatingRouteForm></Guard>} />
            <Route path="work-orders/estimates/new" element={<Guard permission="estimates.manage"><FloatingRouteForm backTo="/work-orders" title="Novo orçamento"><EstimateFormPage embedded /></FloatingRouteForm></Guard>} />
            <Route path="work-orders/estimates/:id/edit" element={<Guard permission="estimates.manage"><FloatingRouteForm backTo="/work-orders" title="Editar orçamento"><EstimateFormPage embedded /></FloatingRouteForm></Guard>} />
            <Route path="work-orders/kanban" element={<Guard permission="work_orders.view"><WorkOrdersKanbanPage /></Guard>} />
            <Route path="work-orders/agenda" element={<Guard permission="work_orders.view"><WorkOrdersAgendaPage /></Guard>} />
            <Route path="work-orders/:id" element={<Guard permission="work_orders.view"><WorkOrderDetailPage /></Guard>} />
            <Route path="work-orders/:id/edit" element={<Guard permission="work_orders.edit"><FloatingRouteForm backTo="/work-orders" title="Editar ordem de serviço"><WorkOrderFormPage embedded /></FloatingRouteForm></Guard>} />
            <Route path="vehicles" element={<Guard permission="vehicles.view"><VehiclesPage /></Guard>} />
            <Route path="categories" element={<Guard permission="categories.view"><CategoriesPage /></Guard>} />
            <Route path="technical/workbench" element={<Guard permission={["technical.dashboard", "dashboard.technical"]}><TechnicalWorkbenchPage /></Guard>} />
            <Route path="workshop-services" element={<Guard permission="services.manage"><WorkshopServicesPage /></Guard>} />
            <Route path="service-packages" element={<Guard permission="service_packages.manage"><ServicePackagesPage /></Guard>} />
            <Route path="parts" element={<Guard permission="parts.manage"><PartsPage /></Guard>} />
            <Route path="stock-movements" element={<Guard permission="stock.view"><StockMovementsPage /></Guard>} />
            <Route path="finance/dashboard" element={<Guard permission="finance.view"><FinanceDashboardPage /></Guard>} />
            <Route path="finance/accounts-receivable" element={<Guard permission="finance.view"><FinanceReceivablesPage /></Guard>} />
            <Route path="finance/accounts-receivable/new" element={<Guard permission="finance.manage"><FloatingRouteForm backTo="/finance/accounts-receivable" title="Nova conta a receber"><FinanceReceivableFormPage embedded /></FloatingRouteForm></Guard>} />
            <Route path="finance/cash-flow" element={<Guard permission="finance.view"><FinanceCashFlowPage /></Guard>} />
            <Route path="finance/accounts-payable" element={<Guard permission="finance.view"><FinancePayablesPage /></Guard>} />
            <Route path="purchasing/purchase-orders" element={<Guard permission="purchases.view"><PurchaseOrdersPage /></Guard>} />
            <Route path="purchasing/suppliers" element={<Guard permission="suppliers.view"><SuppliersPage /></Guard>} />
            <Route path="notification-rules" element={<Guard permission="messaging.manage"><NotificationRulesPage /></Guard>} />
            <Route path="contacts" element={<Guard permission="contacts.view"><ContactsPage /></Guard>} />
            <Route path="groups" element={<Guard permission="contacts.view"><ContactGroupsPage /></Guard>} />
            <Route path="templates" element={<Guard permission="messaging.manage"><TemplatesPage /></Guard>} />
            <Route path="templates/new" element={<Guard permission="messaging.manage"><FloatingRouteForm backTo="/templates" title="Novo template"><TemplateFormPage embedded /></FloatingRouteForm></Guard>} />
            <Route path="templates/:id" element={<Guard permission="messaging.manage"><FloatingRouteForm backTo="/templates" title="Editar template"><TemplateFormPage embedded /></FloatingRouteForm></Guard>} />
            <Route path="send" element={<Guard permission="messages.send"><SendManualPage /></Guard>} />
            <Route path="automations" element={<Guard permission="messaging.manage"><AutomationsPage /></Guard>} />
            <Route path="automations/new" element={<Guard permission="messaging.manage"><FloatingRouteForm backTo="/automations" title="Nova automação"><AutomationFormPage embedded /></FloatingRouteForm></Guard>} />
            <Route path="automations/:id" element={<Guard permission="messaging.manage"><FloatingRouteForm backTo="/automations" title="Editar automação"><AutomationFormPage embedded /></FloatingRouteForm></Guard>} />
            <Route path="history" element={<Guard permission="messaging.manage"><HistoryPage /></Guard>} />
            <Route path="settings" element={<Guard permission="settings.manage"><SettingsPage /></Guard>} />
            <Route path="users" element={<Guard permission="users.manage"><UsersPage /></Guard>} />
            <Route path="system/health" element={<Guard permission="settings.manage"><SystemHealthPage /></Guard>} />
            <Route path="reports/executive" element={<Guard permission="reports.view"><ReportsExecutivePage /></Guard>} />
            <Route path="reports/work-orders" element={<Guard permission="reports.view"><ReportsWorkOrdersPage /></Guard>} />
            <Route path="reports/estimates" element={<Guard permission="reports.view"><ReportsEstimatesPage /></Guard>} />
            <Route path="reports/finance" element={<Guard permission="reports.view"><ReportsFinancePage /></Guard>} />
            <Route path="reports/inventory" element={<Guard permission="reports.view"><ReportsInventoryPage /></Guard>} />
            <Route path="system/audit" element={<Guard permission="settings.manage"><AuditLogsPage /></Guard>} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
