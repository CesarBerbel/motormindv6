import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "/api";

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

export function apiUrl(path = "") {
  const base = API_BASE_URL.replace(/\/$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalizedPath}`;
}

const publicEndpoints = ["/token/", "/token/refresh/", "/token/logout/", "/password-setup/confirm/", "/workshop/customer-approvals/", "/attendance/estimate-approvals/"];
let refreshPromise = null;

const NUMERIC_ZERO_FIELDS = new Set([
  "amount",
  "discount_amount",
  "manual_discount_amount",
  "payment_amount",
  "unit_price",
  "unit_cost",
  "cost_price",
  "sale_price",
  "stock_quantity",
  "minimum_stock",
  "estimated_hours",
  "mileage_in",
  "odometer_km",
  "paid_amount",
  "received_quantity",
  "position",
]);

function normalizeNumericEmptyValues(value, key = "") {
  if (Array.isArray(value)) return value.map((item) => normalizeNumericEmptyValues(item));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([childKey, childValue]) => [childKey, normalizeNumericEmptyValues(childValue, childKey)]));
  }
  if (value === "" && NUMERIC_ZERO_FIELDS.has(key)) return "0.00";
  return value;
}

function normalizeUrl(url = "") {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) {
    try {
      const parsed = new URL(url);
      return parsed.pathname.replace(/^\/api/, "") || "/";
    } catch {
      return url;
    }
  }
  return url.startsWith("/") ? url : `/${url}`;
}

function isPublicEndpoint(url = "") {
  const normalized = normalizeUrl(url);
  return publicEndpoints.some((endpoint) => normalized === endpoint || normalized.startsWith(endpoint));
}

function isLoginEndpoint(url = "") {
  return normalizeUrl(url) === "/token/";
}

function isRefreshEndpoint(url = "") {
  return normalizeUrl(url) === "/token/refresh/";
}

export function clearAuthState(reason = "Sessão encerrada.", { notify = true } = {}) {
  if (notify) {
    window.dispatchEvent(new CustomEvent("auth:session-ended", { detail: { reason } }));
  }
}

async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = axios
      .post(`${API_BASE_URL.replace(/\/$/, "")}/token/refresh/`, {}, { withCredentials: true })
      .then((response) => response.data)
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

api.interceptors.request.use((config) => {
  config.headers = config.headers || {};
  config.withCredentials = true;

  if (config.data && typeof config.data === "object" && !(config.data instanceof FormData)) {
    config.data = normalizeNumericEmptyValues(config.data);
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config || {};
    const status = error.response?.status;
    const requestUrl = originalRequest.url || "";

    if (status !== 401 || originalRequest._retry || isPublicEndpoint(requestUrl)) {
      return Promise.reject(error);
    }

    try {
      originalRequest._retry = true;
      await refreshAccessToken();
      originalRequest.withCredentials = true;
      return api(originalRequest);
    } catch (refreshError) {
      clearAuthState("Sua sessão expirou. Entre novamente para continuar.");
      return Promise.reject(refreshError.response ? refreshError : error);
    }
  }
);

export async function logoutSession() {
  try {
    await api.post("/token/logout/", {});
  } finally {
    clearAuthState("Sessão encerrada pelo usuário.");
  }
}

export function results(data) {
  return Array.isArray(data) ? data : data?.results || [];
}

function formatApiPrimitive(value) {
  if (value === null || value === undefined || value === "") return "Campo inválido";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function flattenApiFields(fields, prefix = "") {
  if (Array.isArray(fields)) {
    return fields.flatMap((item, index) => {
      const itemPrefix = prefix ? `${prefix}[${index + 1}]` : `item ${index + 1}`;
      if (item && typeof item === "object") return flattenApiFields(item, itemPrefix);
      return [`${itemPrefix}: ${formatApiPrimitive(item)}`];
    });
  }
  if (!fields || typeof fields !== "object") return prefix ? [`${prefix}: ${formatApiPrimitive(fields)}`] : [];
  return Object.entries(fields).flatMap(([key, value]) => {
    const fieldName = prefix ? `${prefix}.${key}` : key;
    if (Array.isArray(value)) return flattenApiFields(value, fieldName);
    if (value && typeof value === "object") return flattenApiFields(value, fieldName);
    return [`${fieldName}: ${formatApiPrimitive(value)}`];
  });
}

export function apiError(error) {
  const status = error.response?.status;
  const data = error.response?.data;
  const requestUrl = error.config?.url || "";

  if (status === 401 && isLoginEndpoint(requestUrl)) {
    return data?.detail || data?.message || "Usuário ou senha inválidos. Verifique os dados informados e tente novamente.";
  }

  if (status === 401 && isRefreshEndpoint(requestUrl)) {
    return "Sua sessão expirou. Entre novamente para continuar.";
  }

  if (status === 401) {
    return "Sua sessão expirou ou o login não foi identificado. Entre novamente para continuar.";
  }

  if (status === 403) {
    return data?.detail || data?.message || "Você não tem permissão para executar esta ação.";
  }

  if (status === 404) {
    return data?.detail || data?.message || "Registro ou endereço da API não encontrado.";
  }

  if (status >= 500) {
    return data?.detail || data?.message || "Erro interno no servidor. Verifique os logs do backend.";
  }

  if (error.code === "ECONNABORTED") return "A requisição demorou demais para responder.";
  if (!error.response) return "Não foi possível conectar ao backend. Verifique se o servidor está rodando.";

  if (!data) return error.message || "Erro inesperado";
  if (typeof data === "string") return data;

  if (data.message || data.fields) {
    const fieldMessages = flattenApiFields(data.fields);
    return [data.message, ...fieldMessages].filter(Boolean).join(" | ");
  }

  if (data.detail) return data.detail;

  return flattenApiFields(data).join(" | ") || error.message || "Erro inesperado";
}

export function isAuthPublicEndpoint(url = "") {
  return isPublicEndpoint(url);
}

export default api;
