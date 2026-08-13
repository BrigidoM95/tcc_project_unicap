from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CadastroUsuarioForm, EdicaoUsuarioForm, LoginForm
from .forms import LoginForm, CadastroUsuarioForm
from .models import Usuario

from django.contrib.auth import authenticate

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken


class UsuarioLoginView(LoginView):
    authentication_form = LoginForm
    template_name = "usuarios/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()

        if not eh_administrador(user):
            form.add_error(
                None,
                "Acesso permitido apenas para administradores."
            )
            return self.form_invalid(form)

        return super().form_valid(form)

def logout_view(request):
    logout(request)
    messages.success(request, 'Você saiu do sistema com segurança.')
    return redirect('login')

def eh_administrador(user):
    if not user.is_authenticated:
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

    return render(
        request,
        "usuarios/listar.html",
        {"usuarios": usuarios},
    )

@user_passes_test(eh_administrador, login_url="login")
def cadastrar_usuario(request):

    if request.method == "POST":
        form = CadastroUsuarioForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Usuário cadastrado com sucesso."
            )

            return redirect("listar_usuarios")

    else:
        form = CadastroUsuarioForm()

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
            usuario=usuario
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
            usuario=usuario
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

        user.is_active = not user.is_active
        user.save()

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
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = request.data.get("email")
        senha = request.data.get("senha")

        if not email or not senha:
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

        if user is None:
            return Response(
                {
                    "erro": "E-mail ou senha inválidos."
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
                },
            },
            status=status.HTTP_200_OK,
        )