from django.db import models
from categories.models import Category
from cloudinary.models import CloudinaryField
from cloudinary.uploader import destroy

class CarouselSlide(models.Model):
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300)
    cta_text = models.CharField(max_length=100, help_text="Call to action text")
    image = CloudinaryField('image', blank=True, null=True)
    image_url = models.URLField(blank=True, null=True, help_text="External image URL")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='carousel_slides')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title

    @property
    def image_url_or_file(self):
        """Return Cloudinary or external image URL"""
        if self.image_url:
            return self.image_url
        elif self.image:
            return self.image.url
        return None

    def delete(self, *args, **kwargs):
        """Delete Cloudinary image on record deletion"""
        if self.image:
            public_id = self.image.public_id
            try:
                destroy(public_id)
                print(f"Cloudinary image {public_id} deleted successfully.")
            except Exception as e:
                print(f"Error deleting image from Cloudinary: {e}")
        super().delete(*args, **kwargs)