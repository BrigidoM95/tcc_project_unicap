from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render
from usuarios.views import eh_administrador
from rotas.models import Viagem
from .models import CheckIn

@user_passes_test(eh_administrador, login_url='login')
def presencas_web(request):
    registros = CheckIn.objects.select_related('viagem__rota', 'fiscal__user')
    viagem = request.GET.get('viagem', '')
    if viagem.isdigit():
        registros = registros.filter(viagem_id=int(viagem))
    return render(request, 'embarques/presencas.html', {
        'registros': registros[:500], 'viagens': Viagem.objects.select_related('rota')[:200],
        'selecionada': viagem, 'total': registros.count(),
    })
