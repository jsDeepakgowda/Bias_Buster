from django.urls import path
from .views import *

urlpatterns = [
    path("", home, name="home"),
    path("analyse/", analyse, name="analyse"),
    path("about/", about, name="about"),
    path("analyze-news/", analyze_news, name="analyze_news"),
]
