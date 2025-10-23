from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, AddressViewSet, PasswordSetupViewSet, forgot_password_view, reset_password_view,
    register_request_view, register_verify_view, setup_password_view
)
from .csrf_views import get_csrf_token

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'addresses', AddressViewSet)
router.register(r'password-setup', PasswordSetupViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('users/login/', UserViewSet.as_view({'post': 'login'}), name='user-login'),
    path('users/register/', UserViewSet.as_view({'post': 'register'}), name='user-register'),
    path('users/logout/', UserViewSet.as_view({'post': 'logout'}), name='user-logout'),
    path('users/setup-password/', UserViewSet.as_view({'post': 'setup_password'}), name='user-setup-password'),
    path('setup-password/', setup_password_view, name='setup-password'),
    path('users/add_address/', UserViewSet.as_view({'post': 'add_address'}), name='user-add-address'),
    path('users/delete_address/', UserViewSet.as_view({'delete': 'delete_address'}), name='user-delete-address'),
    path('users/cart/', UserViewSet.as_view({'get': 'cart', 'patch': 'cart'}), name='user-cart'),
    path('users/wishlist/', UserViewSet.as_view({'get': 'wishlist', 'patch': 'wishlist'}), name='user-wishlist'),
    # Admin
    path('users/admin/list/', UserViewSet.as_view({'get': 'admin_list'}), name='admin-user-list'),
    path('users/admin/unactivated/', UserViewSet.as_view({'get': 'admin_unactivated_users'}), name='admin-unactivated-users'),
    path('users/admin/create/', UserViewSet.as_view({'post': 'admin_create'}), name='admin-user-create'),
    path('users/<int:pk>/admin/detail/', UserViewSet.as_view({'get': 'admin_retrieve'}), name='admin-user-detail'),
    path('users/<int:pk>/admin/update/', UserViewSet.as_view({'patch': 'admin_update'}), name='admin-user-update'),
    path('users/<int:pk>/admin/edit/', UserViewSet.as_view({'patch': 'admin_edit'}), name='admin-user-edit'),
    path('users/<int:pk>/admin/resend-setup/', UserViewSet.as_view({'post': 'admin_resend_setup'}), name='admin-resend-setup'),
    path('users/<int:pk>/admin/delete/', UserViewSet.as_view({'delete': 'admin_destroy'}), name='admin-user-delete'),
    path('forgot_password/', forgot_password_view, name='forgot-password'),
    path('reset_password/', reset_password_view, name='reset-password'),
    path('register_request/', register_request_view, name='register-request'),
    path('register_verify/', register_verify_view, name='register-verify'),
    path('csrf-token/', get_csrf_token, name='csrf_token'),
]
