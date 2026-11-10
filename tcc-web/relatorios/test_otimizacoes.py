from datetime import timedelta

from django.db import connection
from django.db.models import Count, F, Max, Min, OuterRef, Subquery
from django.db.models.functions import TruncDate
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from embarques.models import CheckIn
from embarques.tests import Cenario
from usuarios.models import Usuario
from .services import RelatorioEmbarques
from .views import pagina


class FrequenciaOtimizadaTests(Cenario,TestCase):
    def setUp(self):
        super().setUp()
        agora=timezone.now()
        self.inicio=(agora-timedelta(days=6)).date()
        self.fim=agora.date()
        itens=[]
        for dia in range(5):
            for pessoa in [self.associado,self.outro]:
                itens.append(CheckIn(viagem=self.viagem,associado=pessoa,fiscal=self.fiscal,
                    sentido='ida',legado=True,vaga=len(itens)+1,data_servico=self.inicio+timedelta(days=dia),
                    nome_associado='Nome anterior' if dia<4 else str(pessoa),rua_associado=pessoa.rua,
                    lido_em=agora-timedelta(days=5-dia)))
        CheckIn.objects.bulk_create(itens)

    def relatorio(self,**extras):
        return RelatorioEmbarques({'data_inicial':self.inicio,'data_final':self.fim,**extras})

    def frequencia_anterior(self,rel):
        ultimo=rel.registros.filter(associado_id=OuterRef('associado_id'))
        return rel.registros.order_by().values('associado_id',instituicao=F('associado__curso__instituicao__nome')).annotate(
            nome=Subquery(ultimo.values('nome_associado')[:1]),rua=Subquery(ultimo.values('rua_associado')[:1]),
            embarques=Count('pk'),dias=Count(TruncDate('ocorrido_em',tzinfo=rel.fuso),distinct=True),
            primeira_presenca=Min('ocorrido_em'),ultima_presenca=Max('ocorrido_em'),
        ).order_by('-embarques','nome','associado_id')

    def test_resultados_preservados_com_filtros_e_nomes_historicos(self):
        CheckIn.objects.filter(associado=self.outro).order_by('pk').first().delete()
        for filtros in [{},{'freq_q':'Nome anterior'},{'associado':self.associado},
                        {'freq_instituicao':self.instituicao},{'sentido':'retorno'}]:
            rel=self.relatorio(**filtros)
            self.assertEqual(list(rel.frequencia),list(self.frequencia_anterior(rel)))

    def test_consulta_externa_uma_linha_por_pessoa_sem_group_by(self):
        rel=self.relatorio()
        self.assertEqual(rel.frequencia.model,Usuario)
        self.assertIsNone(rel.frequencia.query.group_by)
        with CaptureQueriesContext(connection) as queries:total=rel.frequencia.count()
        self.assertEqual(total,2)
        self.assertEqual(len(queries),1)
        self.assertNotIn('GROUP BY',queries[0]['sql'])
        self.assertNotIn('MIN(',queries[0]['sql'])

    def test_paginador_reutiliza_resumo_sem_recontar_frequencia(self):
        rel=self.relatorio();total=rel.resumo['associados']
        with CaptureQueriesContext(connection) as queries:
            resultado=pagina(rel.frequencia,RequestFactory().get('/relatorios/'),'pagina_frequencia',total=total)
        self.assertEqual(len(queries),0)
        self.assertEqual(resultado.paginator.count,2)
        self.assertEqual(len(resultado),2)
