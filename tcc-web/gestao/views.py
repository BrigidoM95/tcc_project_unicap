from decimal import Decimal
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from relatorios.views import administrador_ativo
from usuarios.models import Usuario, Instituicao, Curso
from onibus.models import Onibus
from .models import Despesa, LogAuditoria
from .forms import PontoForm
from rotas.models import Ponto
from .forms import InstituicaoForm, CursoForm, DespesaForm, FiltroDespesas

CONFIG = {'pontos':(Ponto,PontoForm,'Pontos de embarque'),'instituicoes':(Instituicao,InstituicaoForm,'Instituições'),
 'cursos':(Curso,CursoForm,'Cursos'),
 'despesas':(Despesa,DespesaForm,'Despesas')}

@administrador_ativo
def painel(request):
    return render(request, 'gestao/painel.html')

@administrador_ativo
def lista(request,tipo):
    if tipo not in CONFIG: raise Http404
    model,_,titulo = CONFIG[tipo]
    qs = model.objects.all()
    if tipo == 'cursos': qs = qs.select_related('instituicao')
    if tipo == 'despesas': return despesas(request)
    q=request.GET.get('q','').strip()
    if q:
        qs=qs.filter(nome__icontains=q)
    estado=request.GET.get('status','')
    if estado in ('ativos','inativos'):
        campo='ativa' if tipo == 'instituicoes' else 'ativo'
        qs=qs.filter(**{campo:estado=='ativos'})
    return render(request,'gestao/lista.html',{'tipo':tipo,'titulo':titulo,
        'objetos':Paginator(qs,30).get_page(request.GET.get('pagina'))})

@administrador_ativo
def editar(request,tipo,pk=None):
    if tipo not in CONFIG: raise Http404
    model,Form,titulo = CONFIG[tipo]
    obj = get_object_or_404(model,pk=pk) if pk else None
    if tipo == 'despesas' and obj and obj.cancelada:
        messages.error(request,'Despesa cancelada não pode ser alterada.')
        return redirect('gestao:lista',tipo=tipo)
    form = Form(request.POST or None,instance=obj)
    if request.method == 'POST' and form.is_valid():
        registro=form.save(commit=False)
        registro.save();form.save_m2m()
        if tipo=='pontos':
            from rotas.models import PontoEmbarque
            PontoEmbarque.objects.filter(ponto=registro).update(nome=registro.nome,endereco=registro.endereco)
        messages.success(request,'Registro salvo.')
        return redirect('gestao:lista',tipo=tipo)
    return render(request,'gestao/formulario.html',{'titulo':titulo,'form':form,'tipo':tipo})

def consulta_despesas(request):
    hoje = timezone.localdate()
    dados = request.GET.copy()
    dados.setdefault('inicio',hoje.replace(day=1).isoformat());dados.setdefault('fim',hoje.isoformat())
    form = FiltroDespesas(dados)
    qs = Despesa.objects.none()
    if form.is_valid():
        qs = Despesa.objects.filter(data__range=(form.cleaned_data['inicio'],form.cleaned_data['fim'])).select_related('onibus')
        if form.cleaned_data.get('onibus'): qs = qs.filter(onibus=form.cleaned_data['onibus'])
    return form,qs

@administrador_ativo
def despesas(request):
    form,qs = consulta_despesas(request)
    total = qs.filter(cancelada=False).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    params = request.GET.copy();params.pop('pagina',None)
    return render(request,'gestao/despesas.html',{'form':form,'total':total,
        'objetos':Paginator(qs,30).get_page(request.GET.get('pagina')),'parametros':params.urlencode()})

@require_POST
@administrador_ativo
def cancelar_despesa(request,pk):
    obj = get_object_or_404(Despesa,pk=pk)
    motivo = request.POST.get('motivo','').strip()
    if not motivo or len(motivo)>200:
        messages.error(request,'Informe o motivo do cancelamento (até 200 caracteres).')
    elif not obj.cancelada:
        obj.cancelada=True;obj.motivo_cancelamento=motivo;obj.save()
        messages.success(request,'Despesa cancelada; o histórico foi mantido.')
    return redirect('gestao:lista',tipo='despesas')

@administrador_ativo
def auditoria(request):
    qs = LogAuditoria.objects.select_related('usuario')
    busca = request.GET.get('q','').strip()[:80]
    from django.db.models import Q
    if busca: qs = qs.filter(Q(modelo__icontains=busca)|Q(descricao__icontains=busca)|Q(usuario__first_name__icontains=busca)|Q(ip__icontains=busca))
    acao=request.GET.get('acao','')
    if acao: qs=qs.filter(acao=acao)
    return render(request,'gestao/auditoria.html',{'objetos':Paginator(qs,50).get_page(request.GET.get('pagina')),'busca':busca,'acao':acao,'acoes':LogAuditoria.objects.values_list('acao',flat=True).distinct()})

@administrador_ativo
def despesas_pdf(request):
    from .pdf import gerar_despesas_pdf
    form,qs = consulta_despesas(request)
    if not form.is_valid(): return render(request,'gestao/formulario.html',{'titulo':'Filtros inválidos','form':form,'tipo':'despesas'},status=400)
    if qs.count() > 5000: return HttpResponse('Reduza o período: limite de 5.000 despesas.',status=400)
    result = HttpResponse(gerar_despesas_pdf(qs,form.cleaned_data),content_type='application/pdf')
    result['Content-Disposition']='attachment; filename="despesas-unicap.pdf"'
    return result


@require_POST
@administrador_ativo
def alterar_status(request,tipo,pk):
    if tipo not in ('pontos','cursos','instituicoes'): raise Http404
    model,_,_=CONFIG[tipo];obj=get_object_or_404(model,pk=pk)
    campo='ativa' if tipo=='instituicoes' else 'ativo'
    if getattr(obj,campo):
        from rotas.models import Rota, PontoEmbarque
        em_uso=(Rota.objects.filter(instituicoes=obj,status='ativa').exists() if tipo=='instituicoes' else PontoEmbarque.objects.filter(ponto=obj,ativo=True,rota__status='ativa').exists() if tipo=='pontos' else False)
        if em_uso:
            messages.error(request,'Este cadastro está vinculado a uma rota ativa. Ajuste a rota antes de desativar.')
            return redirect('gestao:lista',tipo=tipo)
    setattr(obj,campo,not getattr(obj,campo));obj.save(update_fields=[campo])
    messages.success(request,'Situação atualizada. O histórico foi preservado.')
    return redirect('gestao:lista',tipo=tipo)
