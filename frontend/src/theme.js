export const defaultThemeSettings = {
  ui_theme_mode: "light",
  ui_primary_color: "#0D6EFD",
  ui_accent_color: "#FD7E14",
  ui_sidebar_color: "#172033",
  ui_form_density: "comfortable",
  ui_table_density: "comfortable",
  ui_card_radius: "rounded",
  ui_button_style: "solid",
  ui_form_layout: "grouped",
  ui_show_required_hint: true,
  ui_enable_motion: true,
};

const radiusMap = { soft: ".55rem", rounded: ".9rem", pill: "1.35rem" };
const densityMap = {
  compact: { controlPaddingY: ".42rem", controlPaddingX: ".65rem", sectionPadding: ".85rem", rowGap: ".75rem" },
  comfortable: { controlPaddingY: ".58rem", controlPaddingX: ".78rem", sectionPadding: "1rem", rowGap: "1rem" },
  spacious: { controlPaddingY: ".75rem", controlPaddingX: ".95rem", sectionPadding: "1.25rem", rowGap: "1.25rem" },
};

function normalizeColor(value, fallback) {
  if (typeof value !== "string") return fallback;
  const cleaned = value.trim();
  return /^#[0-9a-fA-F]{6}$/.test(cleaned) ? cleaned : fallback;
}

function hexToRgb(hex) {
  const value = normalizeColor(hex, "#0D6EFD").replace("#", "");
  const numeric = Number.parseInt(value, 16);
  return `${(numeric >> 16) & 255}, ${(numeric >> 8) & 255}, ${numeric & 255}`;
}

function isDarkMode(settings) {
  const mode = settings.ui_theme_mode || "light";
  if (mode === "dark") return true;
  if (mode === "auto" && typeof window !== "undefined") return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches || false;
  return false;
}

export function normalizeThemeSettings(raw = {}) {
  return {
    ...defaultThemeSettings,
    ...raw,
    ui_primary_color: normalizeColor(raw.ui_primary_color, defaultThemeSettings.ui_primary_color),
    ui_accent_color: normalizeColor(raw.ui_accent_color, defaultThemeSettings.ui_accent_color),
    ui_sidebar_color: normalizeColor(raw.ui_sidebar_color, defaultThemeSettings.ui_sidebar_color),
    ui_form_density: ["compact", "comfortable", "spacious"].includes(raw.ui_form_density) ? raw.ui_form_density : defaultThemeSettings.ui_form_density,
    ui_table_density: ["compact", "comfortable"].includes(raw.ui_table_density) ? raw.ui_table_density : defaultThemeSettings.ui_table_density,
    ui_card_radius: ["soft", "rounded", "pill"].includes(raw.ui_card_radius) ? raw.ui_card_radius : defaultThemeSettings.ui_card_radius,
    ui_button_style: ["solid", "soft", "outline"].includes(raw.ui_button_style) ? raw.ui_button_style : defaultThemeSettings.ui_button_style,
    ui_form_layout: ["grouped", "flat", "wizard"].includes(raw.ui_form_layout) ? raw.ui_form_layout : defaultThemeSettings.ui_form_layout,
    ui_show_required_hint: raw.ui_show_required_hint !== false,
    ui_enable_motion: raw.ui_enable_motion !== false,
  };
}

export function applyAdminTheme(rawSettings = {}) {
  if (typeof document === "undefined") return normalizeThemeSettings(rawSettings);
  const settings = normalizeThemeSettings(rawSettings);
  const root = document.documentElement;
  const density = densityMap[settings.ui_form_density] || densityMap.comfortable;
  const isDark = isDarkMode(settings);

  root.style.setProperty("--mm-primary", settings.ui_primary_color);
  root.style.setProperty("--mm-primary-rgb", hexToRgb(settings.ui_primary_color));
  root.style.setProperty("--mm-accent", settings.ui_accent_color);
  root.style.setProperty("--mm-accent-rgb", hexToRgb(settings.ui_accent_color));
  root.style.setProperty("--mm-sidebar", settings.ui_sidebar_color);
  root.style.setProperty("--mm-sidebar-rgb", hexToRgb(settings.ui_sidebar_color));
  root.style.setProperty("--mm-radius", radiusMap[settings.ui_card_radius] || radiusMap.rounded);
  root.style.setProperty("--mm-control-padding-y", density.controlPaddingY);
  root.style.setProperty("--mm-control-padding-x", density.controlPaddingX);
  root.style.setProperty("--mm-section-padding", density.sectionPadding);
  root.style.setProperty("--mm-form-gap", density.rowGap);

  document.body.dataset.themeMode = isDark ? "dark" : "light";
  document.body.dataset.formDensity = settings.ui_form_density;
  document.body.dataset.tableDensity = settings.ui_table_density;
  document.body.dataset.cardRadius = settings.ui_card_radius;
  document.body.dataset.buttonStyle = settings.ui_button_style;
  document.body.dataset.formLayout = settings.ui_form_layout;
  document.body.dataset.requiredHints = settings.ui_show_required_hint ? "on" : "off";
  document.body.dataset.motion = settings.ui_enable_motion ? "on" : "off";
  return settings;
}
