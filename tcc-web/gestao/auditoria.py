"""Auditoria sem senhas, JWT, QR, corpos de requisição ou coordenadas GPS."""
from contextvars import ContextVar
from django.core.cache import cache
from rest_framework.exceptions import AuthenticationFailed
from django.apps import apps
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import LogAuditoria

_request = ContextVar('audit_request', default=None)
MODELOS = {'auth.user','usuarios.usuario','usuarios.instituicao','usuarios.curso','usuarios.matriculaanual',
 'onibus.onibus','rotas.rota','rotas.pontoembarque','rotas.viagem','embarques.sessaoembarque',
 'embarques.checkin','gestao.despesa'}
def registrar(acao, *, usuario=None, modelo='', objeto_id='', detalhes=None):
    request = _request.get()
    if usuario is None and request is not None: usuario = getattr(request, 'user', None)
    if usuario is not None and (not usuario.is_authenticated or not usuario.pk): usuario = None
    return LogAuditoria.objects.create(usuario=usuario, acao=acao, modelo=modelo,
        objeto_id=str(objeto_id), detalhes=detalhes or {})

class AuditJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        resultado = super().authenticate(request)
        if resultado and cache.get('jwt_logout:'+str(resultado[1]['jti'])):
            raise AuthenticationFailed('Sessão encerrada.')
        if resultado:
            request._request.user = resultado[0]
        return resultado

class AuditoriaMiddleware:
    def __init__(self,get_response): self.get_response = get_response
    def __call__(self, request):
        token = _request.set(request)
        try:
            response = self.get_response(request)
            if request.user.is_authenticated:
                response['Cache-Control'] = 'private, no-store'
                # Consultas administrativas; polling de API não gera milhares de logs.
                if request.method == 'GET' and response.status_code == 200 and not request.path.startswith(('/api/','/static/','/media/')):
                    registrar('consulta', detalhes={'caminho':request.path[:180]})
            return response
        finally: _request.reset(token)

@receiver(post_save)
def registro_salvo(sender, instance, created, raw=False, **kwargs):
    if raw or sender._meta.apps is not apps or sender._meta.label_lower not in MODELOS: return
    detalhes = {}
    for nome in ('is_active','is_staff','is_superuser','tipo','status','ano','ativa','cancelada','situacao','valor','categoria','onibus_id','associado_id','viagem_id'):
        if hasattr(instance,nome):
            v = getattr(instance,nome)
            detalhes[nome] = v if isinstance(v,(int,bool,str,type(None))) else str(v)
    if sender._meta.label_lower == 'usuarios.usuario': detalhes['ativo'] = instance.user.is_active
    registrar('criado' if created else 'alterado',modelo=sender._meta.label_lower,objeto_id=instance.pk,detalhes=detalhes)

@receiver(post_delete)
def registro_excluido(sender, instance, **kwargs):
    if sender._meta.apps is apps and sender._meta.label_lower in MODELOS:
        registrar('excluido',modelo=sender._meta.label_lower,objeto_id=instance.pk)

@receiver(user_logged_in)
def login_registrado(sender,request,user,**kwargs): registrar('login',usuario=user)
@receiver(user_logged_out)
def logout_registrado(sender,request,user,**kwargs): registrar('logout',usuario=user)
@receiver(user_login_failed)
def falha_login(sender,credentials,request,**kwargs): registrar('login_recusado')
