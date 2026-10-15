from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from embarques.models import CheckIn
from onibus.models import Onibus
from rotas.models import PontoEmbarque, Rota, Viagem
from usuarios.models import Usuario

from .forms import FiltrosRelatorioForm
from .services import RelatorioEmbarques, fuso_relatorios
from .views import painel


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RelatoriosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def perfil(nome, tipo):
            u = get_user_model().objects.create_user(username=nome, first_name=nome, password="Teste123456!")
            return Usuario.objects.create(user=u, tipo=tipo)
        cls.admin = perfil("Gestor", "administrador")
        cls.ana = perfil("Ana", "associado")
        cls.beto = perfil("Beto", "associado")
        cls.fiscal = perfil("Fiscal", "fiscal")
        cls.motorista = perfil("Motorista", "motorista")
        cls.onibus = Onibus.objects.create(nome="Azul", placa="ABC1234", capacidade=4,
                                           motorista=cls.motorista, foto="teste.jpg")
        cls.rota = Rota.objects.create(nome="Universidade", origem="Caarapó", destino="Dourados", onibus=cls.onibus,
                                       horario_ida="17:40", horario_retorno="22:10")
        cls.ponto = PontoEmbarque.objects.create(rota=cls.rota, nome="Praça Central", endereco="Centro", sentido="ida", ordem=1)
        cls.ponto_volta = PontoEmbarque.objects.create(rota=cls.rota, nome="Faculdade", endereco="Campus", sentido="retorno", ordem=1)
        cls.ids = []
        cls.viagens = []
        for dia, hora, sentido in [(10, 17, "ida"), (10, 22, "retorno"), (11, 23, "retorno"), (11, 12, "ida")]:
            inicio = datetime(2026, 10, dia, hora, tzinfo=fuso_relatorios())
            cls.viagens.append(Viagem.objects.create(rota=cls.rota, onibus=cls.onibus, motorista=cls.motorista,
                sentido=sentido, iniciada_em=inicio, finalizada_em=inicio+timedelta(minutes=45), status="finalizada"))
        for viagem, associado, ponto, nome in [
            (cls.viagens[0], cls.ana, cls.ponto, "Ana"),
            (cls.viagens[0], cls.beto, cls.ponto, "Beto"),
            (cls.viagens[1], cls.ana, cls.ponto_volta, "Ana Silva"),
            (cls.viagens[2], cls.ana, None, "Ana Silva"),
        ]:
            c = CheckIn.objects.create(viagem=viagem, associado=associado, fiscal=cls.fiscal,
                vaga=viagem.checkins.count()+1, nome_associado=nome, rua_associado=associado.rua,
                placa_onibus=cls.onibus.placa, codigo_onibus=cls.onibus.codigo,
                ponto=ponto, nome_ponto=ponto.nome if ponto else "")
            CheckIn.objects.filter(pk=c.pk).update(registrado_em=viagem.iniciada_em+timedelta(minutes=30))
            cls.ids.append(c.pk)
        cls.filtros = {"data_inicial": "2026-10-10", "data_final": "2026-10-11"}

    def setUp(self):
        self.client.force_login(self.admin.user)

    def relatorio(self, **extras):
        form = FiltrosRelatorioForm({**self.filtros, **extras})
        self.assertTrue(form.is_valid(), form.errors)
        return RelatorioEmbarques(form.cleaned_data)

    def test_resumo_pessoas_e_embarques_separados(self):
        self.assertEqual(self.relatorio().resumo, {
            "embarques": 4, "associados": 2, "viagens_com_embarque": 3,
            "onibus_utilizados": 1, "sem_ponto": 1,
        })

    def test_frequencia_agrupa_id_apesar_de_mudanca_de_nome(self):
        ana = next(x for x in self.relatorio().frequencia if x["associado_id"] == self.ana.pk)
        self.assertEqual((ana["embarques"], ana["dias"], ana["nome"]), (3, 2, "Ana Silva"))

    def test_fuso_inclui_noite_local_do_dia_final(self):
        ultimo = CheckIn.objects.get(pk=self.ids[-1])
        self.assertEqual(ultimo.registrado_em.astimezone(dt_timezone.utc).day, 12)
        rel = self.relatorio(data_inicial="2026-10-11")
        self.assertEqual(rel.resumo["embarques"], 1)
        CheckIn.objects.filter(pk=ultimo.pk).update(registrado_em=datetime(2026, 10, 12, 0, tzinfo=fuso_relatorios()))
        self.assertEqual(self.relatorio(data_inicial="2026-10-11").resumo["embarques"], 0)

    def test_grafico_dias_sem_registro_e_totais(self):
        dias = self.relatorio(data_inicial="2026-10-09").por_dia
        self.assertEqual([x["total"] for x in dias], [0, 3, 1])

    def test_ocupacao_nao_encolhe_ao_filtrar_associado(self):
        rel = self.relatorio(associado=self.ana.pk, sentido="ida")
        self.assertEqual(rel.resumo["embarques"], 1)
        v = rel.preparar_viagens(rel.viagens)[0]
        self.assertEqual((v["presentes"], v["capacidade"], v["vagas"], v["ocupacao"]), (2, 4, 2, 50.0))

    def test_inclui_viagem_vazia_e_capacidade_antiga_desconhecida(self):
        Viagem.objects.filter(pk=self.viagens[-1].pk).update(capacidade_registrada=None)
        rel = self.relatorio()
        self.assertEqual(rel.viagens.count(), 4)
        vazia = next(v for v in rel.preparar_viagens(rel.viagens) if v["id"] == self.viagens[-1].pk)
        self.assertEqual(vazia["presentes"], 0)
        self.assertIsNone(vazia["ocupacao"])
        self.assertIsNone(vazia["vagas"])

    def test_capacidade_e_identificacao_historicas_nao_mudam_com_cadastro(self):
        Onibus.objects.filter(pk=self.onibus.pk).update(capacidade=10, placa="XYZ9876")
        Rota.objects.filter(pk=self.rota.pk).update(nome="Nome novo")
        rel = self.relatorio()
        v = next(v for v in rel.preparar_viagens(rel.viagens) if v["id"] == self.viagens[0].pk)
        self.assertEqual((v["capacidade"], v["placa"], v["rota"]), (4, "ABC1234", "Universidade"))

    def test_filtros_combinados(self):
        rel = self.relatorio(onibus=self.onibus.pk, rota=self.rota.pk, associado=self.ana.pk,
                            sentido="ida", ponto=self.ponto.pk)
        self.assertEqual(rel.resumo["embarques"], 1)

    def test_sem_ponto_e_pontos_agregados(self):
        self.assertEqual(self.relatorio(sem_ponto="on").resumo["embarques"], 1)
        self.assertEqual(sum(p["total"] for p in self.relatorio().por_ponto), 4)

    def test_nomes_originais_de_pontos(self):
        PontoEmbarque.objects.filter(pk=self.ponto.pk).update(nome="Novo nome")
        ponto = next(p for p in self.relatorio().por_ponto if p["ponto_id"] == self.ponto.pk)
        self.assertEqual(ponto["nome"], "Praça Central")

    def test_inativos_continuam_no_historico_e_filtros(self):
        self.ana.user.is_active = False
        self.ana.user.save(update_fields=["is_active"])
        Onibus.objects.filter(pk=self.onibus.pk).update(status="inativo")
        Rota.objects.filter(pk=self.rota.pk).update(status="inativa")
        self.assertEqual(self.relatorio(associado=self.ana.pk).resumo["embarques"], 3)

    def test_embarque_de_viagem_iniciada_fora_do_periodo(self):
        Viagem.objects.filter(pk=self.viagens[0].pk).update(iniciada_em=datetime(2026, 10, 9, 23, tzinfo=fuso_relatorios()))
        self.assertIn(self.viagens[0].pk, list(self.relatorio().viagens.values_list("pk", flat=True)))

    def test_filtros_invalidos_nao_mostram_resultados(self):
        for dados in [
            {"data_final": "2026-10-01"}, {"data_inicial": "invalida"}, {"data_inicial": ""},
            {"data_inicial": "2024-01-01"}, {"associado": "999999"}, {"sentido": "invalido"},
            {"ponto": self.ponto.pk, "sentido": "retorno"},
            {"ponto": self.ponto.pk, "sem_ponto": "on"},
        ]:
            with self.subTest(dados=dados):
                resposta = self.client.get(reverse("relatorios:painel"), {**self.filtros, **dados})
                self.assertFalse(resposta.context["form"].is_valid())
                self.assertNotIn("relatorio", resposta.context)

    def test_pagina_e_navegacao(self):
        resposta = self.client.get(reverse("relatorios:painel"), self.filtros)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Ana Silva")
        self.assertContains(resposta, "relatorios/relatorios.css")
        self.assertContains(self.client.get("/"), reverse("relatorios:painel"))
        self.assertIn("no-store", resposta["Cache-Control"])

    def test_padrao_mes_atual(self):
        resposta = self.client.get(reverse("relatorios:painel"))
        hoje = timezone.localdate(timezone=fuso_relatorios())
        self.assertEqual(resposta.context["form"].cleaned_data["data_inicial"], hoje.replace(day=1))

    def test_periodo_sem_resultado(self):
        resposta = self.client.get(reverse("relatorios:painel"), {"data_inicial": "2025-01-01", "data_final": "2025-01-02"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Nenhum embarque encontrado")

    def test_acesso_anonimo(self):
        self.client.logout()
        for url in ("relatorios:painel", "relatorios:pdf"):
            self.assertEqual(self.client.get(reverse(url), self.filtros).status_code, 302)

    def test_outros_perfis_negados(self):
        for perfil in (self.ana, self.fiscal, self.motorista):
            self.client.force_login(perfil.user)
            for url in ("relatorios:painel", "relatorios:pdf"):
                with self.subTest(perfil=perfil.tipo, url=url):
                    self.assertEqual(self.client.get(reverse(url), self.filtros).status_code, 403)

    def test_administrador_inativo_negado(self):
        pedido = RequestFactory().get(reverse("relatorios:painel"))
        pedido.user = self.admin.user
        pedido.user.is_active = False
        with self.assertRaises(PermissionDenied):
            painel(pedido)

    def test_superusuario_sem_perfil(self):
        user = get_user_model().objects.create_superuser(username="root", password="Teste123456!")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("relatorios:painel"), self.filtros).status_code, 200)

    def test_exporta_pdf_e_rejeita_filtro_invalido(self):
        r = self.client.get(reverse("relatorios:pdf"), self.filtros)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn("no-store", r["Cache-Control"])
        r = self.client.get(reverse("relatorios:pdf"), {**self.filtros, "sentido": "erro"})
        self.assertEqual(r.status_code, 400)

    def test_exportacao_sem_resultados(self):
        r = self.client.get(reverse("relatorios:pdf"), {"data_inicial": "2025-01-01", "data_final": "2025-01-02"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF"))

    def test_post_nao_altera_dados(self):
        antes = CheckIn.objects.count()
        self.assertEqual(self.client.post(reverse("relatorios:painel")).status_code, 405)
        self.assertEqual(CheckIn.objects.count(), antes)

    def test_texto_do_usuario_e_escapado(self):
        CheckIn.objects.filter(pk=self.ids[0]).update(nome_associado="<script>alert('x')</script>")
        r = self.client.get(reverse("relatorios:painel"), self.filtros)
        self.assertNotContains(r, "<script>alert")
        self.assertContains(r, "&lt;script&gt;")
        self.assertEqual(self.client.get(reverse("relatorios:pdf"), self.filtros).status_code, 200)

    def test_paginacao_preserva_filtros_e_pdf_completo(self):
        viagem = self.viagens[0]
        novos = []
        for i in range(30):
            u = get_user_model().objects.create_user(username=f"teste{i}")
            p = Usuario.objects.create(user=u, tipo="associado")
            novos.append(CheckIn(viagem=viagem, associado=p, fiscal=self.fiscal, vaga=i+3,
                nome_associado=f"Pessoa {i}", rua_associado=p.rua, codigo_onibus=self.onibus.codigo, placa_onibus=self.onibus.placa))
        CheckIn.objects.bulk_create(novos)
        CheckIn.objects.filter(pk__in=[x.pk for x in novos]).update(registrado_em=viagem.iniciada_em)
        r = self.client.get(reverse("relatorios:painel"), {**self.filtros, "pagina_embarques": 2})
        self.assertEqual(r.context["embarques"].number, 2)
        self.assertEqual(r.context["embarques"].paginator.count, 34)
        self.assertIn("data_inicial=2026-10-10", r.context["parametros"])
        with patch("relatorios.pdf.gerar_pdf", return_value=b"%PDF-test") as gerar:
            self.client.get(reverse("relatorios:pdf"), {**self.filtros, "pagina_embarques": 2})
            self.assertEqual(gerar.call_args.args[0].registros.count(), 34)
