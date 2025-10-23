from django.urls import path
from .views import (
    ProductListView,
    ProductDetailView,
    FeaturedProductsView,
    TopSellingProductsView,
    AdminProductListView,
    AdminProductDetailView,
)

urlpatterns = [
    # Public endpoints
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/featured/', FeaturedProductsView.as_view(), name='product-featured'),
    path('products/top_selling/', TopSellingProductsView.as_view(), name='product-top-selling'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product-detail'),
    
    # Admin-only endpoints
    path('admin/products/', AdminProductListView.as_view(), name='admin-product-list'),
    path('admin/products/<int:pk>/', AdminProductDetailView.as_view(), name='admin-product-detail'),
]
