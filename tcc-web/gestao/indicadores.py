from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone
from usuarios.models import Usuario
from onibus.models import Onibus
from rotas.models import Rota, PontoEmbarque
from embarques.models import CheckIn, ReservaAssento
from .models import LogAuditoria

def associados_por_instituicao():
    estudantes=Usuario.objects.filter(tipo__in=['associado','fiscal'],curso__isnull=False,user__is_active=True)
    return {'associados_instituicao':estudantes.values('curso__instituicao__nome').annotate(total=Count('pk')).order_by('-total'),
            'total_instituicoes':estudantes.count()}

def rotas_pendentes():
    return Rota.objects.filter(status='ativa').annotate(
        tem_pontos=Exists(PontoEmbarque.objects.filter(rota=OuterRef('pk'),ativo=True)),
        tem_instituicoes=Exists(Rota.instituicoes.through.objects.filter(rota_id=OuterRef('pk'))),
    ).filter(Q(tem_pontos=False)|Q(tem_instituicoes=False)).order_by('nome','pk')

def indicadores(acoes=1):
    from rotas.operacao import data_operacional
    hoje=data_operacional()
    reservados=ReservaAssento.objects.filter(viagem__data_servico=hoje,ativa=True,expira_em__gt=timezone.now()).values('associado_id')
    confirmados=CheckIn.objects.filter(data_servico=hoje,cancelado_em__isnull=True).values('associado_id')
    estudantes=Usuario.objects.filter(tipo='associado',user__is_active=True)
    sem_curso=estudantes.filter(curso__isnull=True).select_related('user').order_by('user__first_name','pk')
    rotas=rotas_pendentes()
    inicio=10 if acoes==2 else 0
    return {'cards':{'Associados ativos':estudantes.count(),'Ônibus ativos':Onibus.objects.filter(status='ativo').count(),
        'Reservas do dia':Usuario.objects.filter(tipo='associado').filter(Q(pk__in=reservados)|Q(pk__in=confirmados)).count()},
        'associados_sem_curso':sem_curso[:5],'total_sem_curso':sem_curso.count(),
        'rotas_incompletas':rotas[:5],'total_rotas_incompletas':rotas.count(),'acoes_pagina':acoes,
        'ultimas_acoes':LogAuditoria.objects.select_related('usuario')[inicio:inicio+10]}
