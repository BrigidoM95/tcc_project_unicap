from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from paginas.views import home
from gestao import revisao
from .health import health


urlpatterns = [
    path('usuarios/<int:pk>/', revisao.detalhe_usuario, name='detalhe_usuario'),
    path('usuarios/<int:pk>/redefinir-senha/', revisao.redefinir_senha, name='redefinir_senha'),
    path('conta/senha/', revisao.trocar_senha_web, name='trocar_senha_web'),
    path('onibus/<int:pk>/detalhes/', revisao.detalhe_onibus, name='detalhe_onibus'),
    path('rotas/<int:pk>/', revisao.detalhe_rota, name='detalhe_rota'),
    path('operacao/', revisao.viagens, name='viagens_admin'),
    path('operacao/<int:pk>/', revisao.intervir, name='intervir_viagem'),
    path('', include('rotas.urls_v3')),
    path("health/",health,name="health"),
    path("gestao/", include("gestao.urls")),
    path("admin/", admin.site.urls),
    path("", include("usuarios.urls")),
    path("", include("onibus.urls")),
    path("", include("rotas.urls")),
    path("", include("embarques.urls")),
    path("relatorios/", include("relatorios.urls")),
    path("", home, name="home"),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
