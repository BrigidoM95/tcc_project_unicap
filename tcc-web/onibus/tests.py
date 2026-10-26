from django.test import TestCase
from embarques.tests import Cenario

class OnibusApiTests(Cenario,TestCase):
    def test_leitura_preservada_sem_email_do_motorista(self):
        c=self.cliente(self.associado)
        resposta=c.get('/api/onibus/')
        self.assertEqual(resposta.status_code,200,resposta.data)
        self.assertEqual(resposta.data[0]['id'],self.onibus.pk)
        self.assertNotIn('motorista_email',resposta.data[0])
        self.assertEqual(c.get(f'/api/onibus/{self.onibus.pk}/').status_code,200)

    def test_api_nao_altera_capacidade_durante_viagem(self):
        gestor=self.perfil('Gestor','administrador');c=self.cliente(gestor)
        resposta=c.patch(f'/api/onibus/{self.onibus.pk}/',{'capacidade':10},format='json')
        self.assertEqual(resposta.status_code,400,resposta.data)
        self.assertEqual(c.post(f'/api/onibus/{self.onibus.pk}/desativar/').status_code,400)
        self.onibus.refresh_from_db();self.assertEqual(self.onibus.capacidade,2)

    def test_foto_ausente_usa_referencia_sem_mudar_cadastro(self):
        self.onibus.foto='onibus/arquivo-ausente.jpg';self.onibus.save()
        self.assertEqual(self.onibus.foto_url,'')
        self.assertEqual(self.onibus.foto.name,'onibus/arquivo-ausente.jpg')
        self.assertEqual(self.cliente(self.associado).get(f'/api/viagens/{self.viagem.pk}/').data['foto'],'')
