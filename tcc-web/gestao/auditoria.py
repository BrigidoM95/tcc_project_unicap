"""Auditoria sem senhas, JWT, QR ou corpos completos de requisição.

Transições da viagem registram a coordenada operacional exigida na especificação.
"""
from contextvars import ContextVar
from django.core.cache import cache
from rest_framework.exceptions import AuthenticationFailed
from django.apps import apps
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import LogAuditoria

_request = ContextVar('audit_request', default=None)
MODELOS = {'auth.user','usuarios.usuario','usuarios.instituicao','usuarios.curso',
 'onibus.onibus','rotas.rota','rotas.pontoembarque','rotas.viagem','embarques.sessaoembarque',
 'embarques.checkin','gestao.despesa','rotas.ponto'}

CAMPOS=('first_name','last_name','email','nome','is_active','is_staff','is_superuser','tipo','status','etapa','ano','ativa','ativo','cancelada','valor','categoria','onibus_id','associado_id','viagem_id','motorista_id','fiscal_id','curso_id','capacidade')

def retrato(instance):
    dados={}
    for nome in CAMPOS:
        if hasattr(instance,nome):
            v=getattr(instance,nome)
            dados[nome]=v if isinstance(v,(int,bool,str,type(None))) else str(v)
    return dados

@receiver(pre_save)
def antes_salvar(sender,instance,raw=False,**kwargs):
    if raw or sender._meta.apps is not apps or sender._meta.label_lower not in MODELOS:return
    anterior=sender.objects.filter(pk=instance.pk).first() if instance.pk else None
    instance._retrato_anterior=retrato(anterior) if anterior else {}
def registrar(acao, *, usuario=None, modelo='', objeto_id='', detalhes=None):
    request = _request.get()
    if usuario is None and request is not None: usuario = getattr(request, 'user', None)
    if usuario is not None and (not usuario.is_authenticated or not usuario.pk): usuario = None
    import ipaddress
    ip = request.META.get('REMOTE_ADDR') if request is not None else None
    try: ip = str(ipaddress.ip_address(ip)) if ip else None
    except ValueError: ip = None
    descricao = acao.replace('_', ' ').capitalize()
    return LogAuditoria.objects.create(usuario=usuario, acao=acao, modelo=modelo,
        objeto_id=str(objeto_id), detalhes=detalhes or {}, ip=ip, descricao=descricao)

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
            if response.status_code == 403:
                registrar('acesso_negado',detalhes={'caminho':request.path})
            if request.user.is_authenticated:
                response['Cache-Control'] = 'private, no-store'
                # Consultas administrativas; polling de API não gera milhares de logs.
                # Consultas comuns não poluem o log; ações relevantes são explícitas.
            return response
        finally: _request.reset(token)

@receiver(post_save)
def registro_salvo(sender, instance, created, raw=False, **kwargs):
    if raw or sender._meta.apps is not apps or sender._meta.label_lower not in MODELOS: return
    if sender._meta.label_lower == 'auth.user' and kwargs.get('update_fields') == frozenset({'last_login'}): return
    depois=retrato(instance);antes=getattr(instance,'_retrato_anterior',{})
    if not created and antes==depois:return
    detalhes={'antes':antes,'depois':depois}
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
