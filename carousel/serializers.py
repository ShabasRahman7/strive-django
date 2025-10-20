from rest_framework import serializers
from .models import CarouselSlide
from categories.serializers import CategorySerializer


class CarouselSlideSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='category.name', read_only=True)
    category_id = serializers.IntegerField(write_only=True)
    cta = serializers.CharField(source='cta_text', read_only=True)

    class Meta:
        model = CarouselSlide
        fields = [
            'id', 'title', 'subtitle', 'cta', 'image',
            'category', 'category_id', 'is_active', 'order',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']



