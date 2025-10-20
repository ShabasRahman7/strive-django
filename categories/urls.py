from django.urls import path
from .views import CategoryListView, ActiveCategoryListView

urlpatterns = [
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('categories/active/', ActiveCategoryListView.as_view(), name='category-active'),
]
