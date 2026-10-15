"""Consultas compartilhadas pela tela e pelo PDF. Não altera registros."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Count, Max, Min, OuterRef, Q, Subquery
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.functional import cached_property

from embarques.models import CheckIn
from rotas.models import Viagem


def fuso_relatorios():
    # Operação da UNICAP em Caarapó/MS. Não altera o fuso dos outros módulos.
    return ZoneInfo(getattr(settings, "RELATORIOS_TIME_ZONE", "America/Campo_Grande"))


class RelatorioEmbarques:
    def __init__(self, filtros):
        self.filtros = filtros
        self.fuso = fuso_relatorios()
        self.inicio = datetime.combine(filtros["data_inicial"], time.min, self.fuso)
        self.fim = datetime.combine(filtros["data_final"] + timedelta(days=1), time.min, self.fuso)
        registros = CheckIn.objects.filter(registrado_em__gte=self.inicio, registrado_em__lt=self.fim)
        for campo in ("onibus", "rota", "sentido"):
            if filtros.get(campo):
                registros = registros.filter(**{f"viagem__{campo}": filtros[campo]})
        for campo in ("associado", "ponto"):
            if filtros.get(campo):
                registros = registros.filter(**{campo: filtros[campo]})
        if filtros.get("sem_ponto"):
            registros = registros.filter(ponto__isnull=True)
        self.registros = registros.select_related("viagem__rota").order_by("-registrado_em", "-pk")

    @cached_property
    def resumo(self):
        return self.registros.aggregate(
            embarques=Count("pk"), associados=Count("associado_id", distinct=True),
            viagens_com_embarque=Count("viagem_id", distinct=True),
            onibus_utilizados=Count("viagem__onibus_id", distinct=True),
            sem_ponto=Count("pk", filter=Q(ponto__isnull=True)),
        )

    @cached_property
    def frequencia(self):
        # Agrupa pelo identificador, nunca pelo nome, que pode ter sido alterado.
        ultimo = self.registros.filter(associado_id=OuterRef("associado_id"))
        return self.registros.order_by().values("associado_id").annotate(
            nome=Subquery(ultimo.values("nome_associado")[:1]),
            rua=Subquery(ultimo.values("rua_associado")[:1]),
            embarques=Count("pk"),
            dias=Count(TruncDate("registrado_em", tzinfo=self.fuso), distinct=True),
            primeira_presenca=Min("registrado_em"), ultima_presenca=Max("registrado_em"),
        ).order_by("-embarques", "nome", "associado_id")

    @cached_property
    def por_dia(self):
        grupos = self.registros.order_by().annotate(
            dia=TruncDate("registrado_em", tzinfo=self.fuso)
        ).values("dia").annotate(total=Count("pk")).order_by("dia")
        mapa = {item["dia"]: item["total"] for item in grupos}
        dia = self.filtros["data_inicial"]
        linhas = []
        while dia <= self.filtros["data_final"]:
            linhas.append({"dia": dia, "total": mapa.get(dia, 0)})
            dia += timedelta(days=1)
        maior = max((r["total"] for r in linhas), default=0)
        for r in linhas:
            r["percentual"] = round(r["total"] * 100 / maior) if maior else 0
        return linhas

    @cached_property
    def por_onibus(self):
        ultimo = self.registros.filter(viagem__onibus_id=OuterRef("viagem__onibus_id"))
        return self.registros.order_by().values("viagem__onibus_id").annotate(
            codigo=Subquery(ultimo.values("codigo_onibus")[:1]),
            placa=Subquery(ultimo.values("placa_onibus")[:1]),
            embarques=Count("pk"), associados=Count("associado_id", distinct=True),
            viagens=Count("viagem_id", distinct=True),
        ).order_by("-embarques", "viagem__onibus_id")

    @cached_property
    def por_ponto(self):
        ultimo = self.registros.filter(ponto_id=OuterRef("ponto_id"))
        grupos = self.registros.order_by().values(
            "ponto_id", "ponto__rota__nome", "ponto__sentido"
        ).annotate(nome=Subquery(ultimo.values("nome_ponto")[:1]), total=Count("pk"))
        return grupos.order_by("-total", "ponto_id")

    @cached_property
    def viagens(self):
        # Inclui viagens vazias iniciadas no período e viagens que atravessaram
        # a meia-noite e tiveram um check-in no período. A ocupação usa TODOS
        # os embarques de cada viagem, inclusive ao filtrar um único associado.
        ids = self.registros.order_by().values("viagem_id")
        viagens = Viagem.objects.filter(
            Q(iniciada_em__gte=self.inicio, iniciada_em__lt=self.fim) | Q(pk__in=ids)
        )
        for campo in ("onibus", "rota", "sentido"):
            if self.filtros.get(campo):
                viagens = viagens.filter(**{campo: self.filtros[campo]})
        if any(self.filtros.get(c) for c in ("associado", "ponto", "sem_ponto")):
            viagens = viagens.filter(pk__in=ids)
        return viagens.select_related("rota", "onibus").annotate(
            presentes=Count("checkins", distinct=True)
        ).order_by("-iniciada_em", "-pk")

    @staticmethod
    def preparar_viagens(viagens):
        linhas = []
        for v in viagens:
            capacidade = v.capacidade_registrada
            linhas.append({
                "id": v.pk, "rota": v.nome_rota_historico,
                "onibus": v.codigo_onibus_registrado or v.onibus.codigo,
                "placa": v.placa_onibus_registrada or v.onibus.placa,
                "inicio": v.iniciada_em, "sentido": v.get_sentido_display(),
                "status": v.get_status_display(), "presentes": v.presentes,
                "capacidade": capacidade,
                "vagas": max(0, capacidade - v.presentes) if capacidade else None,
                "ocupacao": round(v.presentes * 100 / capacidade, 1) if capacidade else None,
            })
        return linhas

    @cached_property
    def filtros_legiveis(self):
        f = self.filtros
        partes = [f"Período: {f['data_inicial']:%d/%m/%Y} a {f['data_final']:%d/%m/%Y}"]
        for campo, titulo in (("onibus", "Ônibus"), ("rota", "Rota"),
                              ("associado", "Associado"), ("ponto", "Ponto")):
            if f.get(campo):
                partes.append(f"{titulo}: {f[campo]}")
        if f.get("sentido"):
            partes.append(f"Sentido: {dict(Viagem.Sentido.choices)[f['sentido']]}")
        if f.get("sem_ponto"):
            partes.append("Somente sem ponto informado")
        partes.append(f"Fuso: {self.fuso.key}")
        return partes
