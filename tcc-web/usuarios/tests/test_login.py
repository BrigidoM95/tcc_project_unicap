from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class LoginTestCase(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@teste.com",
            password="123456",
        )

        self.usuario_comum = User.objects.create_user(
            username="usuario@teste.com",
            email="usuario@teste.com",
            password="123456",
        )

    def test_pagina_de_login_deve_carregar_com_sucesso(self):
        resposta = self.client.get(
            reverse("login")
        )

        self.assertEqual(
            resposta.status_code,
            200,
        )

    def test_login_deve_usar_template_correto(self):
        resposta = self.client.get(
            reverse("login")
        )

        self.assertTemplateUsed(
            resposta,
            "usuarios/login.html",
        )

    def test_administrador_com_dados_corretos_deve_conseguir_logar(self):
        resposta = self.client.post(
            reverse("login"),
            {
                "username": "admin",
                "password": "123456",
            },
        )

        self.assertEqual(
            resposta.status_code,
            302,
        )

        self.assertEqual(
            resposta.url,
            reverse("home"),
        )

        self.assertIn(
            "_auth_user_id",
            self.client.session,
        )

    def test_usuario_comum_nao_deve_conseguir_logar_no_sistema_web(self):
        resposta = self.client.post(
            reverse("login"),
            {
                "username": "usuario@teste.com",
                "password": "123456",
            },
        )

        self.assertEqual(
            resposta.status_code,
            200,
        )

        self.assertNotIn(
            "_auth_user_id",
            self.client.session,
        )

        self.assertContains(
            resposta,
            "Usuário ou senha inválidos.",
        )

    def test_usuario_com_dados_invalidos_nao_deve_conseguir_logar(self):
        resposta = self.client.post(
            reverse("login"),
            {
                "username": "admin",
                "password": "senha_errada",
            },
        )

        self.assertEqual(
            resposta.status_code,
            200,
        )

        self.assertNotIn(
            "_auth_user_id",
            self.client.session,
        )

        self.assertContains(
            resposta,
            "Usuário ou senha inválidos.",
        )

    def test_logout_deve_redirecionar_para_login_com_mensagem(self):
        self.client.login(
            username="admin",
            password="123456",
        )

        resposta = self.client.get(
            reverse("logout"),
            follow=True,
        )

        self.assertRedirects(
            resposta,
            reverse("login"),
        )

        self.assertNotIn(
            "_auth_user_id",
            self.client.session,
        )

        self.assertContains(
            resposta,
            "Você saiu do sistema com segurança.",
        )

    def test_home_deve_redirecionar_usuario_nao_logado_para_login(self):
        resposta = self.client.get(
            reverse("home")
        )

        self.assertEqual(
            resposta.status_code,
            302,
        )

        self.assertIn(
            "/login/",
            resposta.url,
        )

    def test_administrador_logado_deve_acessar_home(self):
        self.client.login(
            username="admin",
            password="123456",
        )

        resposta = self.client.get(
            reverse("home")
        )

        self.assertEqual(
            resposta.status_code,
            200,
        )

        self.assertContains(
            resposta,
            "Home Administrativa",
        )