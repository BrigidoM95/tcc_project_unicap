from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from paginas.views import home
from .health import health


urlpatterns = [
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