"""Consultas compartilhadas pela tela e pelo PDF. Não altera registros."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import models
from django.db.models import Count, Max, Min, OuterRef, Q, Subquery, Value
from django.db.models.functions import TruncDate, Coalesce, NullIf
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
        registros = CheckIn.objects.annotate(ocorrido_em=Coalesce('lido_em','registrado_em')).filter(ocorrido_em__gte=self.inicio, ocorrido_em__lt=self.fim,cancelado_em__isnull=True)
        for campo in ("onibus", "rota"):
            if filtros.get(campo):
                registros = registros.filter(**{f"viagem__{campo}": filtros[campo]})
        if filtros.get("sentido"): registros=registros.filter(sentido=filtros["sentido"])
        for campo in ("associado", "ponto"):
            if filtros.get(campo):
                registros = registros.filter(**{campo: filtros[campo]})
        if filtros.get("sem_ponto"):
            registros = registros.filter(ponto__isnull=True, nome_ponto="")
        busca = filtros.get("freq_q", "").strip()
        if busca:
            # Localiza a pessoa também pelos dados históricos, depois inclui
            # todos os seus embarques no período, mesmo se o nome mudou.
            pessoas = registros.filter(
                Q(associado__user__first_name__icontains=busca)
                | Q(associado__user__last_name__icontains=busca)
                | Q(associado__user__email__icontains=busca)
                | Q(associado__rua__icontains=busca)
                | Q(nome_associado__icontains=busca)
                | Q(rua_associado__icontains=busca)
            ).order_by().values("associado_id")
            registros = registros.filter(associado_id__in=Subquery(pessoas))
        if filtros.get("freq_instituicao"):
            registros = registros.filter(associado__curso__instituicao=filtros["freq_instituicao"])
        self.registros = registros.annotate(
            ponto_informado=Coalesce(
                NullIf("nome_ponto", Value("")), NullIf("ponto__nome", Value("")),
                Value("Não informado"),
            ),
        ).select_related("viagem__rota").order_by("-ocorrido_em", "-pk")

    @cached_property
    def resumo(self):
        return self.registros.aggregate(
            embarques=Count("pk"), associados=Count("associado_id", distinct=True),
            viagens_com_embarque=Count("viagem_id", distinct=True),
            onibus_utilizados=Count("viagem__onibus_id", distinct=True),
        )

    @cached_property
    def frequencia(self):
        # Agrupa pelo identificador, nunca pelo nome, que pode ter sido alterado.
        ultimo = self.registros.filter(associado_id=OuterRef("associado_id"))
        return self.registros.order_by().values("associado_id", instituicao=models.F('associado__curso__instituicao__nome')).annotate(
            nome=Subquery(ultimo.values("nome_associado")[:1]),
            rua=Subquery(ultimo.values("rua_associado")[:1]),
            embarques=Count("pk"),
            dias=Count(TruncDate("ocorrido_em", tzinfo=self.fuso), distinct=True),
            primeira_presenca=Min("ocorrido_em"), ultima_presenca=Max("ocorrido_em"),
        ).order_by("-embarques", "nome", "associado_id")

    @cached_property
    def por_dia(self):
        grupos = self.registros.order_by().annotate(
            dia=TruncDate("ocorrido_em", tzinfo=self.fuso)
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
    def viagens(self):
        # Inclui viagens vazias iniciadas no período e viagens que atravessaram
        # a meia-noite e tiveram um check-in no período. A ocupação usa TODOS
        # os embarques de cada viagem, inclusive ao filtrar um único associado.
        ids = self.registros.order_by().values("viagem_id")
        viagens = Viagem.objects.filter(
            Q(iniciada_em__gte=self.inicio, iniciada_em__lt=self.fim) | Q(pk__in=ids)
        )
        for campo in ("onibus", "rota"):
            if self.filtros.get(campo):
                viagens = viagens.filter(**{campo: self.filtros[campo]})
        if self.filtros.get("sentido"):
            viagens = viagens.filter(Q(ciclo_completo=True) | Q(sentido=self.filtros["sentido"]))
        if any(self.filtros.get(c) for c in ("associado", "ponto", "sem_ponto", "freq_q", "freq_instituicao")):
            viagens = viagens.filter(pk__in=ids)
        return viagens.select_related("rota", "onibus").annotate(
            presentes=Count("checkins", filter=Q(checkins__cancelado_em__isnull=True),distinct=True),
            presentes_ida=Count("checkins",filter=Q(checkins__sentido='ida',checkins__cancelado_em__isnull=True),distinct=True),
            presentes_retorno=Count("checkins",filter=Q(checkins__sentido='retorno',checkins__cancelado_em__isnull=True),distinct=True)
        ).order_by("-iniciada_em", "-pk")

    def preparar_viagens(self, viagens):
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
        separados=[]
        for v,linha in zip(viagens,linhas):
            if not v.ciclo_completo:
                separados.append(linha);continue
            for sentido,campo in [('Ida','presentes_ida'),('Volta','presentes_retorno')]:
                codigo = 'ida' if sentido == 'Ida' else 'retorno'
                if self.filtros.get('sentido') and self.filtros['sentido'] != codigo:
                    continue
                item=dict(linha);presentes=getattr(v,campo)
                item.update(sentido=sentido,presentes=presentes,vagas=max(0,v.capacidade_registrada-presentes) if v.capacidade_registrada else None,ocupacao=round(presentes*100/v.capacidade_registrada,1) if v.capacidade_registrada else None)
                separados.append(item)
        return separados

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
        if f.get("freq_q"): partes.append(f"Associado (nome, e-mail ou RUA): {f['freq_q']}")
        if f.get("freq_instituicao"): partes.append(f"Instituição: {f['freq_instituicao']}")
        partes.append(f"Fuso: {self.fuso.key}")
        return partes
