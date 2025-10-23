from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework import permissions
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Product
from .serializers import AdminProductSerializer, ProductListSerializer


class ProductListView(generics.ListAPIView):
    """Public view for listing products"""
    serializer_class = ProductListSerializer
    queryset = Product.objects.filter(is_active=True).select_related('category').prefetch_related('images')


class ProductDetailView(generics.RetrieveAPIView):
    """Public view for product details"""
    serializer_class = ProductListSerializer
    queryset = Product.objects.filter(is_active=True).select_related('category').prefetch_related('images')


class FeaturedProductsView(generics.ListAPIView):
    """Public view for featured products"""
    serializer_class = ProductListSerializer
    queryset = Product.objects.filter(is_active=True).select_related('category').prefetch_related('images')


class TopSellingProductsView(generics.ListAPIView):
    """Public view for top selling products"""
    serializer_class = ProductListSerializer
    queryset = Product.objects.filter(is_active=True).select_related('category').prefetch_related('images')


class AdminProductListView(generics.ListCreateAPIView):
    """Simple admin view for listing and creating products"""
    serializer_class = AdminProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Product.objects.select_related('category').prefetch_related('images').all()

    def list(self, request, *args, **kwargs):
        # Get query parameters
        page = int(request.GET.get('_page', 1))
        limit = int(request.GET.get('_limit', 5))
        search_query = request.GET.get('q', '')
        
        # Build queryset
        queryset = self.get_queryset()
        
        # Apply search filter
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(category__name__icontains=search_query)
            )
        
        # Paginate
        paginator = Paginator(queryset, limit)
        page_obj = paginator.get_page(page)
        
        # Serialize data
        serializer = self.get_serializer(page_obj, many=True)
        
        # Return paginated response
        return Response({
            'data': serializer.data,
            'pagination': {
                'total_count': paginator.count,
                'total_pages': paginator.num_pages,
                'current_page': page,
                'limit': limit,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })

    def create(self, request, *args, **kwargs):
        # Map frontend field names to model field names
        data = request.data.copy()
        if 'isActive' in data:
            data['is_active'] = data.pop('isActive')
        
        # Let the serializer handle category lookup by name
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Simple admin view for retrieving, updating, and deleting products"""
    serializer_class = AdminProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Product.objects.select_related('category').prefetch_related('images').all()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)