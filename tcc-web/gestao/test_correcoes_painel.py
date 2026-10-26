from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from embarques.tests import Cenario
from embarques.models import CheckIn
from rotas.models import Rota, Viagem
from rotas import operacao
from rotas.operacao import data_operacional
from .models import LogAuditoria


class CorrecoesPainelTests(Cenario, TestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.perfil('AdministradorPainel', 'administrador')
        self.client.force_login(self.admin.user)

    def encerrar_viagem(self):
        Viagem.objects.filter(pk=self.viagem.pk).update(
            status='finalizada', etapa='encerrada', finalizada_em=timezone.now(),
            partida_ida_em=self.viagem.iniciada_em,
        )

    def test_redefinicao_disponivel_na_lista_e_detalhe(self):
        url = reverse('redefinir_senha', args=[self.associado.pk])
        self.assertContains(self.client.get(reverse('listar_usuarios')), url)
        self.assertContains(self.client.get(reverse('detalhe_usuario', args=[self.associado.pk])), url)
        resposta = self.client.get(url)
        self.assertContains(resposta, 'new_password1')
        self.assertContains(resposta, 'new_password2')
        self.assertContains(resposta, '8 caracteres')

    def test_redefinicao_valida_os_tres_perfis_e_revoga_tokens(self):
        for perfil in [self.associado, self.motorista, self.fiscal]:
            with self.subTest(tipo=perfil.tipo):
                refresh = RefreshToken.for_user(perfil.user)
                api = self.cliente(perfil)
                nova = 'NovaSenhaSegura#2984'
                resposta = self.client.post(reverse('redefinir_senha', args=[perfil.pk]), {
                    'new_password1': nova, 'new_password2': nova,
                })
                self.assertEqual(resposta.status_code, 302)
                perfil.user.refresh_from_db()
                perfil.refresh_from_db()
                self.assertTrue(perfil.user.check_password(nova))
                self.assertIsNotNone(perfil.senha_definida_em)
                self.assertEqual(api.get('/api/viagens/hoje/').status_code, 401)
                self.assertEqual(api.post('/api/token/refresh/', {'refresh':str(refresh)}, format='json').status_code, 401)
        self.assertNotIn('NovaSenhaSegura#2984', str(list(LogAuditoria.objects.values_list('detalhes',flat=True))))

    def test_senha_fraca_divergente_ou_ausente_preserva_senha(self):
        url = reverse('redefinir_senha', args=[self.associado.pk])
        for dados in [{}, {'new_password1':'abc','new_password2':'abc'},
                      {'new_password1':'NovaSenhaSegura#2984','new_password2':'SenhaDiferente#4928'}]:
            resposta = self.client.post(url,dados)
            self.assertEqual(resposta.status_code,200)
            self.assertTrue(resposta.context['form'].errors)
            self.associado.user.refresh_from_db()
            self.assertTrue(self.associado.user.check_password('Teste123456!'))

    def test_redefinicao_exclusiva_do_administrador(self):
        self.client.force_login(self.fiscal.user)
        resposta = self.client.post(reverse('redefinir_senha',args=[self.associado.pk]), {
            'new_password1':'NovaSenhaSegura#2984','new_password2':'NovaSenhaSegura#2984'})
        self.assertEqual(resposta.status_code,403)
        self.assertEqual(self.client.get('/conta/senha/').status_code,403)

    def test_app_nao_pode_alterar_senha(self):
        for perfil in [self.associado,self.motorista,self.fiscal]:
            resposta=self.cliente(perfil).post('/api/senha/', {
                'senha_atual':'Teste123456!', 'nova_senha':'OutraSenha#9874'},format='json')
            self.assertEqual(resposta.status_code,410)
            self.assertIn('administração',resposta.data['detail'])
            perfil.user.refresh_from_db()
            self.assertTrue(perfil.user.check_password('Teste123456!'))

    def test_confirmacao_lista_rotas_e_get_nao_inativa(self):
        outra=Rota.objects.create(nome='Rota noturna',destino='Campus',onibus=self.onibus,
            horario_ida='19:00',horario_retorno='23:00')
        url=reverse('alterar_status_onibus',args=[self.onibus.pk])
        for resposta in [self.client.get(url),self.client.post(url)]:
            self.assertContains(resposta,self.rota.nome)
            self.assertContains(resposta,outra.nome)
            self.assertContains(resposta,'Confirmar inativação')
        self.onibus.refresh_from_db();self.assertTrue(self.onibus.ativo)

    def test_inativacao_cascata_e_reativacao_nao_reativa_rotas(self):
        self.encerrar_viagem()
        outra=Rota.objects.create(nome='Segunda rota',destino='Campus',onibus=self.onibus,
            horario_ida='19:00',horario_retorno='23:00')
        url=reverse('alterar_status_onibus',args=[self.onibus.pk])
        resposta=self.client.post(url,{'confirmar':'1','status':'inativo'})
        self.assertEqual(resposta.status_code,302)
        self.onibus.refresh_from_db();self.rota.refresh_from_db();outra.refresh_from_db()
        self.assertFalse(self.onibus.ativo);self.assertFalse(self.rota.ativa);self.assertFalse(outra.ativa)
        self.assertTrue(LogAuditoria.objects.filter(modelo='rotas.rota',objeto_id=str(outra.pk),acao='alterado').exists())
        self.client.post(url,{'confirmar':'1','status':'ativo'})
        self.onibus.refresh_from_db();self.rota.refresh_from_db()
        self.assertTrue(self.onibus.ativo);self.assertFalse(self.rota.ativa)

    def test_inativacao_nao_interrompe_viagem_em_andamento(self):
        resposta=self.client.post(reverse('alterar_status_onibus',args=[self.onibus.pk]),
            {'confirmar':'1','status':'inativo'},follow=True)
        self.assertContains(resposta,'Há uma viagem em andamento')
        self.onibus.refresh_from_db();self.rota.refresh_from_db()
        self.assertTrue(self.onibus.ativo);self.assertTrue(self.rota.ativa)

    def test_cascata_atomica_reverte_tudo_se_salvamento_falhar(self):
        self.encerrar_viagem()
        outra=Rota.objects.create(nome='Segunda rota',destino='Campus',onibus=self.onibus,
            horario_ida='19:00',horario_retorno='23:00')
        salvar=Rota.save
        def falhar(rota,*args,**kwargs):
            if rota.pk==outra.pk:raise RuntimeError('falha simulada')
            return salvar(rota,*args,**kwargs)
        with patch.object(Rota,'save',falhar),self.assertRaises(RuntimeError):
            self.onibus.desativar()
        self.onibus.refresh_from_db();self.rota.refresh_from_db()
        self.assertTrue(self.onibus.ativo);self.assertTrue(self.rota.ativa)

    def test_filtro_compartilhado_preserva_busca_e_reinicia_pagina(self):
        for nome in ['listar_onibus','listar_rotas']:
            for status in ['ativos','inativos','todos','invalido']:
                resposta=self.client.get(reverse(nome),{'status':status,'q':'A&B','pagina':3})
                self.assertTemplateUsed(resposta,'paginas/filtro_status.html')
                self.assertEqual(resposta.context['filtro_status'],'ativos' if status=='invalido' else status)
                self.assertContains(resposta,'q=A%26B')
                self.assertNotContains(resposta,'pagina=3')
        for antigo,novo in [('ativas','ativos'),('inativas','inativos'),('todas','todos')]:
            self.assertEqual(self.client.get(reverse('listar_rotas'),{'status':antigo}).context['filtro_status'],novo)

    def test_filtro_retorna_mesma_situacao_em_onibus_e_rotas(self):
        self.encerrar_viagem();self.onibus.desativar()
        for nome,chave in [('listar_onibus','onibus'),('listar_rotas','rotas')]:
            self.assertEqual(len(self.client.get(reverse(nome)).context[chave]),0)
            for status in ['inativos','todos']:
                self.assertEqual(len(self.client.get(reverse(nome),{'status':status}).context[chave]),1)

    def test_embarques_abrem_ultimo_inicio_real_com_data_visivel(self):
        antiga=data_operacional()-timedelta(days=3)
        instante=timezone.now()-timedelta(days=3)
        Viagem.objects.filter(pk=self.viagem.pk).update(data_servico=antiga,iniciada_em=instante,
            status='finalizada',etapa='encerrada',partida_ida_em=instante,finalizada_em=instante+timedelta(hours=2))
        for data,status,etapa in [(data_operacional(),'agendada','agendada'),
                                 (data_operacional()-timedelta(days=1),'finalizada','encerrada')]:
            inicio=timezone.now()
            Viagem.objects.create(rota=self.rota,onibus=self.onibus,motorista=self.motorista,
                sentido='ida',data_servico=data,status=status,etapa=etapa,iniciada_em=inicio,
                finalizada_em=inicio if status=='finalizada' else None,encerrada_pelo_sistema=status=='finalizada')
        resposta=self.client.get('/embarques/')
        self.assertEqual(resposta.context['ultima_viagem'].pk,self.viagem.pk)
        self.assertEqual(resposta.context['data_exibida'],antiga)
        self.assertContains(resposta,'Data dos embarques: '+antiga.strftime('%d/%m/%Y'))
        resposta=self.client.get('/embarques/',{'data':data_operacional().isoformat()})
        self.assertEqual(resposta.context['data_exibida'],data_operacional())
        self.assertIsNone(resposta.context['ultima_viagem'])

    def test_inicio_auditado_conta_mesmo_encerrado_antes_da_partida(self):
        self.encerrar_viagem()
        inicio=timezone.now()
        recente=Viagem.objects.create(rota=self.rota,onibus=self.onibus,motorista=self.motorista,
            sentido='ida',data_servico=data_operacional()-timedelta(days=1),status='finalizada',etapa='encerrada',
            encerrada_pelo_sistema=True,iniciada_em=inicio,finalizada_em=inicio)
        LogAuditoria.objects.create(modelo='rotas.viagem',objeto_id=str(recente.pk),acao='iniciar_rota')
        self.assertEqual(self.client.get('/embarques/').context['ultima_viagem'].pk,recente.pk)

    def test_menus_ativos_e_pontos_dentro_de_gestao(self):
        resposta=self.client.get('/gestao/')
        self.assertContains(resposta,'Ver pontos de embarque')
        self.assertContains(resposta,'class="submenu"')
        resposta=self.client.get('/gestao/pontos/')
        self.assertContains(resposta,'href="/gestao/pontos/" aria-current="page"',html=False)
        with patch('gestao.revisao.operacao.gerar_viagens'),patch('gestao.revisao.operacao.encerrar_antigas'):
            resposta=self.client.get('/operacao/')
        self.assertContains(resposta,'href="/operacao/" aria-current="page"',html=False)

    def test_intervencao_fiscal_troca_acesso_sem_reescrever_historico(self):
        confirmado=self.confirmar()
        self.assertEqual(confirmado.status_code,201,confirmado.data)
        qr_anterior=self.gerar().data['codigo']
        self.assertEqual(self.reservar(self.outro,2).status_code,201)
        novo=self.perfil('FiscalSubstituto','fiscal')
        antes=Viagem.objects.values().get(pk=self.viagem.pk)
        resposta=self.client.post(reverse('intervir_viagem',args=[self.viagem.pk]),{
            'acao':'alterar_fiscal','fiscal':novo.pk,'motivo':'Substituição durante o embarque'})
        self.assertEqual(resposta.status_code,302)
        depois=Viagem.objects.values().get(pk=self.viagem.pk)
        self.assertEqual(depois.pop('fiscal_id'),novo.pk)
        antes.pop('fiscal_id');self.assertEqual(depois,antes)
        self.rota.refresh_from_db();self.assertEqual(self.rota.fiscal_id,self.fiscal.pk)
        self.assertEqual(CheckIn.objects.get(pk=confirmado.data['checkin']['id']).fiscal_id,self.fiscal.pk)
        self.assertEqual(self.gerar().status_code,404)
        self.assertEqual(self.checkin(qr_anterior,self.outro,2).status_code,403)
        qr_novo=self.cliente(novo).post(f'/api/viagens/{self.viagem.pk}/qr-do-dia/',{'sentido':'ida'},format='json')
        self.assertEqual(qr_novo.status_code,200,qr_novo.data)
        resposta=self.checkin(qr_novo.data['codigo'],self.outro,2)
        self.assertEqual(resposta.status_code,201,resposta.data)
        self.assertEqual(CheckIn.objects.get(pk=resposta.data['checkin']['id']).fiscal_id,novo.pk)
        log=LogAuditoria.objects.get(modelo='rotas.viagem',objeto_id=str(self.viagem.pk),acao='intervencao_viagem')
        self.assertEqual(log.detalhes['fiscal_anterior_id'],self.fiscal.pk)
        self.assertEqual(log.detalhes['novo_fiscal_id'],novo.pk)
        self.assertEqual(log.usuario_id,self.admin.user_id)

    def test_intervencao_fiscal_preserva_janelas_em_cada_etapa(self):
        novo=self.perfil('FiscalEtapas','fiscal')
        for etapa,sentido,aberto in [('transito_ida','ida',False),('no_destino','retorno',True),('transito_volta','retorno',False)]:
            with self.subTest(etapa=etapa):
                instante=timezone.now()
                Viagem.objects.filter(pk=self.viagem.pk).update(etapa=etapa,fiscal=self.fiscal,
                    partida_ida_em=instante,chegada_em=instante if sentido=='retorno' else None,
                    partida_volta_em=instante if etapa=='transito_volta' else None)
                self.viagem.refresh_from_db()
                antes=operacao.janela_embarque(self.viagem,sentido,timezone.now())
                resposta=self.client.post(reverse('intervir_viagem',args=[self.viagem.pk]),{
                    'acao':'alterar_fiscal','fiscal':novo.pk,'motivo':'Substituir responsável'})
                self.assertEqual(resposta.status_code,302)
                self.viagem.refresh_from_db()
                self.assertEqual(self.viagem.etapa,etapa)
                self.assertEqual(self.viagem.embarque_aberto(sentido),aberto)
                self.assertEqual(operacao.janela_embarque(self.viagem,sentido,timezone.now()),antes)
                qr=self.cliente(novo).post(f'/api/viagens/{self.viagem.pk}/qr-do-dia/',{'sentido':sentido},format='json')
                self.assertEqual(qr.status_code,200 if aberto else 409,qr.data)

    def test_intervencao_exige_fiscal_ativo_e_perfil_correto(self):
        inativo=self.perfil('FiscalInativo','fiscal')
        inativo.user.is_active=False;inativo.user.save(update_fields=['is_active'])
        for fiscal in ['',inativo.pk,self.motorista.pk]:
            resposta=self.client.post(reverse('intervir_viagem',args=[self.viagem.pk]),{
                'acao':'alterar_fiscal','fiscal':fiscal,'motivo':'Substituir responsável'})
            self.assertEqual(resposta.status_code,200)
            self.assertIn('fiscal',resposta.context['form'].errors)
            self.viagem.refresh_from_db();self.assertEqual(self.viagem.fiscal_id,self.fiscal.pk)

    def test_intervencao_fiscal_recusa_viagem_agendada_ou_encerrada(self):
        novo=self.perfil('FiscalBloqueado','fiscal')
        for status,etapa in [('agendada','agendada'),('finalizada','encerrada'),('cancelada','cancelada')]:
            Viagem.objects.filter(pk=self.viagem.pk).update(status=status,etapa=etapa,
                finalizada_em=None if status=='agendada' else timezone.now())
            resposta=self.client.post(reverse('intervir_viagem',args=[self.viagem.pk]),{
                'acao':'alterar_fiscal','fiscal':novo.pk,'motivo':'Substituir responsável'})
            self.assertEqual(resposta.status_code,200)
            self.assertTrue(resposta.context['form'].non_field_errors())
            self.viagem.refresh_from_db();self.assertEqual(self.viagem.fiscal_id,self.fiscal.pk)

    def test_fiscal_opcional_nao_impede_outras_intervencoes(self):
        resposta=self.client.post(reverse('intervir_viagem',args=[self.viagem.pk]),{
            'acao':'encerrar','motivo':'Encerramento administrativo'})
        self.assertEqual(resposta.status_code,302)
        self.viagem.refresh_from_db()
        self.assertEqual(self.viagem.status,'finalizada')
        self.assertEqual(self.viagem.fiscal_id,self.fiscal.pk)

    def test_substituicao_em_agendada_orienta_editar_cadastros(self):
        novo=self.perfil('MotoristaAgendada','motorista')
        Viagem.objects.filter(pk=self.viagem.pk).update(status='agendada',etapa='agendada')
        antes=Viagem.objects.values().get(pk=self.viagem.pk)
        resposta=self.client.post(reverse('intervir_viagem',args=[self.viagem.pk]),{
            'acao':'substituir','motorista':novo.pk,'motivo':'Troca antes do início'})
        self.assertContains(resposta,'Altere o ônibus no cadastro da rota ou o motorista no cadastro do ônibus.')
        self.assertTrue(resposta.context['form'].non_field_errors())
        self.assertEqual(Viagem.objects.values().get(pk=self.viagem.pk),antes)
