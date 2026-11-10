from django.urls import path
from .views import presencas_web
urlpatterns = [
    path('embarques/', presencas_web, name='presencas_embarque'),
]
