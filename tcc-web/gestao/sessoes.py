"""Renova a sessão web no máximo a cada cinco minutos.

Requer SESSION_SAVE_EVERY_REQUEST=False e deve ficar depois de
AuthenticationMiddleware. SessionMiddleware continua responsável por salvar e
expirar a sessão, inclusive ao fechar o navegador. Com idade de 30 minutos e
renovação agrupada, a expiração ocorre após 25–30 minutos sem atividade: nunca
amplia o limite de 30 minutos. Alterações explícitas na sessão ainda são salvas.
"""
from math import isfinite
from hashlib import sha256
from time import time

from django.conf import settings
from django.contrib.auth import SESSION_KEY


class RenovacaoSessaoMiddleware:
    marcador = '_sessao_renovada_em'
    marcador_chave = '_sessao_renovada_chave'
    intervalo = 300

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        sessao = request.session
        # JWT não deve criar/renovar sessões web. Logout também não recria a sessão.
        if (response.status_code < 500 and request.user.is_authenticated
                and sessao.session_key
                and str(sessao.get(SESSION_KEY)) == str(request.user.pk)):
            agora = time()
            anterior = sessao.get(self.marcador)
            chave = sha256(sessao.session_key.encode()).hexdigest()
            intervalo = min(self.intervalo, settings.SESSION_COOKIE_AGE)
            valido = type(anterior) in (int, float) and isfinite(anterior) and anterior <= agora
            if not valido or sessao.get(self.marcador_chave) != chave or agora - anterior >= intervalo:
                sessao[self.marcador] = agora
                sessao[self.marcador_chave] = chave
        return response
