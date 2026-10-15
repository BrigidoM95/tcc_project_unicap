from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    UsuarioLoginView, RenovarTokenApi, LogoutApi, AlterarSenhaApi,
    LoginApiView,
    alterar_status_usuario,
    cadastrar_usuario,
    editar_usuario,
    listar_usuarios,
    logout_view,
)


urlpatterns = [
    path('api/logout/', LogoutApi.as_view(), name='api_logout'),
    path('api/senha/', AlterarSenhaApi.as_view(), name='api_senha'),
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
        RenovarTokenApi.as_view(),
        name="api_token_refresh",
    ),
]