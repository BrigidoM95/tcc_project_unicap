from django.test import TestCase
from django.urls import reverse
from .tests import Cenario
from .models import CheckIn

class RevisaoTests(Cenario,TestCase):
    def test_mensagem_simples_e_limite(self):
        for _ in range(20):
            r=self.checkin('errado');self.assertEqual(r.status_code,409);self.assertIn('QR inválido',str(r.data['mensagem']))
        self.assertEqual(self.checkin('errado').status_code,429);self.assertFalse(CheckIn.objects.exists())
    def test_telas_admin_e_detalhes(self):
        admin=self.perfil('Admin','administrador');self.client.force_login(admin.user)
        for route in ['home','listar_usuarios','cadastrar_usuario','listar_onibus','cadastrar_onibus','listar_rotas','cadastrar_rota','presencas_embarque']:
            r=self.client.get(reverse(route));self.assertEqual(r.status_code,200,route);self.assertTemplateUsed(r,'paginas/base.html')
        for url in (f'/usuarios/{self.associado.pk}/',f'/onibus/{self.onibus.pk}/detalhes/',f'/rotas/{self.rota.pk}/','/operacao/'):
            self.assertEqual(self.client.get(url).status_code,200,url)
    def test_endpoints_antigos_nao_contornam_etapas(self):
        c=self.cliente(self.motorista)
        for url in ('/api/viagens/iniciar/',f'/api/viagens/{self.viagem.pk}/finalizar/',f'/api/viagens/{self.viagem.pk}/localizacao/'):
            self.assertEqual(c.post(url,{},format='json').status_code,410)
