from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CadastroUsuarioForm, EdicaoUsuarioForm, LoginForm
from .models import Usuario

from django.contrib.auth import authenticate

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from django.views.decorators.http import require_POST
from django.contrib.auth.signals import user_logged_in
from gestao.auditoria import registrar

class LimiteLogin(AnonRateThrottle):
    scope = 'login'
class LimiteRefresh(AnonRateThrottle):
    scope = 'refresh'
class LimiteSenha(UserRateThrottle):
    scope = 'senha'
class RenovarTokenApi(TokenRefreshView):
    throttle_classes = [LimiteRefresh]



class UsuarioLoginView(LoginView):
    authentication_form = LoginForm
    template_name = "usuarios/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        from .seguranca import limite_login_web
        if limite_login_web(request):
            form = self.get_form()
            form.is_valid()
            form.add_error(None, 'Muitas tentativas. Aguarde 15 minutos antes de tentar novamente.')
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()

        if not eh_administrador(user):
            form.add_error(
                None,
                "Acesso permitido apenas para administradores."
            )
            return self.form_invalid(form)

        return super().form_valid(form)

@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, 'Você saiu do sistema com segurança.')
    return redirect('login')

def eh_administrador(user):
    if not user.is_authenticated or not user.is_active:
        return False

    if user.is_superuser:
        return True

    return (
        hasattr(user, "perfil")
        and user.perfil.tipo == Usuario.Tipo.ADMINISTRADOR
    )

@user_passes_test(eh_administrador, login_url="login")
def listar_usuarios(request):
    usuarios = Usuario.objects.select_related("user").order_by(
        "user__first_name"
    )

    from django.db.models import Q
    from django.core.paginator import Paginator
    q=request.GET.get('q','').strip(); tipo=request.GET.get('tipo',''); inativos=request.GET.get('status')=='inativos'
    usuarios=usuarios.filter(user__is_active=not inativos)
    if request.GET.get('pendencia')=='sem_curso': usuarios=usuarios.filter(tipo='associado',curso__isnull=True,user__is_active=True)
    if q: usuarios=usuarios.filter(Q(user__first_name__icontains=q)|Q(user__email__icontains=q)|Q(rua__icontains=q))
    if tipo in Usuario.Tipo.values: usuarios=usuarios.filter(tipo=tipo)
    pagina=Paginator(usuarios,25).get_page(request.GET.get('pagina'))
    parametros=request.GET.copy();parametros.pop('pagina',None)
    return render(request, 'usuarios/listar.html', {'usuarios':pagina,'pagina':pagina,'busca':q,'tipo':tipo,'inativos':inativos,'tipos':Usuario.Tipo.choices,'parametros':parametros.urlencode()})

@user_passes_test(eh_administrador, login_url="login")
def cadastrar_usuario(request):

    if request.method == "POST":
        form = CadastroUsuarioForm(request.POST, ator=request.user)

        if form.is_valid():
            user = form.save()
            return render(request, 'usuarios/senha_acesso.html', {'usuario':user.perfil, 'senha':form.senha_gerada})

    else:
        form = CadastroUsuarioForm(ator=request.user)

    return render(
        request,
        "usuarios/cadastrar.html",
        {"form": form},
    )

@user_passes_test(eh_administrador, login_url="login")
def editar_usuario(request, usuario_id):
    usuario = get_object_or_404(
        Usuario.objects.select_related("user"),
        pk=usuario_id
    )

    if request.method == "POST":
        form = EdicaoUsuarioForm(
            request.POST,
            usuario=usuario, ator=request.user
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Usuário atualizado com sucesso."
            )

            return redirect("listar_usuarios")

    else:
        form = EdicaoUsuarioForm(
            usuario=usuario, ator=request.user
        )

    return render(
        request,
        "usuarios/editar.html",
        {
            "form": form,
            "usuario": usuario,
        },
    )

@user_passes_test(eh_administrador, login_url="login")
def alterar_status_usuario(request, usuario_id):
    usuario = get_object_or_404(
        Usuario.objects.select_related("user"),
        pk=usuario_id
    )

    if request.method == "POST":
        user = usuario.user

        if user.pk == request.user.pk or user.is_superuser:
            messages.error(request, 'Esta conta não pode ser inativada por esta tela.')
            return redirect('listar_usuarios')
        if usuario.tipo == Usuario.Tipo.MOTORISTA and user.is_active and (usuario.viagens.filter(status='em_andamento').exists() or usuario.onibus.filter(status='ativo').exists()):
            messages.error(request, 'Desvincule o motorista dos ônibus ativos e finalize suas viagens antes de inativá-lo.')
            return redirect('listar_usuarios')
        user.is_active = not user.is_active
        user.save()
        registrar('status_usuario', modelo='usuarios.usuario', objeto_id=usuario.pk, detalhes={'ativo':user.is_active})

        if user.is_active:
            messages.success(
                request,
                "Usuário reativado com sucesso."
            )
        else:
            messages.success(
                request,
                "Usuário inativado com sucesso."
            )

    return redirect("listar_usuarios")


class LoginApiView(APIView):
    throttle_classes = [LimiteLogin]
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        identificador = str(request.data.get('identificador', request.data.get('email', ''))).strip()
        from django.contrib.auth import get_user_model
        from django.db.models import Q
        candidato = get_user_model().objects.filter(Q(email__iexact=identificador)|Q(perfil__rua__iexact=identificador)|Q(perfil__rua_anterior__iexact=identificador)).first() if identificador else None
        email = candidato.username if candidato else identificador.lower()
        senha = request.data.get("senha")

        if not email or not isinstance(senha, str) or not senha:
            return Response(
                {
                    "erro": "E-mail e senha são obrigatórios."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(
            request=request,
            username=email,
            password=senha,
        )

        if user is None and candidato and candidato.check_password(senha) and not candidato.is_active:
            return Response({'erro':'Conta inativa. Procure a administração.'}, status=403)
        if user is None:
            return Response(
                {
                    "erro": "E-mail, RUA ou senha inválidos."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {
                    "erro": "Usuário inativo."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not hasattr(user, "perfil"):
            return Response(
                {
                    "erro": "Este usuário não possui acesso ao aplicativo."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        perfil = user.perfil

        tipos_permitidos = [
            Usuario.Tipo.ASSOCIADO,
            Usuario.Tipo.FISCAL,
            Usuario.Tipo.MOTORISTA,
        ]

        if perfil.tipo not in tipos_permitidos:
            return Response(
                {
                    "erro": "Este usuário não possui acesso ao aplicativo."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user_logged_in.send(sender=type(user), request=request, user=user)
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "usuario": {
                    "id": user.id,
                    "nome": user.first_name,
                    "email": user.email,
                    "tipo": perfil.tipo,
                    "rua": perfil.rua,
                    "perfil_id": perfil.pk,
                    "estudante": perfil.curso_id is not None,
                    "instituicao": perfil.curso.instituicao.nome if perfil.curso_id else None,
                    "curso": perfil.curso.nome if perfil.curso_id else None,
                },
            },
            status=status.HTTP_200_OK,
        )

class LogoutApi(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        valor = request.data.get('refresh')
        if not isinstance(valor,str): return Response({'detail':'Informe o refresh token.'},status=400)
        try:
            token = RefreshToken(valor)
            if str(token['user_id']) != str(request.user.pk):
                return Response({'detail':'Token de outra sessão.'},status=403)
            token.blacklist()
        except TokenError:
            return Response({'detail':'Token inválido ou já encerrado.'},status=400)
        from django.core.cache import cache
        from django.utils import timezone
        cache.set('jwt_logout:'+str(request.auth['jti']),True,timeout=max(1,int(request.auth['exp']-timezone.now().timestamp())))
        registrar('logout',usuario=request.user)
        return Response({'detail':'Sessão encerrada.'})

class AlterarSenhaApi(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [LimiteSenha]
    def post(self, request):
        return Response(
            {'detail':'A troca de senha é feita pelo painel web. Procure a administração para redefinir sua senha.'},
            status=status.HTTP_410_GONE,
        )
