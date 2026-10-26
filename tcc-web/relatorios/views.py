from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from usuarios.views import eh_administrador

from .forms import FiltrosRelatorioForm
from .services import RelatorioEmbarques, fuso_relatorios


def administrador_ativo(view):
    @wraps(view)
    def protegida(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url="login")
        if not request.user.is_active or not eh_administrador(request.user):
            raise PermissionDenied("Acesso exclusivo para administradores ativos.")
        with timezone.override(fuso_relatorios()):
            return view(request, *args, **kwargs)
    return protegida


def formulario(request):
    dados = request.GET.copy()
    hoje = timezone.localdate()
    # Datas ausentes usam o mês atual. Datas vazias/inválidas geram erro.
    dados.setdefault("data_inicial", hoje.replace(day=1).isoformat())
    dados.setdefault("data_final", hoje.isoformat())
    return FiltrosRelatorioForm(dados)


def pagina(queryset, request, parametro):
    return Paginator(queryset, 25).get_page(request.GET.get(parametro))


@never_cache
@require_GET
@administrador_ativo
def painel(request):
    form = formulario(request)
    from gestao.indicadores import associados_por_instituicao
    contexto = {"form": form, "fuso": fuso_relatorios().key,**associados_por_instituicao()}
    if form.is_valid():
        rel = RelatorioEmbarques(form.cleaned_data)
        parametros = form.data.copy()
        for chave in ("pagina_embarques", "pagina_frequencia", "pagina_viagens"):
            parametros.pop(chave, None)
        viagens = pagina(rel.viagens, request, "pagina_viagens")
        contexto.update(
            relatorio=rel, resumo=rel.resumo, parametros=parametros.urlencode(),
            embarques=pagina(rel.registros, request, "pagina_embarques"),
            frequencia=pagina(rel.frequencia, request, "pagina_frequencia"),
            viagens=viagens, linhas_viagens=rel.preparar_viagens(viagens),
            por_dia=rel.por_dia,
        )
    return render(request, "relatorios/painel.html", contexto)


@never_cache
@require_GET
@administrador_ativo
def exportar_pdf(request):
    form = formulario(request)
    if not form.is_valid():
        return render(request, "relatorios/painel.html", {"form": form, "fuso": fuso_relatorios().key}, status=400)
    from .pdf import gerar_pdf
    rel = RelatorioEmbarques(form.cleaned_data)
    # Limite explícito para não gerar um PDF gigantesco no servidor.
    # Nunca corta registros silenciosamente.
    if rel.resumo["embarques"] > 10000 or rel.viagens.count() > 3000:
        form.add_error(None, "O PDF admite até 10.000 embarques e 3.000 viagens. Reduza o período ou use os filtros.")
        return render(request, "relatorios/painel.html", {"form": form, "fuso": fuso_relatorios().key}, status=400)
    resposta = HttpResponse(gerar_pdf(rel), content_type="application/pdf")
    inicio = form.cleaned_data["data_inicial"].isoformat()
    fim = form.cleaned_data["data_final"].isoformat()
    resposta["Content-Disposition"] = f'attachment; filename="relatorios-unicap-{inicio}-{fim}.pdf"'
    return resposta
