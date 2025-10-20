from django.urls import path
from .views import (
    ProductListView,
    ProductDetailView,
    FeaturedProductsView,
    TopSellingProductsView,
)

urlpatterns = [
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/featured/', FeaturedProductsView.as_view(), name='product-featured'),
    path('products/top_selling/', TopSellingProductsView.as_view(), name='product-top-selling'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product-detail'),
]
