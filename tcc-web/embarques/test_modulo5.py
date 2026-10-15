from django.test import TestCase, override_settings

from rotas.models import PontoEmbarque, Rota

from .models import CheckIn
from .tests import Cenario


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PontosEHistoricoTests(Cenario, TestCase):
    def setUp(self):
        super().setUp()
        self.ponto = PontoEmbarque.objects.create(rota=self.rota, nome="Praça", endereco="Centro", sentido="ida", ordem=1)
        self.volta = PontoEmbarque.objects.create(rota=self.rota, nome="Campus", endereco="Faculdade", sentido="retorno", ordem=1)
        self.url = f"/api/embarques/viagens/{self.viagem.pk}/qr/"

    def gerar_ponto(self, ponto):
        return self.cliente(self.fiscal).post(self.url, {"ponto_id": ponto}, format="json")

    def test_lista_somente_pontos_da_rota_e_sentido(self):
        r = self.cliente(self.fiscal).get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([p["id"] for p in r.data["pontos"]], [self.ponto.pk])

    def test_ponto_no_checkin_e_historico(self):
        r = self.gerar_ponto(self.ponto.pk)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["ponto_nome"], "Praça")
        self.assertEqual(self.checkin(r.data["codigo"]).status_code, 201)
        c = CheckIn.objects.get()
        self.assertEqual((c.ponto_id, c.nome_ponto), (self.ponto.pk, "Praça"))
        h = self.cliente(self.associado).get("/api/embarques/historico/")
        self.assertEqual(h.data["checkins"][0]["ponto_nome"], "Praça")

    def test_snapshot_do_ponto_permanece_apos_edicao(self):
        r = self.gerar_ponto(self.ponto.pk)
        PontoEmbarque.objects.filter(pk=self.ponto.pk).update(nome="Outro nome")
        self.checkin(r.data["codigo"])
        self.assertEqual(CheckIn.objects.get().nome_ponto, "Praça")

    def test_troca_de_ponto_invalida_codigo_anterior(self):
        r = self.gerar_ponto(self.ponto.pk)
        novo = self.gerar_ponto(None)
        self.assertEqual(self.checkin(r.data["codigo"]).status_code, 400)
        self.assertEqual(self.checkin(novo.data["codigo_manual"]).status_code, 201)
        self.assertIsNone(CheckIn.objects.get().ponto_id)

    def test_rejeita_ponto_do_sentido_ou_rota_errados(self):
        rota = Rota.objects.create(nome="Outra", origem="A", destino="B", onibus=self.onibus, horario_ida="18:00", horario_retorno="22:00")
        ponto = PontoEmbarque.objects.create(rota=rota, nome="Outro", endereco="Rua", sentido="ida", ordem=1)
        for valor in [self.volta.pk, ponto.pk, 999999, -1, "abc"]:
            with self.subTest(valor=valor):
                self.assertEqual(self.gerar_ponto(valor).status_code, 400)

    def test_qr_antigo_sem_parametro_ponto_continua_funcionando(self):
        r = self.gerar()
        self.assertEqual(self.checkin(r.data["codigo"]).status_code, 201)
        self.assertIsNone(CheckIn.objects.get().ponto_id)

    def test_nao_permite_associado_escolher_ponto_pelo_corpo(self):
        r = self.gerar_ponto(self.ponto.pk)
        c = self.cliente(self.associado).post("/api/embarques/checkin/", {
            "codigo": r.data["codigo"], "ponto_id": self.volta.pk}, format="json")
        self.assertEqual(c.status_code, 201)
        self.assertEqual(CheckIn.objects.get().ponto_id, self.ponto.pk)

    def test_capacidade_registrada_controla_vagas(self):
        self.onibus.capacidade = 10
        self.onibus.save(update_fields=["capacidade"])
        r = self.gerar()
        self.assertEqual(r.data["viagem"]["capacidade"], 1)
        self.assertEqual(self.checkin(r.data["codigo"]).status_code, 201)
        self.assertEqual(self.checkin(r.data["codigo"], self.outro).status_code, 409)

    def test_lista_pontos_exige_fiscal(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.cliente(self.associado).get(self.url).status_code, 403)
