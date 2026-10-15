from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from rest_framework import status
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.views import eh_administrador

from .forms import OnibusForm
from .models import Onibus
from .serializers import OnibusSerializer

class AdministradorOuSomenteLeitura(BasePermission):
    def has_permission(self, request, view):
        if not request.user:
            return False

        if not request.user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        return eh_administrador(request.user)

@user_passes_test(
    eh_administrador,
    login_url="login",
)
def listar_onibus(request):

    filtro_status = request.GET.get(
        "status",
        "ativos",
    )

    busca = request.GET.get(
        "q",
        "",
    ).strip()

    queryset = Onibus.objects.select_related(
        "motorista",
        "motorista__user",
    )


    if filtro_status == "ativos":

        queryset = queryset.filter(
            status=Onibus.Status.ATIVO
        )

    elif filtro_status == "inativos":

        queryset = queryset.filter(
            status=Onibus.Status.INATIVO
        )

    elif filtro_status == "todos":

        pass

    else:

        filtro_status = "ativos"

        queryset = queryset.filter(
            status=Onibus.Status.ATIVO
        )

    if busca:

        queryset = queryset.filter(
            Q(codigo__icontains=busca)
            | Q(nome__icontains=busca)
            | Q(placa__icontains=busca)
            | Q(
                motorista__user__first_name__icontains=busca
            )
            | Q(
                motorista__user__last_name__icontains=busca
            )
            | Q(
                motorista__user__email__icontains=busca
            )
        )

    queryset = queryset.order_by(
        "codigo"
    )

    total = Onibus.objects.count()

    total_ativos = Onibus.objects.filter(
        status=Onibus.Status.ATIVO
    ).count()

    total_inativos = Onibus.objects.filter(
        status=Onibus.Status.INATIVO
    ).count()

    contexto = {
        "onibus": queryset,
        "busca": busca,
        "filtro_status": filtro_status,
        "total": total,
        "total_ativos": total_ativos,
        "total_inativos": total_inativos,
    }

    return render(
        request,
        "onibus/listar.html",
        contexto,
    )

@user_passes_test(
    eh_administrador,
    login_url="login",
)
def cadastrar_onibus(request):

    if request.method == "POST":

        form = OnibusForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():

            onibus = form.save()

            messages.success(
                request,
                (
                    f"Ônibus {onibus.codigo} "
                    "cadastrado com sucesso."
                ),
            )

            return redirect(
                "listar_onibus"
            )

    else:

        form = OnibusForm()

    contexto = {
        "form": form,
        "titulo": "Cadastrar ônibus",
        "texto_botao": "Cadastrar ônibus",
        "modo_edicao": False,
    }

    return render(
        request,
        "onibus/formulario.html",
        contexto,
    )

@user_passes_test(
    eh_administrador,
    login_url="login",
)
def editar_onibus(
    request,
    onibus_id,
):

    onibus = get_object_or_404(
        Onibus.objects.select_related(
            "motorista",
            "motorista__user",
        ),
        pk=onibus_id,
    )

    if request.method == "POST":

        form = OnibusForm(
            request.POST,
            request.FILES,
            instance=onibus,
        )

        if form.is_valid():

            onibus = form.save()

            messages.success(
                request,
                (
                    f"Ônibus {onibus.codigo} "
                    "atualizado com sucesso."
                ),
            )

            return redirect(
                "listar_onibus"
            )

    else:

        form = OnibusForm(
            instance=onibus
        )

    contexto = {
        "form": form,
        "titulo": "Editar ônibus",
        "texto_botao": "Salvar alterações",
        "modo_edicao": True,
        "onibus": onibus,
    }

    return render(
        request,
        "onibus/formulario.html",
        contexto,
    )

@require_POST
@user_passes_test(
    eh_administrador,
    login_url="login",
)
def alterar_status_onibus(
    request,
    onibus_id,
):

    onibus = get_object_or_404(
        Onibus,
        pk=onibus_id,
    )

    if onibus.status == Onibus.Status.ATIVO:

        onibus.desativar()

        messages.success(
            request,
            (
                f"Ônibus {onibus.codigo} "
                "inativado com sucesso."
            ),
        )

    else:

        try:

            onibus.full_clean()

            onibus.reativar()

            messages.success(
                request,
                (
                    f"Ônibus {onibus.codigo} "
                    "reativado com sucesso."
                ),
            )

        except ValidationError as erro:

            messages.error(
                request,
                (
                    "Não foi possível reativar o ônibus. "
                    f"{erro}"
                ),
            )

    return redirect(
        "listar_onibus"
    )



class OnibusListaApiView(APIView):

    permission_classes = [
        AdministradorOuSomenteLeitura
    ]

    def get(self, request):

        queryset = Onibus.objects.select_related(
            "motorista",
            "motorista__user",
        ).order_by(
            "codigo"
        )

        mostrar_todos = (
            request.query_params.get(
                "todos"
            )
            == "1"
        )

        # Usuário comum vê somente ônibus ativos
        if not (
            mostrar_todos
            and eh_administrador(request.user)
        ):

            queryset = queryset.filter(
                status=Onibus.Status.ATIVO
            )

        serializer = OnibusSerializer(
            queryset,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def post(self, request):

        serializer = OnibusSerializer(
            data=request.data,
            context={
                "request": request,
            },
        )

        if serializer.is_valid():

            onibus = serializer.save()

            resposta = OnibusSerializer(
                onibus,
                context={
                    "request": request,
                },
            )

            return Response(
                resposta.data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

class OnibusDetalheApiView(APIView):

    permission_classes = [
        AdministradorOuSomenteLeitura
    ]

    def get_object(
        self,
        request,
        onibus_id,
    ):

        queryset = Onibus.objects.select_related(
            "motorista",
            "motorista__user",
        )

        # Quem não é administrador
        # só pode visualizar ônibus ativos
        if not eh_administrador(
            request.user
        ):

            queryset = queryset.filter(
                status=Onibus.Status.ATIVO
            )

        return get_object_or_404(
            queryset,
            pk=onibus_id,
        )

    def get(
        self,
        request,
        onibus_id,
    ):

        onibus = self.get_object(
            request,
            onibus_id,
        )

        serializer = OnibusSerializer(
            onibus,
            context={
                "request": request,
            },
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def put(
        self,
        request,
        onibus_id,
    ):

        onibus = self.get_object(
            request,
            onibus_id,
        )

        serializer = OnibusSerializer(
            onibus,
            data=request.data,
            context={
                "request": request,
            },
        )

        if serializer.is_valid():

            serializer.save()

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    def patch(
        self,
        request,
        onibus_id,
    ):

        onibus = self.get_object(
            request,
            onibus_id,
        )

        serializer = OnibusSerializer(
            onibus,
            data=request.data,
            partial=True,
            context={
                "request": request,
            },
        )

        if serializer.is_valid():

            serializer.save()

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


class DesativarOnibusApiView(APIView):

    permission_classes = [
        AdministradorOuSomenteLeitura
    ]

    def post(
        self,
        request,
        onibus_id,
    ):

        onibus = get_object_or_404(
            Onibus,
            pk=onibus_id,
        )

        onibus.desativar()

        return Response(
            {
                "mensagem": (
                    "Ônibus inativado com sucesso."
                ),
                "id": onibus.id,
                "codigo": onibus.codigo,
                "status": onibus.status,
            },
            status=status.HTTP_200_OK,
        )


class ReativarOnibusApiView(APIView):

    permission_classes = [
        AdministradorOuSomenteLeitura
    ]

    def post(
        self,
        request,
        onibus_id,
    ):

        onibus = get_object_or_404(
            Onibus,
            pk=onibus_id,
        )

        try:

            onibus.full_clean()

            onibus.reativar()

        except ValidationError as erro:

            return Response(
                {
                    "erro": (
                        "Não foi possível reativar o ônibus."
                    ),
                    "detalhes": erro.message_dict,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "mensagem": (
                    "Ônibus reativado com sucesso."
                ),
                "id": onibus.id,
                "codigo": onibus.codigo,
                "status": onibus.status,
            },
            status=status.HTTP_200_OK,
        )