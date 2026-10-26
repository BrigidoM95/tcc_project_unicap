from django import forms
from django.core.paginator import Paginator
from django.db.models import CharField, Exists, OuterRef, Q
from django.db.models.functions import Cast, Coalesce
from django.shortcuts import render
from relatorios.views import administrador_ativo
from rotas.models import Viagem
from rotas.operacao import data_operacional
from onibus.models import Onibus
from gestao.models import LogAuditoria
from .models import CheckIn

class FiltrosEmbarque(forms.Form):
    data=forms.DateField(label='Data',widget=forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d'))
    onibus=forms.ModelChoiceField(label='Ônibus',queryset=Onibus.objects.all(),required=False,empty_label='Todos')
    sentido=forms.ChoiceField(choices=[('','Ida e volta'),('ida','Ida'),('retorno','Volta')],required=False)
    q=forms.CharField(label='Buscar associado',required=False,max_length=150,widget=forms.TextInput(attrs={'placeholder':'Nome ou RUA'}))

@administrador_ativo
def presencas_web(request):
    dados=request.GET.copy()
    ultima_viagem=None
    if not dados.get('data'):
        # Agendadas já possuem iniciada_em; encerramentos automáticos também
        # podem envolver viagens que nunca saíram. Exigimos evidência do início.
        inicios=LogAuditoria.objects.filter(modelo='rotas.viagem',acao='iniciar_rota',objeto_id=Cast(OuterRef('pk'),CharField()))
        iniciadas=Viagem.objects.annotate(inicio_confirmado=Exists(inicios)).filter(
            Q(status='em_andamento') | Q(ciclo_completo=False,status='finalizada') |
            Q(partida_ida_em__isnull=False) | Q(chegada_em__isnull=False) |
            Q(partida_volta_em__isnull=False) | Q(inicio_confirmado=True)
        )
        if dados.get('onibus','').isdigit():
            iniciadas=iniciadas.filter(onibus_id=dados['onibus'])
        ultima_viagem=iniciadas.select_related('rota','onibus').order_by('-iniciada_em','-pk').first()
        dados['data']=(ultima_viagem.data_servico if ultima_viagem else data_operacional()).isoformat()
    form=FiltrosEmbarque(dados)
    grupos=[]
    data_exibida=None
    if form.is_valid():
        d=form.cleaned_data
        data_exibida=d['data']
        viagens=Viagem.objects.filter(data_servico=d['data']).select_related('rota','onibus').order_by('onibus__codigo','pk')
        if d.get('onibus'): viagens=viagens.filter(onibus=d['onibus'])
        registros=CheckIn.objects.filter(viagem__data_servico=d['data'],cancelado_em__isnull=True).select_related('viagem__rota','viagem__onibus').annotate(horario=Coalesce('lido_em','registrado_em')).order_by('-horario','-pk')
        if d.get('q'): registros=registros.filter(Q(nome_associado__icontains=d['q'])|Q(rua_associado__icontains=d['q']))
        for v in viagens:
            for sentido in ([d['sentido']] if d.get('sentido') else ['ida','retorno']):
                if not v.ciclo_completo and v.sentido!=sentido: continue
                chave=f'pagina_{v.pk}_{sentido}'
                pagina=Paginator(registros.filter(viagem=v,sentido=sentido),50).get_page(request.GET.get(chave))
                parametros=dados.copy();parametros.pop(chave,None)
                grupos.append({'viagem':v,'sentido':'Ida' if sentido=='ida' else 'Volta','id':f'grupo-{v.pk}-{sentido}',
                    'registros':pagina,'total':pagina.paginator.count,'percentual':min(100,round(pagina.paginator.count*100/v.capacidade_embarque)),
                    'chave':chave,'parametros':parametros.urlencode()})
    return render(request,'embarques/presencas.html',{'form':form,'grupos':grupos,'parametros':dados.urlencode(),
        'data_exibida':data_exibida,'ultima_viagem':ultima_viagem,'hoje':data_operacional()})
