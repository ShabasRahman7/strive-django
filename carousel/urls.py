from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CarouselSlideViewSet

router = DefaultRouter()
router.register(r'slides', CarouselSlideViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # Active slides endpoint for frontend compatibility
    path('slides/active/', CarouselSlideViewSet.as_view({'get': 'active'}), name='carousel-active'),
]
