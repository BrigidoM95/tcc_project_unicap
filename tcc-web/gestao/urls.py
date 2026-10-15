from django.urls import path
from . import views
app_name='gestao'
urlpatterns=[
 path('',views.painel,name='painel'),
 path('auditoria/',views.auditoria,name='auditoria'),
 path('despesas/pdf/',views.despesas_pdf,name='despesas_pdf'),
 path('despesas/<int:pk>/cancelar/',views.cancelar_despesa,name='cancelar_despesa'),
 path('<str:tipo>/',views.lista,name='lista'),
 path('<str:tipo>/novo/',views.editar,name='novo'),
 path('<str:tipo>/<int:pk>/editar/',views.editar,name='editar'),
]
