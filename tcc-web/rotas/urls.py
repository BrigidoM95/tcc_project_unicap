from django.urls import path

from . import views

from .api import (
    PainelMotoristaApi,
    IniciarViagemApi,
    FinalizarViagemApi,
    EnviarLocalizacaoApi,

)


urlpatterns = [
    path(
        "rotas/",
        views.listar_rotas,
        name="listar_rotas",
    ),
    path(
        "rotas/cadastrar/",
        views.cadastrar_rota,
        name="cadastrar_rota",
    ),
    path(
        "rotas/<int:rota_id>/editar/",
        views.editar_rota,
        name="editar_rota",
    ),
    path(
        "rotas/<int:rota_id>/status/",
        views.alterar_status_rota,
        name="alterar_status_rota",
    ),
    path(
        "rotas/<int:rota_id>/pontos/",
        views.listar_pontos,
        name="listar_pontos",
    ),
    path(
        "rotas/<int:rota_id>/pontos/cadastrar/",
        views.cadastrar_ponto,
        name="cadastrar_ponto",
    ),
    path(
        "rotas/<int:rota_id>/pontos/<int:ponto_id>/editar/",
        views.editar_ponto,
        name="editar_ponto",
    ),
    path(
        "api/viagens/painel/",
        PainelMotoristaApi.as_view(),
        name="api_painel_motorista",
    ),
    path(
        "api/viagens/iniciar/",
        IniciarViagemApi.as_view(),
        name="api_iniciar_viagem",
    ),
    path(
        "api/viagens/<int:viagem_id>/finalizar/",
        FinalizarViagemApi.as_view(),
        name="api_finalizar_viagem",
    ),
     path(
        "api/viagens/<int:viagem_id>/localizacao/",
        EnviarLocalizacaoApi.as_view(),
        name="api_enviar_localizacao",
    ),
]