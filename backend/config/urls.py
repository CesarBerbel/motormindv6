from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .auth_views import CookieTokenLogoutView, CookieTokenObtainPairView, CookieTokenRefreshView
from .health import DeepHealthCheckView, PublicHealthCheckView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/token/", CookieTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/logout/", CookieTokenLogoutView.as_view(), name="token_logout"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/health/", PublicHealthCheckView.as_view(), name="health-check"),
    path("api/health/deep/", DeepHealthCheckView.as_view(), name="health-check-deep"),
    path("api/", include("messaging.urls")),
    path("api/ai/", include("ai_assistant.urls")),
    path("api/accounts/", include("accounts.urls")),
    path("api/workshop/", include("workshop.urls")),
    path("api/attendance/", include("attendance.urls")),
    path("api/finance/", include("finance.urls")),
    path("api/purchasing/", include("purchasing.urls")),
    path("api/reports/", include("reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
