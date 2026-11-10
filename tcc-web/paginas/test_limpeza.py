from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import Resolver404, resolve
from django.utils import timezone

from embarques.tests import Cenario
from rotas import api_v3
from rotas.models import LocalizacaoViagem


class CompatibilidadeRotasTests(SimpleTestCase):
    def test_aliases_restantes_usam_a_operacao_atual(self):
        caminhos = {
            "/api/embarques/viagens/": api_v3.HojeApi,
            "/api/embarques/viagens/1/qr/": api_v3.QrApi,
            "/api/embarques/viagens/1/presencas/": api_v3.EmbarquesApi,
            "/api/embarques/checkin/": api_v3.CheckinApi,
            "/api/embarques/historico/": api_v3.HistoricoApi,
            "/api/viagens/iniciar/": api_v3.LegadoDesativadoApi,
            "/api/viagens/1/finalizar/": api_v3.LegadoDesativadoApi,
            "/api/viagens/1/localizacao/": api_v3.LegadoDesativadoApi,
        }
        for caminho, classe in caminhos.items():
            with self.subTest(caminho=caminho):
                self.assertIs(resolve(caminho).func.view_class, classe)
        with self.assertRaises(Resolver404):
            resolve("/api/viagens/painel/")


class IndiceGpsTests(Cenario, TestCase):
    def test_indice_unico_atende_viagem_e_preserva_integridade(self):
        tabela = LocalizacaoViagem._meta.db_table
        with connection.cursor() as cursor:
            indices = connection.introspection.get_constraints(cursor, tabela)
        self.assertNotIn("loc_viagem_captura_idx", indices)
        self.assertFalse(any(
            i["index"] and not i["unique"] and i["columns"] == ["viagem_id"]
            for i in indices.values()
        ))
        unico = indices["loc_viagem_captura_unica"]
        self.assertTrue(unico["unique"])
        self.assertEqual(unico["columns"], ["viagem_id", "capturada_em"])
        self.assertTrue(any(i["foreign_key"] for i in indices.values()))
        agora = timezone.now()
        for segundos in (0, 10, 20):
            LocalizacaoViagem.objects.create(
                viagem=self.viagem, latitude=-22, longitude=-54,
                capturada_em=agora + timedelta(seconds=segundos),
            )
        consulta = LocalizacaoViagem.objects.filter(viagem=self.viagem).order_by("-capturada_em")
        self.assertEqual(consulta.first().capturada_em, agora + timedelta(seconds=20))
        # O SQLite explicita o uso do índice composto também pelo prefixo viagem.
        if connection.vendor == "sqlite":
            self.assertIn("USING INDEX", consulta.explain())
        with self.assertRaises(IntegrityError), transaction.atomic():
            LocalizacaoViagem.objects.create(
                viagem=self.viagem, latitude=-22, longitude=-54, capturada_em=agora,
            )


# O stub histórico pode já ter sido retirado de INSTALLED_APPS. Ativá-lo aqui
# mantém o ensaio de atualização de uma base antiga no banco isolado dos testes.
APPS_COM_HISTORICO = [*settings.INSTALLED_APPS]
if "associados" not in APPS_COM_HISTORICO:
    APPS_COM_HISTORICO.append("associados")


@override_settings(INSTALLED_APPS=APPS_COM_HISTORICO)
class GuardasMigracoesTests(Cenario, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.destinos = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.linhas_legadas = []
        self.addCleanup(self.restaurar_schema)

    def migrar(self, app, nome):
        executor = MigrationExecutor(connection)
        destino = [(app, nome)]
        executor.migrate(destino)
        return executor.loader.project_state(destino).apps

    def restaurar_schema(self):
        # Remove apenas as linhas artificiais criadas por estes testes, para
        # permitir que a guarda conclua a migração após a verificação de recusa.
        tabelas = connection.introspection.table_names()
        with connection.cursor() as cursor:
            for tabela, pk in self.linhas_legadas:
                if tabela in tabelas:
                    cursor.execute(
                        f"DELETE FROM {connection.ops.quote_name(tabela)} WHERE id = %s", [pk]
                    )
        MigrationExecutor(connection).migrate(self.destinos)

    def verificar_modelo_vazio(self, app, modelo, destino):
        estado = self.migrar(app, "0001_initial")
        antigo = estado.get_model(app, modelo)
        linha = antigo.objects.create()
        self.linhas_legadas.append((antigo._meta.db_table, linha.pk))
        with self.assertRaisesMessage(RuntimeError, "contém registros"):
            self.migrar(app, destino)
        self.assertTrue(antigo.objects.filter(pk=linha.pk).exists())
        linha.delete()
        self.migrar(app, destino)
        self.assertNotIn(antigo._meta.db_table, connection.introspection.table_names())

    def test_associado_preenchido_impede_remocao(self):
        self.verificar_modelo_vazio("associados", "Associado", "0002_remove_associado_vazio")

    def test_pagina_preenchida_impede_remocao(self):
        self.verificar_modelo_vazio("paginas", "Pagina", "0002_remove_pagina_vazia")

    def test_codigo_preenchido_impede_remocao_e_sessao_vazia_e_preservada(self):
        estado = self.migrar("embarques", "0006_reservaassento_ponto_reservaassento_trajeto")
        sessao = estado.get_model("embarques", "SessaoEmbarque")
        linha = sessao.objects.create(
            viagem_id=self.viagem.pk, fiscal_id=self.fiscal.pk, codigo_curto="123456",
            expira_em=timezone.now() + timedelta(hours=1), data_servico=self.viagem.data_servico,
        )
        self.linhas_legadas.append((sessao._meta.db_table, linha.pk))
        with self.assertRaisesMessage(RuntimeError, "codigo_curto preenchido"):
            self.migrar("embarques", "0007_remove_codigo_curto_sem_uso")
        self.assertEqual(sessao.objects.get(pk=linha.pk).codigo_curto, "123456")
        sessao.objects.filter(pk=linha.pk).update(codigo_curto=None)
        novo = self.migrar("embarques", "0007_remove_codigo_curto_sem_uso")
        preservada = novo.get_model("embarques", "SessaoEmbarque").objects.get(pk=linha.pk)
        self.assertEqual(preservada.token, linha.token)
        self.assertEqual(preservada.viagem_id, self.viagem.pk)
