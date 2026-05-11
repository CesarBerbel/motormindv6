from urllib.parse import urlparse

from django.conf import settings

LOCAL_FRONTEND_URLS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
}


def normalize_base_url(url):
    """Return a clean scheme://host[:port] URL without path/query/trailing slash."""
    value = str(url or "").strip().rstrip("/")
    if not value:
        return ""
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _is_local_frontend_url(url):
    return normalize_base_url(url) in LOCAL_FRONTEND_URLS


def _allowed_request_origins():
    allowed = set()
    for attr in ("CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS"):
        for origin in getattr(settings, attr, []) or []:
            normalized = normalize_base_url(origin)
            if normalized:
                allowed.add(normalized)
    return allowed


def _origin_from_request(request):
    if request is None:
        return ""

    allowed = _allowed_request_origins()
    candidates = [
        request.META.get("HTTP_ORIGIN", ""),
        request.META.get("HTTP_REFERER", ""),
    ]

    for candidate in candidates:
        normalized = normalize_base_url(candidate)
        if not normalized:
            continue
        if settings.DEBUG or not allowed or normalized in allowed:
            return normalized

    try:
        normalized = normalize_base_url(request.build_absolute_uri("/"))
    except Exception:
        normalized = ""
    return normalized


def get_frontend_base_url(request=None):
    """
    Resolve the public frontend URL used in emails/public links.

    Priority:
    1. FRONTEND_BASE_URL when configured to a production/non-local URL.
    2. Browser Origin/Referer from the authenticated admin request, when allowed.
    3. FRONTEND_BASE_URL even if local, useful for local/dev scripts without request.
    4. Local Vite default.

    This avoids sending production password setup links pointing to localhost when the
    environment variable was not configured but the request came from the real frontend.
    """
    configured = normalize_base_url(getattr(settings, "FRONTEND_BASE_URL", ""))
    if configured and (settings.DEBUG or not _is_local_frontend_url(configured)):
        return configured

    request_origin = _origin_from_request(request)
    if request_origin:
        return request_origin

    if configured:
        return configured

    return "http://localhost:5173"
