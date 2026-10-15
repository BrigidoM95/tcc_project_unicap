from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APIClient
from usuarios.models import Usuario, MatriculaAnual, Instituicao, Curso
from usuarios.forms import CadastroUsuarioForm, EdicaoUsuarioForm
from onibus.models import Onibus
from rotas.models import Rota, PontoEmbarque, Viagem, LocalizacaoViagem
from embarques.models import CheckIn
from .models import Despesa, LogAuditoria

class SistemaIntegradoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U=get_user_model()
        cls.admin=U.objects.create_superuser('admin','admin@example.test','Testes!753912')
        def usuario(nome,tipo):
            user=U.objects.create_user(nome+'@example.test',nome+'@example.test','Testes!753912',first_name=nome)
            return Usuario.objects.create(user=user,tipo=tipo)
        cls.motorista=usuario('motorista','motorista');cls.fiscal=usuario('fiscal','fiscal')
        cls.associado=usuario('associado','associado');cls.outro=usuario('outro','associado')
        cls.bus=Onibus.objects.create(nome='Ônibus de teste',placa='TST1A23',capacidade=1,motorista=cls.motorista,foto='')
        cls.rota=Rota.objects.create(nome='Campus',origem='Centro',destino='Universidade',onibus=cls.bus,horario_ida='18:00',horario_retorno='22:00')
        cls.ponto=PontoEmbarque.objects.create(rota=cls.rota,nome='Praça',endereco='Centro',sentido='ida',ordem=1,latitude='-22.634000',longitude='-54.821000')
    def setUp(self): cache.clear()
    def api(self,perfil):
        c=APIClient();r=c.post('/api/login/',{'email':perfil.user.email,'senha':'Testes!753912'},format='json')
        self.assertEqual(r.status_code,200,r.data);c.credentials(HTTP_AUTHORIZATION='Bearer '+r.data['access'])
        return c,r.data
    def iniciar(self):
        c,_=self.api(self.motorista)
        r=c.post('/api/viagens/iniciar/',{'rota_id':self.rota.pk,'sentido':'ida'},format='json')
        self.assertEqual(r.status_code,201,r.data)
        return c,r.data['id']
    def qr(self,id):
        c,_=self.api(self.fiscal);r=c.post(f'/api/embarques/viagens/{id}/qr/',{'ponto_id':self.ponto.pk},format='json')
        self.assertEqual(r.status_code,200,r.data);return r.data['codigo']
    def test_fluxo_completo_login_gps_qr_lotacao_mapa_relatorio_fim(self):
        driver,vid=self.iniciar()
        r=driver.post(f'/api/viagens/{vid}/localizacao/',{'latitude':'-22.634010','longitude':'-54.821010','precisao_metros':'7.5','capturada_em':timezone.now().isoformat()},format='json')
        self.assertEqual(r.status_code,201,r.data)
        codigo=self.qr(vid);a,_=self.api(self.associado)
        r=a.post('/api/embarques/checkin/',{'codigo':codigo},format='json')
        self.assertEqual(r.status_code,201,r.data)
        self.assertEqual(r.data['checkin']['ponto_nome'],'Praça')
        self.assertEqual(a.post('/api/embarques/checkin/',{'codigo':codigo},format='json').status_code,409)
        b,_=self.api(self.outro)
        self.assertEqual(b.post('/api/embarques/checkin/',{'codigo':codigo},format='json').status_code,409)
        mapa=a.get('/api/mapa/').data
        self.assertEqual(mapa['viagens'][0]['presentes'],1);self.assertEqual(mapa['viagens'][0]['vagas'],0)
        self.assertFalse(mapa['viagens'][0]['localizacao']['desatualizada'])
        self.assertEqual(a.get(f'/api/mapa/viagens/{vid}/').data['rota']['pontos'][0]['nome'],'Praça')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/relatorios/'),'associado')
        pdf=self.client.get(reverse('relatorios:pdf'))
        self.assertEqual(pdf.status_code,200);self.assertTrue(pdf.content.startswith(b'%PDF'))
        self.assertEqual(driver.post(f'/api/viagens/{vid}/finalizar/').status_code,200)
        self.assertEqual(a.get(f'/api/mapa/viagens/{vid}/').status_code,404)
        self.assertEqual(a.get('/api/mapa/').data['viagens'],[])
        self.assertEqual(a.post('/api/embarques/checkin/',{'codigo':codigo},format='json').status_code,409)
        log=LogAuditoria.objects.get(acao='viagem_finalizada',objeto_id=str(vid))
        self.assertEqual(log.usuario_id,self.motorista.user_id)
    def test_matricula_anual_bloqueia_ate_renovacao(self):
        _,vid=self.iniciar();codigo=self.qr(vid);a,_=self.api(self.associado)
        atual=MatriculaAnual.objects.get(associado=self.associado,ano=timezone.localdate().year)
        atual.ativa=False;atual.save()
        self.assertEqual(a.post('/api/embarques/checkin/',{'codigo':codigo},format='json').status_code,403)
        anterior=MatriculaAnual.objects.create(associado=self.associado,ano=timezone.localdate().year-1,ativa=True)
        self.assertEqual(a.post('/api/embarques/checkin/',{'codigo':codigo},format='json').status_code,403)
        atual.ativa=True;atual.save()
        self.assertEqual(a.post('/api/embarques/checkin/',{'codigo':codigo},format='json').status_code,201)
        self.assertTrue(MatriculaAnual.objects.filter(pk=anterior.pk).exists())
    def test_anonimo_e_usuario_sem_perfil_nao_veem_gps(self):
        a=APIClient();self.assertEqual(a.get('/api/mapa/').status_code,401)
        user=get_user_model().objects.create_user('sem-perfil')
        a.force_authenticate(user=user);self.assertEqual(a.get('/api/mapa/').status_code,403)
    def test_motorista_nao_ve_viagem_de_outro_motorista(self):
        _,vid=self.iniciar()
        user=get_user_model().objects.create_user('driver2@example.test',password='Testes!753912',email='driver2@example.test')
        perfil=Usuario.objects.create(user=user,tipo='motorista');a,_=self.api(perfil)
        self.assertEqual(a.get(f'/api/mapa/viagens/{vid}/').status_code,404)
    def test_gps_antigo_e_mapa_sem_coordenadas(self):
        _,vid=self.iniciar();v=Viagem.objects.get(pk=vid)
        LocalizacaoViagem.objects.create(viagem=v,latitude=-22.6,longitude=-54.8,capturada_em=timezone.now()-timedelta(minutes=3))
        a,_=self.api(self.associado)
        self.assertTrue(a.get('/api/mapa/').data['viagens'][0]['localizacao']['desatualizada'])
        self.ponto.latitude=None;self.ponto.longitude=None;self.ponto.save()
        self.assertIsNone(a.get('/api/mapa/').data['rotas'][0]['pontos'][0]['latitude'])
    def test_veiculo_em_manutencao_nao_inicia_viagem(self):
        self.bus.situacao='manutencao';self.bus.save()
        a,_=self.api(self.motorista)
        self.assertEqual(a.post('/api/viagens/iniciar/',{'rota_id':self.rota.pk,'sentido':'ida'},format='json').status_code,400)
        self.assertEqual(a.get('/api/mapa/').data['rotas'],[])
    def test_refresh_rotaciona_e_logout_invalida_acesso(self):
        c,d=self.api(self.associado)
        r=c.post('/api/token/refresh/',{'refresh':d['refresh']},format='json')
        self.assertEqual(r.status_code,200)
        self.assertEqual(c.post('/api/token/refresh/',{'refresh':d['refresh']},format='json').status_code,401)
        c.credentials(HTTP_AUTHORIZATION='Bearer '+r.data['access'])
        self.assertEqual(c.post('/api/logout/',{'refresh':r.data['refresh']},format='json').status_code,200)
        self.assertEqual(c.get('/api/mapa/').status_code,401)
        self.assertEqual(c.post('/api/token/refresh/',{'refresh':r.data['refresh']},format='json').status_code,401)
    def test_troca_senha_invalida_tokens_anteriores(self):
        c,d=self.api(self.associado)
        self.assertEqual(c.post('/api/senha/',{'senha_atual':'errada','nova_senha':'Outra!873462'},format='json').status_code,400)
        self.assertEqual(c.post('/api/senha/',{'senha_atual':'Testes!753912','nova_senha':'Outra!873462'},format='json').status_code,200)
        self.assertEqual(c.get('/api/mapa/').status_code,401)
        self.assertEqual(c.post('/api/token/refresh/',{'refresh':d['refresh']},format='json').status_code,401)
    def test_logout_web_exige_post_e_csrf(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/logout/').status_code,405)
        self.assertEqual(self.client.post('/logout/').status_code,302)
    def test_usuario_comum_nao_acessa_gestao(self):
        self.client.force_login(self.associado.user)
        for caminho in ['/gestao/','gestao/matriculas/','/gestao/auditoria/','/gestao/despesas/','/mapa/']:
            self.assertEqual(self.client.get('/'+caminho.lstrip('/')).status_code,403)
    def test_admin_telas_com_mesma_base(self):
        self.client.force_login(self.admin)
        for url in ['/','/mapa/','/gestao/','/gestao/instituicoes/','/gestao/cursos/','/gestao/matriculas/','/gestao/despesas/','/gestao/auditoria/']:
            r=self.client.get(url);self.assertEqual(r.status_code,200,url);self.assertTemplateUsed(r,'paginas/base.html')
    def test_despesa_cancelada_preserva_historico_e_exclui_total(self):
        self.client.force_login(self.admin)
        d=Despesa.objects.create(onibus=self.bus,data=timezone.localdate(),categoria='combustivel',descricao='Abastecimento <teste>',valor=Decimal('250.30'))
        self.assertContains(self.client.get('/gestao/despesas/'),'250,30')
        self.client.post(f'/gestao/despesas/{d.pk}/cancelar/',{'motivo':'Lançamento duplicado'})
        d.refresh_from_db();self.assertTrue(d.cancelada)
        self.assertContains(self.client.get('/gestao/despesas/'),'Total válido: R$ 0,00')
        self.assertTrue(self.client.get('/gestao/despesas/pdf/').content.startswith(b'%PDF'))
        self.assertEqual(self.client.get('/gestao/despesas/pdf/?inicio=inválido').status_code,400)
    def test_auditoria_sem_credenciais(self):
        _,d=self.api(self.associado)
        logs=list(LogAuditoria.objects.values_list('detalhes',flat=True))
        self.assertNotIn(d['access'],str(logs));self.assertNotIn('Testes!753912',str(logs))
        self.assertTrue(LogAuditoria.objects.filter(acao='login',usuario=self.associado.user).exists())
    def test_cadastro_form_telefone_curso_e_matricula(self):
        i=Instituicao.objects.create(nome='Universidade de teste');c=Curso.objects.create(instituicao=i,nome='Computação')
        form=CadastroUsuarioForm({'nome':'Nova Pessoa','email':'NOVA@example.test','telefone':'(67) 99999-1234','tipo':'associado',
            'curso':c.pk,'senha1':'Nova!843710','senha2':'Nova!843710'},ator=self.admin)
        self.assertTrue(form.is_valid(),form.errors);u=form.save()
        self.assertEqual(u.email,'nova@example.test');self.assertEqual(u.perfil.telefone,'67999991234')
        m=u.perfil.matriculas.get();self.assertEqual(m.curso_registrado,'Computação');self.assertEqual(m.instituicao_registrada,i.nome)
    def test_usuario_nao_pode_se_inativar(self):
        perfil=Usuario.objects.create(user=self.admin,tipo='administrador');self.client.force_login(self.admin)
        self.client.post(f'/usuarios/{perfil.pk}/status/');self.admin.refresh_from_db();self.assertTrue(self.admin.is_active)
