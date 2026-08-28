from django.urls import path

from .views import (
    DesativarOnibusApiView,
    OnibusDetalheApiView,
    OnibusListaApiView,
    ReativarOnibusApiView,
    alterar_status_onibus,
    cadastrar_onibus,
    editar_onibus,
    listar_onibus,
)


urlpatterns = [
    path(
        "onibus/",
        listar_onibus,
        name="listar_onibus",
    ),

    path(
        "onibus/cadastrar/",
        cadastrar_onibus,
        name="cadastrar_onibus",
    ),

    path(
        "onibus/<int:onibus_id>/editar/",
        editar_onibus,
        name="editar_onibus",
    ),

    path(
        "onibus/<int:onibus_id>/status/",
        alterar_status_onibus,
        name="alterar_status_onibus",
    ),

    path(
        "api/onibus/",
        OnibusListaApiView.as_view(),
        name="api_onibus_lista",
    ),

    path(
        "api/onibus/<int:onibus_id>/",
        OnibusDetalheApiView.as_view(),
        name="api_onibus_detalhe",
    ),

    path(
        "api/onibus/<int:onibus_id>/desativar/",
        DesativarOnibusApiView.as_view(),
        name="api_onibus_desativar",
    ),

    path(
        "api/onibus/<int:onibus_id>/reativar/",
        ReativarOnibusApiView.as_view(),
        name="api_onibus_reativar",
    ),
]