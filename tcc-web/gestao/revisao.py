"""Telas administrativas da revisão documental de outubro de 2026."""
from django import forms
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from relatorios.views import administrador_ativo
from usuarios.models import Usuario
from onibus.models import Onibus
from rotas.models import Rota, Viagem, Ponto
from rotas import operacao
from .auditoria import registrar


@administrador_ativo
def detalhe_usuario(request, pk):
    p=get_object_or_404(Usuario.objects.select_related('user','curso__instituicao'),pk=pk)
    campos={'Nome':str(p),'RUA':p.rua,'E-mail':p.user.email,'Telefone':p.telefone,'Tipo':p.get_tipo_display(),
        'Situação':'Ativo' if p.user.is_active else 'Inativo','Instituição / curso':str(p.curso or 'Não informado'),
        'Administrador':'Sim' if p.tipo=='administrador' or p.user.is_superuser else 'Não'}
    return render(request,'gestao/detalhe.html',{'titulo':'Detalhes do usuário','campos':campos,
        'editar':reverse('editar_usuario',args=[pk]),'usuario':p,'embarques':Paginator(p.checkins.select_related('viagem__rota'),25).get_page(request.GET.get('pagina')),'voltar':reverse('listar_usuarios')})


@administrador_ativo
def redefinir_senha(request,pk):
    p=get_object_or_404(Usuario.objects.select_related('user'),pk=pk)
    if p.user.is_superuser and not request.user.is_superuser:
        messages.error(request,'Somente um superusuário pode redefinir esta senha.');return redirect('detalhe_usuario',pk=pk)
    form=SetPasswordForm(p.user,request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            user=form.save()
            Usuario.objects.filter(pk=p.pk).update(senha_definida_em=timezone.now())
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
            for token in OutstandingToken.objects.filter(user=user):
                BlacklistedToken.objects.get_or_create(token=token)
            registrar('senha_redefinida',modelo='usuarios.usuario',objeto_id=p.pk)
        if request.user.pk==user.pk:
            update_session_auth_hash(request,user)
        messages.success(request,f'Senha de {p} redefinida. O usuário deverá entrar novamente com a nova senha.')
        return redirect('detalhe_usuario',pk=pk)
    return render(request,'usuarios/redefinir_senha.html',{'usuario':p,'form':form})


@administrador_ativo
def trocar_senha_web(request):
    if not request.user.is_authenticated:return redirect('login')
    form=PasswordChangeForm(request.user,request.POST or None)
    if request.method=='POST' and form.is_valid():
        user=form.save();Usuario.objects.filter(user=user).update(senha_definida_em=timezone.now())
        update_session_auth_hash(request,user);registrar('senha_alterada',usuario=user)
        return redirect('home')
    return render(request,'gestao/formulario.html',{'titulo':'Definir sua senha','form':form,'tipo':'instituicoes'})


@administrador_ativo
def detalhe_onibus(request,pk):
    o=get_object_or_404(Onibus.objects.select_related('motorista__user'),pk=pk)
    campos={'Código':o.codigo,'Nome':o.nome,'Placa':o.placa,'Capacidade':o.capacidade,'Motorista':str(o.motorista),
        'Situação':o.get_status_display(),'Observações':o.observacoes}
    if o.foto and not o.foto_url: campos['Foto']='Arquivo anterior indisponível. Reenvie a fotografia em Editar.'
    return render(request,'gestao/detalhe.html',{'titulo':'Detalhes do ônibus','campos':campos,'foto':o.foto_url,
        'editar':reverse('editar_onibus',args=[pk]),'voltar':reverse('listar_onibus')})


@administrador_ativo
def detalhe_rota(request,pk):
    r=get_object_or_404(Rota.objects.select_related('onibus__motorista__user','fiscal__user'),pk=pk)
    campos={'Rota':r.nome,'Destino':r.destino,'Ônibus':str(r.onibus),'Motorista':str(r.motorista),
        'Fiscal':str(r.fiscal or 'Sem fiscal'),'Saída':r.horario_ida,'Retorno':r.horario_retorno,
        'Instituições':', '.join(r.instituicoes.values_list('nome',flat=True)),
        'Dias de operação':', '.join(['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'][i] for i in (r.dias_operacao or range(7))),
        'Situação':r.get_status_display(),'Pontos':', '.join(str(p) for p in r.pontos.all())}
    return render(request,'gestao/detalhe.html',{'titulo':'Detalhes da rota','campos':campos,
        'editar':reverse('editar_rota',args=[pk]),'voltar':reverse('listar_rotas')})


class IntervencaoForm(forms.Form):
    acao=forms.ChoiceField(choices=[('encerrar','Encerrar viagem'),('cancelar','Cancelar viagem'),('substituir','Substituir ônibus / motorista'),('alterar_fiscal','Alterar fiscal da viagem')])
    onibus=forms.ModelChoiceField(Onibus.objects.filter(status='ativo'),required=False,label='Novo ônibus')
    motorista=forms.ModelChoiceField(Usuario.objects.filter(tipo='motorista',user__is_active=True),required=False,label='Novo motorista')
    fiscal=forms.ModelChoiceField(Usuario.objects.filter(tipo='fiscal',user__is_active=True),required=False,
        label='Novo fiscal',help_text='Preencha ao escolher Alterar fiscal da viagem. A troca vale somente para esta viagem já iniciada.')
    motivo=forms.CharField(max_length=300,widget=forms.Textarea(attrs={'rows':3}))

    def clean(self):
        dados=super().clean()
        if dados.get('acao')=='alterar_fiscal' and not dados.get('fiscal'):
            self.add_error('fiscal','Selecione o novo fiscal responsável pela viagem.')
        return dados


@administrador_ativo
def viagens(request):
    operacao.encerrar_antigas();operacao.gerar_viagens()
    qs=Viagem.objects.select_related('rota','onibus','motorista__user','fiscal__user').order_by('-data_servico','-pk')
    if request.GET.get('revisar')=='1':qs=qs.filter(encerrada_pelo_sistema=True)
    return render(request,'gestao/viagens.html',{'viagens':Paginator(qs,30).get_page(request.GET.get('pagina'))})


@administrador_ativo
def intervir(request,pk):
    v=get_object_or_404(Viagem,pk=pk);form=IntervencaoForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                v=operacao.bloquear(pk);d=form.cleaned_data;acao=d['acao']
                detalhes={'acao':acao,'motivo':d['motivo']}
                if v.status in ('finalizada','cancelada'):raise ValidationError('A viagem já está encerrada.')
                if acao=='cancelar' and v.etapa not in ('agendada','embarque_ida'):raise ValidationError('Só é possível cancelar antes da partida da ida.')
                if acao in ('cancelar','encerrar'):
                    v.status='cancelada' if acao=='cancelar' else 'finalizada';v.etapa='cancelada' if acao=='cancelar' else 'encerrada'
                    v.finalizada_em=max(timezone.now(),v.iniciada_em);v.motivo_cancelamento=d['motivo']
                    v.reservas.filter(ativa=True).update(ativa=False)
                    if acao=='cancelar':v.checkins.filter(cancelado_em__isnull=True).update(cancelado_em=timezone.now(),motivo_cancelamento=d['motivo'])
                elif acao=='alterar_fiscal':
                    if v.etapa=='agendada':raise ValidationError('A viagem ainda não foi iniciada. Altere o fiscal no cadastro da rota.')
                    detalhes.update({'fiscal_anterior_id':v.fiscal_id,'novo_fiscal_id':d['fiscal'].pk})
                    v.fiscal=d['fiscal']
                else:
                    if v.etapa=='agendada':raise ValidationError('A viagem ainda não foi iniciada. Altere o ônibus no cadastro da rota ou o motorista no cadastro do ônibus.')
                    if not d['onibus'] and not d['motorista']:raise ValidationError('Selecione o novo ônibus ou motorista.')
                    if d['onibus']:
                        novo=Onibus.objects.select_for_update().get(pk=d['onibus'].pk)
                        maior=max(v.checkins.filter(cancelado_em__isnull=True).values_list('vaga',flat=True),default=0)
                        maior=max(maior,max(v.reservas.filter(ativa=True,expira_em__gt=timezone.now()).values_list('assento',flat=True),default=0))
                        if novo.capacidade<maior:raise ValidationError('O novo ônibus não comporta as poltronas confirmadas ou reservadas.')
                        if Viagem.objects.filter(onibus=novo,status='em_andamento').exclude(pk=v.pk).exists():raise ValidationError('O novo ônibus está em outra viagem.')
                        v.onibus=novo;v.capacidade_registrada=novo.capacidade
                        v.codigo_onibus_registrado=novo.codigo;v.placa_onibus_registrada=novo.placa
                    if d['motorista']:
                        if Viagem.objects.filter(motorista=d['motorista'],status='em_andamento').exclude(pk=v.pk).exists():raise ValidationError('O motorista está em outra viagem.')
                        v.motorista=d['motorista']
                v.save(update_fields=['fiscal'] if acao=='alterar_fiscal' else None)
                registrar('intervencao_viagem',modelo='rotas.viagem',objeto_id=v.pk,detalhes=detalhes)
            messages.success(request,'Viagem atualizada; a intervenção foi registrada na auditoria.');return redirect('viagens_admin')
        except ValidationError as e:form.add_error(None,e)
    return render(request,'gestao/intervir.html',{'viagem':v,'form':form})
