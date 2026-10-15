from django.conf import settings
from django.db.models import Count, OuterRef, Subquery
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from gestao.auditoria import AuditJWTAuthentication
from relatorios.views import administrador_ativo
from usuarios.views import eh_administrador
from usuarios.models import Usuario
from .models import Rota, Viagem, LocalizacaoViagem

def dados_localizacao(loc):
    if loc is None: return None
    idade = max(0, int((timezone.now()-loc.capturada_em).total_seconds()))
    return {'latitude':float(loc.latitude),'longitude':float(loc.longitude),
        'capturada_em':loc.capturada_em.isoformat(),'idade_segundos':idade,'desatualizada':idade>60,
        'precisao_metros':float(loc.precisao_metros) if loc.precisao_metros is not None else None}

def dados_rota(r):
    return {'id':r.pk,'nome':r.nome,'origem':r.origem,'destino':r.destino,
        'horario_ida':r.horario_ida.strftime('%H:%M'),'horario_retorno':r.horario_retorno.strftime('%H:%M'),
        'onibus_codigo':r.onibus.codigo,'pontos':[{'id':p.pk,'nome':p.nome,'endereco':p.endereco,
            'sentido':p.sentido,'ordem':p.ordem,'latitude':float(p.latitude) if p.latitude is not None else None,
            'longitude':float(p.longitude) if p.longitude is not None else None} for p in r.pontos.all()]}

def dados_viagem_mapa(v,loc):
    total = v.total_checkins if hasattr(v,'total_checkins') else v.checkins.count()
    return {'id':v.pk,'rota_id':v.rota_id,'rota_nome':v.nome_rota_historico,
        'onibus_codigo':v.codigo_onibus_registrado or v.onibus.codigo,
        'placa':v.placa_onibus_registrada or v.onibus.placa,'sentido':v.sentido,'status':v.status,
        'iniciada_em':v.iniciada_em.isoformat(),'finalizada_em':v.finalizada_em.isoformat() if v.finalizada_em else None,
        'presentes':total,'capacidade':v.capacidade_embarque,'vagas':max(0,v.capacidade_embarque-total),
        'localizacao':dados_localizacao(loc)}

class BaseMapaApi(APIView):
    authentication_classes=[AuditJWTAuthentication,SessionAuthentication]
    permission_classes=[IsAuthenticated]
    def perfil(self,request):
        if not request.user.is_active: raise PermissionDenied('Conta inativa.')
        if eh_administrador(request.user): return None
        p=Usuario.objects.filter(user=request.user,tipo__in=['associado','fiscal','motorista']).first()
        if p is None: raise PermissionDenied('Perfil sem acesso ao mapa.')
        return p
    def viagens(self,request,p):
        qs=Viagem.objects.select_related('rota','onibus').annotate(total_checkins=Count('checkins'))
        if not eh_administrador(request.user): qs=qs.filter(status='em_andamento',onibus__status='ativo',rota__status='ativa')
        if p and p.tipo=='motorista': qs=qs.filter(motorista=p)
        return qs

class MapaApi(BaseMapaApi):
    def get(self,request):
        p=self.perfil(request)
        rotas=Rota.objects.filter(status='ativa',onibus__status='ativo').exclude(onibus__situacao='manutencao').select_related('onibus').prefetch_related('pontos')
        if p and p.tipo=='motorista': rotas=rotas.filter(onibus__motorista=p)
        ult=LocalizacaoViagem.objects.filter(viagem_id=OuterRef('pk')).order_by('-capturada_em','-pk')
        viagens=list(self.viagens(request,p).filter(status='em_andamento').annotate(ultima_id=Subquery(ult.values('pk')[:1])))
        locais=LocalizacaoViagem.objects.in_bulk(v.ultima_id for v in viagens if v.ultima_id)
        return Response({'atualizado_em':timezone.now().isoformat(),
            'mapa':{'tiles':settings.MAP_TILE_URL,'atribuicao':settings.MAP_ATTRIBUTION,'atribuicao_url':settings.MAP_ATTRIBUTION_URL},
            'rotas':[dados_rota(r) for r in rotas],
            'viagens':[dados_viagem_mapa(v,locais.get(v.ultima_id)) for v in viagens]})

class DetalheMapaApi(BaseMapaApi):
    def get(self,request,viagem_id):
        p=self.perfil(request);v=get_object_or_404(self.viagens(request,p),pk=viagem_id)
        # No máximo 300 leituras recentes (~50 minutos); o restante permanece no banco.
        locais=list(v.localizacoes.order_by('-capturada_em','-pk')[:300])
        rota=Rota.objects.select_related('onibus').prefetch_related('pontos').get(pk=v.rota_id)
        return Response({'viagem':dados_viagem_mapa(v,locais[0] if locais else None),'rota':dados_rota(rota),
            'trajeto':[{'latitude':float(l.latitude),'longitude':float(l.longitude)} for l in reversed(locais)],
            'limite_trajeto':300})

@administrador_ativo
def mapa(request):
    return render(request,'rotas/mapa.html')
