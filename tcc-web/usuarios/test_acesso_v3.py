from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from embarques.tests import Cenario
from gestao.models import LogAuditoria
from .forms import CadastroUsuarioForm, EdicaoUsuarioForm
from .models import Usuario


class AcessoV3Tests(Cenario, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def criar(self):
        f = CadastroUsuarioForm({'nome':'Novo estudante','email':'novo@example.test',
            'telefone':'67999998888','tipo':'associado','instituicao':self.instituicao.pk,'curso':self.associado.curso_id})
        self.assertTrue(f.is_valid(),f.errors)
        u=f.save()
        return u, f.senha_gerada

    def test_senha_acesso_permite_uso_e_redefinicao_web_revoga(self):
        u, senha=self.criar()
        self.assertRegex(senha,r'^[A-Za-z]{3}[0-9]{3}$')
        self.assertNotEqual(u.password,senha)
        c=APIClient()
        r=c.post('/api/login/',{'identificador':u.perfil.rua,'senha':senha},format='json')
        self.assertEqual(r.status_code,200,r.data)
        self.assertNotIn('senha_provisoria',r.data['usuario'])
        token=r.data['access'];refresh=r.data['refresh']
        c.credentials(HTTP_AUTHORIZATION='Bearer '+token)
        bloqueio=c.get('/api/viagens/hoje/')
        self.assertEqual(bloqueio.status_code,200)
        nova='SenhaDefinitiva#8472'
        r=c.post('/api/senha/',{'senha_atual':senha,'nova_senha':nova},format='json')
        self.assertEqual(r.status_code,410,r.data)
        admin=self.perfil('AdministradorSenha','administrador')
        self.client.force_login(admin.user)
        r=self.client.post(f'/usuarios/{u.perfil.pk}/redefinir-senha/',{'new_password1':nova,'new_password2':nova})
        self.assertEqual(r.status_code,302)
        u.perfil.refresh_from_db();self.assertIsNotNone(u.perfil.senha_definida_em)
        self.assertEqual(c.post('/api/token/refresh/',{'refresh':refresh},format='json').status_code,401)
        c.credentials()
        self.assertEqual(c.post('/api/login/',{'identificador':u.email,'senha':nova},format='json').status_code,200)
        self.assertNotIn(senha,str(list(LogAuditoria.objects.values_list('detalhes',flat=True))))

    def test_rua_permanece_apos_editar_e_inativar(self):
        u,_=self.criar();p=u.perfil;rua=p.rua
        f=EdicaoUsuarioForm({'nome':'Nome corrigido','email':'corrigido@example.test',
            'telefone':'67999998888','tipo':'fiscal','instituicao':p.curso.instituicao_id,'curso':p.curso_id},usuario=p)
        self.assertTrue(f.is_valid(),f.errors);f.save()
        u.is_active=False;u.save(update_fields=['is_active']);p.refresh_from_db()
        self.assertEqual(p.rua,rua)

    def test_cadastro_associado_requer_curso_fiscal_nao(self):
        dados={'nome':'Fiscal','email':'fiscalnovo@example.test','telefone':'67999998888','tipo':'associado'}
        f=CadastroUsuarioForm(dados);self.assertFalse(f.is_valid());self.assertIn('curso',f.errors)
        f=CadastroUsuarioForm({**dados,'tipo':'fiscal'});self.assertTrue(f.is_valid(),f.errors)
