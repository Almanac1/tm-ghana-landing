from django.urls import path

from .views import blog_detail, blog_list, home

urlpatterns = [
    path("", home, name="home"),
    path("blog/", blog_list, name="blog_list"),
    path("blog/<slug:slug>/", blog_detail, name="blog_detail"),
]
