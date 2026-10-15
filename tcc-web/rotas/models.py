from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from onibus.models import Onibus
from usuarios.models import Usuario


class Rota(models.Model):

    class Status(models.TextChoices):
        ATIVA = "ativa", "Ativa"
        INATIVA = "inativa", "Inativa"

    nome = models.CharField(
        max_length=100,
        verbose_name="Nome da rota",
    )

    origem = models.CharField(
        max_length=150,
        verbose_name="Origem",
    )

    destino = models.CharField(
        max_length=150,
        verbose_name="Destino",
    )

    onibus = models.ForeignKey(
        Onibus,
        on_delete=models.PROTECT,
        related_name="rotas",
        verbose_name="Ônibus",
    )

    horario_ida = models.TimeField(
        verbose_name="Horário previsto de ida",
    )

    horario_retorno = models.TimeField(
        verbose_name="Horário previsto de retorno",
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ATIVA,
        verbose_name="Status",
    )

    observacoes = models.TextField(
        max_length=500,
        blank=True,
        verbose_name="Observações",
    )

    class Meta:
        verbose_name = "Rota"
        verbose_name_plural = "Rotas"
        ordering = ["nome", "pk"]

    def __str__(self):
        return f"{self.nome} — {self.origem} → {self.destino}"

    @property
    def ativa(self):
        return self.status == self.Status.ATIVA

    @property
    def motorista(self):
        if not self.onibus_id:
            return None

        return self.onibus.motorista

    def clean(self):
        super().clean()

        self.nome = (self.nome or "").strip()
        self.origem = (self.origem or "").strip()
        self.destino = (self.destino or "").strip()

        erros = {}

        if not self.nome:
            erros["nome"] = "Informe o nome da rota."

        if not self.origem:
            erros["origem"] = "Informe a origem."

        if not self.destino:
            erros["destino"] = "Informe o destino."

        if (
            self.origem
            and self.destino
            and self.origem.casefold() == self.destino.casefold()
        ):
            erros["destino"] = (
                "O destino deve ser diferente da origem."
            )

        if self.ativa and self.onibus_id:
            onibus = (
                Onibus.objects
                .select_related("motorista__user")
                .filter(pk=self.onibus_id)
                .first()
            )

            if onibus is None:
                erros["onibus"] = (
                    "O ônibus selecionado não existe."
                )

            elif not onibus.ativo:
                erros["onibus"] = (
                    "Selecione um ônibus ativo para esta rota."
                )

            elif (
                onibus.motorista.tipo != Usuario.Tipo.MOTORISTA
                or not onibus.motorista.user.is_active
            ):
                erros["onibus"] = (
                    "O ônibus precisa estar vinculado "
                    "a um motorista ativo."
                )

        if erros:
            raise ValidationError(erros)


class PontoEmbarque(models.Model):

    class Sentido(models.TextChoices):
        IDA = "ida", "Ida"
        RETORNO = "retorno", "Retorno"

    rota = models.ForeignKey(
        Rota,
        on_delete=models.PROTECT,
        related_name="pontos",
        verbose_name="Rota",
    )

    nome = models.CharField(
        max_length=100,
        verbose_name="Nome do ponto",
    )

    endereco = models.CharField(
        max_length=200,
        verbose_name="Endereço ou referência",
    )

    sentido = models.CharField(
        max_length=10,
        choices=Sentido.choices,
        default=Sentido.IDA,
        verbose_name="Sentido",
    )

    ordem = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Ordem da parada",
    )

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90),
        ],
        verbose_name="Latitude",
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180),
        ],
        verbose_name="Longitude",
    )

    class Meta:
        verbose_name = "Ponto de embarque"
        verbose_name_plural = "Pontos de embarque"
        ordering = ["sentido", "ordem", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["rota", "sentido", "ordem"],
                name="ponto_rota_sentido_ordem_unicos",
            ),
            models.CheckConstraint(
                condition=models.Q(ordem__gte=1),
                name="ponto_ordem_maior_zero",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_sentido_display()} "
            f"— {self.ordem}: {self.nome}"
        )

    def clean(self):
        super().clean()

        self.nome = (self.nome or "").strip()
        self.endereco = (self.endereco or "").strip()

        erros = {}

        if not self.nome:
            erros["nome"] = "Informe o nome do ponto."

        if not self.endereco:
            erros["endereco"] = (
                "Informe o endereço ou referência."
            )

        if self.latitude is not None and self.longitude is None:
            erros["longitude"] = (
                "Informe também a longitude."
            )

        if self.longitude is not None and self.latitude is None:
            erros["latitude"] = (
                "Informe também a latitude."
            )

        if erros:
            raise ValidationError(erros)


class Viagem(models.Model):

    class Sentido(models.TextChoices):
        IDA = "ida", "Ida"
        RETORNO = "retorno", "Retorno"

    class Status(models.TextChoices):
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        FINALIZADA = "finalizada", "Finalizada"

    rota = models.ForeignKey(
        Rota,
        on_delete=models.PROTECT,
        related_name="viagens",
        verbose_name="Rota",
    )

    onibus = models.ForeignKey(
        Onibus,
        on_delete=models.PROTECT,
        related_name="viagens",
        verbose_name="Ônibus utilizado",
    )

    motorista = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="viagens",
        verbose_name="Motorista responsável",
    )

    sentido = models.CharField(
        max_length=10,
        choices=Sentido.choices,
        verbose_name="Sentido",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.EM_ANDAMENTO,
        verbose_name="Status",
    )

    iniciada_em = models.DateTimeField(
        default=timezone.now,
        editable=False,
        verbose_name="Iniciada em",
    )

    finalizada_em = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name="Finalizada em",
    )

    # Fotografia da capacidade no início da viagem. Viagens antigas ficam
    # sem este dado: não podemos reconstruir a capacidade histórica.
    capacidade_registrada = models.PositiveSmallIntegerField(
        null=True, blank=True, editable=False,
        validators=[MinValueValidator(1)],
    )
    nome_rota_registrado = models.CharField(max_length=100, blank=True, editable=False)

    codigo_onibus_registrado = models.CharField(max_length=20, blank=True, editable=False)
    placa_onibus_registrada = models.CharField(max_length=7, blank=True, editable=False)

    def save(self, *args, **kwargs):
        if self._state.adding:
            if self.capacidade_registrada is None:
                self.capacidade_registrada = self.onibus.capacidade
            if not self.nome_rota_registrado:
                self.nome_rota_registrado = self.rota.nome
            if not self.codigo_onibus_registrado:
                self.codigo_onibus_registrado = self.onibus.codigo or ''
            if not self.placa_onibus_registrada:
                self.placa_onibus_registrada = self.onibus.placa
        super().save(*args, **kwargs)

    @property
    def capacidade_embarque(self):
        # Compatibilidade com viagens já abertas antes da atualização.
        return self.capacidade_registrada or self.onibus.capacidade

    @property
    def nome_rota_historico(self):
        return self.nome_rota_registrado or self.rota.nome

    class Meta:
        verbose_name = "Viagem"
        verbose_name_plural = "Viagens"
        ordering = ["-iniciada_em", "-pk"]

        constraints = [
            models.UniqueConstraint(
                fields=["onibus"],
                condition=models.Q(status="em_andamento"),
                name="viagem_onibus_em_andamento_unico",
            ),
            models.UniqueConstraint(
                fields=["motorista"],
                condition=models.Q(status="em_andamento"),
                name="viagem_motorista_em_andamento_unico",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="em_andamento",
                        finalizada_em__isnull=True,
                    )
                    | models.Q(
                        status="finalizada",
                        finalizada_em__isnull=False,
                    )
                ),
                name="viagem_status_fim_coerentes",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(finalizada_em__isnull=True)
                    | models.Q(
                        finalizada_em__gte=models.F("iniciada_em")
                    )
                ),
                name="viagem_fim_apos_inicio",
            ),
            models.CheckConstraint(
                condition=models.Q(sentido__in=["ida", "retorno"]),
                name="viagem_sentido_valido",
            ),
        ]

    def __str__(self):
        return (
            f"Viagem {self.pk or 'nova'} — "
            f"{self.rota.nome} — "
            f"{self.get_sentido_display()}"
        )

    @property
    def em_andamento(self):
        return self.status == self.Status.EM_ANDAMENTO        


class LocalizacaoViagem(models.Model):
    viagem = models.ForeignKey(
        Viagem,
        on_delete=models.CASCADE,
        related_name="localizacoes",
    )

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90),
        ],
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180),
        ],
    )

    precisao_metros = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    capturada_em = models.DateTimeField()

    recebida_em = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Localização da viagem"
        verbose_name_plural = "Localizações das viagens"
        ordering = ["capturada_em", "pk"]

        indexes = [
            models.Index(
                fields=["viagem", "capturada_em"],
                name="loc_viagem_captura_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["viagem", "capturada_em"],
                name="loc_viagem_captura_unica",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    latitude__gte=-90,
                    latitude__lte=90,
                ),
                name="loc_latitude_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    longitude__gte=-180,
                    longitude__lte=180,
                ),
                name="loc_longitude_valida",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(precisao_metros__isnull=True)
                    | models.Q(precisao_metros__gte=0)
                ),
                name="loc_precisao_valida",
            ),
        ]

    def __str__(self):
        return (
            f"Viagem {self.viagem_id} — "
            f"{self.latitude}, {self.longitude}"
        )