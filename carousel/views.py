from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import CarouselSlide
from .serializers import CarouselSlideSerializer


class CarouselSlideViewSet(viewsets.ModelViewSet):
    queryset = CarouselSlide.objects.select_related('category').order_by('order', '-created_at')
    serializer_class = CarouselSlideSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active carousel slides ordered by display order"""
        slides = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(slides, many=True)
        return Response({'results': serializer.data})
