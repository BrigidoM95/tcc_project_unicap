from django.contrib import admin
from django.urls import include, path

from paginas.views import home


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('usuarios.urls')),
    path('', home, name='home'),
]
