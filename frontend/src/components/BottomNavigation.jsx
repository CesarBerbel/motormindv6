import React, { useEffect, useMemo, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import api, { results } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { hasPermission } from "../auth/permissions";

const iconPaths = {
  attendance: "M7 11a4 4 0 1 1 8 0v1h1a3 3 0 0 1 3 3v4h-2v-4a1 1 0 0 0-1-1h-1v2H7v-2H6a1 1 0 0 0-1 1v4H3v-4a3 3 0 0 1 3-3h1v-1Zm2 3h4v-3a2 2 0 1 0-4 0v3Z",
  wrench: "M21 6.5a5.5 5.5 0 0 1-7.15 5.24L6.4 19.2a2.26 2.26 0 0 1-3.2-3.2l7.46-7.45A5.5 5.5 0 0 1 17.5 1.9l-3.04 3.04 2.6 2.6L20.1 4.5c.58.57.9 1.29.9 2Z",
  receipt: "M6 2h12v20l-3-1.5-3 1.5-3-1.5L6 22V2Zm2 3v13.76l1-.5 3 1.5 3-1.5 1 .5V5H8Zm2 3h6v2h-6V8Zm0 4h6v2h-6v-2Z",
  clipboard: "M8 3h8v3h3v15H5V6h3V3Zm2 2v2h4V5h-4Zm-3 4v10h10V9H7Zm2 2h6v2H9v-2Zm0 4h6v2H9v-2Z",
  car: "M5 11 6.5 6.5A2.2 2.2 0 0 1 8.6 5h6.8a2.2 2.2 0 0 1 2.1 1.5L19 11h1v6h-2v2h-2v-2H8v2H6v-2H4v-6h1Zm2.1 0h9.8l-1.3-3.8a.2.2 0 0 0-.2-.2H8.6a.2.2 0 0 0-.2.14L7.1 11ZM7 15a1.3 1.3 0 1 0 0-2.6A1.3 1.3 0 0 0 7 15Zm10 0a1.3 1.3 0 1 0 0-2.6A1.3 1.3 0 0 0 17 15Z",
  box: "M4 7.4 12 3l8 4.4v9.2L12 21l-8-4.4V7.4Zm2.2.38L12 11l5.8-3.22L12 4.56 6.2 7.78ZM6 9.44v5.98l5 2.78v-5.98L6 9.44Zm7 8.76 5-2.78V9.44l-5 2.78v5.98Z",
  cart: "M7 18a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm10 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4ZM5.2 4H3V2h3.7l.6 3H21l-2 9H8.4l.35 1.75H19v2H7.1L5.2 4Zm2.5 3 .98 5H17.4l1.1-5H7.7Z",
  finance: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 15.5V19h-2v-1.47c-1.57-.24-2.83-1.13-3.5-2.45l1.8-.83c.46.84 1.3 1.35 2.34 1.35 1.07 0 1.86-.45 1.86-1.2 0-.73-.63-1.03-2.28-1.43-1.85-.45-3.24-1.12-3.24-3 0-1.46 1.1-2.57 2.72-2.9V5.5h2v1.55c1.27.28 2.25 1.04 2.86 2.18l-1.74.9c-.43-.75-1.07-1.13-1.92-1.13-1 0-1.66.43-1.66 1.1 0 .69.58.98 2.25 1.38 1.98.48 3.3 1.2 3.3 3.05 0 1.55-1.12 2.7-2.8 2.97Z",
  chart: "M4 19h16v2H2V3h2v16Zm4-2H6v-6h2v6Zm5 0h-2V7h2v10Zm5 0h-2V10h2v7Z",
  message: "M4 4h16v11H7.75L4 18.5V4Zm2 2v8.05L7 13h11V6H6Z",
  users: "M8.5 11a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7Zm7 1a3 3 0 1 1 0-6 3 3 0 0 1 0 6ZM2 20a6.5 6.5 0 0 1 13 0H2Zm12.6 0a8.5 8.5 0 0 0-2.1-5.6A5.5 5.5 0 0 1 22 18v2h-7.4Z",
  tools: "M5 20h14v2H5v-2Zm2-2h10l-1-8H8l-1 8ZM8 8h8l-1.2-4H9.2L8 8Z",
  package: "M3 6.5 12 2l9 4.5v11L12 22l-9-4.5v-11Zm3.1.2L12 9.65l5.9-2.95L12 3.75 6.1 6.7ZM5 8.4v7.85l6 3v-7.85l-6-3Zm8 10.85 6-3V8.4l-6 3v7.85Z",
  gear: "M9 3h6l.4 2.2a7 7 0 0 1 1.3.74l2.13-.75 3 5.2-1.7 1.45c.03.22.04.45.04.68s-.01.46-.04.68l1.7 1.45-3 5.2-2.13-.75c-.4.3-.84.55-1.3.74L15 22H9l-.4-2.2a7 7 0 0 1-1.3-.74l-2.13.75-3-5.2 1.7-1.45a5.4 5.4 0 0 1 0-1.36l-1.7-1.45 3-5.2 2.13.75c.4-.3.84-.55 1.3-.74L9 3Zm3 6.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5Z",
  send: "M3 20 21 12 3 4v6l10 2-10 2v6Z",
  bell: "M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm7-6V11a7 7 0 1 0-14 0v5l-2 2v1h18v-1l-2-2Z",
  health: "M12 21s-8-4.8-8-11a4.5 4.5 0 0 1 8-2.83A4.5 4.5 0 0 1 20 10c0 6.2-8 11-8 11Zm-1-7H8v-2h3V9h2v3h3v2h-3v3h-2v-3Z",
  audit: "M6 2h10l4 4v16H6V2Zm9 2.5V7h2.5L15 4.5ZM8 10h8v2H8v-2Zm0 4h8v2H8v-2Zm0 4h5v2H8v-2Z",
  home: "M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3V10.5Zm2 1V19h2v-6h10v6h2v-7.5l-7-5.83-7 5.83Z",
  plus: "M11 3h2v8h8v2h-8v8h-2v-8H3v-2h8V3Z",
};

const fallbackItems = [
  { label: "Início", path: "/dashboard/atendimento", icon: "home", permission_code: "dashboard.attendance", position: 10 },
  { label: "OS", path: "/work-orders", icon: "receipt", permission_code: "work_orders.view", position: 20 },
  { label: "Kanban", path: "/work-orders/kanban", icon: "clipboard", permission_code: "work_orders.view", position: 30 },
  { label: "Nova OS", path: "/work-orders/new", icon: "plus", permission_code: "work_orders.create", position: 40, highlight: true },
  { label: "Estoque", path: "/parts", icon: "box", permission_code: "parts.manage", position: 50 },
  { label: "Financeiro", path: "/finance/dashboard", icon: "finance", permission_code: "finance.view", position: 60 },
];

function splitPermissions(permissionCode = "") {
  return String(permissionCode || "")
    .replace(/;/g, ",")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function canShowFallbackItem(user, item) {
  const permissions = splitPermissions(item.permission_code);
  return permissions.length === 0 || permissions.some((permission) => hasPermission(user, permission));
}

function normalizeItems(items = []) {
  return items
    .filter((item) => item?.label && item?.path)
    .map((item) => ({
      ...item,
      id: item.id || `${item.path}-${item.label}`,
      icon: item.icon || "receipt",
      highlight: Boolean(item.highlight),
      open_in_new_tab: Boolean(item.open_in_new_tab),
    }))
    .sort((a, b) => Number(a.position || 0) - Number(b.position || 0));
}

function routeMatches(path, pathname) {
  if (!path || /^https?:\/\//i.test(path)) return false;
  return pathname === path || pathname.startsWith(`${path}/`);
}

function BottomNavIcon({ icon }) {
  return (
    <span className="bottom-nav-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" role="img" focusable="false">
        <path d={iconPaths[icon] || iconPaths.receipt} />
      </svg>
    </span>
  );
}

function BottomNavItem({ item, pathname }) {
  const external = /^https?:\/\//i.test(item.path);
  const className = ({ isActive }) => {
    const active = isActive || routeMatches(item.path, pathname);
    return `bottom-nav-link ${active ? "active" : ""} ${item.highlight ? "highlight" : ""}`.trim();
  };

  if (external) {
    return (
      <a href={item.path} className={className({ isActive: false })} target={item.open_in_new_tab ? "_blank" : undefined} rel={item.open_in_new_tab ? "noreferrer" : undefined}>
        <BottomNavIcon icon={item.icon} />
        <span>{item.label}</span>
      </a>
    );
  }

  return (
    <NavLink to={item.path} end={item.path === "/work-orders"} className={className}>
      <BottomNavIcon icon={item.icon} />
      <span>{item.label}</span>
    </NavLink>
  );
}

export default function BottomNavigation() {
  const { user } = useAuth();
  const location = useLocation();
  const [configuredItems, setConfiguredItems] = useState([]);
  const [loadStatus, setLoadStatus] = useState("loading");

  useEffect(() => {
    let active = true;
    async function loadItems() {
      try {
        const { data } = await api.get("/workshop/bottom-navigation/");
        if (active) {
          setConfiguredItems(normalizeItems(results(data)));
          setLoadStatus("success");
        }
      } catch {
        if (active) {
          setConfiguredItems([]);
          setLoadStatus("error");
        }
      }
    }
    loadItems();
    return () => {
      active = false;
    };
  }, []);

  const items = useMemo(() => {
    if (loadStatus === "success") return configuredItems;
    if (loadStatus === "error") return normalizeItems(fallbackItems.filter((item) => canShowFallbackItem(user, item)));
    return [];
  }, [configuredItems, loadStatus, user]);

  if (loadStatus === "loading") return null;
  if (items.length === 0) return null;

  return (
    <nav className="bottom-navigation" aria-label="Menu inferior principal">
      <div className="bottom-navigation-scroll">
        {items.map((item) => (
          <BottomNavItem key={item.id} item={item} pathname={location.pathname} />
        ))}
      </div>
    </nav>
  );
}
