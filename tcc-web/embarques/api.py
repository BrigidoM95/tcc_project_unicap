import uuid
import secrets
import re
from datetime import timedelta
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rotas.api import BaseViagemApi, dados_viagem
from rotas.models import PontoEmbarque, Viagem
from usuarios.models import Usuario
from .models import CheckIn, SessaoEmbarque
from django.conf import settings
from django.core.paginator import Paginator
from usuarios.models import MatriculaAnual


def perfil(user, tipos):
    obj = Usuario.objects.filter(user=user, user__is_active=True, tipo__in=tipos).first()
    if obj is None:
        raise PermissionDenied('Seu perfil não pode realizar esta operação.')
    return obj


def bloquear_viagem(pk):
    # A primeira operação é uma escrita: também serializa transações no SQLite.
    # No PostgreSQL, UPDATE bloqueia a mesma linha usada na finalização da viagem.
    Viagem.objects.filter(pk=pk).update(status=F('status'))
    return get_object_or_404(Viagem.objects.select_for_update().select_related('rota', 'onibus'), pk=pk)


def disponivel(v):
    return v.em_andamento and v.rota.ativa and v.onibus.ativo


def resumo(v):
    dados = dados_viagem(v)
    dados.update(capacidade=v.capacidade_embarque, presentes=v.checkins.count())
    dados['vagas_disponiveis'] = max(0, dados['capacidade'] - dados['presentes'])
    return dados


def registro(c):
    return {'id': c.pk, 'viagem_id': c.viagem_id, 'associado_id': c.associado_id,
            'nome': c.nome_associado, 'rua': c.rua_associado, 'onibus_codigo': c.codigo_onibus,
            'placa': c.placa_onibus, 'registrado_em': c.registrado_em.isoformat(),
            'rota_nome': c.viagem.nome_rota_historico, 'sentido': c.viagem.sentido,
            'ponto_id': c.ponto_id, 'ponto_nome': c.nome_ponto or None}


class ViagensEmbarqueApi(BaseViagemApi):
    def get(self, request):
        perfil(request.user, [Usuario.Tipo.FISCAL])
        viagens = Viagem.objects.filter(status=Viagem.Status.EM_ANDAMENTO,
                    rota__status='ativa', onibus__status='ativo').select_related('rota', 'onibus', 'motorista__user')
        return Response({'viagens': [resumo(v) for v in viagens]})


class PontoQrEntrada(serializers.Serializer):
    ponto_id = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)


class GerarQrApi(BaseViagemApi):
    def get(self, request, viagem_id):
        perfil(request.user, [Usuario.Tipo.FISCAL])
        viagem = get_object_or_404(Viagem.objects.select_related('rota'), pk=viagem_id)
        pontos = PontoEmbarque.objects.filter(rota_id=viagem.rota_id, sentido=viagem.sentido)
        return Response({'pontos': [{'id': p.pk, 'nome': p.nome, 'ordem': p.ordem}
                                    for p in pontos]})

    def post(self, request, viagem_id):
        fiscal = perfil(request.user, [Usuario.Tipo.FISCAL])
        entrada = PontoQrEntrada(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                v = bloquear_viagem(viagem_id)
                if not disponivel(v):
                    return Response({'detail': 'A viagem, rota e ônibus devem estar ativos.'}, status=409)
                ponto = None
                ponto_id = entrada.validated_data['ponto_id']
                if ponto_id is not None:
                    ponto = PontoEmbarque.objects.filter(
                        pk=ponto_id, rota_id=v.rota_id, sentido=v.sentido).first()
                    if ponto is None:
                        return Response({'detail': 'Selecione um ponto da rota e do sentido desta viagem.'}, status=400)
                # A restrição única também protege colisões entre viagens concorrentes.
                for tentativa in range(5):
                    curto = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
                    if SessaoEmbarque.objects.filter(codigo_curto=curto).exists():
                        continue
                    try:
                        with transaction.atomic():
                            sessao, _ = SessaoEmbarque.objects.update_or_create(viagem=v, defaults={
                                'fiscal': fiscal, 'token': uuid.uuid4(), 'codigo_curto': curto,
                                'ponto': ponto, 'nome_ponto': ponto.nome if ponto else '',
                                'expira_em': timezone.now() + timedelta(minutes=5)})
                        break
                    except IntegrityError:
                        if not SessaoEmbarque.objects.filter(codigo_curto=curto).exists():
                            raise
                else:
                    return Response({'detail': 'Não foi possível gerar o código. Tente novamente.'}, status=503)
                return Response({'codigo': f'UNIBUS:M4:{sessao.token}',
                                 'codigo_manual': f'UNIBUS-{sessao.codigo_curto}',
                                 'expira_em': sessao.expira_em.isoformat(), 'viagem': resumo(v),
                                 'ponto_id': sessao.ponto_id, 'ponto_nome': sessao.nome_ponto or None})
        except OperationalError:
            return Response({'detail': 'Sistema ocupado. Tente novamente.'}, status=503)


class EntradaCheckIn(serializers.Serializer):
    codigo = serializers.CharField(max_length=100, trim_whitespace=True)

    def validate_codigo(self, value):
        normalizado = value.strip().upper()
        if normalizado.startswith('UNIBUS:M4:'):
            try:
                return {'token': uuid.UUID(normalizado[len('UNIBUS:M4:'):])}
            except ValueError:
                pass
        # Aceita o código exibido com ou sem prefixo, hífen e espaços.
        curto = re.sub(r'[\s-]', '', normalizado)
        if curto.startswith('UNIBUS'):
            curto = curto[6:]
        if re.fullmatch(r'[A-HJ-NP-Z2-9]{6}', curto):
            return {'codigo_curto': curto}
        raise serializers.ValidationError('Código inválido. Confira o código apresentado pelo fiscal.')


class LimiteCheckIn(UserRateThrottle):
    scope = 'embarque_checkin'
    rate = '12/min'


class CheckInApi(BaseViagemApi):
    throttle_classes = [LimiteCheckIn]

    def throttled(self, request, wait):
        from rest_framework.exceptions import Throttled
        raise Throttled(wait=wait, detail='Muitas tentativas. Aguarde um minuto antes de tentar novamente.')

    def post(self, request):
        associado = perfil(request.user, [Usuario.Tipo.ASSOCIADO])
        if settings.EXIGIR_MATRICULA_ANUAL and not MatriculaAnual.objects.filter(
                associado=associado, ano=timezone.localdate().year, ativa=True).exists():
            return Response({'detail':'Matrícula do ano atual pendente. Solicite a renovação à administração.'},status=403)
        entrada = EntradaCheckIn(data=request.data)
        if not entrada.is_valid():
            return Response({'detail': 'Código inválido. Confira o código apresentado pelo fiscal.'}, status=400)
        identificador = entrada.validated_data['codigo']
        viagem_id = SessaoEmbarque.objects.filter(**identificador).values_list('viagem_id', flat=True).first()
        if viagem_id is None:
            return Response({'detail': 'Código inválido ou substituído. Solicite o código atual ao fiscal.'}, status=400)
        try:
            with transaction.atomic():
                v = bloquear_viagem(viagem_id)
                sessao = SessaoEmbarque.objects.select_related('fiscal__user').filter(viagem=v, **identificador).first()
                if sessao is None or sessao.expira_em <= timezone.now():
                    return Response({'detail': 'Código expirado ou substituído. Solicite um novo ao fiscal.'}, status=400)
                if not sessao.fiscal.user.is_active or sessao.fiscal.tipo != Usuario.Tipo.FISCAL:
                    raise PermissionDenied('O fiscal deste QR Code não está ativo.')
                associado = perfil(request.user, [Usuario.Tipo.ASSOCIADO])
                if not disponivel(v):
                    return Response({'detail': 'Embarque encerrado ou veículo indisponível.'}, status=409)
                if CheckIn.objects.filter(viagem=v, associado=associado).exists():
                    return Response({'detail': 'Você já realizou check-in nesta viagem.'}, status=409)
                vagas = set(v.checkins.values_list('vaga', flat=True))
                vaga = next((n for n in range(1, v.capacidade_embarque + 1) if n not in vagas), None)
                if vaga is None:
                    return Response({'detail': 'Ônibus lotado. Não há vagas disponíveis.'}, status=409)
                c = CheckIn.objects.create(viagem=v, associado=associado, fiscal=sessao.fiscal,
                    vaga=vaga, nome_associado=str(associado)[:150], rua_associado=associado.rua or '',
                    placa_onibus=v.onibus.placa, codigo_onibus=v.onibus.codigo or '',
                    ponto_id=sessao.ponto_id, nome_ponto=sessao.nome_ponto)
                return Response({'detail': 'Embarque confirmado!', 'checkin': registro(c), 'viagem': resumo(v)}, status=201)
        except IntegrityError:
            return Response({'detail': 'Embarque já registrado ou vaga ocupada. Atualize e confira seu histórico.'}, status=409)
        except OperationalError:
            return Response({'detail': 'Sistema ocupado. Confira seu histórico e tente novamente.'}, status=503)


class HistoricoApi(BaseViagemApi):
    def get(self, request):
        associado = perfil(request.user, [Usuario.Tipo.ASSOCIADO])
        registros = CheckIn.objects.filter(associado=associado).select_related('viagem__rota')
        pagina = Paginator(registros,50).get_page(request.query_params.get('pagina',1))
        return Response({'checkins': [registro(c) for c in pagina], 'total':pagina.paginator.count,
            'pagina':pagina.number, 'proxima':pagina.next_page_number() if pagina.has_next() else None})


class PresencasApi(BaseViagemApi):
    def get(self, request, viagem_id):
        fiscal = perfil(request.user, [Usuario.Tipo.FISCAL])
        v = get_object_or_404(Viagem.objects.select_related('rota', 'onibus', 'motorista__user'), pk=viagem_id)
        if not SessaoEmbarque.objects.filter(viagem=v, fiscal=fiscal).exists():
            raise PermissionDenied('A lista está disponível para o fiscal responsável pelo QR Code atual.')
        return Response({'viagem': resumo(v), 'checkins': [registro(c) for c in v.checkins.select_related('viagem__rota')]})
