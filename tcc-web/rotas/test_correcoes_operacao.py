from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta

from django.db import close_old_connections
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from embarques.models import ReservaAssento
from embarques.tests import Cenario
from onibus.models import Onibus
from . import operacao as op
from .models import LocalizacaoViagem, PontoEmbarque, Rota, Viagem


class DoisOnibus(Cenario):
    def setUp(self):
        super().setUp()
        self.motorista_b = self.perfil('MotoristaB', 'motorista')
        self.fiscal_b = self.perfil('FiscalB', 'fiscal')
        self.onibus_b = Onibus.objects.create(nome='Ônibus B', placa='DEF5678', capacidade=2, motorista=self.motorista_b)
        self.rota_b = Rota.objects.create(nome='Rota B', destino='Campus', onibus=self.onibus_b,
            fiscal=self.fiscal_b, horario_ida=time(0), horario_retorno=time(23, 59))
        self.rota_b.instituicoes.add(self.instituicao)
        for sentido in ('ida', 'retorno'):
            PontoEmbarque.objects.create(rota=self.rota_b, nome='Ponto B ' + sentido, ordem=1, sentido=sentido)
        self.viagem_b = Viagem.objects.create(rota=self.rota_b, onibus=self.onibus_b,
            motorista=self.motorista_b, fiscal=self.fiscal_b, sentido='ida', status='em_andamento',
            etapa='embarque_ida', data_servico=op.data_operacional(), iniciada_em=timezone.now()-timedelta(minutes=10))

    def escolher(self, viagem, trajeto):
        return self.cliente(self.associado).post(f'/api/viagens/{viagem.pk}/reservas/',
            {'trajeto':trajeto, 'poltrona':1}, format='json')


class ReservasPorSentidoTests(DoisOnibus, TestCase):
    def test_ida_volta_bloqueia_todas_opcoes_em_outro_onibus(self):
        self.assertEqual(self.escolher(self.viagem, 'ida_volta').status_code, 201)
        for trajeto in ('ida', 'volta', 'ida_volta'):
            resposta = self.escolher(self.viagem_b, trajeto)
            self.assertEqual(resposta.status_code, 409, resposta.data)
            self.assertIn(self.onibus.nome, resposta.data['mensagem'])
        self.assertEqual(ReservaAssento.objects.filter(ativa=True).count(), 2)
        self.assertEqual(op.dados_viagem(self.viagem_b, self.associado)['trajetos_disponiveis'], [])

    def test_ida_a_volta_b_sem_substituir_ida(self):
        self.assertEqual(self.escolher(self.viagem, 'ida').status_code, 201)
        self.assertEqual(op.dados_viagem(self.viagem_b, self.associado)['trajetos_disponiveis'], ['volta'])
        self.assertEqual(self.escolher(self.viagem_b, 'volta').status_code, 201)
        self.assertEqual(set(ReservaAssento.objects.filter(ativa=True).values_list('viagem_id', 'sentido')),
                         {(self.viagem.pk, 'ida'), (self.viagem_b.pk, 'retorno')})

    def test_volta_a_ida_b_sem_substituir_volta(self):
        self.assertEqual(self.escolher(self.viagem, 'volta').status_code, 201)
        self.assertEqual(op.dados_viagem(self.viagem_b, self.associado)['trajetos_disponiveis'], ['ida'])
        self.assertEqual(self.escolher(self.viagem_b, 'ida').status_code, 201)
        self.assertEqual(ReservaAssento.objects.filter(ativa=True).count(), 2)

    def test_ida_lotada_nao_oculta_vagas_da_volta(self):
        self.escolher(self.viagem, 'ida')
        for numero, p in enumerate((self.outro, self.perfil('Terceiro', 'associado')), start=1):
            op.registrar_embarque(self.viagem_b.pk, p, 'ida', numero, self.fiscal_b,
                                  origem='manual', motivo='Câmera indisponível')
        dados = op.dados_viagem(self.viagem_b, self.associado)
        self.assertEqual(dados['vagas_disponiveis'], 0)
        self.assertEqual(dados['vagas_por_sentido'], {'ida':0, 'retorno':2})
        self.assertEqual(dados['trajetos_disponiveis'], ['volta'])
        self.assertEqual(self.escolher(self.viagem_b, 'volta').status_code, 201)

    def test_cancelamento_libera_outro_onibus(self):
        self.escolher(self.viagem, 'ida_volta')
        r = self.cliente(self.associado).delete(f'/api/viagens/{self.viagem.pk}/minha-escolha/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.escolher(self.viagem_b, 'ida_volta').status_code, 201)

    def test_alteracao_libera_apenas_sentido_removido(self):
        self.escolher(self.viagem, 'ida_volta')
        self.assertEqual(self.escolher(self.viagem, 'ida').status_code, 201)
        self.assertEqual(self.escolher(self.viagem_b, 'volta').status_code, 201)
        self.assertEqual(self.escolher(self.viagem_b, 'ida').status_code, 409)
        self.assertEqual(ReservaAssento.objects.filter(ativa=True).count(), 2)

    def test_checkin_bloqueia_sentido_e_nao_aparece_como_comprovante_em_outro_onibus(self):
        self.assertEqual(self.confirmar().status_code, 201)
        dados = op.dados_viagem(self.viagem_b, self.associado)
        self.assertIsNone(dados['meu_embarque'])
        self.assertEqual(dados['trajetos_disponiveis'], ['volta'])
        self.assertIn('check-in', dados['bloqueios_trajeto']['ida'])
        self.assertEqual(self.escolher(self.viagem_b, 'ida').status_code, 409)
        self.assertEqual(self.escolher(self.viagem_b, 'volta').status_code, 201)

    def test_reserva_expirada_nao_bloqueia(self):
        self.escolher(self.viagem, 'ida')
        ReservaAssento.objects.update(expira_em=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.escolher(self.viagem_b, 'ida').status_code, 201)

    def test_embarque_manual_nao_contorna_reserva_em_outro_onibus(self):
        self.escolher(self.viagem, 'ida')
        with self.assertRaisesMessage(op.Regra, 'Cancele essa escolha'):
            op.registrar_embarque(self.viagem_b.pk, self.associado, 'ida', 1,
                                  self.fiscal_b, origem='manual', motivo='Câmera indisponível')


class VinculosEGpsTests(DoisOnibus, TestCase):
    def test_troca_onibus_da_rota_atualiza_agendada_e_somente_novo_motorista_ve(self):
        Viagem.objects.filter(pk=self.viagem.pk).update(status='agendada', etapa='agendada')
        Rota.objects.filter(pk=self.rota.pk).update(onibus=self.onibus_b)
        url = f'/api/viagens/{self.viagem.pk}/'
        self.assertEqual(self.cliente(self.motorista).get(url).status_code, 404)
        dados = self.cliente(self.motorista_b).get(url).data
        self.assertEqual(dados['onibus_id'], self.onibus_b.pk)
        op.gerar_viagens()
        self.viagem.refresh_from_db()
        self.assertEqual((self.viagem.onibus_id, self.viagem.motorista_id), (self.onibus_b.pk, self.motorista_b.pk))
        self.assertEqual(self.viagem.placa_onibus_registrada, self.onibus_b.placa)

    def test_painel_nao_transfere_reservas_silenciosamente_ao_trocar_onibus(self):
        self.escolher(self.viagem, 'ida')
        Viagem.objects.filter(pk=self.viagem.pk).update(status='agendada', etapa='agendada')
        self.rota.onibus = self.onibus_b
        with self.assertRaisesMessage(ValidationError, 'Cancele as reservas antes de trocar o ônibus'):
            self.rota.clean()

    def test_painel_direciona_troca_de_fiscal_em_operacao_para_intervencao(self):
        self.rota.fiscal = self.fiscal_b
        with self.assertRaisesMessage(ValidationError, 'intervenção administrativa'):
            self.rota.clean()

    def test_motorista_e_fiscal_veem_somente_suas_viagens(self):
        for pessoa in (self.motorista, self.fiscal):
            c = self.cliente(pessoa)
            r = c.get('/api/viagens/hoje/')
            self.assertEqual([v['id'] for v in r.data['viagens']], [self.viagem.pk])
            self.assertEqual(c.get(f'/api/viagens/{self.viagem_b.pk}/').status_code, 404)
            self.assertEqual(c.get(f'/api/viagens/{self.viagem_b.pk}/assentos/').status_code, 404)

    def test_fiscal_nao_ve_ou_assume_viagem_sem_vinculo(self):
        Viagem.objects.filter(pk=self.viagem_b.pk).update(fiscal=None)
        Rota.objects.filter(pk=self.rota_b.pk).update(fiscal=None)
        c = self.cliente(self.fiscal)
        self.assertEqual(c.get(f'/api/viagens/{self.viagem_b.pk}/').status_code, 404)
        self.assertEqual(c.post(f'/api/viagens/{self.viagem_b.pk}/assumir/', {}, format='json').status_code, 403)
        self.assertNotIn(self.rota_b.pk, [r['id'] for r in c.get('/api/mapa/').data['rotas']])
        self.assertEqual(c.post(f'/api/viagens/{self.viagem_b.pk}/reservas/',
                              {'trajeto':'ida', 'poltrona':1}, format='json').status_code, 403)

    def test_vinculo_agendado_reflete_painel_sem_expor_ao_responsavel_antigo(self):
        novo_m = self.perfil('NovoMotorista', 'motorista')
        novo_f = self.perfil('NovoFiscal', 'fiscal')
        Viagem.objects.filter(pk=self.viagem.pk).update(etapa='agendada', status='agendada')
        Onibus.objects.filter(pk=self.onibus.pk).update(motorista=novo_m)
        Rota.objects.filter(pk=self.rota.pk).update(fiscal=novo_f)
        for antigo, novo in ((self.motorista, novo_m), (self.fiscal, novo_f)):
            self.assertEqual(self.cliente(antigo).get(f'/api/viagens/{self.viagem.pk}/').status_code, 404)
            self.assertEqual(self.cliente(novo).get(f'/api/viagens/{self.viagem.pk}/').status_code, 200)
        self.assertEqual(self.cliente(self.motorista).post(f'/api/viagens/{self.viagem.pk}/transicao/',
            {'acao':'iniciar_rota'}, format='json').status_code, 403)
        self.assertEqual(op.transicao(self.viagem.pk, novo_m, 'iniciar_rota').motorista_id, novo_m.pk)
        self.viagem.refresh_from_db()
        self.assertEqual(self.viagem.fiscal_id, novo_f.pk)

    def test_geracao_sincroniza_agendadas_mas_preserva_viagens_iniciadas(self):
        novo_m = self.perfil('NovoMotorista', 'motorista')
        novo_f = self.perfil('NovoFiscal', 'fiscal')
        Viagem.objects.filter(pk=self.viagem.pk).update(etapa='agendada', status='agendada')
        Onibus.objects.filter(pk=self.onibus.pk).update(motorista=novo_m)
        Rota.objects.filter(pk__in=[self.rota.pk, self.rota_b.pk]).update(fiscal=novo_f)
        self.assertEqual(op.gerar_viagens(), 0)
        self.viagem.refresh_from_db(); self.viagem_b.refresh_from_db()
        self.assertEqual((self.viagem.motorista_id, self.viagem.fiscal_id), (novo_m.pk, novo_f.pk))
        self.assertEqual(self.viagem_b.fiscal_id, self.fiscal_b.pk)

    def test_gps_100m_aparece_no_app_e_no_mapa_web_com_motivo_de_recusa(self):
        agora = timezone.now()
        pos = {'latitude':'-22.123456', 'longitude':'-54.123456',
               'precisao_metros':'100.00', 'capturada_em':agora.isoformat()}
        url = f'/api/viagens/{self.viagem.pk}/localizacoes/'
        c = self.cliente(self.motorista)
        r = c.post(url, {'posicoes':[pos, {**pos, 'precisao_metros':'100.01'}]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['aceitas'], r.data['descartadas']), (1, 1))
        self.assertIn('100 m', r.data['motivos'][0])
        repetido = c.post(url, {'posicoes':[pos]}, format='json').data
        self.assertEqual((repetido['aceitas'], repetido['repetidas'], repetido['descartadas']), (0, 1, 0))
        self.assertEqual(LocalizacaoViagem.objects.count(), 1)
        self.assertEqual(op.dados_viagem(self.viagem, self.associado)['localizacao']['precisao_metros'], 100)
        admin = self.perfil('Admin', 'administrador')
        self.client.force_login(admin.user)
        mapa = self.client.get(f'/api/mapa/viagens/{self.viagem.pk}/').data
        self.assertEqual(mapa['viagem']['localizacao']['latitude'], float(pos['latitude']))
        self.assertEqual(len(mapa['trajeto']), 1)
        self.assertEqual(self.cliente(self.motorista_b).post(url, {'posicoes':[pos]}, format='json').status_code, 403)

    def test_qr_abre_ao_iniciar_rota_e_fecha_para_todos_ao_partir(self):
        Viagem.objects.filter(pk=self.viagem.pk).update(status='agendada', etapa='agendada')
        self.assertEqual(self.gerar().status_code, 409)
        op.transicao(self.viagem.pk, self.motorista, 'iniciar_rota')
        qr = self.gerar()
        self.assertEqual(qr.status_code, 200, qr.data)
        self.assertEqual(self.reservar().status_code, 201)
        op.transicao(self.viagem.pk, self.motorista, 'iniciar_ida')
        self.assertEqual(self.checkin(qr.data['codigo']).status_code, 409)
        self.assertEqual(self.gerar().status_code, 409)
        self.viagem.refresh_from_db()
        for pessoa in (self.associado, self.outro, self.fiscal):
            self.assertFalse(op.dados_viagem(self.viagem, pessoa)['embarque_aberto'])


class ReservasConcorrentesTests(DoisOnibus, TransactionTestCase):
    def test_mesma_pessoa_nao_reserva_ida_em_dois_onibus_ao_mesmo_tempo(self):
        clientes = [(self.cliente(self.associado), v.pk) for v in (self.viagem, self.viagem_b)]
        def enviar(item):
            close_old_connections()
            try:
                c, pk = item
                return c.post(f'/api/viagens/{pk}/reservas/', {'trajeto':'ida', 'poltrona':1}, format='json').status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            status = list(pool.map(enviar, clientes))
        self.assertEqual(sorted(status), [201, 409])
        self.assertEqual(ReservaAssento.objects.filter(associado=self.associado, ativa=True).count(), 1)
