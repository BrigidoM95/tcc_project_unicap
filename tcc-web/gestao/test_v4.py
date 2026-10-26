from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.apps import apps
from embarques.tests import Cenario
from embarques.models import CheckIn
from rotas.models import Rota, Viagem, PontoEmbarque
from rotas.operacao import data_operacional
from usuarios.models import Usuario, Instituicao, Curso
from .models import LogAuditoria
from .indicadores import indicadores


class PainelV4Tests(Cenario,TestCase):
    def setUp(self):
        super().setUp();self.admin=self.perfil('GestorV4','administrador');self.client.force_login(self.admin.user)

    def test_home_tres_indicadores_e_contagem_distinta(self):
        self.confirmar();self.reservar(self.outro,2)
        r=self.client.get('/');self.assertEqual(r.status_code,200)
        self.assertEqual(r.context['cards']['Reservas do dia'],2)
        for texto in ['Associados ativos','Ônibus ativos','Reservas do dia','Nenhuma pendência']:
            self.assertContains(r,texto)
        for texto in ['Resumo administrativo','Rotas ativas','Check-ins hoje','Viagens em andamento']:
            self.assertNotContains(r,texto)

    def test_reserva_e_checkin_mesmo_aluno_contam_uma_vez(self):
        self.confirmar();self.reservar(sentido='retorno')
        self.assertEqual(indicadores()['cards']['Reservas do dia'],1)

    def test_abas_acoes_server_side(self):
        for i in range(22):LogAuditoria.objects.create(acao='teste_v4',descricao=f'Ação específica {i}')
        recentes=list(LogAuditoria.objects.order_by('-criado_em','-pk').values_list('pk',flat=True)[:20])
        for numero,inicio in [(1,0),(2,10)]:
            r=self.client.get('/',{'acoes':numero})
            self.assertEqual([a.pk for a in r.context['ultimas_acoes']],recentes[inicio:inicio+10])

    def test_pendencias_mostram_cinco_e_ver_todos_funciona(self):
        for i in range(7):self.perfil(f'SemCurso{i}','associado',curso=False)
        self.rota.pontos.update(ativo=False);self.rota.instituicoes.clear()
        r=self.client.get('/');self.assertEqual(r.context['total_sem_curso'],7)
        self.assertEqual(len(r.context['associados_sem_curso']),5)
        self.assertContains(r,'Sem ponto ativo');self.assertContains(r,'Sem instituição')
        r=self.client.get('/usuarios/',{'pendencia':'sem_curso'})
        self.assertEqual(r.context['usuarios'].paginator.count,7)
        self.assertTrue(all(p.curso_id is None for p in r.context['usuarios']))
        r=self.client.get('/rotas/',{'pendencia':'incompleta'})
        self.assertEqual(r.context['rotas'].paginator.count,1)

    def test_gestao_somente_tres_modulos_sem_matricula(self):
        r=self.client.get('/gestao/')
        for texto in ['Instituições e cursos','Despesas','Auditoria']:self.assertContains(r,texto)
        for texto in ['Matrículas anuais','Situação dos associados','Despesas e veículos']:self.assertNotContains(r,texto)
        self.assertEqual(self.client.get('/gestao/matriculas/').status_code,404)
        with self.assertRaises(LookupError):apps.get_model('usuarios','MatriculaAnual')

    def test_campos_removidos_dos_formularios(self):
        for url,campos in [(f'/onibus/{self.onibus.pk}/editar/',['situacao','cor','ano_fabricacao','tipo_veiculo','combustivel']),
                           (f'/rotas/{self.rota.pk}/editar/',['origem']),('/gestao/pontos/novo/',['latitude','longitude'])]:
            r=self.client.get(url);self.assertEqual(r.status_code,200)
            for nome in campos:self.assertNotIn(nome,r.context['form'].fields)

    def test_senha_redefinida_admin_sem_redirecionamento_obrigatorio(self):
        # A URL canônica é resolvida pelo nome para acompanhar o roteamento.
        from django.urls import reverse
        senha='SenhaAdministrativa#9472'
        r=self.client.post(reverse('redefinir_senha',args=[self.admin.pk]),{'new_password1':senha,'new_password2':senha})
        self.assertEqual(r.status_code,302)
        self.assertEqual(self.client.get('/').status_code,200)
        self.client.logout()
        self.assertTrue(self.client.login(username=self.admin.user.username,password=senha))
        self.assertEqual(self.client.get('/').status_code,200)

    def test_area_embarque_grupos_horario_filtros_e_cancelados(self):
        c=self.confirmar().data['checkin']
        outro=self.confirmar(self.outro,2).data['checkin']
        CheckIn.objects.filter(pk=outro['id']).update(cancelado_em=timezone.now())
        r=self.client.get('/embarques/');self.assertEqual(r.status_code,200)
        self.assertContains(r,'Área de embarque');self.assertEqual(len(r.context['grupos']),2)
        self.assertEqual(sum(g['total'] for g in r.context['grupos']),1)
        self.assertContains(r,timezone.localtime(CheckIn.objects.get(pk=c['id']).registrado_em).strftime('%H:%M:%S'))
        r=self.client.get('/embarques/',{'sentido':'ida','onibus':self.onibus.pk,'q':self.associado.rua})
        self.assertEqual(len(r.context['grupos']),1);self.assertEqual(r.context['grupos'][0]['total'],1)
        self.assertNotContains(r,self.outro.rua)
        self.assertContains(self.client.get('/embarques/',{'sentido':'retorno'}),'Nenhum embarque')

    def test_area_embarque_outro_onibus_e_paginacao_de_grupo(self):
        from onibus.models import Onibus
        motorista=self.perfil('Motorista2V4','motorista')
        bus=Onibus.objects.create(nome='Segundo ônibus',placa='VAA1234',capacidade=46,motorista=motorista)
        rota=Rota.objects.create(nome='Segunda rota',destino='Campus',onibus=bus,horario_ida='18:00',horario_retorno='22:30')
        v=Viagem.objects.create(rota=rota,onibus=bus,motorista=motorista,sentido='ida',status='agendada',data_servico=data_operacional())
        # Histórico importado pode exceder a capacidade atual: nenhuma linha é ocultada.
        for i in range(51):
            CheckIn.objects.create(viagem=v,associado=self.associado,fiscal=self.fiscal,sentido='ida',legado=True,vaga=i+1,
                data_servico=data_operacional(),nome_associado=f'Histórico {i}',rua_associado=self.associado.rua,
                placa_onibus=bus.placa,codigo_onibus=bus.codigo)
        r=self.client.get('/embarques/');self.assertEqual(len(r.context['grupos']),4)
        grupo=next(g for g in r.context['grupos'] if g['viagem'].pk==v.pk and g['sentido']=='Ida')
        self.assertEqual(grupo['registros'].paginator.count,51);self.assertEqual(len(grupo['registros']),50)
        r=self.client.get('/embarques/',{grupo['chave']:2})
        self.assertEqual(len(next(g for g in r.context['grupos'] if g['id']==grupo['id'])['registros']),1)
        self.client.force_login(self.associado.user);self.assertEqual(self.client.get('/embarques/').status_code,403)

    def test_filtros_associado_unificados_nos_resultados_e_pdf(self):
        self.confirmar();self.confirmar(self.outro,2)
        outra=Instituicao.objects.create(nome='Outra faculdade');curso=Curso.objects.create(instituicao=outra,nome='Direito')
        Usuario.objects.filter(pk=self.outro.pk).update(curso=curso)
        r=self.client.get('/relatorios/',{'freq_instituicao':outra.pk})
        self.assertEqual(r.context['resumo']['embarques'],1)
        self.assertEqual(r.context['embarques'].paginator.count,1)
        self.assertEqual([p['associado_id'] for p in r.context['frequencia']],[self.outro.pk])
        self.assertContains(r,'Outra faculdade');self.assertNotContains(r,'Fechamentos mensais')
        self.assertNotContains(r,'Utilização por ônibus');self.assertNotContains(r,'Pontos informados nos embarques')
        r=self.client.get('/relatorios/',{'freq_q':self.associado.user.email})
        self.assertEqual(r.context['frequencia'].paginator.count,1)
        from unittest.mock import patch
        from relatorios.pdf import gerar_pdf
        with patch('relatorios.pdf.gerar_pdf',wraps=gerar_pdf) as gerar:
            from django.urls import reverse
            pdf=self.client.get(reverse('relatorios:pdf'),{'freq_instituicao':outra.pk})
            relatorio=gerar.call_args.args[0]
            self.assertEqual([f['associado_id'] for f in relatorio.frequencia],[self.outro.pk])
            self.assertIn('Instituição: Outra faculdade',relatorio.filtros_legiveis)
        self.assertEqual(pdf.status_code,200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))
