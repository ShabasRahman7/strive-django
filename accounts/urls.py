from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, AddressViewSet, forgot_password_view, reset_password_view,
    register_request_view, register_verify_view
)
from .csrf_views import get_csrf_token

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'addresses', AddressViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('users/login/', UserViewSet.as_view({'post': 'login'}), name='user-login'),
    path('users/register/', UserViewSet.as_view({'post': 'register'}), name='user-register'),
    path('users/logout/', UserViewSet.as_view({'post': 'logout'}), name='user-logout'),
    path('users/add_address/', UserViewSet.as_view({'post': 'add_address'}), name='user-add-address'),
    path('users/delete_address/', UserViewSet.as_view({'delete': 'delete_address'}), name='user-delete-address'),
    path('users/cart/', UserViewSet.as_view({'get': 'cart', 'patch': 'cart'}), name='user-cart'),
    path('users/wishlist/', UserViewSet.as_view({'get': 'wishlist', 'patch': 'wishlist'}), name='user-wishlist'),
    path('forgot_password/', forgot_password_view, name='forgot-password'),
    path('reset_password/', reset_password_view, name='reset-password'),
    path('register_request/', register_request_view, name='register-request'),
    path('register_verify/', register_verify_view, name='register-verify'),
    path('csrf-token/', get_csrf_token, name='csrf_token'),
]
