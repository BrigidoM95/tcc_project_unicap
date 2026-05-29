from django.urls import path

from .views import UsuarioLoginView, logout_view


urlpatterns = [
    path('login/', UsuarioLoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
]
