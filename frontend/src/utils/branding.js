const DEFAULT_TITLE = "MotorMind";
const DEFAULT_FAVICON = "/favicon.svg";

function ensureFaviconLink() {
  let link = document.querySelector('link[rel="icon"]');
  if (!link) {
    link = document.createElement("link");
    link.setAttribute("rel", "icon");
    document.head.appendChild(link);
  }
  return link;
}

function normalizeName(profile = {}) {
  return profile.display_name || profile.trade_name || profile.legal_name || profile.name || DEFAULT_TITLE;
}

function normalizeLogo(profile = {}) {
  return profile.logo_url || profile.logo || "";
}

export function applyBrowserBranding(profile = {}) {
  if (typeof document === "undefined") return;

  const companyName = normalizeName(profile);
  document.title = companyName;

  const favicon = ensureFaviconLink();
  const logoUrl = normalizeLogo(profile);
  if (logoUrl) {
    favicon.setAttribute("href", logoUrl);
  } else {
    favicon.setAttribute("href", DEFAULT_FAVICON);
  }
}

export function resetBrowserBranding() {
  applyBrowserBranding({ display_name: DEFAULT_TITLE, logo_url: DEFAULT_FAVICON });
}
