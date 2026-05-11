from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


def _cookie_domain():
    return settings.JWT_AUTH_COOKIE_DOMAIN or None


def _cookie_secure():
    return bool(settings.JWT_AUTH_COOKIE_SECURE)


def _access_max_age():
    return int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())


def _refresh_max_age():
    return int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


def set_jwt_auth_cookies(response, *, access=None, refresh=None):
    """Grava tokens JWT em cookies HttpOnly, sem expor os valores ao JavaScript."""
    common = {
        "httponly": True,
        "secure": _cookie_secure(),
        "samesite": settings.JWT_AUTH_COOKIE_SAMESITE,
        "domain": _cookie_domain(),
    }
    if access:
        response.set_cookie(
            settings.JWT_AUTH_COOKIE_ACCESS,
            access,
            max_age=_access_max_age(),
            path=settings.JWT_AUTH_COOKIE_PATH,
            **common,
        )
    if refresh:
        response.set_cookie(
            settings.JWT_AUTH_COOKIE_REFRESH,
            refresh,
            max_age=_refresh_max_age(),
            path=settings.JWT_AUTH_REFRESH_COOKIE_PATH,
            **common,
        )
    return response


def clear_jwt_auth_cookies(response):
    """Remove os cookies de autenticação usando os mesmos paths/domínio usados na gravação."""
    common = {
        "domain": _cookie_domain(),
        "samesite": settings.JWT_AUTH_COOKIE_SAMESITE,
    }
    response.delete_cookie(settings.JWT_AUTH_COOKIE_ACCESS, path=settings.JWT_AUTH_COOKIE_PATH, **common)
    response.delete_cookie(settings.JWT_AUTH_COOKIE_REFRESH, path=settings.JWT_AUTH_REFRESH_COOKIE_PATH, **common)
    return response


class CookieTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = TokenObtainPairSerializer
    throttle_scope = "auth_login"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data
        response = Response({"detail": "Login realizado com sucesso."})
        return set_jwt_auth_cookies(response, access=tokens.get("access"), refresh=tokens.get("refresh"))


class CookieTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    serializer_class = TokenRefreshSerializer
    throttle_scope = "auth_refresh"

    def post(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data or {})
        if not data.get("refresh"):
            cookie_refresh = request.COOKIES.get(settings.JWT_AUTH_COOKIE_REFRESH)
            if cookie_refresh:
                data["refresh"] = cookie_refresh

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data
        response = Response({"detail": "Sessão renovada com sucesso."})
        return set_jwt_auth_cookies(response, access=tokens.get("access"), refresh=tokens.get("refresh"))


class CookieTokenLogoutView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth_refresh"

    def post(self, request, *args, **kwargs):
        response = Response({"detail": "Sessão encerrada com sucesso."})
        return clear_jwt_auth_cookies(response)
