from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from gestao.models import LogAuditoria
from rotas.models import Viagem, Rota, PontoEmbarque
from rotas import operacao as op
from .models import ReservaAssento, CheckIn
from .tests import Cenario


class EscolhasV4Tests(Cenario, TestCase):
    def test_migracao_estende_vigente_sem_recuperar_reserva_vencida(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        from django.db import connection
        agora=timezone.now()
        vencida=ReservaAssento.objects.create(viagem=self.viagem,associado=self.associado,
            sentido='ida',assento=1,ativa=True,expira_em=agora-timedelta(minutes=1))
        vigente=ReservaAssento.objects.create(viagem=self.viagem,associado=self.outro,
            sentido='retorno',assento=2,ativa=True,expira_em=agora+timedelta(minutes=4))
        migracao=import_module('embarques.migrations.0006_reservaassento_ponto_reservaassento_trajeto')
        migracao.adaptar_reservas(apps,SimpleNamespace(connection=connection))
        vencida.refresh_from_db();vigente.refresh_from_db()
        self.assertEqual(vencida.expira_em,agora-timedelta(minutes=1))
        self.assertEqual(timezone.localtime(vigente.expira_em).time(),time(3))
        self.assertEqual(vigente.trajeto,'volta');self.assertEqual(vigente.ponto_id,self.volta.pk)

    def cliente(self,p):
        c=APIClient();c.force_authenticate(user=p.user);return c

    def escolha(self,trajeto='ida_volta',poltrona=1,p=None,**extras):
        return self.cliente(p or self.associado).post(f'/api/viagens/{self.viagem.pk}/reservas/',
            {'trajeto':trajeto,'poltrona':poltrona,**extras},format='json')

    def horario(self,h,m=0):
        return timezone.make_aware(datetime.combine(op.data_operacional(),time(h,m)))

    def agendar(self):
        Viagem.objects.filter(pk=self.viagem.pk).update(status='agendada',etapa='agendada',fiscal=None)

    def chegada(self):
        op.transicao(self.viagem.pk,self.motorista,'iniciar_ida')
        op.transicao(self.viagem.pk,self.motorista,'finalizar_ida')

    def test_0759_recusa_0800_abre_sem_fiscal_ou_embarque(self):
        self.agendar()
        with patch('rotas.operacao.timezone.now',return_value=self.horario(7,59)):
            r=self.escolha();self.assertEqual(r.status_code,409)
            self.assertEqual(r.data['mensagem'],'A escolha de poltrona abre às 08:00.')
        with patch('rotas.operacao.timezone.now',return_value=self.horario(8)):
            r=self.escolha();self.assertEqual(r.status_code,201,r.data)
            self.assertTrue(r.data['viagem']['escolha_aberta']);self.assertFalse(r.data['viagem']['embarque_aberto'])
            self.assertEqual(len(r.data['reservas']),2)

    def test_motorista_abre_0540_antes_das_08(self):
        self.agendar();Rota.objects.filter(pk=self.rota.pk).update(horario_ida=time(6,30))
        with patch('rotas.operacao.timezone.now',return_value=self.horario(5,40)):
            op.transicao(self.viagem.pk,self.motorista,'iniciar_rota')
            r=self.escolha();self.assertEqual(r.status_code,201,r.data)
            self.assertEqual(r.data['viagem']['escolha_abre_em'],self.horario(5,40).isoformat())

    def test_escolha_dura_mais_de_dez_minutos(self):
        agora=timezone.now();r=self.escolha();self.assertEqual(r.status_code,201,r.data)
        with patch('rotas.operacao.timezone.now',return_value=agora+timedelta(minutes=10)):
            self.assertEqual(op.reservas(self.viagem,'ida').count(),1)
            self.assertEqual(op.reservas(self.viagem,'retorno').count(),1)
        for x in ReservaAssento.objects.all():
            self.assertEqual(timezone.localtime(x.expira_em).time(),time(3))

    def test_ida_volta_mesma_poltrona_pontos_e_auditoria(self):
        r=self.escolha();self.assertEqual(r.status_code,201,r.data)
        self.assertEqual({x['sentido'] for x in r.data['reservas']},{'ida','retorno'})
        self.assertEqual({x['poltrona'] for x in r.data['reservas']},{1})
        e=r.data['minha_escolha'];self.assertEqual(e['ponto_ida_id'],self.ponto.pk);self.assertEqual(e['ponto_volta_id'],self.volta.pk)
        log=LogAuditoria.objects.get(acao='escolha_poltrona')
        self.assertEqual(log.detalhes['trajeto'],'ida_volta');self.assertEqual(log.detalhes['ponto_volta_id'],self.volta.pk)

    def test_colisao_so_na_volta_rejeita_roundtrip_sem_perder_anterior(self):
        self.escolha('ida',1)
        self.escolha('volta',2,self.outro)
        r=self.escolha('ida_volta',2);self.assertEqual(r.status_code,409)
        self.assertEqual(r.data['mensagem'],'Essa poltrona não está livre na ida e na volta. Escolha outra.')
        self.assertEqual(ReservaAssento.objects.get(associado=self.associado,ativa=True).assento,1)
        mapa=self.cliente(self.associado).get(f'/api/viagens/{self.viagem.pk}/assentos/?sentido=ida&trajeto=ida_volta').data
        self.assertEqual([a['estado'] for a in mapa['assentos']],['reservada','ocupada'])

    def test_ponto_inativo_ou_de_outro_sentido_recusado(self):
        self.assertEqual(self.escolha(ponto_ida_id=self.volta.pk).status_code,409)
        self.ponto.ativo=False;self.ponto.save()
        self.assertEqual(self.escolha(ponto_ida_id=self.ponto.pk).status_code,409)

    def test_escolha_antes_da_partida_nao_apaga_ao_abrir_rota(self):
        self.agendar()
        with patch('rotas.operacao.timezone.now',return_value=self.horario(9)):
            self.assertEqual(self.escolha().status_code,201)
            op.transicao(self.viagem.pk,self.motorista,'iniciar_rota')
            self.assertEqual(ReservaAssento.objects.filter(ativa=True).count(),2)

    def test_checkin_usa_poltrona_e_ponto_da_reserva(self):
        self.escolha();r=self.checkin(self.gerar().data['codigo'],poltrona=2,ponto_id=self.volta.pk)
        self.assertEqual(r.status_code,201,r.data);c=CheckIn.objects.get()
        self.assertEqual((c.vaga,c.ponto_id),(1,self.ponto.pk))

    def test_partida_fecha_online_e_offline_posterior(self):
        self.escolha();q=self.gerar().data['codigo'];op.transicao(self.viagem.pk,self.motorista,'iniciar_ida')
        for extras in ({},{'offline':True,'lido_em':timezone.now().isoformat()}):
            r=self.checkin(q,**extras);self.assertEqual(r.status_code,409)
            self.assertEqual(r.data['mensagem'],'Check-in encerrado: o ônibus já iniciou a viagem.')
        self.assertEqual(self.escolha('ida').data['mensagem'],'Este sentido já partiu.')

    def test_roundtrip_volta_exige_ida(self):
        self.escolha();self.chegada();q=self.gerar('retorno').data['codigo']
        r=self.checkin(q,sentido='retorno');self.assertEqual(r.status_code,409)
        self.assertIn('só é liberado depois do check-in da ida',r.data['mensagem'])

    def test_roundtrip_volta_com_ida_valida(self):
        self.escolha();self.assertEqual(self.checkin(self.gerar().data['codigo']).status_code,201)
        self.chegada();self.assertEqual(ReservaAssento.objects.filter(ativa=True,sentido='retorno').count(),1)
        self.assertEqual(self.checkin(self.gerar('retorno').data['codigo'],sentido='retorno').status_code,201)

    def test_so_volta_independe_de_ida(self):
        self.escolha('volta');self.chegada()
        r=self.checkin(self.gerar('retorno').data['codigo'],sentido='retorno')
        self.assertEqual(r.status_code,201,r.data)

    def test_so_ida_avisa_e_pode_incluir_volta_depois(self):
        self.escolha('ida');self.checkin(self.gerar().data['codigo']);self.chegada()
        q=self.gerar('retorno').data['codigo'];r=self.checkin(q,sentido='retorno')
        self.assertEqual(r.data['mensagem'],'Seu trajeto de hoje é só ida. Altere o trajeto para voltar neste ônibus.')
        self.assertEqual(self.escolha('volta',2).status_code,201)
        self.assertEqual(self.checkin(q,sentido='retorno').status_code,201)
        self.assertEqual(CheckIn.objects.get(sentido='ida').vaga,1)
        self.assertEqual(CheckIn.objects.get(sentido='retorno').vaga,2)

    def test_partida_libera_faltante_e_mantem_confirmado_e_so_volta(self):
        self.onibus.capacidade=3;self.onibus.save();self.viagem.capacidade_registrada=3;self.viagem.save()
        terceiro=self.perfil('TerceiroV4','associado')
        self.escolha();self.escolha('ida_volta',2,self.outro);self.escolha('volta',3,terceiro)
        self.checkin(self.gerar().data['codigo']);self.chegada()
        self.assertEqual(set(ReservaAssento.objects.filter(ativa=True).values_list('associado_id',flat=True)),{self.associado.pk,terceiro.pk})
        op.transicao(self.viagem.pk,self.motorista,'iniciar_volta')
        self.assertFalse(ReservaAssento.objects.filter(ativa=True).exists())

    def test_inicio_volta_nao_depende_do_horario_previsto(self):
        Rota.objects.filter(pk=self.rota.pk).update(horario_retorno=time(22,30))
        Viagem.objects.filter(pk=self.viagem.pk).update(etapa='no_destino',iniciada_em=self.horario(17),partida_ida_em=self.horario(18),chegada_em=self.horario(19))
        self.viagem.refresh_from_db();self.assertTrue(op.dados_viagem(self.viagem)['pode_iniciar_volta'])
        with patch('rotas.operacao.timezone.now',return_value=self.horario(19,10)):
            self.assertEqual(op.transicao(self.viagem.pk,self.motorista,'iniciar_volta').etapa,'transito_volta')

    def test_manual_e_fiscal_exigem_motivo_na_volta(self):
        self.chegada();c=self.cliente(self.fiscal)
        for tipo,pessoa,poltrona in [('manual',self.associado,1),('fiscal',self.fiscal,2)]:
            url=f'/api/viagens/{self.viagem.pk}/embarques/{tipo}/';d={'sentido':'retorno','poltrona':poltrona,'associado_id':pessoa.pk}
            self.assertEqual(c.post(url,d,format='json').status_code,409)
            self.assertEqual(c.post(url,{**d,'motivo':'Veio de outra forma'},format='json').status_code,201)
        self.assertEqual(LogAuditoria.objects.filter(acao='embarque_confirmado',detalhes__motivo='Veio de outra forma').count(),2)

    def test_cancelar_escolha_preserva_checkin_e_libera_so_volta(self):
        self.escolha();self.checkin(self.gerar().data['codigo'])
        r=self.cliente(self.associado).delete(f'/api/viagens/{self.viagem.pk}/minha-escolha/')
        self.assertEqual(r.status_code,200,r.data)
        self.assertFalse(ReservaAssento.objects.filter(ativa=True).exists());self.assertEqual(CheckIn.objects.count(),1)
        self.assertTrue(LogAuditoria.objects.filter(acao='escolha_cancelada').exists())

    def test_mapa_manual_permite_reserva_do_passageiro_somente_ao_fiscal(self):
        self.escolha('ida')
        url=f'/api/viagens/{self.viagem.pk}/assentos/?sentido=ida&associado_id={self.associado.pk}'
        self.assertEqual(self.cliente(self.fiscal).get(url).data['assentos'][0]['estado'],'reservada')
        self.assertEqual(self.cliente(self.outro).get(url).status_code,403)

    def test_trocar_trajeto_libera_sentido_removido(self):
        self.escolha();r=self.escolha('ida',2)
        self.assertEqual(r.status_code,201,r.data)
        self.assertEqual(list(ReservaAssento.objects.filter(ativa=True).values_list('sentido','assento')),[('ida',2)])

    def test_trocar_onibus_exige_liberar_mesmo_sentido_no_mesmo_dia(self):
        self.escolha('ida')
        rota=Rota.objects.create(nome='Outra rota',destino='Campus',onibus=self.onibus,horario_ida=time(0),horario_retorno=time(23,59))
        rota.instituicoes.add(self.instituicao);PontoEmbarque.objects.create(rota=rota,nome='Outro ponto',endereco='Centro',ordem=1,sentido='ida')
        outra=Viagem.objects.create(rota=rota,onibus=self.onibus,motorista=self.motorista,sentido='ida',status='agendada',etapa='agendada',data_servico=op.data_operacional())
        with patch('rotas.operacao.timezone.now',return_value=self.horario(12)):
            r=self.cliente(self.associado).post(f'/api/viagens/{outra.pk}/reservas/',{'trajeto':'ida','poltrona':2},format='json')
        self.assertEqual(r.status_code,409,r.data)
        self.assertIn('Cancele essa escolha',r.data['mensagem'])
        self.assertEqual(list(ReservaAssento.objects.filter(associado=self.associado,ativa=True).values_list('viagem_id',flat=True)),[self.viagem.pk])
