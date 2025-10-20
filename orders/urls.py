from django.urls import path
from .views import (
    OrderListView,
    OrderDetailView,
    CreateOrderFromCartView,
    RazorpayCreateOrderView,
    RazorpayVerifyPaymentView,
    CartListCreateView,
    CartDetailView,
    CartClearView,
    WishlistListCreateView,
    WishlistDetailView,
    WishlistClearView,
)

urlpatterns = [
    path('orders/', OrderListView.as_view(), name='order-list'),
    path('orders/<int:pk>/', OrderDetailView.as_view(), name='order-detail'),
    path('orders/create_from_cart/', CreateOrderFromCartView.as_view(), name='order-create-from-cart'),
    # Razorpay payment endpoints
    path('payments/razorpay/create-order/', RazorpayCreateOrderView.as_view(), name='razorpay-create-order'),
    path('payments/razorpay/verify/', RazorpayVerifyPaymentView.as_view(), name='razorpay-verify'),
    path('cart/', CartListCreateView.as_view(), name='cart-list-create'),
    path('cart/<int:pk>/', CartDetailView.as_view(), name='cart-detail'),
    path('cart/clear/', CartClearView.as_view(), name='cart-clear'),
    path('wishlist/', WishlistListCreateView.as_view(), name='wishlist-list-create'),
    path('wishlist/<int:pk>/', WishlistDetailView.as_view(), name='wishlist-detail'),
    path('wishlist/clear/', WishlistClearView.as_view(), name='wishlist-clear'),
]
