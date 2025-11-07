from rest_framework import serializers
from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_image(self, obj):
        """Return full Cloudinary or local image URL"""
        if not obj:
            return None

        image_url = obj.image_url_or_file
        if not image_url:
            return None

        # Already a Cloudinary/external URL
        if image_url.startswith("http"):
            return image_url

        # Otherwise build absolute URI for local media
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(image_url)
        return image_url