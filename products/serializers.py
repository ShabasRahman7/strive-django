from rest_framework import serializers
from .models import Product, ProductImage
from categories.serializers import CategorySerializer


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'created_at']
        read_only_fields = ['id', 'created_at']


class ProductSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
    category = serializers.CharField(source='category.name', read_only=True)
    category_id = serializers.IntegerField(write_only=True)
    count = serializers.IntegerField(source='stock_count', read_only=True)
    isActive = serializers.BooleanField(source='is_active', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'count', 
            'category', 'category_id', 'isActive', 'images', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_images(self, obj):
        images = obj.images.all()
        if not images.exists():
            return ['/placeholder.svg']  # Fallback image
        
        #primary image first, then others
        primary_image = images.filter(is_primary=True).first()
        if primary_image:
            image_list = [primary_image.image_url_or_file]
            other_images = images.exclude(id=primary_image.id)
            image_list.extend([img.image_url_or_file for img in other_images])
            return image_list
        else:
            return [img.image_url_or_file for img in images]

    def create(self, validated_data):
        images_data = self.context.get('view').request.FILES
        product = Product.objects.create(**validated_data)
        
        for image_data in images_data.getlist('images'):
            ProductImage.objects.create(product=product, image=image_data)
        
        return product


class ProductListSerializer(serializers.ModelSerializer):
    """Simplified serializer for product lists - matches frontend expectations"""
    images = serializers.SerializerMethodField()
    category = serializers.CharField(source='category.name', read_only=True)
    count = serializers.IntegerField(source='stock_count', read_only=True)
    isActive = serializers.BooleanField(source='is_active', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'price', 'count', 'category',
            'isActive', 'images', 'created_at'
        ]

    def get_images(self, obj):
        """Return array of image URLs as expected by frontend"""
        images = obj.images.all()
        if not images.exists():
            return ['/placeholder.svg']
        
        # Return primary image first, then others
        primary_image = images.filter(is_primary=True).first()
        if primary_image:
            image_list = [primary_image.image_url_or_file]
            other_images = images.exclude(id=primary_image.id)
            image_list.extend([img.image_url_or_file for img in other_images])
            return image_list
        else:
            return [img.image_url_or_file for img in images]



