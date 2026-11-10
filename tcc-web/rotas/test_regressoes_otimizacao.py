"""Regras e contratos que devem permanecer após agrupar as leituras da API."""
from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from embarques.models import ReservaAssento
from embarques.tests import Cenario
from . import operacao as op
from .models import LocalizacaoViagem, Rota, Viagem
from .test_correcoes_operacao import DoisOnibus


class LeiturasAgrupadasTests(DoisOnibus, TestCase):
    def lote(self, passageiro):
        viagens = list(op.consulta_viagens(passageiro).filter(data_servico=op.data_operacional()))
        contexto = op.preparar_dados_viagens(viagens, passageiro)
        # Depois das leituras agrupadas, cada ônibus adicional deve ser serializado
        # sem consultas de pontos, contagens, reservas ou dados do passageiro.
        with self.assertNumQueries(0):
            dados = {v.pk: op.dados_viagem(v, passageiro, trajeto=False, contexto=contexto) for v in viagens}
        return dados

    def test_reservas_por_sentido_e_dados_pessoais_ficam_no_onibus_correto(self):
        self.assertEqual(self.escolher(self.viagem, 'ida').status_code, 201)
        self.assertEqual(self.escolher(self.viagem_b, 'volta').status_code, 201)
        dados = self.lote(self.associado)
        self.assertEqual(dados[self.viagem.pk]['minha_escolha']['trajeto'], 'ida')
        self.assertEqual(dados[self.viagem_b.pk]['minha_escolha']['trajeto'], 'volta')
        self.assertEqual(dados[self.viagem.pk]['trajetos_disponiveis'], ['ida'])
        self.assertEqual(dados[self.viagem_b.pk]['trajetos_disponiveis'], ['volta'])
        self.assertEqual(dados[self.viagem.pk]['vagas_por_sentido'], {'ida': 1, 'retorno': 2})
        self.assertEqual(dados[self.viagem_b.pk]['vagas_por_sentido'], {'ida': 2, 'retorno': 1})
        for item in self.lote(self.outro).values():
            self.assertIsNone(item['minha_reserva'])
            self.assertIsNone(item['minha_escolha'])
            self.assertIsNone(item['meu_embarque'])
            self.assertEqual(item['trajetos_disponiveis'], ['ida', 'volta', 'ida_volta'])

    def test_checkin_preserva_escolha_historica_sem_vazar_comprovante(self):
        self.assertEqual(self.escolher(self.viagem, 'ida_volta').status_code, 201)
        self.assertEqual(self.checkin(self.gerar().data['codigo']).status_code, 201)
        dados = self.lote(self.associado)
        propria = dados[self.viagem.pk]
        self.assertEqual(propria['minha_escolha'], op.minha_escolha(self.viagem, self.associado))
        self.assertEqual(propria['minha_escolha']['trajeto'], 'ida_volta')
        self.assertEqual(propria['meu_embarque']['viagem_id'], self.viagem.pk)
        self.assertEqual(propria['total_ida'], 1)
        self.assertEqual(propria['reservados'], 0)
        self.assertEqual(propria['trajetos_disponiveis'], ['volta'])
        outra = dados[self.viagem_b.pk]
        self.assertIsNone(outra['meu_embarque'])
        self.assertIsNone(outra['minha_escolha'])
        self.assertEqual(outra['trajetos_disponiveis'], [])

    def test_reservas_expiradas_e_canceladas_nao_ocupam_nem_bloqueiam(self):
        self.escolher(self.viagem, 'ida_volta')
        ReservaAssento.objects.filter(sentido='ida').update(expira_em=timezone.now()-timedelta(seconds=1))
        ReservaAssento.objects.filter(sentido='retorno').update(ativa=False)
        for item in self.lote(self.associado).values():
            self.assertEqual(item['vagas_por_sentido'], {'ida': 2, 'retorno': 2})
            self.assertIsNone(item['minha_escolha'])
            self.assertEqual(item['trajetos_disponiveis'], ['ida', 'volta', 'ida_volta'])

    def test_leitura_anterior_nao_autoriza_escrita_apos_conflito(self):
        antes = self.lote(self.associado)
        self.assertIn('ida', antes[self.viagem_b.pk]['trajetos_disponiveis'])
        self.assertEqual(self.escolher(self.viagem, 'ida').status_code, 201)
        resposta = self.escolher(self.viagem_b, 'ida')
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(list(ReservaAssento.objects.filter(ativa=True).values_list('viagem_id', flat=True)), [self.viagem.pk])

    def test_lista_poltronas_e_fiscal_nao_enviam_trajeto_detalhe_preserva(self):
        inicial = self.viagem.iniciada_em
        LocalizacaoViagem.objects.bulk_create([
            LocalizacaoViagem(viagem=self.viagem, latitude=-22, longitude=-54,
                              capturada_em=inicial+timedelta(seconds=i)) for i in range(500)
        ])
        associado, fiscal = self.cliente(self.associado), self.cliente(self.fiscal)
        op.atualizar_operacao_se_necessario()
        with patch('rotas.progresso.progresso', side_effect=AssertionError('Trajeto não é necessário nesta tela')):
            lista = associado.get('/api/viagens/hoje/')
            poltronas = associado.get(f'/api/viagens/{self.viagem.pk}/assentos/')
            embarques = fiscal.get(f'/api/viagens/{self.viagem.pk}/embarques/')
        for resposta in (lista, poltronas, embarques):
            self.assertEqual(resposta.status_code, 200, resposta.data)
        viagem = next(v for v in lista.data['viagens'] if v['id'] == self.viagem.pk)
        for item in (viagem, poltronas.data['viagem'], embarques.data['viagem']):
            self.assertEqual(item['trajeto_percorrido'], [])
            self.assertEqual(item['localizacao']['capturada_em'], (inicial+timedelta(seconds=499)).isoformat())
            self.assertIn('miniatura', item)
        detalhe = associado.get(f'/api/viagens/{self.viagem.pk}/')
        self.assertEqual(detalhe.status_code, 200, detalhe.data)
        trilha = detalhe.data['trajeto_percorrido']
        self.assertLessEqual(len(trilha), 401)
        self.assertEqual(trilha[0]['capturada_em'], inicial.isoformat())
        self.assertEqual(trilha[-1]['capturada_em'], (inicial+timedelta(seconds=499)).isoformat())

    def test_fiscal_e_motorista_so_recebem_viagem_atribuida(self):
        for pessoa in (self.fiscal, self.motorista):
            resposta = self.cliente(pessoa).get('/api/viagens/hoje/')
            self.assertEqual(resposta.status_code, 200, resposta.data)
            self.assertEqual([v['id'] for v in resposta.data['viagens']], [self.viagem.pk])


class GpsLoteEMapaTests(Cenario, TestCase):
    def posicao(self, segundos=0, **campos):
        return {'latitude': '-22.123456', 'longitude': '-54.123456', 'precisao_metros': '15',
                'capturada_em': (self.viagem.iniciada_em+timedelta(seconds=segundos)).isoformat(), **campos}

    def test_lote_mistura_novas_repetidas_e_descartadas_sem_sobrescrever(self):
        cliente = self.cliente(self.motorista)
        url = f'/api/viagens/{self.viagem.pk}/localizacoes/'
        existente = self.posicao(10)
        self.assertEqual(cliente.post(url, {'posicoes': [existente]}, format='json').data['aceitas'], 1)
        nova, outra = self.posicao(20), self.posicao(30)
        lote = [nova, {**nova, 'latitude': '-21.000000'}, outra,
                {**outra, 'precisao_metros': '101'}, existente, existente]
        resposta = cliente.post(url, {'posicoes': lote}, format='json')
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual({k: resposta.data[k] for k in ('aceitas', 'repetidas', 'descartadas')},
                         {'aceitas': 2, 'repetidas': 3, 'descartadas': 1})
        self.assertEqual(str(LocalizacaoViagem.objects.get(capturada_em=nova['capturada_em']).latitude), '-22.123456')
        repetida = cliente.post(url, {'posicoes': lote}, format='json')
        self.assertEqual({k: repetida.data[k] for k in ('aceitas', 'repetidas', 'descartadas')},
                         {'aceitas': 0, 'repetidas': 5, 'descartadas': 1})
        self.assertEqual(LocalizacaoViagem.objects.count(), 3)

    def test_entrada_invalida_nao_grava_parte_do_lote(self):
        resposta = self.cliente(self.motorista).post(f'/api/viagens/{self.viagem.pk}/localizacoes/',
            {'posicoes': [self.posicao(), self.posicao(1, latitude='-91')]}, format='json')
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(LocalizacaoViagem.objects.count(), 0)

    def test_cursor_incremental_inclui_posicao_offline_e_mantem_ultima_captura(self):
        locais = LocalizacaoViagem.objects.bulk_create([
            LocalizacaoViagem(viagem=self.viagem, latitude=-22, longitude=-54, velocidade=10,
                              capturada_em=self.viagem.iniciada_em+timedelta(seconds=i)) for i in range(305)
        ])
        cliente = self.cliente(self.associado)
        url = f'/api/mapa/viagens/{self.viagem.pk}/'
        primeiro = cliente.get(url)
        self.assertEqual(primeiro.status_code, 200, primeiro.data)
        self.assertEqual([p['id'] for p in primeiro.data['trajeto']], [p.pk for p in locais[-300:]])
        self.assertEqual(primeiro.data['viagem']['localizacao']['velocidade_kmh'], 36)
        cursor = primeiro.data['cursor']
        self.assertEqual(cliente.get(url, {'apos': cursor}).data['trajeto'], [])
        # Recebida depois, porém capturada entre duas posições já conhecidas.
        offline = LocalizacaoViagem.objects.create(viagem=self.viagem, latitude=-22, longitude=-54,
            capturada_em=self.viagem.iniciada_em+timedelta(seconds=200, milliseconds=500))
        nova = cliente.get(url, {'apos': cursor})
        self.assertEqual([p['id'] for p in nova.data['trajeto']], [offline.pk])
        self.assertEqual(nova.data['cursor'], offline.pk)
        self.assertEqual(nova.data['viagem']['localizacao']['capturada_em'], locais[-1].capturada_em.isoformat())
        self.assertEqual(cliente.get(url, {'apos': offline.pk}).data['trajeto'], [])

    def test_cursor_invalido_responde_400_sem_erro_interno(self):
        cliente = self.cliente(self.associado)
        for cursor in ('-1', 'x', '', '²', '９', '9223372036854775808', '9'*100):
            with self.subTest(cursor=cursor):
                resposta = cliente.get(f'/api/mapa/viagens/{self.viagem.pk}/', {'apos': cursor})
                self.assertEqual(resposta.status_code, 400, resposta.data)


class GeracaoEconomicaTests(Cenario, TestCase):
    def test_agendada_sem_mudanca_nao_grava_e_ativa_preserva_vinculos(self):
        data = op.data_operacional()+timedelta(days=1)
        self.assertEqual(op.gerar_viagens(data), 1)
        with CaptureQueriesContext(connection) as consultas:
            self.assertEqual(op.gerar_viagens(data), 0)
        self.assertEqual(len(consultas), 2)
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('UPDATE', 'INSERT', 'DELETE')) for q in consultas))
        nome_historico = self.viagem.nome_rota_registrado
        Rota.objects.filter(pk=self.rota.pk).update(nome='Novo nome no cadastro')
        op.gerar_viagens(data)
        self.assertEqual(Viagem.objects.get(rota=self.rota, data_servico=data).nome_rota_registrado, 'Novo nome no cadastro')
        op.gerar_viagens(self.viagem.data_servico)
        self.viagem.refresh_from_db()
        self.assertEqual(self.viagem.nome_rota_registrado, nome_historico)

    def test_fallback_nao_repete_trabalho_no_mesmo_minuto(self):
        with patch('rotas.operacao.gerar_viagens') as gerar, patch('rotas.operacao.encerrar_antigas') as encerrar:
            for _ in range(3):
                op.atualizar_operacao_se_necessario()
            gerar.assert_called_once_with()
            encerrar.assert_called_once_with()

    def test_falha_de_geracao_permite_nova_tentativa(self):
        with patch('rotas.operacao.gerar_viagens', side_effect=[RuntimeError('Falha transitória'), 0]) as gerar:
            with self.assertRaises(RuntimeError):
                op.atualizar_operacao_se_necessario()
            op.atualizar_operacao_se_necessario()
            self.assertEqual(gerar.call_count, 2)
