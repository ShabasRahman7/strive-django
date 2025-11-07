from django.db import models
from categories.models import Category
from cloudinary.models import CloudinaryField
from cloudinary.uploader import destroy

class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_count = models.PositiveIntegerField(default=0)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def is_in_stock(self):
        return self.stock_count > 0


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = CloudinaryField('image', blank=True, null=True) 
    image_url = models.URLField(blank=True, null=True, help_text="External image URL")
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'created_at']

    def __str__(self):
        return f"{self.product.name} - Image {self.id}"
    
    @property
    def image_url_or_file(self):
        """Return image URL or file URL"""
        if self.image_url:
            return self.image_url
        elif self.image:
            return self.image.url
        return None

    def delete(self, *args, **kwargs):
        """Override the delete method to delete the image from Cloudinary."""
        if self.image:
            public_id = self.image.public_id  # Cloudinary img identifier
            try:
                destroy(public_id)  #del img from cloudinary
                print(f"Cloudinary image {public_id} deleted successfully.")
            except Exception as e:
                print(f"Error deleting image from Cloudinary: {e}")
        super().delete(*args, **kwargs)  # Call the parent class delete method
