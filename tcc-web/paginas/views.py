from django.shortcuts import render
from relatorios.views import administrador_ativo
@administrador_ativo
def home(request):
    from gestao.indicadores import indicadores
    return render(request, 'paginas/home.html', indicadores(2 if request.GET.get('acoes')=='2' else 1))
