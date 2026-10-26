import re

from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models, transaction

from usuarios.models import Usuario


def validar_tamanho_foto(arquivo):
    """
    Limita o tamanho da imagem do ônibus a 5 MB.
    """

    limite = 5 * 1024 * 1024

    try:
        tamanho = arquivo.size
    except FileNotFoundError:
        # Alguns cadastros legados apontam para fotos que não vieram no projeto.
        return
    if tamanho > limite:
        raise ValidationError(
            "A foto do ônibus deve possuir no máximo 5 MB."
        )


class Onibus(models.Model):
    miniatura = models.ImageField(upload_to='onibus/miniaturas/',blank=True,editable=False)

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
        constraints = [models.CheckConstraint(condition=models.Q(capacidade__gte=1, capacidade__lte=46), name='onibus_capacidade_1_46')]


    def __str__(self):
        return (
            f"{self.codigo or 'Novo ônibus'} - "
            f"{self.nome} - "
            f"{self.placa}"
        )

    @property
    def ativo(self):
        return self.status == self.Status.ATIVO

    @property
    def foto_url(self):
        return self.foto.url if self.foto and self.foto.storage.exists(self.foto.name) else ''

    @property
    def miniatura_url(self):
        return self.miniatura.url if self.miniatura and self.miniatura.storage.exists(self.miniatura.name) else self.foto_url

    def clean(self):
        super().clean()

        if self.pk:
            anterior = type(self).objects.get(pk=self.pk)
            if self.viagens.filter(status='em_andamento').exists() and any(getattr(anterior, f) != getattr(self, f) for f in ['status','capacidade','motorista_id']):
                raise ValidationError('Há uma viagem em andamento. Use a intervenção administrativa da viagem.')

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

    @transaction.atomic
    def desativar(self):
        # Um único comando mantém ônibus e rotas consistentes e auditados.
        atual = type(self).objects.select_for_update().get(pk=self.pk)
        rotas = list(atual.rotas.select_for_update().filter(status='ativa').order_by('pk'))
        if atual.viagens.filter(status='em_andamento').exists() or any(
            rota.viagens.filter(status='em_andamento').exists() for rota in rotas
        ):
            raise ValidationError('Há uma viagem em andamento. Encerre a viagem ou use a intervenção administrativa antes de inativar o ônibus.')
        atual.status = self.Status.INATIVO
        for rota in rotas:
            rota.status = 'inativa'
            rota.save(update_fields=['status'])
        atual.save(update_fields=['status', 'atualizado_em'])
        self.status = atual.status
        self.atualizado_em = atual.atualizado_em
        return rotas

    def reativar(self):

        if self.status != self.Status.ATIVO:

            self.status = self.Status.ATIVO

            self.save(
                update_fields=[
                    "status",
                    "atualizado_em",
                ]
            )
