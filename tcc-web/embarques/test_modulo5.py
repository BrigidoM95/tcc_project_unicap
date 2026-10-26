from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rotas.models import PontoEmbarque,LocalizacaoViagem
from .models import CheckIn
from .tests import Cenario

class PontosEHistoricoTests(Cenario,TestCase):
    def test_snapshot_preserva_ponto(self):
        self.confirmar();self.ponto.nome='Renomeado';self.ponto.save()
        self.assertEqual(CheckIn.objects.get().nome_ponto,'Praça')
    def test_gps_nao_substitui_ponto_informado_pelo_fiscal(self):
        outro=PontoEmbarque.objects.create(rota=self.rota,nome='Bairro',sentido='ida',ordem=2)
        LocalizacaoViagem.objects.create(viagem=self.viagem,latitude=-22.70,longitude=-54.90,precisao_metros=5,capturada_em=timezone.now())
        r=self.cliente(self.fiscal).post(f'/api/viagens/{self.viagem.pk}/embarques/manual/',{'associado_id':self.associado.pk,'sentido':'ida','poltrona':1,'ponto_id':outro.pk,'motivo':'Sem celular'},format='json')
        self.assertEqual(r.status_code,201,r.data)
        self.assertEqual(CheckIn.objects.get().ponto_id,outro.pk)
    def test_reserva_exige_escolha_entre_pontos_e_qr_usa_reserva(self):
        outro=PontoEmbarque.objects.create(rota=self.rota,nome='Bairro',sentido='ida',ordem=2)
        self.assertEqual(self.reservar().status_code,409)
        c=self.cliente(self.associado);url=f'/api/viagens/{self.viagem.pk}/reservas/'
        dados={'trajeto':'ida','poltrona':1,'ponto_ida_id':self.volta.pk}
        self.assertEqual(c.post(url,dados,format='json').status_code,409)
        dados['ponto_ida_id']=outro.pk
        self.assertEqual(c.post(url,dados,format='json').status_code,201)
        self.assertEqual(self.checkin(self.gerar().data['codigo']).status_code,201)
        self.assertEqual(CheckIn.objects.get().ponto_id,outro.pk)
    def test_snapshot_de_capacidade(self):
        self.onibus.capacidade=10;self.onibus.save()
        self.assertEqual(self.gerar().data['viagem']['capacidade'],2)
    def test_filtro_e_historico_de_cancelamento(self):
        c=self.confirmar().data['checkin'];self.cliente(self.fiscal).delete(f"/api/checkins/{c['id']}/",{'motivo':'Desistiu'},format='json')
        h=self.cliente(self.associado).get('/api/me/embarques/').data
        self.assertTrue(h['checkins'][0]['cancelado']);self.assertEqual(h['frequencia']['dias'],0)
