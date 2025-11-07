from django.db import models
from cloudinary.models import CloudinaryField
from cloudinary.uploader import destroy

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    image = CloudinaryField('image', blank=True, null=True)
    image_url = models.URLField(blank=True, null=True, help_text="External image URL")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

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
