from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from .tests import Cenario
from .models import SessaoEmbarque, CheckIn

class RevisaoTests(Cenario, TestCase):
    def test_codigo_manual_curto_e_qr(self):
        d = self.gerar().data
        self.assertRegex(d['codigo_manual'], r'^UNIBUS-[A-HJ-NP-Z2-9]{6}$')
        self.assertEqual(self.checkin(d['codigo_manual']).status_code, 201)
        self.assertEqual(self.checkin(d['codigo']).status_code, 409)
        self.assertEqual(CheckIn.objects.count(), 1)

    def test_normaliza_digitacao(self):
        d = self.gerar().data
        codigo = d['codigo_manual'].replace('UNIBUS-', '').lower()
        self.assertEqual(self.checkin('  '+codigo[:3]+' '+codigo[3:]+'  ').status_code, 201)

    def test_renovacao_invalida_manual_antigo(self):
        antigo = self.gerar().data['codigo_manual']
        novo = self.gerar().data['codigo_manual']
        self.assertNotEqual(antigo, novo)
        self.assertEqual(self.checkin(antigo).status_code, 400)
        self.assertEqual(self.checkin(novo).status_code, 201)

    def test_expiracao_do_manual(self):
        from django.utils import timezone
        from datetime import timedelta
        d = self.gerar().data
        SessaoEmbarque.objects.update(expira_em=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.checkin(d['codigo_manual']).status_code, 400)

    def test_mensagem_simples(self):
        r = self.checkin('codigo-errado')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.data), {'detail'})
        self.assertEqual(r.data['detail'], 'Código inválido. Confira o código apresentado pelo fiscal.')

    def test_limita_tentativas(self):
        for _ in range(12): self.assertEqual(self.checkin('errado').status_code, 400)
        self.assertEqual(self.checkin('errado').status_code, 429)
        self.assertFalse(CheckIn.objects.exists())

    def test_repete_geracao_se_codigo_colidir(self):
        self.gerar()
        SessaoEmbarque.objects.update(codigo_curto='AAAAAA')
        with patch('embarques.api.secrets.choice', side_effect=list('AAAAAABBBBBB')):
            r = self.gerar()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['codigo_manual'], 'UNIBUS-BBBBBB')

    def test_menu_consistente_e_home_com_embarques(self):
        admin = self.perfil('Admin', 'administrador')
        self.client.force_login(admin.user)
        for route in ['home','listar_usuarios','cadastrar_usuario','listar_onibus','cadastrar_onibus','listar_rotas','cadastrar_rota','presencas_embarque']:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'paginas/base.html')
                for target in ['listar_usuarios','listar_onibus','listar_rotas','presencas_embarque']:
                    self.assertContains(response, f'href="{reverse(target)}"')
        self.assertContains(self.client.get('/'), 'Consultar embarques')
