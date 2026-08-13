from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CadastroUsuarioForm, EdicaoUsuarioForm, LoginForm
from .forms import LoginForm, CadastroUsuarioForm
from .models import Usuario


class UsuarioLoginView(LoginView):
    authentication_form = LoginForm
    template_name = 'usuarios/login.html'
    redirect_authenticated_user = True


def logout_view(request):
    logout(request)
    messages.success(request, 'Você saiu do sistema com segurança.')
    return redirect('login')

def eh_administrador(user):
    if not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
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