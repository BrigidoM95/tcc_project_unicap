"""Benchmark reproduzível com dados fictícios e regressões de custo das APIs."""
import json
import os
from datetime import timedelta, time
from pathlib import Path
from time import perf_counter

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from embarques.tests import Cenario
from embarques.models import CheckIn, ReservaAssento
from onibus.models import Onibus
from .models import LocalizacaoViagem, PontoEmbarque, Rota, Viagem
from . import operacao as op


class DesempenhoTests(Cenario, TestCase):
    def setUp(self):
        super().setUp()
        Onibus.objects.filter(pk=self.onibus.pk).update(capacidade=46)
        Viagem.objects.filter(pk=self.viagem.pk).update(capacidade_registrada=46,
            iniciada_em=timezone.now()-timedelta(hours=4))
        self.viagem.refresh_from_db()
        self.viagens = [self.viagem]
        for n in (2, 3):
            m = self.perfil(f'Motorista{n}', 'motorista')
            b = Onibus.objects.create(nome=f'Ônibus {n}', placa=f'ABC123{n}', capacidade=46, motorista=m)
            r = Rota.objects.create(nome=f'Rota {n}', destino='Campus', onibus=b, fiscal=self.fiscal,
                horario_ida=time(0), horario_retorno=time(23, 59))
            r.instituicoes.add(self.instituicao)
            for sentido in ('ida', 'retorno'):
                PontoEmbarque.objects.create(rota=r, nome='Ponto '+sentido, ordem=1, sentido=sentido)
            self.viagens.append(Viagem.objects.create(rota=r, onibus=b, motorista=m, fiscal=self.fiscal,
                data_servico=op.data_operacional(), status='em_andamento', etapa='embarque_ida',
                sentido='ida', iniciada_em=self.viagem.iniciada_em))
        alunos = [self.associado, self.outro] + [self.perfil(f'Aluno{i}', 'associado') for i in range(38)]
        fim = timezone.make_aware(timezone.datetime.combine(op.data_operacional()+timedelta(days=1),time(3)))
        for i, a in enumerate(alunos):
            if i < 15:
                CheckIn.objects.create(viagem=self.viagem, associado=a, fiscal=self.fiscal,
                    data_servico=self.viagem.data_servico, sentido='ida', vaga=i+1,
                    ponto=self.ponto, nome_ponto=self.ponto.nome, nome_associado=str(a), rua_associado=a.rua)
            else:
                ReservaAssento.objects.create(viagem=self.viagem, associado=a, sentido='ida',
                    assento=i+1, trajeto='ida', ponto=self.ponto, expira_em=fim)
        LocalizacaoViagem.objects.bulk_create([
            LocalizacaoViagem(viagem=v, capturada_em=v.iniciada_em+timedelta(seconds=i*10),
                latitude=-22.6, longitude=-54.8, precisao_metros=15)
            for v in self.viagens for i in range(1440)
        ], batch_size=300)

    def test_medicao_endpoints(self):
        associado = self.cliente(self.associado)
        fiscal = self.cliente(self.fiscal)
        motorista = self.cliente(self.motorista)
        chamadas = [
            ('lista_associado', associado, '/api/viagens/hoje/', None),
            ('lista_fiscal', fiscal, '/api/viagens/hoje/', None),
            ('lista_motorista', motorista, '/api/viagens/hoje/', None),
            ('detalhe', associado, f'/api/viagens/{self.viagem.pk}/', None),
            ('poltronas', associado, f'/api/viagens/{self.viagem.pk}/assentos/', None),
            ('fiscal', fiscal, f'/api/viagens/{self.viagem.pk}/embarques/', None),
            ('busca', fiscal, f'/api/viagens/{self.viagem.pk}/associados/?q=Aluno', None),
            ('gps6', motorista, f'/api/viagens/{self.viagem.pk}/localizacoes/', {'posicoes':[
                {'latitude':'-22.123456','longitude':'-54.123456','precisao_metros':'15',
                 'capturada_em':(timezone.now()-timedelta(seconds=i)).isoformat()} for i in range(6)]}),
        ]
        resultados = {}
        limites = {'lista_associado': 16, 'lista_fiscal': 13, 'lista_motorista': 11,
                   'detalhe': 14, 'poltronas': 15, 'fiscal': 14, 'busca': 8, 'gps6': 10}
        for nome, cliente, url, corpo in chamadas:
            inicio = perf_counter()
            with CaptureQueriesContext(connection) as consultas:
                resposta = cliente.get(url) if corpo is None else cliente.post(url, corpo, format='json')
            self.assertEqual(resposta.status_code, 200, (nome, getattr(resposta,'data',None)))
            resultados[nome] = {'consultas':len(consultas), 'gravacoes':sum(
                q['sql'].lstrip().upper().startswith(('UPDATE','INSERT','DELETE')) for q in consultas),
                'ms':round((perf_counter()-inicio)*1000,2), 'bytes':len(resposta.content)}
            self.assertLessEqual(len(consultas), limites[nome], nome)
            if corpo is None:
                self.assertEqual(resultados[nome]['gravacoes'], 0, nome)
            if nome.startswith('lista_') or nome in ('poltronas', 'fiscal'):
                self.assertLess(len(resposta.content), 12000, nome)
        destino = os.getenv('BENCHMARK_SAIDA')
        if destino:
            Path(destino).parent.mkdir(parents=True, exist_ok=True)
            Path(destino).write_text(json.dumps(resultados, indent=2), encoding='utf-8')
        print(json.dumps(resultados))

    def test_custo_da_lista_nao_cresce_por_onibus(self):
        cliente = self.cliente(self.associado)
        url = '/api/viagens/hoje/'
        cliente.get(url)  # Primeira passagem do fallback de manutenção.
        with CaptureQueriesContext(connection) as antes:
            resposta = cliente.get(url)
        self.assertEqual(len(resposta.data['viagens']), 3)
        for n in range(4, 9):
            motorista = self.perfil(f'Motorista{n}', 'motorista')
            onibus = Onibus.objects.create(nome=f'Ônibus {n}', placa=f'BCD123{n}',
                capacidade=46, motorista=motorista)
            rota = Rota.objects.create(nome=f'Rota {n}', destino='Campus', onibus=onibus,
                fiscal=self.fiscal, horario_ida=time(0), horario_retorno=time(23, 59))
            rota.instituicoes.add(self.instituicao)
            PontoEmbarque.objects.create(rota=rota, nome='Praça', sentido='ida', ordem=1)
            Viagem.objects.create(rota=rota, onibus=onibus, motorista=motorista,
                fiscal=self.fiscal, data_servico=self.viagem.data_servico,
                status='agendada', etapa='agendada', sentido='ida')
        with CaptureQueriesContext(connection) as depois:
            resposta = cliente.get(url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.data['viagens']), 8)
        self.assertEqual(len(antes), len(depois))
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('UPDATE','INSERT','DELETE')) for q in depois))
