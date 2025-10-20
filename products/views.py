from rest_framework import generics, permissions
from django.db.models import Q
from .models import Product
from .serializers import ProductSerializer, ProductListSerializer


class ProductListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        queryset = Product.objects.select_related('category').prefetch_related('images').filter(is_active=True)

        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(Q(category__slug__iexact=category) | Q(category__name__iexact=category))

        min_price = self.request.query_params.get('minPrice')
        max_price = self.request.query_params.get('maxPrice')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        name_like = self.request.query_params.get('name_like')
        if name_like:
            queryset = queryset.filter(name__icontains=name_like)

        return queryset.order_by('-created_at')


class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductSerializer
    queryset = Product.objects.select_related('category').prefetch_related('images').filter(is_active=True)


class FeaturedProductsView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        return Product.objects.select_related('category').prefetch_related('images').filter(is_active=True)[:8]


class TopSellingProductsView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        return Product.objects.select_related('category').prefetch_related('images').filter(is_active=True)[:8]
