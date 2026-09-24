from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    UsuarioLoginView,
    LoginApiView,
    alterar_status_usuario,
    cadastrar_usuario,
    editar_usuario,
    listar_usuarios,
    logout_view,
)


urlpatterns = [
    path("login/", UsuarioLoginView.as_view(), name="login"),
    path("logout/", logout_view, name="logout"),

    path("api/login/", LoginApiView.as_view(), name="api_login"),

    path("usuarios/", listar_usuarios, name="listar_usuarios"),
    path("usuarios/cadastrar/", cadastrar_usuario, name="cadastrar_usuario"),
    path(
        "usuarios/<int:usuario_id>/editar/",
        editar_usuario,
        name="editar_usuario",
    ),
    path(
        "usuarios/<int:usuario_id>/status/",
        alterar_status_usuario,
        name="alterar_status_usuario",
    ),
    path(
        "api/token/refresh/",
        TokenRefreshView.as_view(),
        name="api_token_refresh",
    ),
]