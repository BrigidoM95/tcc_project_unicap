from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta


from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from onibus.models import Onibus
from usuarios.models import Usuario

from .models import LocalizacaoViagem, Rota, Viagem



def buscar_motorista(user):
    return Usuario.objects.filter(
        user=user,
        user__is_active=True,
        tipo=Usuario.Tipo.MOTORISTA,
    ).first()


def exigir_motorista(user):
    motorista = buscar_motorista(user)

    if motorista is None:
        raise PermissionDenied(
            "Esta operação é exclusiva para motoristas ativos."
        )

    return motorista


def dados_viagem(viagem):
    return {
        "id": viagem.pk,
        "rota_id": viagem.rota_id,
        "rota_nome": viagem.rota.nome,
        "onibus_codigo": viagem.onibus.codigo,
        "placa": viagem.onibus.placa,
        "motorista_nome": str(viagem.motorista),
        "sentido": viagem.sentido,
        "status": viagem.status,
        "iniciada_em": viagem.iniciada_em.isoformat(),
        "finalizada_em": (
            viagem.finalizada_em.isoformat()
            if viagem.finalizada_em
            else None
        ),
    }


class InicioViagemSerializer(serializers.Serializer):
    rota_id = serializers.IntegerField(min_value=1)
    sentido = serializers.ChoiceField(
        choices=Viagem.Sentido.choices
    )


class BaseViagemApi(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


class PainelMotoristaApi(BaseViagemApi):
    def get(self, request):
        motorista = buscar_motorista(request.user)

        if motorista is None:
            return Response({
                "motorista": False,
                "rotas": [],
                "viagem": None,
            })

        rotas = (
            Rota.objects
            .filter(
                status=Rota.Status.ATIVA,
                onibus__status=Onibus.Status.ATIVO,
                onibus__motorista=motorista,
            )
            .select_related("onibus")
            .order_by("nome", "pk")
        )

        # Não depende do vínculo atual do ônibus.
        viagem = (
            Viagem.objects
            .filter(
                motorista=motorista,
                status=Viagem.Status.EM_ANDAMENTO,
            )
            .select_related("rota", "onibus", "motorista__user")
            .first()
        )

        return Response({
            "motorista": True,
            "rotas": [
                {
                    "id": rota.pk,
                    "nome": rota.nome,
                    "origem": rota.origem,
                    "destino": rota.destino,
                    "onibus_codigo": rota.onibus.codigo,
                    "placa": rota.onibus.placa,
                    "horario_ida": rota.horario_ida.strftime("%H:%M"),
                    "horario_retorno": (
                        rota.horario_retorno.strftime("%H:%M")
                    ),
                }
                for rota in rotas
            ],
            "viagem": dados_viagem(viagem) if viagem else None,
        })


class IniciarViagemApi(BaseViagemApi):
    def post(self, request):
        motorista = exigir_motorista(request.user)

        entrada = InicioViagemSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                # Serializa tentativas do mesmo motorista
                # nos bancos que suportam bloqueio de linhas.
                motorista = get_object_or_404(
                    Usuario.objects.select_for_update(),
                    pk=motorista.pk,
                    tipo=Usuario.Tipo.MOTORISTA,
                    user__is_active=True,
                )

                rota = get_object_or_404(
                    Rota.objects.select_for_update(),
                    pk=entrada.validated_data["rota_id"],
                )

                onibus = get_object_or_404(
                    Onibus.objects.select_for_update(),
                    pk=rota.onibus_id,
                )

                if onibus.motorista_id != motorista.pk:
                    raise PermissionDenied(
                        "Você não é o motorista deste ônibus."
                    )

                if not rota.ativa or not onibus.ativo:
                    return Response(
                        {"detail": "A rota e o ônibus precisam estar ativos."},
                        status=400,
                    )

                existe_viagem = Viagem.objects.filter(
                    Q(onibus=onibus) | Q(motorista=motorista),
                    status=Viagem.Status.EM_ANDAMENTO,
                ).exists()

                if existe_viagem:
                    return Response(
                        {
                            "detail": (
                                "O ônibus ou motorista já possui "
                                "uma viagem em andamento."
                            )
                        },
                        status=409,
                    )

                viagem = Viagem.objects.create(
                    rota=rota,
                    onibus=onibus,
                    motorista=motorista,
                    sentido=entrada.validated_data["sentido"],
                )

        except IntegrityError:
            # As restrições do modelo também protegem
            # contra solicitações concorrentes.
            return Response(
                {
                    "detail": (
                        "Não foi possível iniciar. Atualize o painel "
                        "e confira se já existe uma viagem em andamento."
                    )
                },
                status=409,
            )

        return Response(dados_viagem(viagem), status=201)


class FinalizarViagemApi(BaseViagemApi):
    def post(self, request, viagem_id):
        motorista = exigir_motorista(request.user)

        with transaction.atomic():
            viagem = get_object_or_404(
                Viagem.objects.select_for_update(),
                pk=viagem_id,
                motorista=motorista,
            )

            # Repetir a solicitação não altera o horário final.
            if viagem.status == Viagem.Status.EM_ANDAMENTO:
                fim = max(timezone.now(), viagem.iniciada_em)

                Viagem.objects.filter(
                    pk=viagem.pk,
                    status=Viagem.Status.EM_ANDAMENTO,
                ).update(
                    status=Viagem.Status.FINALIZADA,
                    finalizada_em=fim,
                )

                viagem.refresh_from_db()

        return Response(dados_viagem(viagem))

class LocalizacaoEntradaSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=-90,
        max_value=90,
    )

    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=-180,
        max_value=180,
    )

    precisao_metros = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
        allow_null=True,
        default=None,
    )

    capturada_em = serializers.DateTimeField()


class EnviarLocalizacaoApi(BaseViagemApi):
    def post(self, request, viagem_id):
        motorista = exigir_motorista(request.user)

        entrada = LocalizacaoEntradaSerializer(
            data=request.data
        )
        entrada.is_valid(raise_exception=True)

        dados = entrada.validated_data

        with transaction.atomic():
            # Usa o mesmo bloqueio da finalização da viagem.
            viagem = get_object_or_404(
                Viagem.objects.select_for_update(),
                pk=viagem_id,
                motorista=motorista,
            )

            if not viagem.em_andamento:
                return Response(
                    {
                        "detail": (
                            "Esta viagem já foi finalizada. "
                            "O envio de localização foi encerrado."
                        )
                    },
                    status=409,
                )

            captura = dados["capturada_em"]
            agora = timezone.now()

            if captura < viagem.iniciada_em:
                return Response(
                    {
                        "detail": (
                            "A localização foi capturada antes "
                            "do início desta viagem."
                        )
                    },
                    status=400,
                )

            # Tolerância para pequena diferença no relógio
            # do aparelho.
            if captura > agora + timedelta(seconds=30):
                return Response(
                    {
                        "detail": (
                            "O horário da localização está no futuro. "
                            "Confira o relógio do aparelho."
                        )
                    },
                    status=400,
                )

            # Nesta primeira versão, aceitamos apenas
            # leituras recentes, sem fila de envio offline.
            if captura < agora - timedelta(minutes=2):
                return Response(
                    {
                        "detail": (
                            "A localização está antiga. "
                            "Capture uma nova posição."
                        )
                    },
                    status=400,
                )

            localizacao, criada = (
                LocalizacaoViagem.objects.get_or_create(
                    viagem=viagem,
                    capturada_em=captura,
                    defaults={
                        "latitude": dados["latitude"],
                        "longitude": dados["longitude"],
                        "precisao_metros": dados["precisao_metros"],
                    },
                )
            )

            if not criada:
                mesma_leitura = (
                    localizacao.latitude == dados["latitude"]
                    and localizacao.longitude == dados["longitude"]
                    and localizacao.precisao_metros
                    == dados["precisao_metros"]
                )

                if not mesma_leitura:
                    return Response(
                        {
                            "detail": (
                                "Já existe uma localização com "
                                "esse horário e dados diferentes."
                            )
                        },
                        status=409,
                    )

        return Response(
            {
                "id": localizacao.pk,
                "viagem_id": localizacao.viagem_id,
                "latitude": float(localizacao.latitude),
                "longitude": float(localizacao.longitude),
                "precisao_metros": (
                    float(localizacao.precisao_metros)
                    if localizacao.precisao_metros is not None
                    else None
                ),
                "capturada_em": (
                    localizacao.capturada_em.isoformat()
                ),
                "recebida_em": (
                    localizacao.recebida_em.isoformat()
                ),
                "criada": criada,
            },
            status=201 if criada else 200,
        )
