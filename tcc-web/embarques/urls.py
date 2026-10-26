from django.urls import path
from .api import ViagensEmbarqueApi, GerarQrApi, CheckInApi, HistoricoApi, PresencasApi
from .views import presencas_web
urlpatterns = [
    path('api/embarques/viagens/', ViagensEmbarqueApi.as_view()),
    path('api/embarques/viagens/<int:viagem_id>/qr/', GerarQrApi.as_view()),
    path('api/embarques/viagens/<int:viagem_id>/presencas/', PresencasApi.as_view()),
    path('api/embarques/checkin/', CheckInApi.as_view()),
    path('api/embarques/historico/', HistoricoApi.as_view()),
    path('embarques/', presencas_web, name='presencas_embarque'),
]
