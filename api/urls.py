from django.urls import path
from .views import analyze_news, home

urlpatterns = [
    path("", home, name="home"),
    path("analyze-news/", analyze_news, name="analyze_news"),
]