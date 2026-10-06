import re

from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models

from usuarios.models import Usuario


def validar_tamanho_foto(arquivo):
    """
    Limita o tamanho da imagem do ônibus a 5 MB.
    """

    limite = 5 * 1024 * 1024

    if arquivo.size > limite:
        raise ValidationError(
            "A foto do ônibus deve possuir no máximo 5 MB."
        )


class Onibus(models.Model):

    class Status(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        INATIVO = "inativo", "Inativo"

    codigo = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        editable=False,
        verbose_name="Código",
    )

    nome = models.CharField(
        max_length=100,
        verbose_name="Nome/Identificação",
    )

    placa = models.CharField(
        max_length=7,
        unique=True,
        verbose_name="Placa",
    )

    capacidade = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(
                1,
                message="A capacidade mínima é de 1 passageiro.",
            ),
            MaxValueValidator(
                46,
                message="A capacidade máxima permitida é de 46 passageiros.",
            ),
        ],
        verbose_name="Capacidade",
    )

    motorista = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="onibus",
        limit_choices_to={
            "tipo": Usuario.Tipo.MOTORISTA,
        },
        verbose_name="Motorista",
    )

    foto = models.ImageField(
        upload_to="onibus/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "jpg",
                    "jpeg",
                    "png",
                    "webp",
                ]
            ),
            validar_tamanho_foto,
        ],
        verbose_name="Foto do veículo",
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ATIVO,
        verbose_name="Status",
    )

    observacoes = models.TextField(
        max_length=500,
        blank=True,
        verbose_name="Observações",
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em",
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em",
    )

    class Meta:
        verbose_name = "Ônibus"
        verbose_name_plural = "Ônibus"
        ordering = ["codigo"]

    def __str__(self):
        return (
            f"{self.codigo or 'Novo ônibus'} - "
            f"{self.nome} - "
            f"{self.placa}"
        )

    @property
    def ativo(self):
        return self.status == self.Status.ATIVO

    def clean(self):
        super().clean()

        # ==================================================
        # VALIDAÇÃO DA PLACA
        # ==================================================

        if self.placa:

            placa = re.sub(
                r"[^A-Za-z0-9]",
                "",
                self.placa,
            ).upper()

            # Aceita:
            # ABC1234 - padrão antigo
            # ABC1D23 - padrão Mercosul

            if not re.fullmatch(
                r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}",
                placa,
            ):
                raise ValidationError(
                    {
                        "placa": (
                            "Informe uma placa brasileira válida. "
                            "Exemplos: ABC1234 ou ABC1D23."
                        )
                    }
                )

            self.placa = placa

        # ==================================================
        # VALIDAÇÃO DO MOTORISTA
        # ==================================================

        if self.motorista_id:

            if self.motorista.tipo != Usuario.Tipo.MOTORISTA:
                raise ValidationError(
                    {
                        "motorista": (
                            "O usuário selecionado não é um motorista."
                        )
                    }
                )

            if not self.motorista.user.is_active:
                raise ValidationError(
                    {
                        "motorista": (
                            "Não é possível vincular "
                            "um motorista inativo."
                        )
                    }
                )

    def save(self, *args, **kwargs):

        # Normaliza a placa antes de salvar
        if self.placa:

            self.placa = re.sub(
                r"[^A-Za-z0-9]",
                "",
                self.placa,
            ).upper()

        super().save(*args, **kwargs)

        # ==================================================
        # GERAÇÃO AUTOMÁTICA DO CÓDIGO
        # ==================================================

        if not self.codigo:

            self.codigo = f"ONI{self.pk:06d}"

            type(self).objects.filter(
                pk=self.pk
            ).update(
                codigo=self.codigo
            )

    def desativar(self):

        if self.status != self.Status.INATIVO:

            self.status = self.Status.INATIVO

            self.save(
                update_fields=[
                    "status",
                    "atualizado_em",
                ]
            )

    def reativar(self):

        if self.status != self.Status.ATIVO:

            self.status = self.Status.ATIVO

            self.save(
                update_fields=[
                    "status",
                    "atualizado_em",
                ]
            )