from django.db import models
from categories.models import Category


class CarouselSlide(models.Model):
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300)
    cta_text = models.CharField(max_length=100, help_text="Call to action text")
    image = models.ImageField(upload_to='carousel/')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='carousel_slides')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title
