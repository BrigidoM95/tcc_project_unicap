from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from usuarios.models import Usuario
from onibus.models import Onibus
from rotas.models import Rota, Viagem
from .models import CheckIn, SessaoEmbarque

class Cenario:
    def perfil(self, nome, tipo):
        user = get_user_model().objects.create_user(username=nome, first_name=nome, password='Teste123456!')
        return Usuario.objects.create(user=user, tipo=tipo)
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.fiscal = self.perfil('Fiscal', 'fiscal')
        self.associado = self.perfil('Associado', 'associado')
        self.outro = self.perfil('Outro', 'associado')
        self.motorista = self.perfil('Motorista', 'motorista')
        self.onibus = Onibus.objects.create(nome='Teste', placa='ABC1234', capacidade=1, motorista=self.motorista, foto='teste.jpg')
        self.rota = Rota.objects.create(nome='Universidade', origem='Caarapó', destino='Dourados', onibus=self.onibus, horario_ida='17:40', horario_retorno='22:10')
        self.viagem = Viagem.objects.create(rota=self.rota, onibus=self.onibus, motorista=self.motorista, sentido='ida')
        self.client = APIClient()
    def cliente(self, perfil):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION='Bearer '+str(RefreshToken.for_user(perfil.user).access_token))
        return c
    def gerar(self):
        return self.cliente(self.fiscal).post(f'/api/embarques/viagens/{self.viagem.pk}/qr/', {}, format='json')
    def checkin(self, codigo, perfil=None):
        return self.cliente(perfil or self.associado).post('/api/embarques/checkin/', {'codigo':codigo}, format='json')

class EmbarquesTests(Cenario, TestCase):
    def test_fluxo_historico_presencas(self):
        qr = self.gerar(); self.assertEqual(qr.status_code, 200)
        res = self.checkin(qr.data['codigo']); self.assertEqual(res.status_code, 201)
        c = CheckIn.objects.get()
        self.assertEqual(c.associado, self.associado)
        self.assertEqual(c.fiscal, self.fiscal)
        self.assertEqual(c.rua_associado, self.associado.rua)
        self.assertEqual(c.placa_onibus, 'ABC1234')
        self.assertEqual(res.data['viagem']['vagas_disponiveis'], 0)
        self.assertEqual(len(self.cliente(self.associado).get('/api/embarques/historico/').data['checkins']), 1)
        self.assertEqual(self.cliente(self.outro).get('/api/embarques/historico/').data['checkins'], [])
        presencas = self.cliente(self.fiscal).get(f'/api/embarques/viagens/{self.viagem.pk}/presencas/')
        self.assertEqual(len(presencas.data['checkins']), 1)
    def test_duplicado(self):
        codigo = self.gerar().data['codigo']
        self.assertEqual(self.checkin(codigo).status_code, 201)
        self.assertEqual(self.checkin(codigo).status_code, 409)
        self.assertEqual(CheckIn.objects.count(), 1)
    def test_lotacao(self):
        codigo = self.gerar().data['codigo']; self.checkin(codigo)
        res = self.checkin(codigo, self.outro)
        self.assertEqual(res.status_code, 409); self.assertIn('lotado', res.data['detail'])
    def test_expiracao(self):
        codigo = self.gerar().data['codigo']
        SessaoEmbarque.objects.update(expira_em=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.checkin(codigo).status_code, 400)
        self.assertFalse(CheckIn.objects.exists())
    def test_rotacao(self):
        antigo = self.gerar().data['codigo']; novo = self.gerar().data['codigo']
        self.assertNotEqual(antigo, novo)
        self.assertEqual(self.checkin(antigo).status_code, 400)
        self.assertEqual(self.checkin(novo).status_code, 201)
    def test_invalidos(self):
        for codigo in ['', 'ONI000001', 'UNIBUS:M4:errado', 'UNIBUS:M4:00000000-0000-0000-0000-000000000000']:
            with self.subTest(codigo=codigo): self.assertEqual(self.checkin(codigo).status_code, 400)
    def test_finalizada(self):
        codigo = self.gerar().data['codigo']
        Viagem.objects.filter(pk=self.viagem.pk).update(status='finalizada', finalizada_em=timezone.now())
        self.assertEqual(self.checkin(codigo).status_code, 409)
        self.assertEqual(self.gerar().status_code, 409)
    def test_rota_inativa(self):
        codigo = self.gerar().data['codigo']; Rota.objects.filter(pk=self.rota.pk).update(status='inativa')
        self.assertEqual(self.checkin(codigo).status_code, 409)
        self.assertEqual(self.gerar().status_code, 409)
    def test_onibus_inativo(self):
        codigo = self.gerar().data['codigo']; self.onibus.desativar()
        self.assertEqual(self.checkin(codigo).status_code, 409)
    def test_fiscal_inativo(self):
        codigo = self.gerar().data['codigo']; self.fiscal.user.is_active = False; self.fiscal.user.save()
        self.assertEqual(self.checkin(codigo).status_code, 403)
    def test_associado_inativo(self):
        codigo = self.gerar().data['codigo']; cliente = self.cliente(self.associado)
        self.associado.user.is_active = False; self.associado.user.save()
        self.assertEqual(cliente.post('/api/embarques/checkin/', {'codigo':codigo}, format='json').status_code, 401)
    def test_perfis_e_autenticacao(self):
        self.assertEqual(self.client.get('/api/embarques/viagens/').status_code, 401)
        self.assertEqual(self.cliente(self.associado).post(f'/api/embarques/viagens/{self.viagem.pk}/qr/', {}, format='json').status_code, 403)
        codigo = self.gerar().data['codigo']
        for p in [self.fiscal, self.motorista]: self.assertEqual(self.checkin(codigo,p).status_code, 403)
        self.assertEqual(self.cliente(self.associado).get(f'/api/embarques/viagens/{self.viagem.pk}/presencas/').status_code, 403)
    def test_fiscal_sem_lista(self):
        self.gerar(); p = self.perfil('Fiscal2', 'fiscal')
        self.assertEqual(self.cliente(p).get(f'/api/embarques/viagens/{self.viagem.pk}/presencas/').status_code, 403)
    def test_ida_retorno(self):
        self.assertEqual(self.checkin(self.gerar().data['codigo']).status_code, 201)
        Viagem.objects.filter(pk=self.viagem.pk).update(status='finalizada', finalizada_em=timezone.now())
        self.viagem = Viagem.objects.create(rota=self.rota, onibus=self.onibus, motorista=self.motorista, sentido='retorno')
        self.assertEqual(self.checkin(self.gerar().data['codigo']).status_code, 201)
        self.assertEqual(CheckIn.objects.count(), 2)
    def test_identidade_nao_forjada(self):
        codigo = self.gerar().data['codigo']
        res = self.cliente(self.associado).post('/api/embarques/checkin/', {'codigo':codigo, 'associado_id':self.outro.pk}, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(CheckIn.objects.get().associado, self.associado)
    def test_web_admin(self):
        p = self.perfil('Admin', 'administrador'); self.checkin(self.gerar().data['codigo'])
        self.client.force_login(p.user)
        res = self.client.get('/embarques/', {'viagem':self.viagem.pk})
        self.assertEqual(res.status_code, 200); self.assertContains(res, self.associado.rua)
    def test_web_associado(self):
        self.client.force_login(self.associado.user)
        self.assertEqual(self.client.get('/embarques/').status_code, 302)

class ConcorrenciaTests(Cenario, TransactionTestCase):
    def test_ultima_vaga_concorrente(self):
        codigo = self.gerar().data['codigo']
        clientes = [self.cliente(self.associado),self.cliente(self.outro)]
        def enviar(c):
            close_old_connections()
            try: return c.post('/api/embarques/checkin/', {'codigo':codigo}, format='json').status_code
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool: status = list(pool.map(enviar,clientes))
        self.assertEqual(status.count(201), 1, status)
        self.assertTrue(all(s in [201,409,503] for s in status), status)
        self.assertEqual(CheckIn.objects.count(), 1)
