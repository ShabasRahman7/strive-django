from rest_framework import serializers
from .models import Product, ProductImage
from categories.models import Category


class AdminProductSerializer(serializers.ModelSerializer):
    """Simple admin serializer for product management"""
    images = serializers.SerializerMethodField()
    category = serializers.SlugRelatedField(queryset=Category.objects.all(), slug_field='name', required=False)
    count = serializers.IntegerField(source='stock_count')
    isActive = serializers.BooleanField(source='is_active', read_only=False)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=False)
    description = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'count',
            'category', 'isActive', 'images', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_images(self, obj):
        images = obj.images.all()
        if not images.exists():
            return ['/placeholder.svg']
        
        # Get primary image first, then others
        primary_image = images.filter(is_primary=True).first()
        if primary_image:
            # Return primary image first, then others
            image_list = [primary_image.image_url_or_file] if primary_image.image_url_or_file else []
            for img in images.exclude(id=primary_image.id):
                if img.image_url_or_file:
                    image_list.append(img.image_url_or_file)
            return image_list if image_list else ['/placeholder.svg']
        else:
            # No primary image, return all available images
            image_list = []
            for img in images:
                if img.image_url_or_file:
                    image_list.append(img.image_url_or_file)
            return image_list if image_list else ['/placeholder.svg']

    def create(self, validated_data):
        # Handle image uploads
        request = self.context.get('view').request
        images_data = request.FILES.getlist('images', [])
        
        # Also check for image URLs (for backward compatibility)
        # NOTE: request.data can contain both files and strings under the same key.
        # We only keep string entries here and ignore files.
        raw_images = request.data.getlist('images', [])
        image_urls = [u.strip() for u in raw_images if isinstance(u, str) and u.strip()]

        product = Product.objects.create(**validated_data)

        # Handle uploaded files
        for i, image_file in enumerate(images_data):
            if image_file:
                ProductImage.objects.create(
                    product=product,
                    image=image_file,
                    is_primary=(i == 0)
                )
        
        # Handle image URLs (for backward compatibility). Only if no files were uploaded
        if not images_data and image_urls:
            for i, image_url in enumerate(image_urls):
                ProductImage.objects.create(
                    product=product,
                    image_url=image_url,
                    is_primary=(i == 0)
                )

        return product

    def update(self, instance, validated_data):
        # Update product fields
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        # Handle image uploads for updates
        request = self.context.get('view').request
        images_data = request.FILES.getlist('images', [])

        # Handle new image uploads (replace existing images)
        if images_data:
            # Clear existing images
            instance.images.all().delete()
            
            # Add new images
            for i, image_file in enumerate(images_data):
                if image_file:
                    ProductImage.objects.create(
                        product=instance,
                        image=image_file,
                        is_primary=(i == 0)
                    )
        
        return instance


class ProductListSerializer(serializers.ModelSerializer):
    """Simplified serializer for product lists - matches frontend expectations"""
    images = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source='is_active')
    count = serializers.IntegerField(source='stock_count')
    category = serializers.CharField(source='category.name')

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'count', 'category',
            'isActive', 'images', 'created_at', 'updated_at'
        ]

    def get_price(self, obj):
        return float(obj.price)

    def get_images(self, obj):
        images = obj.images.all()
        if not images.exists():
            return ['/placeholder.svg']
        
        # Get primary image first, then others
        primary_image = images.filter(is_primary=True).first()
        if primary_image:
            # Return primary image first, then others
            image_list = [primary_image.image_url_or_file] if primary_image.image_url_or_file else []
            for img in images.exclude(id=primary_image.id):
                if img.image_url_or_file:
                    image_list.append(img.image_url_or_file)
            return image_list if image_list else ['/placeholder.svg']
        else:
            # No primary image, return all available images
            image_list = []
            for img in images:
                if img.image_url_or_file:
                    image_list.append(img.image_url_or_file)
            return image_list if image_list else ['/placeholder.svg']