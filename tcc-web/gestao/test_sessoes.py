from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model, logout
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import path
from django.utils import timezone

from .sessoes import RenovacaoSessaoMiddleware


def painel(request):
    return HttpResponse('autenticado' if request.user.is_authenticated else 'anonimo')


def sair(request):
    logout(request)
    return HttpResponse('saiu')


urlpatterns=[path('painel/',painel),path('sair/',sair),path('erro/',lambda request:HttpResponse(status=500))]


@override_settings(ROOT_URLCONF=__name__,SESSION_SAVE_EVERY_REQUEST=False,SESSION_COOKIE_AGE=1800,
    SESSION_EXPIRE_AT_BROWSER_CLOSE=True,MIDDLEWARE=[
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'gestao.sessoes.RenovacaoSessaoMiddleware'])
class RenovacaoSessaoTests(TestCase):
    def setUp(self):
        self.usuario=get_user_model().objects.create_user(username='GestorSessao',password='Senha#4578')
        self.client.force_login(self.usuario)

    def consultar(self,instante,caminho='/painel/'):
        with patch('gestao.sessoes.time',return_value=instante),CaptureQueriesContext(connection) as queries:
            resposta=self.client.get(caminho)
        escritas=[q['sql'] for q in queries if 'django_session' in q['sql'] and q['sql'].startswith(('INSERT','UPDATE'))]
        return resposta,escritas

    def test_marcador_ausente_inicializa_sem_alterar_cookie_de_fim_do_navegador(self):
        resposta,escritas=self.consultar(1000)
        self.assertEqual(len(escritas),1)
        self.assertEqual(self.client.session[RenovacaoSessaoMiddleware.marcador],1000)
        self.assertEqual(resposta.cookies['sessionid']['max-age'],'')
        self.assertEqual(resposta.cookies['sessionid']['expires'],'')

    def test_299_segundos_nao_grava_e_301_renova_uma_vez(self):
        self.consultar(1000)
        _,escritas=self.consultar(1299)
        self.assertEqual(escritas,[])
        _,escritas=self.consultar(1301)
        self.assertEqual(len(escritas),1)
        self.assertEqual(self.client.session[RenovacaoSessaoMiddleware.marcador],1301)
        self.assertEqual(self.consultar(1302)[1],[])

    def test_sessao_expirada_nao_e_renovada(self):
        self.consultar(1000)
        chave=self.client.session.session_key
        Session.objects.filter(session_key=chave).update(expire_date=timezone.now()-timedelta(seconds=1))
        resposta,escritas=self.consultar(2801)
        self.assertEqual(resposta.content,b'anonimo')
        self.assertEqual(escritas,[])

    def test_rotacao_de_chave_reinicia_marcador(self):
        self.consultar(1000)
        sessao=self.client.session;sessao.cycle_key();sessao.save()
        self.client.cookies['sessionid']=sessao.session_key
        _,escritas=self.consultar(1001)
        self.assertEqual(len(escritas),1)
        self.assertEqual(self.client.session[RenovacaoSessaoMiddleware.marcador],1001)

    def test_logout_e_erro_nao_recriam_nem_renovam_sessao(self):
        self.consultar(1000)
        self.assertEqual(self.consultar(1301,'/erro/')[1],[])
        resposta,escritas=self.consultar(1301,'/sair/')
        self.assertEqual(resposta.content,b'saiu');self.assertEqual(escritas,[])
        self.assertEqual(Session.objects.count(),0)

    def test_jwt_sem_sessao_web_nao_cria_sessao(self):
        request=RequestFactory().get('/api/mapa/')
        request.user=self.usuario;request.session=SessionStore()
        RenovacaoSessaoMiddleware(lambda request:HttpResponse())(request)
        self.assertIsNone(request.session.session_key)
        self.assertFalse(request.session.modified)
