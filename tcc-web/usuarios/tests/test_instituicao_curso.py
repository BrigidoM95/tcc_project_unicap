from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from usuarios.forms import CadastroUsuarioForm, EdicaoUsuarioForm
from usuarios.models import Curso, Instituicao, Usuario


class InstituicaoCursoUsuarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('admin', password='Teste123456!')
        cls.instituicao = Instituicao.objects.create(nome='Universidade A')
        cls.curso = Curso.objects.create(nome='Computação', instituicao=cls.instituicao)
        cls.outra = Instituicao.objects.create(nome='Universidade B')
        cls.outro_curso = Curso.objects.create(nome='Computação', instituicao=cls.outra)

    def dados(self, **alteracoes):
        return {'nome': 'Estudante', 'email': 'estudante@example.test',
                'telefone': '67999998888', 'tipo': 'associado',
                'instituicao': self.instituicao.pk, 'curso': self.curso.pk, **alteracoes}

    def test_instituicao_criada_na_gestao_aparece_antes_de_ter_cursos(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(reverse('gestao:novo', args=['instituicoes']),
                                   {'nome': 'Nova instituição sem cursos', 'ativa': 'on'})
        self.assertEqual(resposta.status_code, 302)
        nova = Instituicao.objects.get(nome='Nova instituição sem cursos')
        self.assertFalse(Curso.objects.filter(instituicao=nova).exists())
        resposta = self.client.get(reverse('cadastrar_usuario'))
        self.assertContains(resposta, f'<option value="{nova.pk}">{nova.nome}</option>', html=True)
        self.assertIn(nova, resposta.context['form'].fields['instituicao'].queryset)
        self.assertContains(resposta, 'name="instituicao"')
        self.assertContains(resposta, 'name="curso"')
        self.assertContains(resposta, 'usuarios/instituicao-curso.js')

    def test_cadastro_e_edicao_salvam_curso_da_instituicao_escolhida(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(reverse('cadastrar_usuario'), self.dados())
        self.assertTemplateUsed(resposta, 'usuarios/senha_acesso.html')
        perfil = Usuario.objects.get(user__email='estudante@example.test')
        self.assertEqual(perfil.curso_id, self.curso.pk)
        url = reverse('editar_usuario', args=[perfil.pk])
        form = self.client.get(url).context['form']
        self.assertEqual(form['instituicao'].value(), self.instituicao.pk)
        self.assertEqual(form['curso'].value(), self.curso.pk)
        resposta = self.client.post(url, self.dados(instituicao=self.outra.pk, curso=self.outro_curso.pk))
        self.assertEqual(resposta.status_code, 302)
        perfil.refresh_from_db()
        self.assertEqual(perfil.curso_id, self.outro_curso.pk)

    def test_rejeita_curso_de_outra_instituicao_mesmo_com_mesmo_nome(self):
        form = CadastroUsuarioForm(self.dados(curso=self.outro_curso.pk))
        self.assertFalse(form.is_valid())
        self.assertIn('pertencente à instituição', form.errors['curso'][0])

    def test_instituicao_sem_cursos_exibe_orientacao_ao_salvar(self):
        vazia = Instituicao.objects.create(nome='Sem cursos')
        for tipo in ('associado', 'fiscal'):
            with self.subTest(tipo=tipo):
                form = CadastroUsuarioForm(self.dados(tipo=tipo, instituicao=vazia.pk, curso=''))
                self.assertFalse(form.is_valid())
                self.assertIn('Gestão > Cursos', form.errors['curso'][0])

    def test_inativos_nao_sao_oferecidos_em_novos_cadastros(self):
        self.outra.ativa = False
        self.outra.save()
        self.curso.ativo = False
        self.curso.save()
        form = CadastroUsuarioForm()
        self.assertNotIn(self.outra, form.fields['instituicao'].queryset)
        self.assertEqual(form.cursos_disponiveis, [])
        form = CadastroUsuarioForm(self.dados(instituicao=self.outra.pk, curso=self.outro_curso.pk))
        self.assertFalse(form.is_valid())
        self.assertIn('instituicao', form.errors)
        self.assertIn('curso', form.errors)

    def test_edicao_preserva_vinculo_atual_mesmo_inativado(self):
        form = CadastroUsuarioForm(self.dados())
        self.assertTrue(form.is_valid(), form.errors)
        perfil = form.save().perfil
        self.instituicao.ativa = False
        self.instituicao.save()
        self.curso.ativo = False
        self.curso.save()
        form = EdicaoUsuarioForm(self.dados(nome='Nome corrigido'), usuario=perfil)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        perfil.refresh_from_db()
        self.assertEqual(perfil.curso_id, self.curso.pk)
        self.assertEqual(perfil.user.first_name, 'Nome corrigido')

    def test_instituicao_obrigatoria_para_associado(self):
        form = CadastroUsuarioForm(self.dados(instituicao=''))
        self.assertFalse(form.is_valid())
        self.assertIn('instituicao', form.errors)

    def test_fiscal_e_motorista_podem_ser_cadastrados_sem_vinculo_academico(self):
        for tipo in ('fiscal', 'motorista'):
            with self.subTest(tipo=tipo):
                form = CadastroUsuarioForm(self.dados(tipo=tipo, instituicao='', curso=''))
                self.assertTrue(form.is_valid(), form.errors)
