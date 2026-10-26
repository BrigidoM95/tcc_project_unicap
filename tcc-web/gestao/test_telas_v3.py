from django.test import TestCase
from embarques.tests import Cenario


class TelasAdministrativasTests(Cenario,TestCase):
    def test_navegacao_e_campos_da_revisao(self):
        admin=self.perfil('Administrador','administrador')
        self.client.force_login(admin.user)
        caminhos=['/','/usuarios/',f'/usuarios/{self.associado.pk}/',
            '/onibus/',f'/onibus/{self.onibus.pk}/detalhes/',f'/onibus/{self.onibus.pk}/editar/',
            '/rotas/',f'/rotas/{self.rota.pk}/',f'/rotas/{self.rota.pk}/editar/',
            '/operacao/',f'/operacao/{self.viagem.pk}/','/gestao/pontos/','/gestao/pontos/novo/',
            '/gestao/auditoria/','/relatorios/']
        for caminho in caminhos:
            with self.subTest(caminho=caminho):
                self.assertEqual(self.client.get(caminho).status_code,200)
        formulario=self.client.get(f'/onibus/{self.onibus.pk}/editar/')
        for campo in ('cor','ano_fabricacao','tipo_veiculo','combustivel'):
            self.assertNotContains(formulario,f'name="{campo}"')
        formulario=self.client.get(f'/rotas/{self.rota.pk}/editar/')
        for campo in ('fiscal','instituicoes','dias_operacao','pontos_ida','pontos_retorno'):
            self.assertIn(campo,formulario.context['form'].fields)
        self.assertEqual(self.client.get('/onibus/').context['objetos'].paginator.per_page,25)
        self.assertEqual(self.client.get('/rotas/').context['objetos'].paginator.per_page,25)
