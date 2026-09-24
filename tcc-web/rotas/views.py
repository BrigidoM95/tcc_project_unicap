from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.db import IntegrityError, transaction
from usuarios.views import eh_administrador

from .forms import RotaForm, PontoEmbarqueForm
from .models import Rota, PontoEmbarque


@user_passes_test(eh_administrador, login_url="login")
def listar_rotas(request):
    filtro_status = request.GET.get("status", "ativas")

    if filtro_status not in ("ativas", "inativas", "todas"):
        filtro_status = "ativas"

    busca = request.GET.get("q", "").strip()

    rotas = Rota.objects.select_related(
        "onibus__motorista__user"
    )

    if filtro_status == "ativas":
        rotas = rotas.filter(status=Rota.Status.ATIVA)
    elif filtro_status == "inativas":
        rotas = rotas.filter(status=Rota.Status.INATIVA)

    if busca:
        rotas = rotas.filter(
            Q(nome__icontains=busca)
            | Q(origem__icontains=busca)
            | Q(destino__icontains=busca)
            | Q(onibus__codigo__icontains=busca)
            | Q(onibus__placa__icontains=busca)
            | Q(onibus__motorista__user__first_name__icontains=busca)
            | Q(onibus__motorista__user__last_name__icontains=busca)
            | Q(onibus__motorista__user__email__icontains=busca)
        )

    return render(
        request,
        "rotas/listar.html",
        {
            "rotas": rotas.order_by("nome", "pk"),
            "busca": busca,
            "filtro_status": filtro_status,
            "total": Rota.objects.count(),
            "total_ativas": Rota.objects.filter(
                status=Rota.Status.ATIVA
            ).count(),
            "total_inativas": Rota.objects.filter(
                status=Rota.Status.INATIVA
            ).count(),
        },
    )


@user_passes_test(eh_administrador, login_url="login")
def cadastrar_rota(request):
    if request.method == "POST":
        form = RotaForm(request.POST)

        if form.is_valid():
            rota = form.save()
            messages.success(
                request,
                f'Rota "{rota.nome}" cadastrada com sucesso.',
            )
            return redirect("listar_rotas")
    else:
        form = RotaForm()

    return render(
        request,
        "rotas/formulario.html",
        {
            "form": form,
            "titulo": "Cadastrar rota",
            "texto_botao": "Cadastrar rota",
        },
    )


@user_passes_test(eh_administrador, login_url="login")
def editar_rota(request, rota_id):
    rota = get_object_or_404(
        Rota.objects.select_related("onibus__motorista__user"),
        pk=rota_id,
    )

    if request.method == "POST":
        form = RotaForm(request.POST, instance=rota)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Rota "{rota.nome}" atualizada com sucesso.',
            )
            return redirect("listar_rotas")
    else:
        form = RotaForm(instance=rota)

    return render(
        request,
        "rotas/formulario.html",
        {
            "form": form,
            "rota": rota,
            "titulo": "Editar rota",
            "texto_botao": "Salvar alterações",
        },
    )


@require_POST
@user_passes_test(eh_administrador, login_url="login")
def alterar_status_rota(request, rota_id):
    rota = get_object_or_404(Rota, pk=rota_id)
    novo_status = request.POST.get("status")

    if novo_status not in Rota.Status.values:
        messages.error(request, "Status inválido.")
        return redirect("listar_rotas")

    if rota.status == novo_status:
        messages.info(request, "A rota já está nesse status.")
        return redirect("listar_rotas")

    rota.status = novo_status

    if novo_status == Rota.Status.ATIVA:
        try:
            rota.full_clean()
        except ValidationError as erro:
            messages.error(
                request,
                "Não foi possível reativar a rota: "
                + " ".join(erro.messages),
            )
            return redirect("listar_rotas")

    rota.save(update_fields=["status"])

    acao = (
        "reativada"
        if novo_status == Rota.Status.ATIVA
        else "inativada"
    )
    messages.success(
        request,
        f'Rota "{rota.nome}" {acao} com sucesso.',
    )

    return redirect("listar_rotas")

@user_passes_test(eh_administrador, login_url="login")
def listar_pontos(request, rota_id):
    rota = get_object_or_404(Rota, pk=rota_id)

    return render(
        request,
        "rotas/pontos.html",
        {
            "rota": rota,
            "pontos": rota.pontos.all(),
        },
    )


@user_passes_test(eh_administrador, login_url="login")
def cadastrar_ponto(request, rota_id):
    rota = get_object_or_404(Rota, pk=rota_id)

    if request.method == "POST":
        form = PontoEmbarqueForm(request.POST, rota=rota)

        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                form.add_error(
                    None,
                    "Não foi possível salvar. Outra alteração pode "
                    "ter ocupado essa posição. Confira a ordem.",
                )
            else:
                messages.success(
                    request,
                    "Ponto de embarque cadastrado com sucesso.",
                )
                return redirect("listar_pontos", rota_id=rota.pk)
    else:
        form = PontoEmbarqueForm(rota=rota)

    return render(
        request,
        "rotas/ponto_formulario.html",
        {
            "form": form,
            "rota": rota,
            "titulo": "Cadastrar ponto de embarque",
        },
    )


@user_passes_test(eh_administrador, login_url="login")
def editar_ponto(request, rota_id, ponto_id):
    rota = get_object_or_404(Rota, pk=rota_id)

    ponto = get_object_or_404(
        PontoEmbarque,
        pk=ponto_id,
        rota=rota,
    )

    if request.method == "POST":
        form = PontoEmbarqueForm(
            request.POST,
            instance=ponto,
            rota=rota,
        )

        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                form.add_error(
                    None,
                    "Não foi possível salvar. Outra alteração pode "
                    "ter ocupado essa posição. Confira a ordem.",
                )
            else:
                messages.success(
                    request,
                    "Ponto de embarque atualizado com sucesso.",
                )
                return redirect("listar_pontos", rota_id=rota.pk)
    else:
        form = PontoEmbarqueForm(instance=ponto, rota=rota)

    return render(
        request,
        "rotas/ponto_formulario.html",
        {
            "form": form,
            "rota": rota,
            "titulo": "Editar ponto de embarque",
        },
    )