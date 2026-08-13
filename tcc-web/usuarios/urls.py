from django.urls import path

from .views import (
    UsuarioLoginView,
    cadastrar_usuario,
    listar_usuarios,
    logout_view,
)


urlpatterns = [
    path("login/", UsuarioLoginView.as_view(), name="login"),
    path("logout/", logout_view, name="logout"),

    path("usuarios/", listar_usuarios, name="listar_usuarios"),
    path(
        "usuarios/cadastrar/",
        cadastrar_usuario,
        name="cadastrar_usuario",
    ),
]