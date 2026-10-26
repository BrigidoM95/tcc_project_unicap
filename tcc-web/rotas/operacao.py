"""Regras transacionais da especificação v2 / mockups v3.

O ciclo novo guarda ida e volta na mesma viagem. Registros anteriores continuam
identificados como ciclos legados; nenhuma hora histórica é inventada.
"""
from datetime import datetime, time, timedelta
from django.conf import settings

from django.core import signing
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied

from embarques.models import CheckIn, ReservaAssento, SessaoEmbarque
from gestao.auditoria import registrar
from onibus.models import Onibus
from usuarios.models import Usuario
from .models import LocalizacaoViagem, Rota, Viagem


class Regra(APIException):
    status_code = 409
    default_code = 'regra_negocio'


def perfil(user):
    p = Usuario.objects.select_related('user', 'curso__instituicao').filter(user=user, user__is_active=True).first()
    if not p or p.tipo not in ('associado', 'fiscal', 'motorista'):
        raise PermissionDenied('Seu perfil não pode acessar o aplicativo.')
    return p


def consulta_viagens(p):
    qs = Viagem.objects.select_related('rota', 'onibus', 'motorista__user', 'fiscal__user').prefetch_related('rota__pontos', 'rota__instituicoes')
    if p.tipo == 'motorista':
        return qs.filter(Q(etapa='agendada', rota__onibus__motorista=p) | (~Q(etapa='agendada') & Q(motorista=p)))
    if p.tipo == 'fiscal':
        return qs.filter(Q(etapa='agendada', rota__fiscal=p) | (~Q(etapa='agendada') & Q(fiscal=p)))
    if not p.curso_id:
        return qs.none()
    return qs.filter(rota__instituicoes=p.curso.instituicao).distinct()


def viagem_visivel(p, pk):
    v = get_object_or_404(consulta_viagens(p), pk=pk)
    if v.etapa == 'agendada':
        aplicar_vinculos_agendados(v)
    return v


def aplicar_vinculos_agendados(v):
    v.onibus = v.rota.onibus
    v.motorista = v.onibus.motorista
    v.fiscal = v.rota.fiscal
    v.capacidade_registrada = v.onibus.capacidade
    v.nome_rota_registrado = v.rota.nome
    v.codigo_onibus_registrado = v.onibus.codigo or ''
    v.placa_onibus_registrada = v.onibus.placa


def exigir_fiscal(v, p):
    if p.tipo != 'fiscal' or v.fiscal_id != p.pk:
        raise PermissionDenied('Ação exclusiva do fiscal responsável por esta viagem.')


def exigir_passageiro(p, v):
    if p.tipo not in ('associado', 'fiscal') or not p.curso_id or not p.user.is_active:
        raise PermissionDenied('É necessário um cadastro ativo de estudante com instituição e curso.')
    if p.tipo == 'fiscal':
        exigir_fiscal(v, p)
    if not v.rota.instituicoes.filter(pk=p.curso.instituicao_id).exists():
        raise PermissionDenied('Esta rota não atende à sua instituição.')


def bloquear(pk):
    # A escrita inicial também serializa concorrência no SQLite.
    Viagem.objects.filter(pk=pk).update(status=F('status'))
    v = get_object_or_404(Viagem.objects.select_for_update(of=('self',)).select_related('rota', 'onibus', 'fiscal__user', 'motorista__user'), pk=pk)
    # Uma viagem ainda não iniciada segue os vínculos atuais do painel.
    # Depois do início, preserva o responsável registrado na operação.
    if v.etapa == 'agendada':
        campos = ['onibus', 'motorista', 'fiscal', 'capacidade_registrada',
                  'nome_rota_registrado', 'codigo_onibus_registrado', 'placa_onibus_registrada']
        antes = [getattr(v, v._meta.get_field(c).attname) for c in campos]
        aplicar_vinculos_agendados(v)
        if antes != [getattr(v, v._meta.get_field(c).attname) for c in campos]:
            v.save(update_fields=campos)
    return v


def data_operacional(agora=None):
    local = timezone.localtime(agora or timezone.now())
    return (local - timedelta(hours=3)).date()


def gerar_viagens(data=None):
    data = data or data_operacional()
    criadas = 0
    for r in Rota.objects.filter(status='ativa', onibus__status='ativo', onibus__motorista__user__is_active=True).select_related('onibus'):
        if data.weekday() not in (r.dias_operacao or range(7)):
            continue
        # Rotas antigas incompletas ficam disponíveis para correção no painel.
        if not r.pontos.filter(ativo=True).exists() or not r.instituicoes.exists():
            continue
        v, nova = Viagem.objects.get_or_create(rota=r, data_servico=data, ciclo_completo=True,
            defaults={'onibus': r.onibus, 'motorista': r.onibus.motorista, 'fiscal': r.fiscal,
                      'sentido': 'ida', 'status': 'agendada', 'etapa': 'agendada'})
        criadas += nova
        if not nova:
            Viagem.objects.filter(pk=v.pk, etapa='agendada', status='agendada').update(
                onibus_id=r.onibus_id, motorista_id=r.onibus.motorista_id, fiscal_id=r.fiscal_id,
                capacidade_registrada=r.onibus.capacidade, nome_rota_registrado=r.nome,
                codigo_onibus_registrado=r.onibus.codigo or '', placa_onibus_registrada=r.onibus.placa)
    return criadas


def encerrar_antigas():
    ids = Viagem.objects.filter(status__in=['agendada','em_andamento'], data_servico__lt=data_operacional()).values_list('pk', flat=True)
    total = 0
    for pk in list(ids):
        with transaction.atomic():
            v = bloquear(pk)
            if v.status not in ('agendada','em_andamento'):
                continue
            v.status = 'finalizada'; v.etapa = 'encerrada'
            v.finalizada_em = max(v.iniciada_em, timezone.now())
            v.encerrada_pelo_sistema = True
            v.save()
            v.reservas.filter(ativa=True).update(ativa=False)
            registrar('encerramento_automatico', modelo='rotas.viagem', objeto_id=v.pk, detalhes={'revisar':True})
            total += 1
    return total


TRANSICOES = {
    'iniciar_rota': ('agendada', 'embarque_ida', 'iniciada_em'),
    'iniciar_ida': ('embarque_ida', 'transito_ida', 'partida_ida_em'),
    'finalizar_ida': ('transito_ida', 'no_destino', 'chegada_em'),
    'iniciar_volta': ('no_destino', 'transito_volta', 'partida_volta_em'),
    'finalizar': ('transito_volta', 'encerrada', 'finalizada_em'),
}


@transaction.atomic
def transicao(pk, p, acao, ocorrida_em=None):
    if acao == 'iniciar_rota':
        # Mesmo bloqueio da inativação: ninguém inicia enquanto o ônibus e
        # suas rotas estão sendo desativados pelo painel.
        agendada = get_object_or_404(Viagem.objects.select_related('rota'), pk=pk)
        get_object_or_404(Onibus.objects.select_for_update(), pk=agendada.rota.onibus_id)
    v = bloquear(pk)
    if p.tipo != 'motorista' or v.motorista_id != p.pk:
        raise PermissionDenied('Ação exclusiva do motorista desta viagem.')
    if acao not in TRANSICOES:
        raise Regra('Etapa inválida.')
    anterior, proxima, campo = TRANSICOES[acao]
    etapas_seguinte = [x[1] for x in TRANSICOES.values()][list(TRANSICOES).index(acao):]
    if v.ciclo_completo and getattr(v, campo) is not None and v.etapa in etapas_seguinte:
        return v  # Reenvio após perda da resposta não repete a ação.
    if not v.ciclo_completo or v.etapa != anterior:
        raise Regra('Etapa fora de ordem. Atualize a viagem.')
    instante = ocorrida_em or timezone.now()
    if timezone.is_naive(instante) or instante > timezone.now()+timedelta(seconds=30):
        raise Regra('Horário da etapa inválido.')
    anteriores = [getattr(v, x[2]) for x in list(TRANSICOES.values())[:list(TRANSICOES).index(acao)]]
    if any(x and instante < x for x in anteriores):
        raise Regra('O horário da etapa deve ser posterior à etapa anterior.')
    if acao == 'iniciar_rota':
        liberada = timezone.make_aware(datetime.combine(v.data_servico, v.rota.horario_ida)) - timedelta(minutes=60)
        if instante < liberada:
            raise Regra(f'Disponível a partir de {liberada:%H:%M}.')
        if v.data_servico != data_operacional() or not v.rota.ativa or not v.onibus.ativo:
            raise Regra('Viagem indisponível para iniciar.')
        if Viagem.objects.filter(Q(motorista=p)|Q(onibus=v.onibus), status='em_andamento').exclude(pk=v.pk).exists():
            raise Regra('O ônibus ou motorista já possui uma viagem em andamento.')
        v.status = 'em_andamento'
        v.capacidade_registrada = v.onibus.capacidade
    v.etapa = proxima
    setattr(v, campo, instante)
    if acao == 'finalizar':
        v.status = 'finalizada'
    v.save()
    if acao == 'iniciar_ida':
        v.reservas.filter(ativa=True, sentido='ida').update(ativa=False)
        embarcados = CheckIn.objects.filter(data_servico=v.data_servico, sentido='ida', cancelado_em__isnull=True).values('associado_id')
        v.reservas.filter(ativa=True, sentido='retorno', trajeto='ida_volta').exclude(associado_id__in=embarcados).update(ativa=False)
    elif acao == 'iniciar_volta':
        v.reservas.filter(ativa=True, sentido='retorno').update(ativa=False)
    elif acao == 'finalizar':
        v.reservas.filter(ativa=True).update(ativa=False)
    gps=v.localizacoes.filter(capturada_em__lte=instante).order_by('-capturada_em').first()
    registrar(acao, usuario=p.user, modelo='rotas.viagem', objeto_id=v.pk, detalhes={'de':anterior,'para':proxima,'ocorrida_em':instante.isoformat(), 'latitude':str(gps.latitude) if gps else None,'longitude':str(gps.longitude) if gps else None})
    return v


def registros(v, sentido):
    return v.checkins.filter(sentido=sentido, cancelado_em__isnull=True)


def reservas(v, sentido):
    return v.reservas.filter(sentido=sentido, ativa=True, expira_em__gt=timezone.now())


def dados_registro(c):
    return {'id':c.pk, 'viagem_id':c.viagem_id, 'associado_id':c.associado_id, 'nome':c.nome_associado,
        'rua':c.rua_associado, 'onibus_codigo':c.codigo_onibus, 'onibus_nome':c.viagem.onibus.nome,
        'placa':c.placa_onibus, 'rota_nome':c.viagem.nome_rota_historico, 'sentido':c.sentido,
        'poltrona':None if c.legado else c.vaga, 'ponto_id':c.ponto_id, 'ponto_nome':c.nome_ponto or 'Ponto não informado',
        'registrado_em':(c.lido_em or c.registrado_em).isoformat(), 'recebido_em':c.registrado_em.isoformat(), 'data':c.data_servico, 'origem':c.origem,
        'cancelado':c.cancelado_em is not None, 'motivo_cancelamento':c.motivo_cancelamento,
        'sincronizado_offline':c.sincronizado_offline, 'comprovante':f'EMB-{c.pk:05d}'}


def dados_reserva(r):
    return {'id':r.pk, 'poltrona':r.assento, 'sentido':r.sentido, 'trajeto':r.trajeto,
        'ponto_id':r.ponto_id, 'ponto_nome':r.ponto.nome if r.ponto_id else None,
        'expira_em':r.expira_em.isoformat()}


def escolha_abre_em(v):
    prevista = timezone.make_aware(datetime.combine(v.data_servico, time.fromisoformat(settings.RESERVA_ABRE_AS)))
    return min(prevista, v.iniciada_em) if v.etapa != 'agendada' else prevista


def escolha_aberta(v, sentido, agora=None):
    agora = agora or timezone.now()
    partida = v.partida_ida_em if sentido == 'ida' else v.partida_volta_em
    return (v.status in ('agendada', 'em_andamento') and v.data_servico == data_operacional(agora)
            and v.rota.ativa and v.onibus.ativo and partida is None and agora >= escolha_abre_em(v))


def validar_escolha(v, sentido):
    if not v.rota.ativa or not v.onibus.ativo:
        raise Regra('Viagem ou veículo indisponível.')
    if (v.partida_ida_em if sentido == 'ida' else v.partida_volta_em):
        raise Regra('Este sentido já partiu.')
    if v.status not in ('agendada', 'em_andamento') or v.data_servico != data_operacional():
        raise Regra('A escolha está encerrada para esta viagem.')
    if timezone.now() < escolha_abre_em(v):
        raise Regra(f'A escolha de poltrona abre às {settings.RESERVA_ABRE_AS}.')


def sentidos_trajeto(trajeto):
    if trajeto not in ('ida', 'volta', 'ida_volta'):
        raise Regra('Selecione seu trajeto: só ida, só volta ou ida e volta.')
    return ['ida', 'retorno'] if trajeto == 'ida_volta' else ['retorno' if trajeto == 'volta' else 'ida']


def selecionar_ponto(v, sentido, ponto_id=None):
    pontos = list(v.rota.pontos.filter(sentido=sentido, ativo=True).order_by('ordem'))
    if ponto_id is not None:
        ponto = next((x for x in pontos if type(ponto_id) is int and x.pk == ponto_id), None)
        if ponto: return ponto
    elif len(pontos) == 1:
        return pontos[0]
    raise Regra('Selecione o ponto de embarque.')


def minha_escolha(v, p):
    escolhidas = {r.sentido:r for r in reservas_do_dia(v, p).order_by('pk') if r.ativa and r.expira_em > timezone.now()}
    for c in v.checkins.filter(associado=p,cancelado_em__isnull=True):
        r = v.reservas.filter(associado=p, sentido=c.sentido, assento=c.vaga).select_related('ponto').order_by('-pk').first()
        if r: escolhidas[c.sentido] = r
    if not escolhidas: return None
    ida, volta = escolhidas.get('ida'), escolhidas.get('retorno')
    r = volta or ida
    return {'trajeto':'ida_volta' if ida and volta else 'ida' if ida else 'volta', 'poltrona':r.assento,
        'ponto_ida_id':ida.ponto_id if ida else None, 'ponto_ida_nome':ida.ponto.nome if ida and ida.ponto_id else None,
        'ponto_volta_id':volta.ponto_id if volta else None, 'ponto_volta_nome':volta.ponto.nome if volta and volta.ponto_id else None}


def reservas_do_dia(v, p):
    return v.reservas.filter(associado=p).select_related('ponto')


def bloquear_passageiro(p):
    # Mesmo passageiro não pode reservar/embarcar simultaneamente em dois ônibus.
    Usuario.objects.filter(pk=p.pk).update(rua=F('rua'))
    Usuario.objects.select_for_update().get(pk=p.pk)


def dados_viagem(v, p=None, sentido=None):
    sentido = sentido or v.sentido_atual
    presentes = registros(v, sentido).count()
    reservadas = reservas(v, sentido).count() if escolha_aberta(v, sentido) else 0
    capacidade = v.capacidade_embarque
    pontos = list(v.rota.pontos.filter(ativo=True).order_by('sentido','ordem'))
    ultima = v.localizacoes.order_by('-capturada_em').first()
    localizacao = None
    if ultima:
        localizacao = {'latitude':float(ultima.latitude), 'longitude':float(ultima.longitude),
            'precisao_metros':float(ultima.precisao_metros) if ultima.precisao_metros is not None else None,
            'capturada_em':ultima.capturada_em.isoformat(), 'atrasada':(timezone.now()-ultima.capturada_em).total_seconds()>120}
    from .progresso import progresso
    andamento = progresso(v,pontos,sentido)
    foto = v.onibus.foto_url
    liberada = timezone.make_aware(datetime.combine(v.data_servico, v.rota.horario_ida))-timedelta(minutes=60)
    dados = {'id':v.pk, 'rota_id':v.rota_id, 'rota_nome':v.nome_rota_historico,
        'destino':v.rota.destino, 'onibus_id':v.onibus_id, 'onibus_nome':v.onibus.nome,
        'onibus_codigo':v.onibus.codigo, 'placa':v.onibus.placa, 'foto':foto, 'motorista_nome':str(v.motorista),
        'fiscal_id':v.fiscal_id, 'fiscal_nome':str(v.fiscal) if v.fiscal_id else None,
        'status':v.status, 'etapa':v.etapa, 'etapa_nome':v.get_etapa_display(), 'sentido':sentido,
        'data':v.data_servico.isoformat(), 'horario_ida':v.rota.horario_ida.strftime('%H:%M'),
        'horario_retorno':v.rota.horario_retorno.strftime('%H:%M'), 'liberada_em':liberada.isoformat(),
        'pode_iniciar':v.etapa=='agendada' and liberada<=timezone.now() and v.data_servico==data_operacional(),
        'escolha_aberta':escolha_aberta(v,sentido), 'escolha_abre_em':timezone.localtime(escolha_abre_em(v)).isoformat(),
        'pode_iniciar_volta':v.etapa=='no_destino', 'embarque_aberto':v.embarque_aberto(sentido), 'capacidade':capacidade, 'presentes':presentes,
        'reservados':reservadas, 'ocupados':presentes+reservadas, 'vagas_disponiveis':max(0,capacidade-presentes-reservadas),
        'vagas_por_sentido':{direcao:max(0, capacidade-registros(v,direcao).count()
            -(reservas(v,direcao).count() if escolha_aberta(v,direcao) else 0)) for direcao in ('ida','retorno')},
        'total_ida':registros(v,'ida').count(), 'total_retorno':registros(v,'retorno').count(),
        'localizacao':localizacao, 'proximo_ponto':andamento['proximo_ponto'],
        'previsao_chegada':andamento['previsao_chegada'], 'previsao_metodo':andamento['previsao_metodo'],
        'trajeto_percorrido':andamento['trajeto_percorrido'],
        'pontos':[{'id':x.pk,'nome':x.nome,'ordem':x.ordem,'sentido':x.sentido,
                   'passou_em':andamento['passagens'].get(x.pk)} for x in pontos],
        'encerrada_pelo_sistema':v.encerrada_pelo_sistema, 'atualizado_em':timezone.now().isoformat()}
    for campo in ['iniciada_em','partida_ida_em','chegada_em','partida_volta_em','finalizada_em']:
        valor = getattr(v,campo)
        dados[campo] = valor.isoformat() if valor and (campo!='iniciada_em' or v.etapa!='agendada') else None
    if p:
        c = v.checkins.filter(associado=p,sentido=sentido,cancelado_em__isnull=True).select_related('viagem__rota','viagem__onibus').first()
        r = reservas(v,sentido).filter(associado=p).first()
        dados['meu_embarque'] = dados_registro(c) if c else None
        dados['minha_reserva'] = dados_reserva(r) if r and escolha_aberta(v,sentido) else None
        dados['minha_escolha'] = minha_escolha(v,p)
        disponiveis, bloqueios = [], {}
        for trajeto in ('ida', 'volta', 'ida_volta'):
            try:
                for direcao in sentidos_trajeto(trajeto):
                    validar_escolha(v, direcao)
                    validar_direcao_disponivel(v, p, direcao)
            except Regra as exc:
                bloqueios[trajeto] = str(exc.detail)
            else:
                disponiveis.append(trajeto)
        dados['trajetos_disponiveis'] = disponiveis
        dados['bloqueios_trajeto'] = bloqueios
    return dados


def validar_sentido(sentido):
    if sentido not in ('ida','retorno'):
        raise Regra('Sentido inválido.')
    return sentido


def duplicado(p, v, sentido):
    return CheckIn.objects.filter(associado=p, data_servico=v.data_servico, sentido=sentido, cancelado_em__isnull=True).select_related('viagem__rota','viagem__onibus').first()


def validar_reserva_outro_onibus(v, p, sentido):
    outra = ReservaAssento.objects.filter(associado=p, ativa=True, expira_em__gt=timezone.now(),
        viagem__data_servico=v.data_servico, sentido=sentido).exclude(viagem=v).select_related('viagem__onibus').first()
    if outra:
        direcao = 'ida' if sentido == 'ida' else 'volta'
        raise Regra(f'Você já reservou a {direcao} no ônibus {outra.viagem.onibus.nome}. '
                    'Cancele essa escolha ou remova esse sentido antes de escolher outro ônibus.')


def validar_direcao_disponivel(v, p, sentido):
    if duplicado(p, v, sentido):
        direcao = 'ida' if sentido == 'ida' else 'volta'
        raise Regra(f'Você já realizou check-in de {direcao} hoje. A escolha desse sentido está bloqueada.')
    validar_reserva_outro_onibus(v, p, sentido)


def validar_assento(v, sentido, assento, p):
    if type(assento) is not int or not 1 <= assento <= v.capacidade_embarque:
        raise Regra('Selecione uma poltrona válida.')
    if registros(v,sentido).filter(vaga=assento).exists() or reservas(v,sentido).filter(assento=assento).exclude(associado=p).exists():
        raise Regra('Essa poltrona acabou de ser ocupada. Escolha outra.')


@transaction.atomic
def reservar(pk, p, trajeto, assento, ponto_ida_id=None, ponto_volta_id=None):
    bloquear_passageiro(p)
    dia = get_object_or_404(Viagem, pk=pk).data_servico
    ids = set(ReservaAssento.objects.filter(associado=p, ativa=True, viagem__data_servico=dia).values_list('viagem_id', flat=True)) | {pk}
    viagens = {i:bloquear(i) for i in sorted(ids)}
    v = viagens[pk]
    exigir_passageiro(p,v)
    sentidos = sentidos_trajeto(trajeto)
    pontos = {}
    for sentido in sentidos:
        validar_escolha(v,sentido)
        validar_direcao_disponivel(v, p, sentido)
        pontos[sentido] = selecionar_ponto(v,sentido,ponto_ida_id if sentido=='ida' else ponto_volta_id)
        try:
            validar_assento(v,sentido,assento,p)
        except Regra:
            if trajeto == 'ida_volta':
                raise Regra('Essa poltrona não está livre na ida e na volta. Escolha outra.')
            raise
    # Só libera a escolha anterior depois de validar todos os sentidos e pontos.
    ReservaAssento.objects.filter(viagem_id__in=ids,ativa=True,expira_em__lte=timezone.now()).update(ativa=False)
    for sentido in ('ida','retorno'):
        if not duplicado(p,v,sentido):
            anteriores = v.reservas.filter(associado=p,ativa=True,sentido=sentido)
            anteriores.update(ativa=False)
    fim = timezone.make_aware(datetime.combine(dia+timedelta(days=1),time(3)))
    resultado = [ReservaAssento.objects.create(viagem=v,associado=p,sentido=sentido,assento=assento,
        trajeto=trajeto,ponto=pontos[sentido],expira_em=fim) for sentido in sentidos]
    registrar('escolha_poltrona',usuario=p.user,modelo='rotas.viagem',objeto_id=v.pk,
        detalhes={'trajeto':trajeto,'poltrona':assento,'ponto_ida_id':pontos['ida'].pk if 'ida' in pontos else None,
                  'ponto_volta_id':pontos['retorno'].pk if 'retorno' in pontos else None})
    return resultado


@transaction.atomic
def cancelar_escolha(pk, p, reserva_id=None):
    bloquear_passageiro(p)
    v = bloquear(pk)
    qs = v.reservas.filter(associado=p,ativa=True)
    if reserva_id: qs = qs.filter(pk=reserva_id)
    canceladas = []
    for sentido in ('ida','retorno'):
        if not duplicado(p,v,sentido):
            canceladas.extend(qs.filter(sentido=sentido).values_list('pk',flat=True))
    v.reservas.filter(pk__in=canceladas).update(ativa=False)
    registrar('escolha_cancelada',usuario=p.user,modelo='rotas.viagem',objeto_id=v.pk,detalhes={'reservas':canceladas})
    return v


def codigo_qr(s):
    return 'UNICAP:V3:'+signing.Signer(salt='unicap.qr.v3').sign_object({'token':str(s.token),'viagem':s.viagem_id,'fiscal':s.fiscal_id,'sentido':s.sentido,'dia':str(s.data_servico)})


@transaction.atomic
def gerar_qr(pk, p, sentido, ponto_id=None):
    v = bloquear(pk)
    exigir_fiscal(v,p)
    validar_sentido(sentido)
    if not v.embarque_aberto(sentido) or not v.rota.ativa or not v.onibus.ativo:
        raise Regra('Embarque fechado.')
    ponto = None
    if ponto_id is not None:
        if type(ponto_id) is not int or ponto_id<1: raise Regra('Ponto inválido.')
        ponto = get_object_or_404(v.rota.pontos, pk=ponto_id, sentido=sentido, ativo=True)
    if ponto is None:
        ponto = v.rota.pontos.filter(sentido=sentido,ativo=True).order_by('ordem').first()
    s, _ = SessaoEmbarque.objects.get_or_create(viagem=v,fiscal=p,sentido=sentido,data_servico=v.data_servico,
        defaults={'expira_em':timezone.make_aware(datetime.combine(v.data_servico+timedelta(days=1),time(3))),
                  'ponto':ponto,'nome_ponto':ponto.nome if ponto else ''})
    if ponto_id and s.ponto_id != ponto_id:
        s.ponto = ponto; s.nome_ponto = ponto.nome; s.save(update_fields=['ponto','nome_ponto'])
    return s


def janela_embarque(v, sentido, lido_em):
    inicio = v.iniciada_em if sentido=='ida' else v.chegada_em
    fim = v.partida_ida_em if sentido=='ida' else v.partida_volta_em
    if v.finalizada_em and (fim is None or v.finalizada_em < fim): fim=v.finalizada_em
    return v.etapa not in ('agendada','cancelada') and inicio is not None and inicio <= lido_em and (fim is None or lido_em < fim)


@transaction.atomic
def registrar_embarque(pk, passageiro, sentido, assento, fiscal, *, origem='qr', motivo='', lido_em=None, offline=False, ponto_id=None):
    bloquear_passageiro(passageiro)
    v = bloquear(pk)
    exigir_passageiro(passageiro,v)
    validar_sentido(sentido)
    exigir_fiscal(v,fiscal)
    c = duplicado(passageiro,v,sentido)
    if c:
        if c.viagem_id == v.pk:
            return c, False
        raise Regra('Você já realizou check-in neste sentido hoje, em outro ônibus.')
    validar_reserva_outro_onibus(v, passageiro, sentido)
    if not v.rota.ativa or not v.onibus.ativo or v.status=='cancelada':
        raise Regra('Viagem ou veículo indisponível.')
    if offline:
        if not lido_em or not janela_embarque(v,sentido,lido_em):
            raise Regra('Check-in encerrado: o ônibus já iniciou a viagem.' if (v.partida_ida_em if sentido=='ida' else v.partida_volta_em) and lido_em and lido_em >= (v.partida_ida_em if sentido=='ida' else v.partida_volta_em) else 'O embarque estava fechado no horário da leitura.')
    elif not v.embarque_aberto(sentido):
        raise Regra('Check-in encerrado: o ônibus já iniciou a viagem.' if (v.partida_ida_em if sentido=='ida' else v.partida_volta_em) else 'Embarque fechado.')
    if origem in ('manual','fiscal') and not motivo.strip():
        raise Regra('Informe o motivo do check-in manual.')
    if origem == 'qr':
        r = reservas_do_dia(v,passageiro).filter(sentido=sentido).order_by('-pk').first()
        if sentido == 'retorno':
            ultima = r or reservas_do_dia(v,passageiro).order_by('-pk').first()
            if ultima and ultima.trajeto == 'ida':
                raise Regra('Seu trajeto de hoje é só ida. Altere o trajeto para voltar neste ônibus.')
            if ultima and ultima.trajeto == 'ida_volta' and not duplicado(passageiro,v,'ida'):
                raise Regra('Você escolheu ida e volta: o check-in da volta só é liberado depois do check-in da ida.')
        if not offline:
            if not r or not r.ativa or r.expira_em <= timezone.now():
                raise Regra('Escolha sua poltrona e seu ponto antes de ler o QR Code.')
            assento, ponto_id = r.assento, r.ponto_id
        elif r and r.assento == assento and r.criada_em <= lido_em < r.expira_em:
            ponto_id = r.ponto_id or ponto_id
    validar_assento(v,sentido,assento,passageiro)
    if registros(v,sentido).count() >= v.capacidade_embarque:
        raise Regra('Ônibus lotado. Não há vagas disponíveis.')
    ponto = selecionar_ponto(v,sentido,ponto_id)
    c = CheckIn.objects.create(viagem=v,associado=passageiro,fiscal=fiscal,sentido=sentido,
        data_servico=v.data_servico,vaga=assento,nome_associado=str(passageiro)[:150],rua_associado=passageiro.rua or '',
        placa_onibus=v.onibus.placa,codigo_onibus=v.onibus.codigo or '',ponto=ponto,nome_ponto=ponto.nome if ponto else '',
        origem=origem,motivo=motivo,lido_em=lido_em,sincronizado_offline=offline)
    v.reservas.filter(associado=passageiro,sentido=sentido,ativa=True).update(ativa=False)
    registrar('embarque_confirmado',usuario=fiscal.user if origem!='qr' else passageiro.user,modelo='embarques.checkin',objeto_id=c.pk,detalhes={'origem':origem,'sentido':sentido,'poltrona':assento,'motivo':motivo})
    return c, True

