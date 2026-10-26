from datetime import datetime, timedelta, time
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from embarques.tests import Cenario
from embarques.models import ReservaAssento
from gestao.models import LogAuditoria
from .models import Viagem,LocalizacaoViagem,Rota
from . import operacao as op

class OperacaoTests(Cenario,TestCase):
    def test_etapas_nao_pulam_nem_retrocedem(self):
        with self.assertRaises(op.Regra):op.transicao(self.viagem.pk,self.motorista,'iniciar_volta')
        for acao,estado in [('iniciar_ida','transito_ida'),('finalizar_ida','no_destino'),('iniciar_volta','transito_volta'),('finalizar','encerrada')]:
            v=op.transicao(self.viagem.pk,self.motorista,acao);self.assertEqual(v.etapa,estado)
        self.viagem.refresh_from_db();self.assertEqual(self.viagem.status,'finalizada')
        self.assertEqual(op.transicao(self.viagem.pk,self.motorista,'finalizar').etapa,'encerrada')
        self.assertEqual(op.transicao(self.viagem.pk,self.motorista,'iniciar_rota').etapa,'encerrada')
        for campo in ('partida_ida_em','chegada_em','partida_volta_em','finalizada_em'):self.assertIsNotNone(getattr(self.viagem,campo))
    def test_somente_motorista_responsavel(self):
        a=self.cliente(self.fiscal);self.assertEqual(a.post(f'/api/viagens/{self.viagem.pk}/transicao/',{'acao':'iniciar_ida'},format='json').status_code,403)
    def test_transicao_offline_preserva_hora(self):
        instante=timezone.now()-timedelta(minutes=3)
        v=op.transicao(self.viagem.pk,self.motorista,'iniciar_ida',instante);self.assertEqual(v.partida_ida_em,instante)
        with self.assertRaises(op.Regra):op.transicao(v.pk,self.motorista,'finalizar_ida',instante-timedelta(minutes=1))
    def test_antes_de_60_minutos_nao_inicia(self):
        now=timezone.make_aware(datetime(2026,10,15,12));local=timezone.localtime(now)
        Viagem.objects.filter(pk=self.viagem.pk).update(status='agendada',etapa='agendada',data_servico=local.date())
        Rota.objects.filter(pk=self.rota.pk).update(horario_ida=(local+timedelta(hours=2)).time(),horario_retorno=time(23,59))
        with patch('rotas.operacao.timezone.now',return_value=now):
            with self.assertRaises(op.Regra):op.transicao(self.viagem.pk,self.motorista,'iniciar_rota')
    def test_geracao_nao_duplica_e_respeita_dias(self):
        self.assertEqual(op.gerar_viagens(),0)
        outro_dia=op.data_operacional()+timedelta(days=1)
        self.rota.dias_operacao=[outro_dia.weekday()];self.rota.save()
        self.assertEqual(op.gerar_viagens(outro_dia),1);self.assertEqual(op.gerar_viagens(outro_dia),0)
        self.assertEqual(op.gerar_viagens(outro_dia+timedelta(days=1)),0)
    def test_encerramento_automatico_preserva_historico(self):
        self.confirmar();Viagem.objects.filter(pk=self.viagem.pk).update(data_servico=op.data_operacional()-timedelta(days=1))
        self.assertEqual(op.encerrar_antigas(),1);self.viagem.refresh_from_db()
        self.assertTrue(self.viagem.encerrada_pelo_sistema);self.assertEqual(self.viagem.checkins.count(),1)
    def test_gps_precisao_lote_e_reenvio(self):
        c=self.cliente(self.motorista);url=f'/api/viagens/{self.viagem.pk}/localizacoes/'
        pos={'latitude':'-22.123456','longitude':'-54.123456','capturada_em':timezone.now().isoformat(),'precisao_metros':'5.00'}
        r=c.post(url,{'posicoes':[pos,{**pos,'precisao_metros':'101.00'}]},format='json')
        self.assertEqual(r.status_code,200,r.data);self.assertEqual((r.data['aceitas'],r.data['descartadas']),(1,1))
        self.assertEqual(c.post(url,{'posicoes':[pos]},format='json').data['aceitas'],0)
        self.assertEqual(LocalizacaoViagem.objects.count(),1)
        self.assertEqual(self.cliente(self.fiscal).post(url,{'posicoes':[pos]},format='json').status_code,403)
    def test_gps_capturado_durante_viagem_chega_depois(self):
        pos={'latitude':'-22.123456','longitude':'-54.123456','capturada_em':timezone.now().isoformat(),'precisao_metros':'5'}
        for a in ['iniciar_ida','finalizar_ida','iniciar_volta','finalizar']:op.transicao(self.viagem.pk,self.motorista,a)
        c=self.cliente(self.motorista);url=f'/api/viagens/{self.viagem.pk}/localizacoes/'
        self.assertEqual(c.post(url,{'posicoes':[pos]},format='json').data['aceitas'],1)
        self.assertEqual(c.post(url,{'posicoes':[{**pos,'capturada_em':timezone.now().isoformat()}]},format='json').data['descartadas'],1)

    def test_mapa_preserva_trajeto_sem_inventar_previsoes_dos_pontos(self):
        LocalizacaoViagem.objects.create(viagem=self.viagem,latitude=-22.1,longitude=-54.1,
            capturada_em=timezone.now(),velocidade=10,precisao_metros=5)
        d=op.dados_viagem(self.viagem,self.motorista)
        self.assertEqual(len(d['trajeto_percorrido']),1)
        self.assertIsNone(d['proximo_ponto']);self.assertIsNone(d['previsao_chegada']);self.assertIsNone(d['previsao_metodo'])
        self.assertTrue(all(p['passou_em'] is None for p in d['pontos']))
        self.assertNotIn('latitude',d['pontos'][0])
    def test_conflito_de_horario_e_desativacao(self):
        r=Rota(nome='Conflito',destino='B',onibus=self.onibus,horario_ida=time(18),horario_retorno=time(22))
        with self.assertRaises(ValidationError):r.full_clean()
        self.rota.status='inativa'
        with self.assertRaises(ValidationError):self.rota.full_clean()
        self.onibus.status='inativo'
        with self.assertRaises(ValidationError):self.onibus.full_clean()
    def test_fechamento_mensal_removido(self):
        from django.apps import apps
        with self.assertRaises(LookupError): apps.get_model('gestao','FechamentoMensal')
    def test_log_tem_ip_antes_depois_e_nao_cria_consulta(self):
        admin=self.perfil('Gestor','administrador');self.client.force_login(admin.user)
        antes=LogAuditoria.objects.count();self.client.get('/');self.assertEqual(LogAuditoria.objects.count(),antes)
        self.client.post(f'/usuarios/{self.outro.pk}/status/',REMOTE_ADDR='127.0.0.1')
        log=LogAuditoria.objects.filter(acao='status_usuario').first();self.assertEqual(log.ip,'127.0.0.1')
        alteracao=LogAuditoria.objects.filter(modelo='auth.user',objeto_id=str(self.outro.user_id),acao='alterado').first()
        self.assertTrue(alteracao.detalhes['antes']['is_active']);self.assertFalse(alteracao.detalhes['depois']['is_active'])
