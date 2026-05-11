from __future__ import annotations

import re

import bleach
from bs4 import BeautifulSoup
from bleach.css_sanitizer import CSSSanitizer

ALLOWED_EMAIL_HTML_TAGS = [
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
]

ALLOWED_EMAIL_HTML_ATTRIBUTES = {
    "*": ["align", "class", "style", "title"],
    "a": ["href", "rel", "target", "title"],
    "td": ["align", "colspan", "rowspan", "style"],
    "th": ["align", "colspan", "rowspan", "style"],
    "li": ["class"],
    "ol": ["class"],
    "ul": ["class"],
}

ALLOWED_EMAIL_HTML_PROTOCOLS = ["http", "https", "mailto", "tel"]
ALLOWED_CSS_PROPERTIES = ["background-color", "color", "text-align"]
SAFE_CLASS_RE = re.compile(r"^ql-[a-z0-9_-]+$", re.IGNORECASE)
UNSAFE_CSS_VALUE_RE = re.compile(r"(url\s*\(|expression\s*\(|javascript:|data:)", re.IGNORECASE)
DANGEROUS_TAGS = ["script", "style", "iframe", "object", "embed", "svg", "form", "input", "button", "textarea", "select", "option", "video", "applet", "base", "link", "meta"]

css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)


def _allowed_attribute(tag: str, name: str, value: str) -> bool:
    allowed_for_all = ALLOWED_EMAIL_HTML_ATTRIBUTES.get("*", [])
    allowed_for_tag = ALLOWED_EMAIL_HTML_ATTRIBUTES.get(tag, [])
    if name not in allowed_for_all and name not in allowed_for_tag:
        return False
    if name == "class":
        return True
    if name == "style":
        return not UNSAFE_CSS_VALUE_RE.search(str(value or ""))
    if name == "target":
        return value == "_blank"
    if name == "rel":
        return value in {"noopener", "noreferrer", "noopener noreferrer"}
    return True



def _remove_dangerous_tags(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup.find_all(DANGEROUS_TAGS):
        tag.decompose()
    return str(soup)


def _harden_links_and_classes(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for element in soup.find_all(True):
        classes = element.get("class") or []
        if classes:
            safe_classes = [class_name for class_name in classes if SAFE_CLASS_RE.match(class_name)]
            if safe_classes:
                element["class"] = safe_classes
            elif element.has_attr("class"):
                del element["class"]

    for link in soup.find_all("a"):
        if link.get("target") == "_blank":
            link["rel"] = "noopener noreferrer"
        elif link.has_attr("rel"):
            del link["rel"]
    return str(soup)


def sanitize_template_html(html: str) -> str:
    """Sanitiza HTML editável antes de salvar, renderizar, registrar ou enviar email."""
    raw_html = _remove_dangerous_tags(html)
    cleaned = bleach.clean(
        raw_html,
        tags=ALLOWED_EMAIL_HTML_TAGS,
        attributes=_allowed_attribute,
        protocols=ALLOWED_EMAIL_HTML_PROTOCOLS,
        strip=True,
        strip_comments=True,
        css_sanitizer=css_sanitizer,
    )
    return _harden_links_and_classes(cleaned).strip()


def sanitize_rendered_email_html(html: str) -> str:
    return sanitize_template_html(html)
