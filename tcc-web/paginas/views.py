from django.shortcuts import render
from relatorios.views import administrador_ativo
@administrador_ativo
def home(request):
    return render(request, 'paginas/home.html')
