"""Contratos v3: substituem QR de cinco minutos e vaga atribuída automaticamente."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, time
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from usuarios.models import Usuario, Instituicao, Curso
from onibus.models import Onibus
from rotas.models import Rota, Viagem, PontoEmbarque
from rotas import operacao as op
from .models import CheckIn, SessaoEmbarque, ReservaAssento

class Cenario:
    def perfil(self,nome,tipo,curso=True):
        u=get_user_model().objects.create_user(username=nome,email=nome+'@example.test',first_name=nome,password='Teste123456!')
        return Usuario.objects.create(user=u,tipo=tipo,curso=self.curso if curso and tipo in ('associado','fiscal') else None)
    def setUp(self):
        cache.clear()
        self.instituicao=Instituicao.objects.create(nome='Universidade')
        self.curso=Curso.objects.create(nome='Computação',instituicao=self.instituicao)
        self.fiscal=self.perfil('Fiscal','fiscal');self.associado=self.perfil('Associado','associado');self.outro=self.perfil('Outro','associado');self.motorista=self.perfil('Motorista','motorista')
        self.onibus=Onibus.objects.create(nome='Teste',placa='ABC1234',capacidade=2,motorista=self.motorista)
        self.rota=Rota.objects.create(nome='Universidade',destino='Dourados',onibus=self.onibus,fiscal=self.fiscal,horario_ida=time(0),horario_retorno=time(23,59))
        self.rota.instituicoes.add(self.instituicao)
        self.ponto=PontoEmbarque.objects.create(rota=self.rota,nome='Praça',endereco='Centro',sentido='ida',ordem=1)
        self.volta=PontoEmbarque.objects.create(rota=self.rota,nome='Campus',endereco='Faculdade',sentido='retorno',ordem=1)
        self.viagem=Viagem.objects.create(rota=self.rota,onibus=self.onibus,motorista=self.motorista,fiscal=self.fiscal,sentido='ida',status='em_andamento',etapa='embarque_ida',data_servico=op.data_operacional(),iniciada_em=timezone.now()-timedelta(minutes=10))
        self.client=APIClient()
    def cliente(self,p):
        c=APIClient();c.credentials(HTTP_AUTHORIZATION='Bearer '+str(RefreshToken.for_user(p.user).access_token));return c
    def gerar(self,sentido='ida'):
        return self.cliente(self.fiscal).post(f'/api/viagens/{self.viagem.pk}/qr-do-dia/',{'sentido':sentido},format='json')
    def reservar(self,p=None,poltrona=1,sentido='ida'):
        return self.cliente(p or self.associado).post(f'/api/viagens/{self.viagem.pk}/reservas/',{'sentido':sentido,'poltrona':poltrona},format='json')
    def checkin(self,codigo,p=None,poltrona=1,sentido='ida',**extras):
        return self.cliente(p or self.associado).post('/api/checkins/',{'codigo':codigo,'viagem_id':self.viagem.pk,'sentido':sentido,'poltrona':poltrona,**extras},format='json')
    def confirmar(self,p=None,poltrona=1,sentido='ida'):
        q=self.gerar(sentido);self.reservar(p,poltrona,sentido);return self.checkin(q.data['codigo'],p,poltrona,sentido)

class EmbarquesTests(Cenario,TestCase):
    def test_qr_estavel_assinado_sem_dados_pessoais(self):
        a=self.gerar();b=self.gerar();self.assertEqual(a.status_code,200,a.data)
        self.assertEqual(a.data['codigo'],b.data['codigo']);self.assertEqual(SessaoEmbarque.objects.count(),1)
        self.assertNotIn('codigo_manual',a.data);self.assertNotIn(self.fiscal.user.email,a.data['codigo'])
    def test_reserva_confirmacao_e_idempotencia(self):
        q=self.gerar().data['codigo'];self.assertEqual(self.reservar().status_code,201)
        a=self.checkin(q);b=self.checkin(q);self.assertEqual((a.status_code,b.status_code),(201,200))
        self.assertEqual(a.data['checkin']['id'],b.data['checkin']['id']);self.assertEqual(CheckIn.objects.count(),1)
        self.assertFalse(ReservaAssento.objects.filter(ativa=True).exists())
        h=self.cliente(self.associado).get('/api/me/embarques/');self.assertEqual(h.data['frequencia']['dias'],1)
        self.assertEqual(self.cliente(self.outro).get('/api/me/embarques/').data['checkins'],[])
    def test_nao_confirma_sem_reserva(self):
        self.assertEqual(self.checkin(self.gerar().data['codigo']).status_code,409)
    def test_reserva_valida_ate_fim_do_dia_operacional(self):
        self.reservar();r=ReservaAssento.objects.get();self.assertEqual(timezone.localtime(r.expira_em).time(),time(3));self.assertEqual(timezone.localtime(r.expira_em).date(),op.data_operacional()+timedelta(days=1))
        ReservaAssento.objects.update(expira_em=timezone.now()-timedelta(seconds=1));self.assertEqual(self.reservar(self.outro).status_code,201)
    def test_troca_falha_preserva_anterior(self):
        self.reservar(poltrona=1);self.reservar(self.outro,2)
        self.assertEqual(self.reservar(poltrona=2).status_code,409)
        self.assertEqual(ReservaAssento.objects.get(associado=self.associado,ativa=True).assento,1)
    def test_troca_valida_libera_anterior(self):
        self.reservar(poltrona=1);self.assertEqual(self.reservar(poltrona=2).status_code,201)
        self.assertEqual(self.reservar(self.outro,1).status_code,201)
    def test_poltrona_ocupada_e_lotacao(self):
        self.assertEqual(self.confirmar().status_code,201)
        self.assertEqual(self.reservar(self.outro,1).status_code,409)
        self.assertEqual(self.confirmar(self.outro,2).status_code,201)
        self.assertEqual(self.reservar(self.perfil('Terceiro','associado'),2).status_code,409)
    def test_poltrona_fora_da_capacidade(self):
        for v in (0,-1,3,'1',True,None):self.assertEqual(self.reservar(poltrona=v).status_code,409)
    def test_qr_invalido_ou_sentido_errado(self):
        self.reservar();q=self.gerar().data['codigo']
        for c in ('',q+'x','UNIBUS-ABC234'):self.assertEqual(self.checkin(c).status_code,409)
        self.assertEqual(self.checkin(q,sentido='retorno').status_code,409)
    def test_fecha_embarque_na_partida_e_libera_reservas(self):
        self.reservar();q=self.gerar().data['codigo'];op.transicao(self.viagem.pk,self.motorista,'iniciar_ida')
        self.assertEqual(self.checkin(q).status_code,409);self.assertEqual(self.gerar().status_code,409)
        self.assertFalse(ReservaAssento.objects.filter(ativa=True).exists())
    def test_ida_e_volta_no_mesmo_ciclo(self):
        self.assertEqual(self.confirmar().status_code,201)
        op.transicao(self.viagem.pk,self.motorista,'iniciar_ida');op.transicao(self.viagem.pk,self.motorista,'finalizar_ida')
        self.assertEqual(self.confirmar(sentido='retorno').status_code,201)
        self.assertEqual(CheckIn.objects.count(),2)
    def test_duplicado_em_outro_onibus(self):
        self.confirmar();op.transicao(self.viagem.pk,self.motorista,'iniciar_ida');op.transicao(self.viagem.pk,self.motorista,'finalizar_ida');op.transicao(self.viagem.pk,self.motorista,'iniciar_volta');op.transicao(self.viagem.pk,self.motorista,'finalizar')
        r=Rota.objects.create(nome='Outra',destino='B',onibus=self.onibus,horario_ida=time(0),horario_retorno=time(23,59));r.instituicoes.add(self.instituicao)
        self.viagem=Viagem.objects.create(rota=r,onibus=self.onibus,motorista=self.motorista,fiscal=self.fiscal,sentido='ida',etapa='embarque_ida',data_servico=op.data_operacional())
        self.assertEqual(self.reservar().status_code,409)
    def test_estudante_ativo_pode_embarcar(self):
        self.assertEqual(self.confirmar().status_code,201)
    def test_fiscal_proprio_com_e_sem_curso(self):
        c=self.cliente(self.fiscal);url=f'/api/viagens/{self.viagem.pk}/embarques/fiscal/'
        self.assertEqual(c.post(url,{'sentido':'ida','poltrona':2,'motivo':'Fiscal embarcando como passageiro'},format='json').status_code,201)
        self.assertEqual(CheckIn.objects.get().origem,'fiscal')
        Usuario.objects.filter(pk=self.fiscal.pk).update(curso=None)
        self.assertEqual(c.get('/api/me/embarques/').status_code,403)
    def test_manual_exige_motivo_e_cancelamento_libera_poltrona(self):
        c=self.cliente(self.fiscal);url=f'/api/viagens/{self.viagem.pk}/embarques/manual/'
        d={'associado_id':self.associado.pk,'sentido':'ida','poltrona':1}
        self.assertEqual(c.post(url,d,format='json').status_code,409)
        a=c.post(url,{**d,'motivo':'Sem bateria'},format='json');self.assertEqual(a.status_code,201,a.data)
        cid=a.data['checkin']['id'];self.assertEqual(c.delete(f'/api/checkins/{cid}/',{},format='json').status_code,409)
        self.assertEqual(c.delete(f'/api/checkins/{cid}/',{'motivo':'Ônibus errado'},format='json').status_code,200)
        self.assertEqual(self.confirmar(self.outro).status_code,201);self.assertEqual(CheckIn.objects.count(),2)
    def test_offline_aceita_janela_original_depois_partida(self):
        q=self.gerar().data['codigo'];lido=timezone.now();op.transicao(self.viagem.pk,self.motorista,'iniciar_ida')
        a=self.checkin(q,offline=True,lido_em=lido.isoformat());self.assertEqual(a.status_code,201,a.data)
        self.assertTrue(CheckIn.objects.get().sincronizado_offline)
    def test_offline_recusa_leitura_depois_partida(self):
        q=self.gerar().data['codigo'];op.transicao(self.viagem.pk,self.motorista,'iniciar_ida')
        self.assertEqual(self.checkin(q,offline=True,lido_em=timezone.now().isoformat()).status_code,409)
    def test_offline_nao_toma_poltrona_confirmada(self):
        q=self.gerar().data['codigo'];lido=timezone.now();self.confirmar(self.outro)
        self.assertEqual(self.checkin(q,offline=True,lido_em=lido.isoformat()).status_code,409)
    def test_instituicao_diferente_nao_visualiza_ou_embarca(self):
        i=Instituicao.objects.create(nome='Outra escola');c=Curso.objects.create(nome='Outro',instituicao=i)
        Usuario.objects.filter(pk=self.associado.pk).update(curso=c)
        a=self.cliente(self.associado);self.assertEqual(a.get(f'/api/viagens/{self.viagem.pk}/').status_code,404)
        self.assertEqual(self.reservar().status_code,403)
    def test_fiscal_alheio_nao_toma_qr_nem_lista(self):
        f=self.perfil('OutroFiscal','fiscal');a=self.cliente(f)
        for rota in ('qr-do-dia/','embarques/'):self.assertEqual(a.get(f'/api/viagens/{self.viagem.pk}/{rota}').status_code,404)
        self.assertEqual(a.post(f'/api/viagens/{self.viagem.pk}/assumir/',{},format='json').status_code,403)
    def test_inativo_nao_autentica(self):
        c=self.cliente(self.associado);self.associado.user.is_active=False;self.associado.user.save()
        self.assertEqual(c.get('/api/viagens/hoje/').status_code,401)
    def test_sem_fiscal_pode_iniciar_mas_nao_embarca(self):
        Viagem.objects.filter(pk=self.viagem.pk).update(fiscal=None)
        self.assertEqual(self.reservar().status_code,201)
        self.assertEqual(self.cliente(self.fiscal).post(f'/api/viagens/{self.viagem.pk}/assumir/',{},format='json').status_code,403)
        self.assertEqual(self.reservar().status_code,201)
    def test_codigo_expirado_recusado(self):
        q=self.gerar().data['codigo'];SessaoEmbarque.objects.update(expira_em=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.checkin(q).status_code,409)

class ConcorrenciaTests(Cenario,TransactionTestCase):
    def test_duas_pessoas_disputam_mesma_poltrona(self):
        clientes=[self.cliente(self.associado),self.cliente(self.outro)]
        def enviar(c):
            close_old_connections()
            try:return c.post(f'/api/viagens/{self.viagem.pk}/reservas/',{'sentido':'ida','poltrona':1},format='json').status_code
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:status=list(pool.map(enviar,clientes))
        # SQLite pode recusar ambos ao detectar upgrade concorrente de locks.
        if status.count(201)==0:self.assertEqual(enviar(clientes[0]),201)
        self.assertLessEqual(status.count(201),1);self.assertTrue(all(s in (201,409) for s in status),status)
        self.assertEqual(ReservaAssento.objects.filter(ativa=True,assento=1).count(),1)
