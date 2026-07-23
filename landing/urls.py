from django.urls import path

from .views import blog_detail, blog_list, home, privacy_policy

urlpatterns = [
    path("", home, name="home"),
    path("privacy-policy/", privacy_policy, name="privacy_policy"),
    path("blog/", blog_list, name="blog_list"),
    path("blog/<slug:slug>/", blog_detail, name="blog_detail"),
]
