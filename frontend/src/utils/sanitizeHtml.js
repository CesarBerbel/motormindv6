import DOMPurify from "dompurify";

const ALLOWED_TAGS = [
  "a",
  "b",
  "blockquote",
  "br",
  "caption",
  "code",
  "col",
  "colgroup",
  "div",
  "em",
  "h1",
  "h2",
  "h3",
  "h4",
  "hr",
  "i",
  "li",
  "ol",
  "p",
  "pre",
  "s",
  "span",
  "strong",
  "table",
  "tbody",
  "td",
  "tfoot",
  "th",
  "thead",
  "tr",
  "u",
  "ul",
];

const ALLOWED_ATTR = [
  "align",
  "class",
  "colspan",
  "data-list",
  "href",
  "rel",
  "rowspan",
  "style",
  "target",
  "title",
];

const SAFE_STYLE_PROPERTIES = new Set([
  "background-color",
  "color",
  "text-align",
]);

const SAFE_URI_PATTERN = /^(https?:|mailto:|tel:|\/|#)/i;
const UNSAFE_CSS_VALUE_PATTERN = /(url\s*\(|expression\s*\(|javascript:|data:)/i;

const PURIFY_CONFIG = {
  ALLOWED_TAGS,
  ALLOWED_ATTR,
  ALLOW_DATA_ATTR: false,
  ALLOWED_URI_REGEXP: SAFE_URI_PATTERN,
  FORBID_TAGS: [
    "applet",
    "base",
    "button",
    "embed",
    "form",
    "frame",
    "frameset",
    "iframe",
    "input",
    "link",
    "meta",
    "object",
    "option",
    "script",
    "select",
    "style",
    "svg",
    "textarea",
    "video",
  ],
  FORBID_ATTR: ["src", "srcdoc", "xlink:href"],
  RETURN_TRUSTED_TYPE: false,
};

function cleanClassList(element) {
  if (!element.classList?.length) return;
  [...element.classList].forEach((className) => {
    if (!className.startsWith("ql-")) {
      element.classList.remove(className);
    }
  });
  if (!element.classList.length) {
    element.removeAttribute("class");
  }
}

function cleanInlineStyle(element) {
  const style = element.getAttribute("style");
  if (!style) return;

  const safeDeclarations = [];
  for (const property of SAFE_STYLE_PROPERTIES) {
    const value = element.style.getPropertyValue(property).trim();
    if (!value || UNSAFE_CSS_VALUE_PATTERN.test(value)) continue;
    safeDeclarations.push(`${property}: ${value}`);
  }

  if (safeDeclarations.length) {
    element.setAttribute("style", `${safeDeclarations.join("; ")};`);
  } else {
    element.removeAttribute("style");
  }
}

function hardenLinks(root) {
  root.querySelectorAll("a").forEach((link) => {
    const href = link.getAttribute("href") || "";
    if (!href || !SAFE_URI_PATTERN.test(href)) {
      link.removeAttribute("href");
    }

    const target = link.getAttribute("target");
    if (target && target !== "_blank") {
      link.removeAttribute("target");
    }
    if (link.getAttribute("target") === "_blank") {
      link.setAttribute("rel", "noopener noreferrer");
    } else {
      link.removeAttribute("rel");
    }
  });
}

function hardenSanitizedHtml(sanitizedHtml) {
  if (typeof document === "undefined") return sanitizedHtml;

  const template = document.createElement("template");
  template.innerHTML = sanitizedHtml;

  template.content.querySelectorAll("*").forEach((element) => {
    cleanClassList(element);
    cleanInlineStyle(element);
  });
  hardenLinks(template.content);

  return template.innerHTML;
}

export function sanitizeRichHtml(html) {
  const sanitizedHtml = DOMPurify.sanitize(html || "", PURIFY_CONFIG);
  return hardenSanitizedHtml(sanitizedHtml);
}

export function sanitizePlainText(text) {
  return String(text || "")
    .replace(/\u0000/g, "")
    .trim();
}

export { PURIFY_CONFIG };
