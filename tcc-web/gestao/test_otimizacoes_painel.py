from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from embarques.tests import Cenario
from rotas.forms import RotaForm
from rotas.models import Ponto, PontoEmbarque, Viagem
from .auditoria import AuditoriaMiddleware
from .models import LogAuditoria


class OtimizacoesPainelTests(Cenario,TestCase):
    def setUp(self):
        super().setUp()
        self.admin=self.perfil('GestorOtimizacoes','administrador')
        self.client.force_login(self.admin.user)

    def test_filtro_auditoria_tem_uma_opcao_por_acao(self):
        LogAuditoria.objects.bulk_create([LogAuditoria(acao='repetida',descricao='Teste') for _ in range(50)])
        resposta=self.client.get('/gestao/auditoria/')
        acoes=list(resposta.context['acoes'])
        self.assertEqual(acoes,sorted(set(acoes)))
        self.assertEqual(acoes.count('repetida'),1)

    def test_403_limitado_por_usuario_e_caminho_por_dez_minutos(self):
        middleware=AuditoriaMiddleware(lambda request:HttpResponse(status=403))
        def chamar(usuario,caminho):
            request=RequestFactory().get(caminho);request.user=usuario
            return middleware(request)
        with patch('django.core.cache.backends.locmem.time.time',return_value=1000):
            chamar(self.fiscal.user,'/operacao/?tentativa=1')
            chamar(self.fiscal.user,'/operacao/?tentativa=2')
            chamar(self.associado.user,'/operacao/')
            chamar(self.fiscal.user,'/gestao/')
        self.assertEqual(LogAuditoria.objects.filter(acao='acesso_negado').count(),3)
        with patch('django.core.cache.backends.locmem.time.time',return_value=1599):
            chamar(self.fiscal.user,'/operacao/')
        self.assertEqual(LogAuditoria.objects.filter(acao='acesso_negado').count(),3)
        with patch('django.core.cache.backends.locmem.time.time',return_value=1601):
            chamar(self.fiscal.user,'/operacao/')
        self.assertEqual(LogAuditoria.objects.filter(acao='acesso_negado').count(),4)

    def test_resumo_onibus_e_rotas_usa_uma_agregacao(self):
        for url,tabela,ativo,inativo in [('/onibus/','onibus_onibus','total_ativos','total_inativos'),
                                         ('/rotas/','rotas_rota','total_ativas','total_inativas')]:
            with CaptureQueriesContext(connection) as queries:
                resposta=self.client.get(url)
            self.assertEqual(resposta.context['total'],1)
            self.assertEqual(resposta.context[ativo],1)
            self.assertEqual(resposta.context[inativo],0)
            counts=[q['sql'] for q in queries if 'COUNT(' in q['sql'] and f'FROM "{tabela}"' in q['sql']]
            self.assertEqual(len(counts),2)  # Um resumo e um COUNT simples da paginação.
            self.assertTrue(any(f'AS "{ativo}"' in sql and f'AS "{inativo}"' in sql for sql in counts))

    def test_api_onibus_exige_administrador_em_todas_operacoes(self):
        chamadas=[('get','/api/onibus/',None),('post','/api/onibus/',{}),
            ('get',f'/api/onibus/{self.onibus.pk}/',None),
            ('patch',f'/api/onibus/{self.onibus.pk}/',{}),
            ('put',f'/api/onibus/{self.onibus.pk}/',{}),
            ('post',f'/api/onibus/{self.onibus.pk}/desativar/',{}),
            ('post',f'/api/onibus/{self.onibus.pk}/reativar/',{})]
        for perfil in [self.associado,self.motorista,self.fiscal]:
            cliente=self.cliente(perfil)
            for metodo,url,dados in chamadas:
                with self.subTest(tipo=perfil.tipo,metodo=metodo,url=url):
                    resposta=getattr(cliente,metodo)(url,dados,format='json')
                    self.assertEqual(resposta.status_code,403,resposta.data)
        self.client.logout()
        self.assertEqual(self.client.get('/api/onibus/').status_code,401)
        gestor=self.cliente(self.admin)
        self.assertEqual(gestor.get('/api/onibus/').status_code,200)
        self.assertEqual(gestor.get(f'/api/onibus/{self.onibus.pk}/').status_code,200)

    def test_detalhe_mostra_ultima_redefinicao_de_senha(self):
        url=reverse('detalhe_usuario',args=[self.associado.pk])
        self.assertContains(self.client.get(url),'Não registrada')
        instante=timezone.now()-timedelta(days=2)
        type(self.associado).objects.filter(pk=self.associado.pk).update(senha_definida_em=instante)
        resposta=self.client.get(url)
        self.assertContains(resposta,'Última redefinição de senha')
        self.assertContains(resposta,timezone.localtime(instante).strftime('%d/%m/%Y %H:%M'))

    def preparar_pontos(self):
        Viagem.objects.filter(pk=self.viagem.pk).update(status='finalizada',etapa='encerrada',finalizada_em=timezone.now())
        self.ponto_ida=Ponto.objects.create(nome='Praça',endereco='Centro')
        self.ponto_volta=Ponto.objects.create(nome='Campus',endereco='Faculdade')
        PontoEmbarque.objects.filter(pk=self.ponto.pk).update(ponto=self.ponto_ida)
        PontoEmbarque.objects.filter(pk=self.volta.pk).update(ponto=self.ponto_volta)

    def formulario_rota(self,**extras):
        dados={'nome':self.rota.nome,'destino':self.rota.destino,'onibus':self.onibus.pk,
            'fiscal':self.fiscal.pk,'instituicoes':[self.instituicao.pk],
            'dias_operacao':[str(i) for i in range(7)],'horario_ida':'00:00','horario_retorno':'23:59',
            'pontos_ida':[self.ponto_ida.pk],'pontos_retorno':[self.ponto_volta.pk]}
        form=RotaForm({**dados,**extras},instance=self.rota)
        self.assertTrue(form.is_valid(),form.errors)
        return form

    def test_editar_rota_sem_mudar_pontos_nao_grava_nem_audita_pontos(self):
        self.preparar_pontos()
        form=self.formulario_rota()
        logs=LogAuditoria.objects.filter(modelo='rotas.pontoembarque').count()
        with CaptureQueriesContext(connection) as queries:form.save()
        self.assertFalse(any(q['sql'].startswith('UPDATE "rotas_pontoembarque"') for q in queries))
        self.assertEqual(LogAuditoria.objects.filter(modelo='rotas.pontoembarque').count(),logs)
        self.assertEqual(list(self.rota.pontos.values_list('ordem',flat=True)),[1,1])

    def test_remover_e_reativar_ponto_preserva_id_ordem_e_um_log_por_alteracao(self):
        self.preparar_pontos()
        novo=Ponto.objects.create(nome='Terminal',endereco='Rua 2')
        logs=LogAuditoria.objects.filter(modelo='rotas.pontoembarque').count()
        self.formulario_rota(pontos_ida=[novo.pk]).save()
        self.ponto.refresh_from_db();self.assertFalse(self.ponto.ativo);self.assertEqual(self.ponto.ordem,1)
        adicionado=self.rota.pontos.get(ponto=novo)
        self.assertEqual(adicionado.ordem,2)
        self.assertEqual(LogAuditoria.objects.filter(modelo='rotas.pontoembarque').count()-logs,2)
        self.formulario_rota(pontos_ida=[self.ponto_ida.pk,novo.pk]).save()
        self.ponto.refresh_from_db();self.assertTrue(self.ponto.ativo);self.assertEqual(self.ponto.ordem,1)
        self.assertEqual(LogAuditoria.objects.filter(modelo='rotas.pontoembarque').count()-logs,3)
        self.assertEqual(self.rota.pontos.filter(ponto=self.ponto_ida).count(),1)

    def test_atualizacao_endereco_grava_so_o_ponto_alterado(self):
        self.preparar_pontos()
        Ponto.objects.filter(pk=self.ponto_ida.pk).update(endereco='Novo endereço')
        logs=LogAuditoria.objects.filter(modelo='rotas.pontoembarque').count()
        with CaptureQueriesContext(connection) as queries:self.formulario_rota().save()
        updates=[q['sql'] for q in queries if q['sql'].startswith('UPDATE "rotas_pontoembarque"')]
        self.assertEqual(len(updates),1)
        self.ponto.refresh_from_db();self.assertEqual(self.ponto.endereco,'Novo endereço')
        self.assertEqual(LogAuditoria.objects.filter(modelo='rotas.pontoembarque').count()-logs,1)
