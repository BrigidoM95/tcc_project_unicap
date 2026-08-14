import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Usuario


User = get_user_model()


class Modulo1UsuariosTests(TestCase):

    def setUp(self):
        self.senha = "SenhaTeste123!"

        # Administrador
        self.admin = User.objects.create_superuser(
            username="admin@teste.com",
            email="admin@teste.com",
            password=self.senha,
        )

        # Associado
        self.associado_user = User.objects.create_user(
            username="associado@teste.com",
            email="associado@teste.com",
            password=self.senha,
            first_name="Associado Teste",
        )

        self.associado = Usuario.objects.create(
            user=self.associado_user,
            tipo=Usuario.Tipo.ASSOCIADO,
        )

        # Fiscal
        self.fiscal_user = User.objects.create_user(
            username="fiscal@teste.com",
            email="fiscal@teste.com",
            password=self.senha,
            first_name="Fiscal Teste",
        )

        self.fiscal = Usuario.objects.create(
            user=self.fiscal_user,
            tipo=Usuario.Tipo.FISCAL,
        )

        # Motorista
        self.motorista_user = User.objects.create_user(
            username="motorista@teste.com",
            email="motorista@teste.com",
            password=self.senha,
            first_name="Motorista Teste",
        )

        self.motorista = Usuario.objects.create(
            user=self.motorista_user,
            tipo=Usuario.Tipo.MOTORISTA,
        )

    # =========================================================
    # RUA
    # =========================================================

    def test_associado_recebe_rua_automaticamente(self):
        self.assertIsNotNone(self.associado.rua)

        self.assertEqual(
            self.associado.rua,
            f"RUA{self.associado.pk:06d}",
        )

    def test_fiscal_nao_possui_rua(self):
        self.assertIsNone(self.fiscal.rua)

    def test_motorista_nao_possui_rua(self):
        self.assertIsNone(self.motorista.rua)

    def test_rua_removido_quando_associado_muda_de_tipo(self):
        self.associado.tipo = Usuario.Tipo.FISCAL
        self.associado.save()

        self.associado.refresh_from_db()

        self.assertIsNone(self.associado.rua)

    def test_rua_volta_quando_usuario_vira_associado(self):
        usuario = self.fiscal

        usuario.tipo = Usuario.Tipo.ASSOCIADO
        usuario.save()

        usuario.refresh_from_db()

        self.assertEqual(
            usuario.rua,
            f"RUA{usuario.pk:06d}",
        )

    # =========================================================
    # PERMISSÕES WEB
    # =========================================================

    def test_administrador_acessa_lista_de_usuarios(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("listar_usuarios")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_associado_nao_acessa_lista_de_usuarios(self):
        self.client.force_login(self.associado_user)

        response = self.client.get(
            reverse("listar_usuarios")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_fiscal_nao_acessa_lista_de_usuarios(self):
        self.client.force_login(self.fiscal_user)

        response = self.client.get(
            reverse("listar_usuarios")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_motorista_nao_acessa_lista_de_usuarios(self):
        self.client.force_login(self.motorista_user)

        response = self.client.get(
            reverse("listar_usuarios")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    # =========================================================
    # API - ASSOCIADO
    # =========================================================

    def test_associado_consegue_login_na_api(self):
        response = self.client.post(
            reverse("api_login"),
            data=json.dumps({
                "email": self.associado_user.email,
                "senha": self.senha,
            }),
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        dados = response.json()

        self.assertIn(
            "access",
            dados,
        )

        self.assertIn(
            "refresh",
            dados,
        )

        self.assertEqual(
            dados["usuario"]["tipo"],
            Usuario.Tipo.ASSOCIADO,
        )

        self.assertEqual(
            dados["usuario"]["rua"],
            self.associado.rua,
        )

    # =========================================================
    # API - FISCAL
    # =========================================================

    def test_fiscal_consegue_login_na_api(self):
        response = self.client.post(
            reverse("api_login"),
            data=json.dumps({
                "email": self.fiscal_user.email,
                "senha": self.senha,
            }),
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        dados = response.json()

        self.assertEqual(
            dados["usuario"]["tipo"],
            Usuario.Tipo.FISCAL,
        )

        self.assertIsNone(
            dados["usuario"]["rua"],
        )

    # =========================================================
    # API - MOTORISTA
    # =========================================================

    def test_motorista_consegue_login_na_api(self):
        response = self.client.post(
            reverse("api_login"),
            data=json.dumps({
                "email": self.motorista_user.email,
                "senha": self.senha,
            }),
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        dados = response.json()

        self.assertEqual(
            dados["usuario"]["tipo"],
            Usuario.Tipo.MOTORISTA,
        )

        self.assertIsNone(
            dados["usuario"]["rua"],
        )

    # =========================================================
    # API - BLOQUEIOS
    # =========================================================

    def test_administrador_nao_consegue_login_na_api(self):
        response = self.client.post(
            reverse("api_login"),
            data=json.dumps({
                "email": self.admin.email,
                "senha": self.senha,
            }),
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_senha_incorreta_e_recusada(self):
        response = self.client.post(
            reverse("api_login"),
            data=json.dumps({
                "email": self.associado_user.email,
                "senha": "senha-errada",
            }),
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            401,
        )

        self.assertNotIn(
            "access",
            response.json(),
        )

    def test_usuario_inativo_nao_consegue_login_na_api(self):
        self.associado_user.is_active = False
        self.associado_user.save()

        response = self.client.post(
            reverse("api_login"),
            data=json.dumps({
                "email": self.associado_user.email,
                "senha": self.senha,
            }),
            content_type="application/json",
        )

        self.assertNotEqual(
            response.status_code,
            200,
        )

        self.assertNotIn(
            "access",
            response.json(),
        )

    def test_campos_obrigatorios_na_api(self):
        response = self.client.post(
            reverse("api_login"),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )