from datetime import datetime, timedelta
from decimal import Decimal

from django.core import signing
from django.core.paginator import Paginator
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from embarques.models import CheckIn, ReservaAssento, SessaoEmbarque
from gestao.auditoria import registrar
from usuarios.models import Usuario
from .api import BaseViagemApi
from .models import LocalizacaoViagem, Viagem
from . import operacao as op


class OperacaoApi(BaseViagemApi):
    def handle_exception(self, exc):
        if isinstance(exc, (IntegrityError, OperationalError)):
            exc = op.Regra('Outra operação ocorreu ao mesmo tempo. Atualize e tente novamente.')
        response = super().handle_exception(exc)
        if isinstance(response.data, dict) and 'detail' in response.data:
            response.data['mensagem'] = str(response.data['detail'])
            response.data['codigo'] = getattr(exc, 'default_code', 'requisicao_invalida')
        return response


class HojeApi(OperacaoApi):
    def get(self, request):
        p=op.perfil(request.user)
        op.encerrar_antigas(); op.gerar_viagens()
        sentido=request.query_params.get('sentido')
        if sentido: op.validar_sentido(sentido)
        qs=op.consulta_viagens(p).filter(data_servico=op.data_operacional()).order_by('rota__horario_ida','pk')
        return Response({'viagens':[op.dados_viagem(v,p,sentido) for v in qs], 'atualizado_em':timezone.now().isoformat()})


class ViagemApi(OperacaoApi):
    def get(self, request, viagem_id):
        p=op.perfil(request.user)
        v=op.viagem_visivel(p,viagem_id)
        sentido=request.query_params.get('sentido')
        if sentido: op.validar_sentido(sentido)
        return Response(op.dados_viagem(v,p,sentido))


class TransicaoApi(OperacaoApi):
    def post(self, request, viagem_id):
        p=op.perfil(request.user)
        instante=parse_datetime(str(request.data.get('ocorrida_em',''))) if request.data.get('ocorrida_em') else None
        if request.data.get('ocorrida_em') and instante is None: raise op.Regra('Horário da etapa inválido.')
        v=op.transicao(viagem_id,p,request.data.get('acao'),instante)
        return Response(op.dados_viagem(v,p))


class AssumirApi(OperacaoApi):
    @transaction.atomic
    def post(self,request,viagem_id):
        p=op.perfil(request.user)
        if p.tipo!='fiscal': raise PermissionDenied('Somente fiscais podem assumir viagens.')
        v=op.bloquear(viagem_id)
        op.exigir_fiscal(v,p)
        if v.etapa not in ('agendada','embarque_ida','no_destino'): raise op.Regra('Esta viagem não pode ser assumida agora.')
        v.fiscal=p;v.save(update_fields=['fiscal'])
        registrar('viagem_assumida',usuario=p.user,modelo='rotas.viagem',objeto_id=v.pk)
        return Response(op.dados_viagem(v,p))


class AssentosApi(OperacaoApi):
    def get(self,request,viagem_id):
        p=op.perfil(request.user);v=op.viagem_visivel(p,viagem_id)
        passageiro=p
        associado_id=request.query_params.get('associado_id')
        if associado_id is not None:
            op.exigir_fiscal(v,p)
            if not associado_id.isdigit(): raise op.Regra('Selecione um associado válido.')
            passageiro=get_object_or_404(Usuario.objects.select_related('user','curso__instituicao'),pk=int(associado_id))
            op.exigir_passageiro(passageiro,v)
        sentido=op.validar_sentido(request.query_params.get('sentido',v.sentido_atual))
        trajeto=request.query_params.get('trajeto')
        sentidos=op.sentidos_trajeto(trajeto) if trajeto else [sentido]
        ocupadas=set()
        minhas=set()
        for direcao in sentidos:
            ocupadas.update(op.registros(v,direcao).values_list('vaga',flat=True))
            if op.escolha_aberta(v,direcao):
                for r in op.reservas(v,direcao):
                    (minhas if r.associado_id==passageiro.pk else ocupadas).add(r.assento)
        return Response({'viagem':op.dados_viagem(v,p,sentido),'assentos':[
            {'numero':n,'estado':'ocupada' if n in ocupadas else 'reservada' if n in minhas else 'livre'}
            for n in range(1,v.capacidade_embarque+1)]})


class ReservasApi(OperacaoApi):
    @transaction.atomic
    def post(self,request,viagem_id):
        p=op.perfil(request.user)
        d=request.data
        trajeto=d.get('trajeto')
        # Compatibilidade com clientes anteriores durante a atualização.
        if trajeto is None:
            trajeto={'ida':'ida','retorno':'volta'}.get(d.get('sentido'))
        reservas=op.reservar(viagem_id,p,trajeto,d.get('poltrona'),d.get('ponto_ida_id'),d.get('ponto_volta_id'))
        r=reservas[0]
        return Response({'reservas':[op.dados_reserva(x) for x in reservas],
            'reserva':op.dados_reserva(r),'minha_escolha':op.minha_escolha(r.viagem,p),
            'viagem':op.dados_viagem(r.viagem,p,r.sentido)},status=201)


class CancelarReservaApi(OperacaoApi):
    def delete(self,request,reserva_id):
        p=op.perfil(request.user)
        r=get_object_or_404(ReservaAssento,pk=reserva_id,associado=p)
        op.cancelar_escolha(r.viagem_id,p,r.pk)
        return Response({'detail':'Reserva liberada.'})


class CancelarEscolhaApi(OperacaoApi):
    def delete(self,request,viagem_id):
        p=op.perfil(request.user)
        op.viagem_visivel(p,viagem_id)
        v=op.cancelar_escolha(viagem_id,p)
        return Response({'detail':'Escolha cancelada nos sentidos sem check-in.',
                         'viagem':op.dados_viagem(v,p)})


class QrApi(OperacaoApi):
    def get(self,request,viagem_id):
        p=op.perfil(request.user);v=op.viagem_visivel(p,viagem_id);op.exigir_fiscal(v,p)
        return Response({'pontos':[{'id':x.pk,'nome':x.nome,'ordem':x.ordem} for x in v.rota.pontos.filter(ativo=True,sentido=v.sentido_atual)]})
    def post(self,request,viagem_id):
        p=op.perfil(request.user)
        v=op.viagem_visivel(p,viagem_id)
        s=op.gerar_qr(v.pk,p,request.data.get('sentido',v.sentido_atual),request.data.get('ponto_id'))
        return Response({'codigo':op.codigo_qr(s),'gerado_em':s.gerado_em.isoformat(),'expira_em':s.expira_em.isoformat(),
            'ponto_id':s.ponto_id,'ponto_nome':s.nome_ponto,'viagem':op.dados_viagem(v,p,s.sentido)})


class LimiteCheckin(UserRateThrottle):
    rate='20/min'


class CheckinApi(OperacaoApi):
    throttle_classes=[LimiteCheckin]
    def post(self,request):
        p=op.perfil(request.user)
        try:
            return self.confirmar(request,p)
        except APIException as e:
            registrar('checkin_recusado',usuario=p.user,detalhes={'motivo':str(e.detail)[:250]})
            raise
    def confirmar(self,request,p):
        d=request.data;codigo=d.get('codigo','')
        try:
            if not isinstance(codigo,str) or not codigo.startswith('UNICAP:V3:'): raise ValueError()
            dados=signing.Signer(salt='unicap.qr.v3').unsign_object(codigo[len('UNICAP:V3:'):])
            s=SessaoEmbarque.objects.select_related('viagem','fiscal__user').get(token=dados['token'],viagem_id=dados['viagem'],fiscal_id=dados['fiscal'],sentido=dados['sentido'],data_servico=dados['dia'])
        except (signing.BadSignature,ValueError,KeyError,TypeError,SessaoEmbarque.DoesNotExist):
            raise op.Regra('QR inválido para esta viagem.')
        if d.get('viagem_id')!=s.viagem_id or d.get('sentido')!=s.sentido:
            raise op.Regra('QR inválido para esta viagem.')
        if not s.fiscal.user.is_active: raise op.Regra('O fiscal deste QR não está ativo.')
        offline=d.get('offline') is True
        lido=parse_datetime(str(d.get('lido_em',''))) if d.get('lido_em') else timezone.now()
        if lido is None or timezone.is_naive(lido) or lido>timezone.now()+timedelta(seconds=30):
            raise op.Regra('Horário de leitura inválido.')
        if lido<s.gerado_em-timedelta(seconds=5) or lido>=s.expira_em or (not offline and timezone.now()>=s.expira_em):
            raise op.Regra('QR inválido para esta viagem.')
        if offline and timezone.now()>s.expira_em+timedelta(hours=24):
            raise op.Regra('O prazo para enviar esta leitura expirou.')
        # A reserva é validada sob o mesmo bloqueio transacional do embarque.
        c,novo=op.registrar_embarque(s.viagem_id,p,s.sentido,d.get('poltrona'),s.fiscal,lido_em=lido,offline=offline,ponto_id=d.get('ponto_id'))
        return Response({'checkin':op.dados_registro(c),'detail':'Check-in finalizado'},status=201 if novo else 200)


class EmbarquesApi(OperacaoApi):
    def get(self,request,viagem_id):
        p=op.perfil(request.user);v=op.viagem_visivel(p,viagem_id);op.exigir_fiscal(v,p)
        sentido=op.validar_sentido(request.query_params.get('sentido',v.sentido_atual))
        return Response({'viagem':op.dados_viagem(v,p,sentido),'checkins':[op.dados_registro(c) for c in v.checkins.filter(sentido=sentido).select_related('viagem__rota','viagem__onibus')]})


class BuscarAssociadosApi(OperacaoApi):
    def get(self,request,viagem_id):
        p=op.perfil(request.user);v=op.viagem_visivel(p,viagem_id);op.exigir_fiscal(v,p)
        q=request.query_params.get('q','').strip()
        sentido=op.validar_sentido(request.query_params.get('sentido',v.sentido_atual))
        if len(q)<3: return Response({'associados':[]})
        pessoas=Usuario.objects.filter(Q(user__first_name__icontains=q)|Q(rua__icontains=q),user__is_active=True,
            tipo__in=['associado','fiscal'],curso__instituicao__in=v.rota.instituicoes.all()).select_related('user','curso__instituicao')[:40]
        resultado=[]
        for a in pessoas:
            c=op.duplicado(a,v,sentido)
            resultado.append({'id':a.pk,'nome':str(a),'rua':a.rua,'curso':a.curso.nome,'instituicao':a.curso.instituicao.nome,
                'embarque':op.dados_registro(c) if c else None})
        return Response({'associados':resultado})


class ManualApi(OperacaoApi):
    proprio=False
    def post(self,request,viagem_id):
        p=op.perfil(request.user);v=op.viagem_visivel(p,viagem_id);op.exigir_fiscal(v,p)
        if not self.proprio and (type(request.data.get('associado_id')) is not int or request.data['associado_id']<1): raise op.Regra('Selecione um associado válido.')
        a=p if self.proprio else get_object_or_404(Usuario.objects.select_related('user','curso__instituicao'),pk=request.data.get('associado_id'))
        motivo=request.data.get('motivo','')
        if not isinstance(motivo,str) or len(motivo)>300: raise op.Regra('Informe um motivo de até 300 caracteres.')
        c,novo=op.registrar_embarque(v.pk,a,request.data.get('sentido',v.sentido_atual),request.data.get('poltrona'),p,
            origem='fiscal' if self.proprio else 'manual',motivo=motivo,ponto_id=request.data.get('ponto_id'))
        return Response({'checkin':op.dados_registro(c)},status=201 if novo else 200)


class ProprioApi(ManualApi):
    proprio=True


class CancelarEmbarqueApi(OperacaoApi):
    @transaction.atomic
    def delete(self,request,checkin_id):
        p=op.perfil(request.user)
        c=get_object_or_404(CheckIn.objects.select_related('viagem'),pk=checkin_id)
        v=op.bloquear(c.viagem_id);op.exigir_fiscal(v,p)
        if not v.embarque_aberto(c.sentido): raise op.Regra('Cancelamento disponível somente durante o embarque.')
        motivo=request.data.get('motivo','')
        if not isinstance(motivo,str) or not motivo.strip() or len(motivo)>300: raise op.Regra('Informe o motivo do cancelamento (até 300 caracteres).')
        if c.cancelado_em is None:
            c.cancelado_em=timezone.now();c.motivo_cancelamento=motivo.strip();c.save(update_fields=['cancelado_em','motivo_cancelamento'])
            registrar('embarque_cancelado',usuario=p.user,modelo='embarques.checkin',objeto_id=c.pk,detalhes={'motivo':motivo})
        return Response({'detail':'Embarque cancelado. Poltrona liberada.'})


class HistoricoApi(OperacaoApi):
    def get(self,request):
        p=op.perfil(request.user)
        if p.tipo not in ('associado','fiscal') or not p.curso_id: raise PermissionDenied('Histórico disponível para estudantes.')
        try:
            mes=datetime.strptime(request.query_params.get('mes',timezone.localdate().strftime('%Y-%m')),'%Y-%m').date()
        except ValueError: raise op.Regra('Mês inválido.')
        qs=CheckIn.objects.filter(associado=p,data_servico__year=mes.year,data_servico__month=mes.month).select_related('viagem__rota','viagem__onibus')
        validos=qs.filter(cancelado_em__isnull=True)
        dias=validos.values('data_servico').distinct().count()
        dias_viagem=Viagem.objects.filter(data_servico__year=mes.year,data_servico__month=mes.month,data_servico__lte=timezone.localdate(),rota__instituicoes=p.curso.instituicao).exclude(status='cancelada').values('data_servico').distinct().count()
        pagina=Paginator(qs,50).get_page(request.query_params.get('pagina',1))
        return Response({'checkins':[op.dados_registro(c) for c in pagina],'total':qs.count(),'proxima':pagina.next_page_number() if pagina.has_next() else None,
            'frequencia':{'dias':dias,'idas':validos.filter(sentido='ida').count(),'voltas':validos.filter(sentido='retorno').count(),'dias_com_viagem':dias_viagem},'mes':mes.strftime('%Y-%m')})


class PosicaoEntrada(serializers.Serializer):
    latitude=serializers.DecimalField(max_digits=9,decimal_places=6,min_value=-90,max_value=90)
    longitude=serializers.DecimalField(max_digits=9,decimal_places=6,min_value=-180,max_value=180)
    precisao_metros=serializers.DecimalField(max_digits=10,decimal_places=2,min_value=0)
    capturada_em=serializers.DateTimeField()
    velocidade=serializers.FloatField(min_value=0,required=False,allow_null=True)


class LocalizacoesApi(OperacaoApi):
    @transaction.atomic
    def post(self,request,viagem_id):
        p=op.perfil(request.user);v=op.bloquear(viagem_id)
        if p.tipo!='motorista' or v.motorista_id!=p.pk: raise PermissionDenied('Localização exclusiva do motorista da viagem.')
        entradas=request.data.get('posicoes')
        if not isinstance(entradas,list) or not 1<=len(entradas)<=200: raise op.Regra('Envie entre 1 e 200 posições por lote.')
        val=PosicaoEntrada(data=entradas,many=True);val.is_valid(raise_exception=True)
        aceitas=descartadas=repetidas=0
        motivos=[]
        for x in val.validated_data:
            motivo=None
            if v.etapa in ('agendada','cancelada'):
                motivo='O rastreamento está disponível após iniciar a rota.'
            elif x['precisao_metros']>Decimal('100'):
                motivo='GPS impreciso: aguarde uma posição com precisão de até 100 m.'
            elif x['capturada_em']<v.iniciada_em or (v.finalizada_em and x['capturada_em']>v.finalizada_em):
                motivo='A posição foi capturada fora do período da viagem.'
            elif x['capturada_em']>timezone.now()+timedelta(seconds=30):
                motivo='O horário da posição está no futuro. Verifique o relógio do dispositivo.'
            if motivo:
                descartadas+=1
                if motivo not in motivos: motivos.append(motivo)
                continue
            _,novo=LocalizacaoViagem.objects.get_or_create(viagem=v,capturada_em=x.pop('capturada_em'),defaults=x)
            aceitas+=int(novo)
            repetidas+=int(not novo)
        return Response({'aceitas':aceitas,'descartadas':descartadas,'repetidas':repetidas,
                         'motivos':motivos,'recebida_em':timezone.now().isoformat()})


class LegadoDesativadoApi(OperacaoApi):
    def post(self,request,**kwargs):
        return Response({'detail':'Atualize o aplicativo para usar as etapas da viagem e o QR do dia.'},status=410)
