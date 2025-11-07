from rest_framework import serializers
from .models import CarouselSlide
from categories.serializers import CategorySerializer
from categories.models import Category

class CarouselSlideSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    cta = serializers.CharField(source='cta_text')
    category = serializers.SlugRelatedField(queryset=Category.objects.all(), slug_field='name')

    class Meta:
        model = CarouselSlide
        fields = [
            'id', 'title', 'subtitle', 'cta', 'image',
            'category', 'is_active', 'order', 'created_at', 'updated_at'
        ]

    def get_image(self, obj):
        """Return image URL with Cloudinary/local/external fallback"""
        url = obj.image_url_or_file
        if url:
            return url
        return '/placeholder.svg'
