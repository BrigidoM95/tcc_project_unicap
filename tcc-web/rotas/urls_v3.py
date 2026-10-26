from django.urls import path
from . import api_v3 as api

urlpatterns = [
    path('api/viagens/hoje/',api.HojeApi.as_view()),
    path('api/viagens/<int:viagem_id>/',api.ViagemApi.as_view()),
    path('api/viagens/<int:viagem_id>/transicao/',api.TransicaoApi.as_view()),
    path('api/viagens/<int:viagem_id>/assumir/',api.AssumirApi.as_view()),
    path('api/viagens/<int:viagem_id>/assentos/',api.AssentosApi.as_view()),
    path('api/viagens/<int:viagem_id>/reservas/',api.ReservasApi.as_view()),
    path('api/viagens/<int:viagem_id>/minha-escolha/',api.CancelarEscolhaApi.as_view()),
    path('api/reservas/<int:reserva_id>/',api.CancelarReservaApi.as_view()),
    path('api/viagens/<int:viagem_id>/qr-do-dia/',api.QrApi.as_view()),
    path('api/viagens/<int:viagem_id>/embarques/',api.EmbarquesApi.as_view()),
    path('api/viagens/<int:viagem_id>/associados/',api.BuscarAssociadosApi.as_view()),
    path('api/viagens/<int:viagem_id>/embarques/manual/',api.ManualApi.as_view()),
    path('api/viagens/<int:viagem_id>/embarques/fiscal/',api.ProprioApi.as_view()),
    path('api/checkins/',api.CheckinApi.as_view()),
    path('api/checkins/sincronizar/',api.CheckinApi.as_view()),
    path('api/checkins/<int:checkin_id>/',api.CancelarEmbarqueApi.as_view()),
    path('api/me/embarques/',api.HistoricoApi.as_view()),
    path('api/viagens/<int:viagem_id>/localizacoes/',api.LocalizacoesApi.as_view()),
    # Os endpoints antigos não podem contornar as novas regras.
    path('api/viagens/iniciar/',api.LegadoDesativadoApi.as_view()),
    path('api/viagens/<int:viagem_id>/finalizar/',api.LegadoDesativadoApi.as_view()),
    path('api/viagens/<int:viagem_id>/localizacao/',api.LegadoDesativadoApi.as_view()),
    path('api/embarques/checkin/',api.CheckinApi.as_view()),
    path('api/embarques/historico/',api.HistoricoApi.as_view()),
    path('api/embarques/viagens/',api.HojeApi.as_view()),
    path('api/embarques/viagens/<int:viagem_id>/qr/',api.QrApi.as_view()),
    path('api/embarques/viagens/<int:viagem_id>/presencas/',api.EmbarquesApi.as_view()),
]
