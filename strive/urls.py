from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from accounts.jwt_views import CookieTokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


urlpatterns = [
    path('admin/', admin.site.urls),
    # JWT Auth
    path('api/auth/jwt/create/', TokenObtainPairView.as_view(), name='jwt-obtain-pair'),
    path('api/auth/jwt/refresh/', CookieTokenRefreshView.as_view(), name='jwt-refresh'),
    path('api/', include('accounts.urls')),
    # Users api
    path('api/', include('products.urls')),
    path('api/', include('categories.urls')),
    path('api/', include('orders.urls')),
    path('api/', include('carousel.urls')),

    # swagger docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
