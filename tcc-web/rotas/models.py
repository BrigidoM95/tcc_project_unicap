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

    fiscal = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.PROTECT, related_name='rotas_fiscal', limit_choices_to={'tipo': 'fiscal'})
    instituicoes = models.ManyToManyField('usuarios.Instituicao', blank=True, related_name='rotas')
    dias_operacao = models.JSONField(default=list, blank=True, help_text='Dias da semana: 0=segunda, 6=domingo; vazio = todos.')

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
        return f"{self.nome} — {self.destino}"

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
        self.destino = (self.destino or "").strip()

        erros = {}

        if not self.nome:
            erros["nome"] = "Informe o nome da rota."

        if not self.destino:
            erros["destino"] = "Informe o destino."

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

        if self.horario_ida and self.horario_retorno and self.horario_retorno <= self.horario_ida:
            erros['horario_retorno'] = 'O retorno deve ser posterior à ida.'
        if self.fiscal_id and (self.fiscal.tipo != 'fiscal' or not self.fiscal.user.is_active):
            erros['fiscal'] = 'Selecione um fiscal ativo.'
        if not isinstance(self.dias_operacao, list) or any(type(d) is not int or d not in range(7) for d in self.dias_operacao):
            erros['dias_operacao'] = 'Informe uma lista de dias entre 0 e 6.'
        if self.ativa and self.onibus_id and self.horario_ida and self.horario_retorno:
            from django.db.models import Q
            conflitos = Rota.objects.filter(Q(onibus_id=self.onibus_id) | Q(onibus__motorista_id=self.onibus.motorista_id), status='ativa', horario_ida__lt=self.horario_retorno, horario_retorno__gt=self.horario_ida).exclude(pk=self.pk)
            for outra in conflitos:
                if set(self.dias_operacao or range(7)) & set(outra.dias_operacao or range(7)):
                    erros['onibus'] = f'Conflito de agenda com a rota {outra.nome}.'
        if self.pk and not self.ativa and self.viagens.filter(status='em_andamento').exists():
            erros['status'] = 'Finalize a viagem antes de desativar a rota.'
        if self.pk:
            anterior = type(self).objects.get(pk=self.pk)
            if (anterior.onibus_id != self.onibus_id or anterior.fiscal_id != self.fiscal_id) and self.viagens.filter(status='em_andamento').exists():
                erros['onibus'] = 'Há uma viagem em andamento. Use a intervenção administrativa da viagem para alterar os responsáveis.'
            elif anterior.onibus_id != self.onibus_id:
                from embarques.models import ReservaAssento
                if ReservaAssento.objects.filter(viagem__rota=self, viagem__etapa='agendada',
                        ativa=True, expira_em__gt=timezone.now()).exists():
                    erros['onibus'] = 'Esta rota tem reservas em uma viagem agendada. Cancele as reservas antes de trocar o ônibus.'
        if erros:
            raise ValidationError(erros)


class PontoEmbarque(models.Model):
    ativo = models.BooleanField(default=True)
    ponto = models.ForeignKey('Ponto', null=True, blank=True, on_delete=models.PROTECT, related_name='vinculos')

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

        if erros:
            raise ValidationError(erros)


class Viagem(models.Model):

    class Sentido(models.TextChoices):
        IDA = "ida", "Ida"
        RETORNO = "retorno", "Retorno"

    class Status(models.TextChoices):
        AGENDADA = "agendada", "Agendada"
        CANCELADA = "cancelada", "Cancelada"
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

    class Etapa(models.TextChoices):
        AGENDADA = 'agendada', 'Agendada'
        EMBARQUE = 'embarque_ida', 'Embarque da ida'
        IDA = 'transito_ida', 'Em trânsito (ida)'
        DESTINO = 'no_destino', 'No destino'
        VOLTA = 'transito_volta', 'Em trânsito (volta)'
        ENCERRADA = 'encerrada', 'Encerrada'
        CANCELADA = 'cancelada', 'Cancelada'
    etapa = models.CharField(max_length=20, choices=Etapa.choices, default=Etapa.AGENDADA)
    data_servico = models.DateField(default=timezone.localdate, db_index=True)
    ciclo_completo = models.BooleanField(default=True)
    fiscal = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.PROTECT, related_name='viagens_fiscal')
    partida_ida_em = models.DateTimeField(null=True, blank=True)
    chegada_em = models.DateTimeField(null=True, blank=True)
    partida_volta_em = models.DateTimeField(null=True, blank=True)
    encerrada_pelo_sistema = models.BooleanField(default=False)
    motivo_cancelamento = models.CharField(max_length=300, blank=True)

    @property
    def sentido_atual(self):
        return 'retorno' if self.etapa in ('no_destino', 'transito_volta', 'encerrada') else 'ida'

    def embarque_aberto(self, sentido):
        return self.status == 'em_andamento' and ((sentido == 'ida' and self.etapa == 'embarque_ida') or (sentido == 'retorno' and self.etapa == 'no_destino'))

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
            models.UniqueConstraint(fields=['rota', 'data_servico'], condition=models.Q(ciclo_completo=True), name='viagem_rota_dia_unica'),
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
                        status__in=["agendada", "em_andamento"],
                        finalizada_em__isnull=True,
                    )
                    | models.Q(
                        status__in=["finalizada", "cancelada"],
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

    velocidade = models.FloatField(null=True, blank=True)
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

class Ponto(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    endereco = models.CharField('Endereço ou referência', max_length=200)
    ativo = models.BooleanField(default=True)
    class Meta:
        ordering = ['nome']
    def __str__(self):
        return self.nome
