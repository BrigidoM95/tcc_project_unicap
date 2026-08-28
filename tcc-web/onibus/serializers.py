from rest_framework import serializers

from usuarios.models import Usuario

from .models import Onibus


class OnibusSerializer(serializers.ModelSerializer):

    motorista_nome = serializers.CharField(
        source="motorista.user.first_name",
        read_only=True,
    )

    motorista_email = serializers.EmailField(
        source="motorista.user.email",
        read_only=True,
    )

    status_descricao = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Onibus

        fields = [
            "id",
            "codigo",
            "nome",
            "placa",
            "capacidade",
            "motorista",
            "motorista_nome",
            "motorista_email",
            "foto",
            "status",
            "status_descricao",
            "observacoes",
            "criado_em",
            "atualizado_em",
        ]

        read_only_fields = [
            "id",
            "codigo",
            "status",
            "criado_em",
            "atualizado_em",
        ]

    def validate_motorista(self, motorista):

        if motorista.tipo != Usuario.Tipo.MOTORISTA:
            raise serializers.ValidationError(
                "O usuário selecionado não é um motorista."
            )

        if not motorista.user.is_active:
            raise serializers.ValidationError(
                "O motorista selecionado está inativo."
            )

        return motorista

    def validate_capacidade(self, capacidade):

        if capacidade < 1 or capacidade > 46:
            raise serializers.ValidationError(
                "A capacidade deve estar entre 1 e 46 passageiros."
            )

        return capacidade

    def validate_foto(self, foto):

        if not foto:
            return foto

        limite = 5 * 1024 * 1024

        if foto.size > limite:
            raise serializers.ValidationError(
                "A foto deve possuir no máximo 5 MB."
            )

        nome = foto.name.lower()

        extensoes_permitidas = (
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        )

        if not nome.endswith(extensoes_permitidas):
            raise serializers.ValidationError(
                "Formato inválido. Utilize JPG, JPEG, PNG ou WEBP."
            )

        return foto