from django.urls import path

from . import views
from .mapa import mapa, MapaApi, DetalheMapaApi

urlpatterns = [
    path('mapa/', mapa, name='mapa'),
    path('api/mapa/', MapaApi.as_view(), name='api_mapa'),
    path('api/mapa/viagens/<int:viagem_id>/', DetalheMapaApi.as_view(), name='api_mapa_viagem'),
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
]
