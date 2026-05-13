import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Badge, Button, Container, Navbar } from "react-bootstrap";
import { useAuth } from "../auth/AuthContext";
import { hasPermission } from "../auth/permissions";

const iconPaths = {
  attendance: "M7 11a4 4 0 1 1 8 0v1h1a3 3 0 0 1 3 3v4h-2v-4a1 1 0 0 0-1-1h-1v2H7v-2H6a1 1 0 0 0-1 1v4H3v-4a3 3 0 0 1 3-3h1v-1Zm2 3h4v-3a2 2 0 1 0-4 0v3Z",
  wrench: "M21 6.5a5.5 5.5 0 0 1-7.15 5.24L6.4 19.2a2.26 2.26 0 0 1-3.2-3.2l7.46-7.45A5.5 5.5 0 0 1 17.5 1.9l-3.04 3.04 2.6 2.6L20.1 4.5c.58.57.9 1.29.9 2Z",
  box: "M4 7.4 12 3l8 4.4v9.2L12 21l-8-4.4V7.4Zm2.2.38L12 11l5.8-3.22L12 4.56 6.2 7.78ZM6 9.44v5.98l5 2.78v-5.98L6 9.44Zm7 8.76 5-2.78V9.44l-5 2.78v5.98Z",
  finance: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 15.5V19h-2v-1.47c-1.57-.24-2.83-1.13-3.5-2.45l1.8-.83c.46.84 1.3 1.35 2.34 1.35 1.07 0 1.86-.45 1.86-1.2 0-.73-.63-1.03-2.28-1.43-1.85-.45-3.24-1.12-3.24-3 0-1.46 1.1-2.57 2.72-2.9V5.5h2v1.55c1.27.28 2.25 1.04 2.86 2.18l-1.74.9c-.43-.75-1.07-1.13-1.92-1.13-1 0-1.66.43-1.66 1.1 0 .69.58.98 2.25 1.38 1.98.48 3.3 1.2 3.3 3.05 0 1.55-1.12 2.7-2.8 2.97Z",
  message: "M4 4h16v11H7.75L4 18.5V4Zm2 2v8.05L7 13h11V6H6Z",
  chart: "M4 19h16v2H2V3h2v16Zm4-2H6v-6h2v6Zm5 0h-2V7h2v10Zm5 0h-2V10h2v7Z",
  admin: "M19.43 12.98c.04-.32.07-.65.07-.98s-.02-.66-.07-.98l2.11-1.65-2-3.46-2.49 1a7.05 7.05 0 0 0-1.7-.98L15 3.25h-4l-.35 2.68c-.6.24-1.17.56-1.7.98l-2.49-1-2 3.46 2.11 1.65c-.04.32-.07.65-.07.98s.02.66.07.98l-2.11 1.65 2 3.46 2.49-1c.53.42 1.1.74 1.7.98L11 20.75h4l.35-2.68c.6-.24 1.17-.56 1.7-.98l2.49 1 2-3.46-2.11-1.65ZM13 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7Z",
  receipt: "M6 2h12v20l-3-1.5-3 1.5-3-1.5L6 22V2Zm2 3v13.76l1-.5 3 1.5 3-1.5 1 .5V5H8Zm2 3h6v2h-6V8Zm0 4h6v2h-6v-2Z",
  cart: "M7 18a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm10 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4ZM5.2 4H3V2h3.7l.6 3H21l-2 9H8.4l.35 1.75H19v2H7.1L5.2 4Zm2.5 3 .98 5H17.4l1.1-5H7.7Z",
  car: "M5 11 6.5 6.5A2.2 2.2 0 0 1 8.6 5h6.8a2.2 2.2 0 0 1 2.1 1.5L19 11h1v6h-2v2h-2v-2H8v2H6v-2H4v-6h1Zm2.1 0h9.8l-1.3-3.8a.2.2 0 0 0-.2-.2H8.6a.2.2 0 0 0-.2.14L7.1 11ZM7 15a1.3 1.3 0 1 0 0-2.6A1.3 1.3 0 0 0 7 15Zm10 0a1.3 1.3 0 1 0 0-2.6A1.3 1.3 0 0 0 17 15Z",
  users: "M8.5 11a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7Zm7 1a3 3 0 1 1 0-6 3 3 0 0 1 0 6ZM2 20a6.5 6.5 0 0 1 13 0H2Zm12.6 0a8.5 8.5 0 0 0-2.1-5.6A5.5 5.5 0 0 1 22 18v2h-7.4Z",
  tools: "M5 20h14v2H5v-2Zm2-2h10l-1-8H8l-1 8ZM8 8h8l-1.2-4H9.2L8 8Z",
  clipboard: "M8 3h8v3h3v15H5V6h3V3Zm2 2v2h4V5h-4Zm-3 4v10h10V9H7Zm2 2h6v2H9v-2Zm0 4h6v2H9v-2Z",
  package: "M3 6.5 12 2l9 4.5v11L12 22l-9-4.5v-11Zm3.1.2L12 9.65l5.9-2.95L12 3.75 6.1 6.7ZM5 8.4v7.85l6 3v-7.85l-6-3Zm8 10.85 6-3V8.4l-6 3v7.85Z",
  gear: "M9 3h6l.4 2.2a7 7 0 0 1 1.3.74l2.13-.75 3 5.2-1.7 1.45c.03.22.04.45.04.68s-.01.46-.04.68l1.7 1.45-3 5.2-2.13-.75c-.4.3-.84.55-1.3.74L15 22H9l-.4-2.2a7 7 0 0 1-1.3-.74l-2.13.75-3-5.2 1.7-1.45a5.4 5.4 0 0 1 0-1.36l-1.7-1.45 3-5.2 2.13.75c.4-.3.84-.55 1.3-.74L9 3Zm3 6.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5Z",
  swap: "M7 7h11l-3-3 1.4-1.4L21.8 8l-5.4 5.4L15 12l3-3H7V7Zm10 10H6l3 3-1.4 1.4L2.2 16l5.4-5.4L9 12l-3 3h11v2Z",
  factory: "M3 21V8l6 3V8l6 3V6h6v15H3Zm14-13v5.24l-6-3V14.24l-6-3V19h14V8Z",
  trendUp: "M3 17.2 9.4 11l4 4L21 7.4 19.6 6l-6.2 6.2-4-4L1.6 15.8 3 17.2Z",
  trendDown: "M3 6.8 9.4 13l4-4L21 16.6 19.6 18l-6.2-6.2-4 4L1.6 8.2 3 6.8Z",
  send: "M3 20 21 12 3 4v6l10 2-10 2v6Z",
  puzzle: "M20 13.5V20h-6.5v-2a1.5 1.5 0 0 0-3 0v2H4v-6.5h2a1.5 1.5 0 0 0 0-3H4V4h6.5v2a1.5 1.5 0 0 0 3 0V4H20v6.5h-2a1.5 1.5 0 0 0 0 3h2Z",
  clock: "M12 2a10 10 0 1 0 .01 0H12Zm1 5v5.58l4 2.37-1 1.73-5-3V7h2Z",
  bell: "M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm7-6V11a7 7 0 1 0-14 0v5l-2 2v1h18v-1l-2-2Z",
  tag: "M3 12.4V4h8.4L21 13.6 13.6 21 3 12.4ZM8 8.5A1.5 1.5 0 1 0 8 5.5a1.5 1.5 0 0 0 0 3Z",
  health: "M12 21s-8-4.8-8-11a4.5 4.5 0 0 1 8-2.83A4.5 4.5 0 0 1 20 10c0 6.2-8 11-8 11Zm-1-7H8v-2h3V9h2v3h3v2h-3v3h-2v-3Z",
  audit: "M6 2h10l4 4v16H6V2Zm9 2.5V7h2.5L15 4.5ZM8 10h8v2H8v-2Zm0 4h8v2H8v-2Zm0 4h5v2H8v-2Z",
};

const baseMenuGroups = [
  {
    title: "Atendimento",
    icon: "attendance",
    to: "/dashboard/atendimento",
    permission: "dashboard.attendance",
    links: [
      ["/work-orders", "Orçamento / OS", ["work_orders.view", "estimates.view"], "receipt"],
      ["/attendance/counter-sales", "Venda avulsa", "counter_sales.view", "cart"],
      ["/vehicles", "Veículos", "vehicles.view", "car"],
      ["/contacts", "Clientes / contatos", "contacts.view", "users"],
    ],
  },
  {
    title: "Técnico",
    icon: "wrench",
    to: "/dashboard/tecnico",
    permission: ["technical.dashboard", "dashboard.technical"],
    links: [
      ["/technical/workbench", "Bancada técnica", ["technical.dashboard", "dashboard.technical"], "tools"],
      ["/workshop-services", "Serviços", "services.manage", "clipboard"],
      ["/service-packages", "Pacotes", "service_packages.manage", "package"],
    ],
  },
  {
    title: "Estoque",
    icon: "box",
    to: "/dashboard/estoque",
    permission: "dashboard.stock",
    links: [
      ["/parts", "Peças / estoque", "parts.manage", "gear"],
      ["/stock-movements", "Movimentos", "stock.view", "swap"],
      ["/purchasing/purchase-orders", "Pedidos de compra", "purchases.view", "receipt"],
      ["/purchasing/suppliers", "Fornecedores", "suppliers.view", "factory"],
    ],
  },
  {
    title: "Financeiro",
    icon: "finance",
    to: "/dashboard/financeiro",
    permission: "dashboard.finance",
    links: [
      ["/finance/dashboard", "Painel financeiro", "finance.view", "chart"],
      ["/finance/accounts-receivable", "Contas a receber", "finance.view", "trendUp"],
      ["/finance/accounts-payable", "Contas a pagar", "finance.view", "trendDown"],
      ["/finance/cash-flow", "Fluxo de caixa", "finance.view", "finance"],
      ["/purchasing/purchase-orders", "Pedidos de compra", "purchases.view", "receipt"],
    ],
  },
  {
    title: "Mensageria",
    icon: "message",
    to: "/message-dashboard",
    permission: "messaging.manage",
    links: [
      ["/send", "Envio manual", "messages.send", "send"],
      ["/templates", "Templates", "messaging.manage", "puzzle"],
      ["/automations", "Automações", "messaging.manage", "clock"],
      ["/history", "Histórico", "messaging.manage", "audit"],
      ["/notification-rules", "Notificações", "messaging.manage", "bell"],
    ],
  },
  {
    title: "Relatórios",
    icon: "chart",
    to: "/reports/executive",
    permission: "reports.view",
    links: [
      ["/reports/work-orders", "Ordens de serviço", "reports.view", "receipt"],
      ["/reports/estimates", "Orçamentos", "reports.view", "clipboard"],
      ["/reports/finance", "Financeiro", "reports.view", "finance"],
      ["/reports/inventory", "Estoque", "reports.view", "box"],
    ],
  },
  {
    title: "Administração",
    icon: "admin",
    to: "/dashboard/administrativo",
    permission: "users.manage",
    links: [
      ["/settings", "Central administrativa", "settings.manage", "admin"],
      ["/users", "Usuários", "users.manage", "users"],
      ["/categories", "Categorias", "categories.manage", "tag"],
      ["/groups", "Grupos de contatos", "contacts.view", "users"],
      ["/system/health", "Saúde do sistema", "settings.manage", "health"],
      ["/system/audit", "Auditoria", "settings.manage", "audit"],
    ],
  },
];

function visibleGroups(user) {
  return baseMenuGroups
    .map((group) => ({ ...group, links: group.links.filter(([, , permission]) => hasPermission(user, permission)) }))
    .filter((group) => hasPermission(user, group.permission) || group.links.length > 0);
}

function groupHref(user, group) {
  if (hasPermission(user, group.permission)) return group.to;
  return group.links[0]?.[0] || group.to || "/";
}

function routeMatches(to, pathname) {
  return pathname === to || pathname.startsWith(`${to}/`);
}

function groupIsActive(group, pathname) {
  return routeMatches(group.to, pathname) || group.links.some(([to]) => routeMatches(to, pathname));
}

function initials(name) {
  return String(name || "OF")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function SidebarIcon({ icon, className = "" }) {
  return (
    <span className={`sidebar-item-icon ${className}`.trim()} aria-hidden="true">
      <svg viewBox="0 0 24 24" role="img" focusable="false">
        <path d={iconPaths[icon] || iconPaths.receipt} />
      </svg>
    </span>
  );
}

export default function Layout() {
  const { user, workshopProfile, logout } = useAuth();
  const location = useLocation();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem("sidebar_collapsed") === "true");
  const groups = visibleGroups(user);
  const activeGroupTitle = groups.find((group) => groupIsActive(group, location.pathname))?.title;

  useEffect(() => {
    localStorage.setItem("sidebar_collapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  function toggleSidebar() {
    setSidebarCollapsed((current) => !current);
  }

  const workshopName = workshopProfile?.display_name || workshopProfile?.trade_name || workshopProfile?.legal_name || "Oficina Admin";
  const userName = user?.full_name || user?.username || "Usuário";
  const isKanbanRoute = location.pathname === "/work-orders/kanban";
  const contentClassName = "py-4 px-4 content-full-width";

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""} ${isKanbanRoute ? "kanban-shell" : ""}`.trim()}>
      <aside className="sidebar" aria-label="Menu lateral principal">
        <div className="sidebar-inner">
          <div className="sidebar-brand">
            {workshopProfile?.logo_url ? (
              <img src={workshopProfile.logo_url} alt={`Logo ${workshopName}`} className="sidebar-brand-logo" />
            ) : (
              <div className="sidebar-brand-fallback">{initials(workshopName)}</div>
            )}
            <div className="sidebar-expanded-only min-width-0">
              <h4 className="mb-0 text-truncate">{workshopName}</h4>
              <div className="sidebar-brand-subtitle text-truncate">Gestão da oficina</div>
            </div>
            <button
              type="button"
              className="sidebar-toggle sidebar-expanded-only ms-auto"
              onClick={toggleSidebar}
              aria-label="Recolher menu lateral"
              title="Recolher menu"
            >
              <span aria-hidden="true">‹</span>
            </button>
          </div>

          <button
            type="button"
            className="sidebar-rail-button sidebar-collapsed-only"
            onClick={toggleSidebar}
            aria-label="Abrir menu lateral"
            title="Abrir menu"
          >
            <span className="sidebar-rail-icon" aria-hidden="true">☰</span>
          </button>

          <div className="sidebar-user sidebar-expanded-only" aria-label="Usuário logado">
            <div className="sidebar-user-label">Logado como</div>
            <div className="sidebar-user-name text-truncate">{userName}</div>
            <div className="sidebar-user-email text-truncate">{user?.email || "Email não informado"}</div>
            {user?.role_label ? <Badge bg="secondary" className="sidebar-user-badge">{user.role_label}</Badge> : null}
          </div>

          <nav className="sidebar-nav sidebar-expanded-only" aria-label="Navegação por setor">
            {groups.map((group) => {
              const active = group.title === activeGroupTitle;
              const href = groupHref(user, group);
              return (
                <section key={group.title} className={`sidebar-nav-group ${active ? "is-active" : ""}`}>
                  <NavLink to={href} className={`sidebar-group-link ${active ? "active" : ""}`}>
                    <SidebarIcon icon={group.icon} />
                    <span className="sidebar-group-title">{group.title}</span>
                  </NavLink>
                  {group.links.length > 0 ? (
                    <div className="sidebar-submenu" aria-label={`Itens de ${group.title}`}>
                      {group.links.map(([to, label, , icon]) => (
                        <NavLink key={`${group.title}-${to}`} to={to} end={to === "/work-orders"} className="sidebar-link">
                          <SidebarIcon icon={icon || "receipt"} className="sidebar-submenu-icon" />
                          <span>{label}</span>
                        </NavLink>
                      ))}
                    </div>
                  ) : null}
                </section>
              );
            })}
          </nav>

          <nav className="sidebar-collapsed-only sidebar-rail-nav" aria-label="Navegação compacta por setor">
            {groups.map((group) => {
              const active = group.title === activeGroupTitle;
              return (
                <NavLink key={group.title} to={groupHref(user, group)} className={`sidebar-rail-nav-link ${active ? "active" : ""}`} title={group.title} aria-label={group.title}>
                  <SidebarIcon icon={group.icon} />
                </NavLink>
              );
            })}
          </nav>
        </div>
      </aside>
      <div className="main-content">
        <Navbar bg="white" className="border-bottom px-3 top-navbar">
          <Container fluid>
            <div className="d-flex align-items-center gap-2 min-width-0">
              <Button
                variant="outline-secondary"
                size="sm"
                className="top-sidebar-toggle"
                onClick={toggleSidebar}
                aria-label={sidebarCollapsed ? "Abrir menu lateral" : "Recolher menu lateral"}
                title={sidebarCollapsed ? "Abrir menu" : "Recolher menu"}
              >
                <span aria-hidden="true">☰</span>
              </Button>
              <Navbar.Text className="text-truncate">
                <strong>{workshopName}</strong>
                <span className="text-muted ms-2">{userName}</span>
                {user?.technician_specialty_label ? <Badge bg="info" className="ms-2">{user.technician_specialty_label}</Badge> : null}
              </Navbar.Text>
            </div>
            <Button variant="outline-secondary" size="sm" onClick={logout}>Sair</Button>
          </Container>
        </Navbar>
        <Container fluid className={contentClassName}><Outlet /></Container>
      </div>
    </div>
  );
}
