from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from embarques.tests import Cenario
from rotas.models import LocalizacaoViagem
from .manutencao import manutencao_diaria
from .models import LogAuditoria


@override_settings(RETENCAO_GPS_DIAS=365, RETENCAO_AUDITORIA_DIAS=730)
class ManutencaoTests(Cenario, TestCase):
    def test_prazos_limites_e_credenciais_validas_preservados(self):
        agora = timezone.now()
        gps = []
        logs = []
        for segundos in (-1, 0, 1):
            gps.append(LocalizacaoViagem.objects.create(viagem=self.viagem,
                latitude=-22, longitude=-54,
                capturada_em=agora-timedelta(days=365)+timedelta(seconds=segundos)).pk)
            log = LogAuditoria.objects.create(acao='teste_retencao')
            LogAuditoria.objects.filter(pk=log.pk).update(
                criado_em=agora-timedelta(days=730)+timedelta(seconds=segundos))
            logs.append(log.pk)
        for nome, delta in [('expirado', -1), ('valido', 1)]:
            expira = agora+timedelta(days=delta)
            Session.objects.create(session_key=nome, session_data='', expire_date=expira)
            token = OutstandingToken.objects.create(user=self.associado.user,
                jti=nome, token='teste', created_at=agora-timedelta(days=2), expires_at=expira)
            BlacklistedToken.objects.create(token=token)
        resultado = manutencao_diaria(agora=agora)
        self.assertEqual(resultado, {'gps': 1, 'auditoria': 1})
        self.assertEqual(set(LocalizacaoViagem.objects.values_list('pk', flat=True)), set(gps[1:]))
        self.assertEqual(set(LogAuditoria.objects.filter(pk__in=logs).values_list('pk', flat=True)), set(logs[1:]))
        self.assertEqual(list(Session.objects.values_list('session_key', flat=True)), ['valido'])
        self.assertEqual(list(OutstandingToken.objects.values_list('jti', flat=True)), ['valido'])
        self.assertEqual(BlacklistedToken.objects.count(), 1)
        self.assertTrue(type(self.viagem).objects.filter(pk=self.viagem.pk).exists())

    def test_roda_uma_vez_por_dia_e_retoma_no_dia_seguinte(self):
        agora = timezone.now()
        with patch('gestao.manutencao.call_command') as comando:
            self.assertIsNotNone(manutencao_diaria(agora=agora))
            self.assertIsNone(manutencao_diaria(agora=agora+timedelta(seconds=1)))
            self.assertEqual(comando.call_count, 2)
            self.assertIsNotNone(manutencao_diaria(agora=agora+timedelta(days=1)))
            self.assertEqual(comando.call_count, 4)

    def test_erro_permite_tentar_novamente(self):
        with patch('gestao.manutencao.call_command', side_effect=RuntimeError('Falha transitória')):
            with self.assertRaises(RuntimeError):
                manutencao_diaria()
        self.assertIsNotNone(manutencao_diaria())

    def test_nao_executa_enquanto_outra_instancia_trabalha(self):
        cache.set('manutencao:executando', True, timeout=60)
        with patch('gestao.manutencao.excluir_em_lotes') as excluir:
            self.assertIsNone(manutencao_diaria())
            excluir.assert_not_called()

    def test_comando_somente_manutencao_nao_muda_operacao(self):
        with patch('gestao.management.commands.processar_operacao.gerar_viagens') as gerar, \
             patch('gestao.management.commands.processar_operacao.encerrar_antigas') as encerrar:
            call_command('processar_operacao', somente_manutencao=True, stdout=StringIO())
            gerar.assert_not_called()
            encerrar.assert_not_called()
